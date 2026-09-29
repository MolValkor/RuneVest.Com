#!/usr/bin/env python3
"""Build data/routes.js: GE tax exemptions + conversion routes verified from the OSRS Wiki.

Every route here is parsed from a wiki page, never typed in by hand:
  * Tax exemptions  <- Category:Items exempt from Grand Exchange tax
  * Item sets       <- https://oldschool.runescape.wiki/w/Item_set (set -> component tables)
  * Decanting       <- Category:Potions  x  /mapping dose families; decanting is free at
                       Bob Barter (GE) per https://oldschool.runescape.wiki/w/Decanting
  * Herblore        <- {{Recipe}} templates on pages in Category:Potions,
                       Category:Unfinished potions and Category:Herbs
Only items that exist in the prices API /mapping (i.e. GE-tradeable) are kept.

Run:  python3 tools/build_routes.py   (writes data/routes.js)
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from wiki import category_members, mapping, page_wikitext  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "routes.js")


def templates(text, name):
    """Yield the inner text of each {{name ...}} template, handling nested braces."""
    i = 0
    pat = re.compile(r"\{\{\s*" + re.escape(name) + r"\s*\|", re.I)
    while True:
        m = pat.search(text, i)
        if not m:
            return
        depth, j = 0, m.start()
        while j < len(text):
            if text.startswith("{{", j):
                depth += 1
                j += 2
            elif text.startswith("}}", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        yield text[m.end():j - 2]
        i = j


def params(inner):
    """Split template params on top-level pipes -> dict (named) ."""
    parts, depth, buf = [], 0, ""
    k = 0
    while k < len(inner):
        if inner.startswith("{{", k) or inner.startswith("[[", k):
            depth += 1; buf += inner[k:k + 2]; k += 2; continue
        if inner.startswith("}}", k) or inner.startswith("]]", k):
            depth -= 1; buf += inner[k:k + 2]; k += 2; continue
        if inner[k] == "|" and depth == 0:
            parts.append(buf); buf = ""; k += 1; continue
        buf += inner[k]; k += 1
    parts.append(buf)
    out = {}
    for p in parts:
        if "=" in p:
            a, b = p.split("=", 1)
            out[a.strip().lower()] = re.sub(r"<!--.*?-->", "", b, flags=re.S).strip()
    return out


def clean_notes(t):
    t = re.sub(r"\{\{SCP\|([^}|]+)[^}]*\}\}", r"\1:", t)
    t = re.sub(r"\[\[(?:[^]|]*\|)?([^]]*)\]\]", r"\1", t)
    t = re.sub(r"<br\s*/?>", "; ", t)
    t = re.sub(r"\{\{[^}]*\}\}|<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip() or None


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    items = mapping()
    by_name = {}
    for it in items:
        by_name.setdefault(it["name"].lower(), it)
    log = []

    def find(name):
        return by_name.get(name.strip().lower())

    # ---------- GE tax exemptions ----------
    special = {  # page title -> exact /mapping names (from the wiki's own wording)
        "Games necklace": ["Games necklace(8)"],      # GE page: "Games necklace(8)"
        "Ring of dueling": ["Ring of dueling(8)"],    # GE page: "Ring of dueling(8)"
        "Energy potion": [f"Energy potion({d})" for d in (1, 2, 3, 4)],  # page: "Energy potions have been exempted"
    }
    exempt = []
    for title in category_members("Items exempt from Grand Exchange tax"):
        names = special.get(title) or [title, re.sub(r" \(tablet\)$", "", title)]
        hit = [find(n) for n in names if find(n)]
        if not hit:
            log.append(f"tax-exempt page not matched to /mapping: {title}")
        for it in {h["id"]: h for h in hit}.values():
            exempt.append({"id": it["id"], "name": it["name"], "page": title})

    # ---------- Item sets ----------
    sets_txt = page_wikitext(["Item set"])["Item set"]
    sets, seen_sets = [], set()
    for row in re.split(r"\n\|-", sets_txt):
        m = re.search(r"\{\{plinkt\|([^}|]+)\}\}", row)
        e = re.search(r"#vardefineecho:pieces\|\{\{#expr:([^\n]*)", row)
        if not m or not e:
            continue
        pieces = re.findall(r"\{\{GEP\|([^}|]+)(?:\|(\d+))?", e.group(1))
        s = find(m.group(1))
        if s and s["id"] in seen_sets:
            continue  # the page lists some sets in more than one table
        comp = [(find(p), int(q or 1), p) for p, q in pieces]
        miss = [p for it, _, p in comp if not it]
        if not s or miss:
            log.append(f"set skipped (not in /mapping): {m.group(1)} missing={miss or 'set'}")
            continue
        seen_sets.add(s["id"])
        sets.append({"set": s["id"], "pieces": [{"id": it["id"], "qty": q} for it, q, _ in comp]})

    # ---------- Decanting ----------
    potion_pages = set(category_members("Potions"))
    fam = {}
    for it in items:
        r = re.match(r"^(.*?)\s*\((\d)\)$", it["name"])
        if r:
            fam.setdefault(r.group(1), {})[int(r.group(2))] = it["id"]
    # Haemostatic dressing is in Category:Potions but is a bandage-type item; not verified as decantable.
    exclude = {"Haemostatic dressing"}
    decant = []
    for base, doses in sorted(fam.items()):
        if base in potion_pages and base not in exclude and 3 in doses and 4 in doses and max(doses) == 4:
            decant.append({"name": base, "d3": doses[3], "d4": doses[4]})

    # ---------- Herblore recipes ----------
    titles = set(potion_pages) | set(category_members("Unfinished potions")) | set(category_members("Herbs"))
    titles = [t for t in titles if not t.startswith("Category:")]
    texts = page_wikitext(sorted(titles))
    recipes, seen = [], set()
    for title, txt in texts.items():
        for inner in templates(txt, "Recipe"):
            p = params(inner)
            if p.get("skill1", "").lower() != "herblore":
                continue
            if any(k.endswith("quantitynote") or k.endswith("cost") or k.endswith("currency") for k in p):
                continue  # chance-based or specially priced recipes are skipped
            mats = [(p[f"mat{i}"], p.get(f"mat{i}quantity", "1")) for i in range(1, 10) if p.get(f"mat{i}")]
            outs = [(p[f"output{i}"], p.get(f"output{i}quantity", "1")) for i in range(1, 5) if p.get(f"output{i}")]
            if not mats or not outs:
                continue
            try:
                ins = [(find(n), float(q)) for n, q in mats]
                ous = [(find(n), float(q)) for n, q in outs]
            except ValueError:
                continue
            if any(it is None for it, _ in ins + ous):
                continue
            key = (tuple((a["id"], q) for a, q in ins), tuple((a["id"], q) for a, q in ous))
            if key in seen:
                continue
            seen.add(key)
            lvl = re.sub(r"[^0-9]", "", p.get("skill1lvl", "")) or None
            recipes.append({
                "page": title,
                "level": int(lvl) if lvl else None,
                "tools": p.get("tools") or None,
                "notes": clean_notes(p.get("notes", "")),
                "inputs": [{"id": a["id"], "qty": q} for a, q in ins],
                "outputs": [{"id": a["id"], "qty": q} for a, q in ous],
            })
    recipes.sort(key=lambda r: (r["level"] or 0, r["page"]))

    data = {
        "builtAt": today,
        "sources": {
            "tax": "https://oldschool.runescape.wiki/w/Grand_Exchange#Convenience_fee_and_item_sink",
            "taxExempt": "https://oldschool.runescape.wiki/w/Category:Items_exempt_from_Grand_Exchange_tax",
            "sets": "https://oldschool.runescape.wiki/w/Item_set",
            "decanting": "https://oldschool.runescape.wiki/w/Decanting",
            "recipes": "https://oldschool.runescape.wiki/w/Template:Recipe (on each potion/herb page)",
        },
        "taxExempt": sorted(exempt, key=lambda x: x["name"]),
        "sets": sets,
        "decant": decant,
        "recipes": recipes,
    }
    with open(OUT, "w") as f:
        f.write("// Generated by tools/build_routes.py on " + today + " from the OSRS Wiki. Do not edit by hand.\n")
        f.write("window.RV_ROUTES = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"tax-exempt ids={len(exempt)} sets={len(sets)} decant={len(decant)} recipes={len(recipes)}")
    for line in log:
        print("  note:", line)


if __name__ == "__main__":
    main()
