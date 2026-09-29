#!/usr/bin/env python3
"""Snapshot the official OSRS news feed into data/news.js for the Update Watch tab.

Why a snapshot: secure.runescape.com sends no Access-Control-Allow-Origin header, so a
browser on github.io cannot read the RSS feed directly. This script fetches it with a
descriptive User-Agent, reads each post, finds item names from the prices API /mapping
that the post mentions, and stores each item's average price on the UTC day BEFORE the
post (from the wiki /24h endpoint) as the baseline. The page compares that baseline to
live prices. The file is stamped with the fetch time so the UI can label it.

Run:  python3 tools/fetch_news.py            (writes data/news.js)
"""
import datetime
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from wiki import PRICES, USER_AGENT, get, mapping  # noqa: E402

RSS = "https://secure.runescape.com/m=news/latest_news.rss?oldschool=true"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "news.js")

# Single-word item names that are also everyday words in news posts. They are skipped
# unless part of a longer item name, to avoid false "mentions".
COMMON = {
    "coins", "bread", "cake", "hammer", "rope", "pot", "jug", "bowl", "bucket", "vial", "logs", "bones", "ashes",
    "feather", "needle", "thread", "chisel", "knife", "saw", "spade", "rake", "shears", "cabbage", "potato",
    "onion", "egg", "milk", "flour", "water", "tinderbox", "bronze", "iron", "steel", "gold", "silver", "clay",
    "coal", "ball", "book", "key", "map", "note", "boots", "gloves", "cape", "hat", "shield", "sword", "bow",
    "staff", "wand", "ring", "amulet", "necklace", "bracelet", "arrow", "bolt", "dart", "knife", "axe", "pickaxe",
    "banana", "orange", "lemon", "lime", "pineapple", "strawberry", "tomato", "grapes", "cheese", "chocolate",
    "beer", "wine", "tea", "stew", "pie", "pizza", "bass", "pike", "tuna", "lobster", "shark", "salmon", "trout",
    "shrimps", "herring", "sardine", "anchovies", "cod", "mackerel", "squid", "crab", "whip", "mask", "robe",
    "scroll", "seed", "seaweed", "sand", "candle", "lantern", "torch", "cannon", "hull", "plank", "nails",
    "compost", "supercompost", "essence", "pet", "sack", "barrel", "crate", "chest", "table", "chair",
    "empty", "cooked", "raw", "ruby", "emerald", "sapphire", "diamond", "opal", "jade", "topaz", "pumpkin",
    "goblin", "frog", "otter", "pheasant", "lotus", "ghost", "bruno",
}


def post_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    s = raw.decode(charset, errors="replace")
    i = s.find("newspost-content")
    j = s.find("</main>", i)
    s = s[i:j if j > 0 else None]
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", s))
    t = re.sub(r"\s+", " ", t)
    # drop the long sign-off list of Jagex Mod names ("Mods Abe, Abyss, ... The Old School Team")
    k = t.rfind(" Mods ")
    if k > 0 and "Old School Team" in t[k:]:
        t = t[:k]
    return t.strip()


def match_items(text, items):
    """Literal item-name matching, tuned for precision over recall:
    * the first letter must be a capital (news posts write item names in Title Case;
      lowercase "easter egg" is usually a figure of speech);
    * single-word names must not be the tail of a longer capitalised name
      ("Log Basket" is not a "Basket") and must not start a sentence;
    * longest names are matched first and their text is masked, so "Dragon scimitar"
      does not also count as "Scimitar".
    """
    found, masked = {}, text
    for it in sorted(items, key=lambda it: -len(it["name"])):
        name = it["name"]
        single = len(name.split()) == 1
        if len(name) < 4 or "(" in name or (single and name.lower() in COMMON):
            continue
        pat = re.compile(r"(?<![\w'])" + re.escape(name[0].upper()) + "(?i:" + re.escape(name[1:]) + r")(?:s|es)?\b")
        hits = []
        for m in pat.finditer(masked):
            before = masked[:m.start()].rstrip()
            if single:
                if not before or before[-1] in ".!?:|\u2022":
                    continue  # sentence start: capital letter proves nothing
                prev = before.split()[-1] if before.split() else ""
                if prev[:1].isupper():
                    continue  # part of a longer proper name
            hits.append(m)
        if hits:
            found[it["id"]] = {"id": it["id"], "name": name, "mentions": len(hits)}
            for m in reversed(hits):
                masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    return list(found.values())


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    req = urllib.request.Request(RSS, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        root = ET.fromstring(r.read())
    items = mapping()
    day_cache = {}

    def day_avg(ts):
        if ts not in day_cache:
            day_cache[ts] = get(PRICES + "/24h", {"timestamp": ts}).get("data", {})
        return day_cache[ts]

    posts = []
    for it in root.iter("item"):
        title = html.unescape(it.findtext("title", "").strip())
        link = it.findtext("link", "").strip()
        pub = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        post_day = int(datetime.datetime(pub.year, pub.month, pub.day, tzinfo=datetime.timezone.utc).timestamp())
        base_ts = post_day - 86400  # UTC day before the post
        text, read_error = "", None
        for attempt in range(2):
            try:
                text = post_text(link)
                read_error = None
                break
            except Exception as e:  # keep the post, flagged, without matches
                read_error = str(e)
                time.sleep(3)
        if read_error:
            print("  could not read", link, read_error)
        mentioned = match_items(text, items)
        base = day_avg(base_ts)
        for m in mentioned:
            b = base.get(str(m["id"]))
            if b:
                hv, lv = b.get("highPriceVolume") or 0, b.get("lowPriceVolume") or 0
                ah, al = b.get("avgHighPrice"), b.get("avgLowPrice")
                if ah and al and hv + lv:
                    avg = (ah * hv + al * lv) / (hv + lv)
                else:
                    avg = ah or al
                m["baseline"] = {"day": base_ts, "avg": round(avg) if avg else None, "volume": hv + lv}
            else:
                m["baseline"] = None
        mentioned.sort(key=lambda m: -m["mentions"])
        posts.append({
            "title": title, "url": link, "date": pub.strftime("%Y-%m-%d"),
            "category": it.findtext("category", ""), "description": html.unescape(it.findtext("description", "").strip()),
            "chars": len(text), "readError": read_error, "items": mentioned,
        })
        print(f"{pub:%Y-%m-%d} {title[:60]:60} items={len(mentioned)}")
    posts.sort(key=lambda p: p["date"], reverse=True)
    data = {"fetchedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": RSS, "posts": posts}
    with open(OUT, "w") as f:
        f.write("// Generated by tools/fetch_news.py at " + data["fetchedAt"] + ". Snapshot, not live.\n")
        f.write("window.RV_NEWS = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    main()
