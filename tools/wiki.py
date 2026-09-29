"""Shared helpers for RuneVest build scripts (stdlib only).

The OSRS Wiki asks every API consumer to send a descriptive User-Agent with contact
info (https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices). Browsers cannot
set User-Agent, so only these scripts send it.
"""
import json
import time
import urllib.parse
import urllib.request

USER_AGENT = (
    "RuneVest/1.0 build script (github.com/MolValkor/RuneVest.Com; "
    "contact: 293700191+MolValkor@users.noreply.github.com)"
)
PRICES = "https://prices.runescape.wiki/api/v1/osrs"
WIKI_API = "https://oldschool.runescape.wiki/api.php"


def get(url, params=None, as_json=True, pause=0.25):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    time.sleep(pause)  # be polite; the wiki does not rate limit but asks for reasonable use
    return json.loads(body) if as_json else body


def mapping():
    return get(PRICES + "/mapping")


def category_members(cat):
    out, cont = [], {}
    while True:
        d = get(WIKI_API, {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
                           "cmlimit": "500", "format": "json", **cont})
        out += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" not in d:
            return out
        cont = d["continue"]


def page_wikitext(titles):
    """Return {title: wikitext} for many pages, 50 per request (bulk, as the wiki prefers)."""
    res = {}
    titles = list(titles)
    for i in range(0, len(titles), 50):
        d = get(WIKI_API, {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                           "format": "json", "formatversion": "2", "redirects": "1",
                           "titles": "|".join(titles[i:i + 50])})
        for p in d["query"].get("pages", []):
            if "revisions" in p:
                res[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
    return res
