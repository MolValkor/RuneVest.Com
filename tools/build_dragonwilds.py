#!/usr/bin/env python3
"""Build data/dragonwilds.js for the RuneScape: Dragonwilds page.

Dragonwilds is a survival/crafting game with no Grand Exchange or player market, so there
are no prices. What exists, and what this script saves:

* Recipes, items, drops and NPCs from the RuneScape: Dragonwilds Wiki's structured data
  (the Bucket extension: Bucket:Recipe, Bucket:Infobox_item, Bucket:Dropsline,
  Bucket:Infobox_npc), plus the Bosses and Resource nodes categories.
  https://dragonwilds.runescape.wiki/w/Bucket:Recipe
* Official patch notes and announcements, from Jagex's Steam announcements feed for the
  game (Steam app 1374490) via the public Steam Web API ISteamNews/GetNewsForApp.

Run:  python3 tools/build_dragonwilds.py            (writes data/dragonwilds.js)
"""
import datetime
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from wiki import get  # noqa: E402

W = "https://dragonwilds.runescape.wiki/api.php"
WIKI = "https://dragonwilds.runescape.wiki/w/"
STEAM_APP = 1374490
STEAM = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "dragonwilds.js")


def bucket(name, fields):
    out, off = [], 0
    while True:
        q = "bucket('%s').select(%s).limit(500).offset(%d).run()" % (name, ",".join("'%s'" % f for f in fields), off)
        d = get(W, {"action": "bucket", "format": "json", "query": q})
        if d.get("error"):
            raise RuntimeError(d["error"])
        rows = d.get("bucket", [])
        out += rows
        if len(rows) < 500:
            return out
        off += 500


def category(cat):
    out, cont = [], {}
    while True:
        d = get(W, {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmlimit": "500",
                    "cmnamespace": "0", "format": "json", **cont})
        out += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" not in d:
            return out
        cont = d["continue"]


def num(x):
    try:
        f = float(str(x).replace(",", ""))
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


def strip_bbcode(s):
    s = re.sub(r"\[/?[a-z0-9*]+(=[^\]]*)?\]", " ", s or "", flags=re.I)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\{STEAM_CLAN_IMAGE\}\S*", " ", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def main():
    now = datetime.datetime.now(datetime.timezone.utc)

    # ---- recipes ----
    recipes, seen = [], set()
    for r in bucket("recipe", ["page_name", "json"]):
        try:
            j = json.loads(r["json"])
        except (TypeError, ValueError):
            continue
        out = j.get("output") or {}
        mats = [[m.get("name") or m.get("item"), num(m.get("quantity") or m.get("qty")) or 1] for m in j.get("materials", []) if (m.get("name") or m.get("item"))]
        if not mats or not (out.get("name") or out.get("item")):
            continue
        skills = [[s.get("name"), num(s.get("experience")), num(s.get("level"))] for s in j.get("skills", []) if s.get("name")]
        rec = {
            "page": r["page_name"],
            "out": out.get("name") or out.get("item"),
            "qty": num(out.get("quantity") or out.get("qty")) or 1,
            "fac": j.get("facility") or "",
            "mats": mats,
            "skills": skills,
        }
        key = json.dumps(rec, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        recipes.append(rec)

    # ---- items ----
    items = {}
    for r in bucket("infobox_item", ["page_name", "item_type", "json"]):
        try:
            j = json.loads(r.get("json") or "{}")
        except ValueError:
            j = {}
        name = r["page_name"]
        if name in items:
            continue
        it = {"type": r.get("item_type") or j.get("item_type") or "", "desc": j.get("description") or ""}
        for k in ("weight", "stacklimit", "health", "sustenance", "hydration", "durability"):
            if j.get(k) not in (None, ""):
                it[k] = num(j[k]) if num(j[k]) is not None else j[k]
        items[name] = it

    # ---- drops (bosses + resource nodes) ----
    bosses = [b for b in category("Bosses") if b != "Boss"]
    nodes = [n for n in category("Resource nodes") if n != "Resource nodes"]
    wanted = set(bosses) | set(nodes)
    drops = {}
    for r in bucket("dropsline", ["page_name", "item_name", "json"]):
        if r["page_name"] not in wanted:
            continue
        try:
            j = json.loads(r.get("json") or "{}")
        except ValueError:
            j = {}
        drops.setdefault(r["page_name"], []).append([r.get("item_name") or j.get("Dropped item"), j.get("Drop Quantity") or "", j.get("Rarity") or ""])
    npcs = {r["page_name"]: r for r in bucket("infobox_npc", ["page_name", "npc_location", "npc_race"])}
    def plain(x):  # "[[Imaru's Tower]]" -> "Imaru's Tower"
        return re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", x or "").strip()
    boss_list = [{"name": b, "location": plain((npcs.get(b) or {}).get("npc_location")), "race": (npcs.get(b) or {}).get("npc_race") or "",
                  "drops": drops.get(b, [])} for b in sorted(bosses)]
    node_list = [{"name": n, "drops": drops.get(n, [])} for n in sorted(nodes)]

    # ---- official announcements / patch notes (Steam) ----
    d = get(STEAM, {"appid": STEAM_APP, "count": 120, "maxlength": 400, "feeds": "steam_community_announcements", "format": "json"})
    news = []
    for n in d["appnews"]["newsitems"]:
        title = html.unescape(n["title"]).strip()
        ver = re.search(r"\b(\d+\.\d+(?:\.\d+){0,2})\b", title)
        t = title.lower()
        if "survey" in t or "giveaway" in t:
            kind = "news"
        elif "hotfix" in t:
            kind = "hotfix"
        elif "event" in t:
            kind = "event"
        elif ver or "patch" in t:
            kind = "patch"
        else:
            kind = "news"
        news.append({
            "date": datetime.datetime.fromtimestamp(n["date"], datetime.timezone.utc).strftime("%Y-%m-%d"),
            "title": title, "version": ver.group(1) if ver else None, "kind": kind,
            "url": "https://store.steampowered.com/news/app/%d/view/%s" % (STEAM_APP, n["gid"]),
            "excerpt": strip_bbcode(n.get("contents"))[:300],
        })
    news.sort(key=lambda x: x["date"], reverse=True)

    data = {
        "builtAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wiki": WIKI,
        "sources": {
            "recipes": WIKI + "Bucket:Recipe", "items": WIKI + "Bucket:Infobox_item", "drops": WIKI + "Bucket:Dropsline",
            "bosses": WIKI + "Category:Bosses", "nodes": WIKI + "Category:Resource_nodes",
            "news": "https://store.steampowered.com/news/app/%d" % STEAM_APP,
        },
        "recipes": recipes, "items": items, "bosses": boss_list, "nodes": node_list, "news": news,
    }
    with open(OUT, "w") as f:
        f.write("// Generated by tools/build_dragonwilds.py at " + data["builtAt"] + ". Snapshot of wiki data + official Steam announcements.\n")
        f.write("window.RV_DW = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n")
    print(len(recipes), "recipes,", len(items), "items,", len(boss_list), "bosses,", len(node_list), "nodes,", len(news), "announcements")


if __name__ == "__main__":
    main()
