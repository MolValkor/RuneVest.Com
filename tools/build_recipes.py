#!/usr/bin/env python3
"""Build data/recipes.js for the Crafting Profits section, from OSRS Wiki data only.

Sources (all read through the MediaWiki API with a descriptive User-Agent):
  * Bucket:Recipe  - structured data behind every {{Recipe}} infobox on the wiki
                     (materials + quantities, output + quantity, skills/levels/XP, members,
                     ticks, tools, facilities).  api.php?action=bucket
  * Spell pages    - rune costs from {{Infobox Spell}} |cost = {{RuneReq|...}} for
                     Lvl-1..7 Enchant, High Level Alchemy and Superheat Item, and the
                     per-gem table on Enchant Crossbow Bolt. Enchanting recipes from the
                     Bucket are cross-checked against these; mismatches are dropped.
  * Staves page    - which staves are elemental; each staff's own page says which runes it
                     "provides unlimited amounts of".
  * prices API /mapping - which items are GE-tradeable (untradeable inputs/outputs are skipped).

Skipped on purpose (counted in the output): recipes with a success chance (output
quantitynote), Blast Furnace recipes (coffer fee not modelled), recipes using an
untradeable item, and duplicates. Cooking recipes are kept but the page labels that
burning is not modelled.

Run:  python3 tools/build_recipes.py   (writes data/recipes.js)
"""
import collections
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from wiki import WIKI_API, category_members, get, mapping, page_wikitext  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.js")
SKILLS = {"Magic", "Fletching", "Cooking", "Smithing", "Crafting", "Herblore"}
ENCHANT_SPELLS = [f"Lvl-{n} Enchant" for n in range(1, 8)]
RUNE_ITEM = lambda r: r.strip().capitalize() + " rune"  # "Cosmic" -> "Cosmic rune"


def bucket_recipes():
    rows, off = [], 0
    while True:
        q = ("bucket('recipe').select('page_name','page_name_sub','source_template','production_json')"
             f".limit(500).offset({off}).run()")
        d = get(WIKI_API, {"action": "bucket", "format": "json", "query": q})
        if "error" in d:
            raise SystemExit("bucket error: " + str(d["error"]))
        rows += d["bucket"]
        if len(d["bucket"]) < 500:
            return rows
        off += 500


def rune_req(text):
    """{{RuneReq|Air=3|Cosmic=1}} -> {'Air rune': 3, 'Cosmic rune': 1}"""
    m = re.search(r"\{\{RuneReq\|([^}]*)\}\}", text)
    if not m:
        return None
    out = {}
    for part in m.group(1).split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[RUNE_ITEM(k)] = int(v.strip())
    return out


def infobox_field(text, field):
    m = re.search(r"^\|\s*" + field + r"\s*=\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    items = mapping()
    by_name = {it["name"].lower(): it for it in items}
    find = lambda n: by_name.get(n.strip().lower())

    # ---------- spells ----------
    pages = page_wikitext(ENCHANT_SPELLS + ["High Level Alchemy", "Superheat Item", "Enchant Crossbow Bolt", "Staves", "Crushed gem"])
    spells = {}
    for name in ENCHANT_SPELLS + ["High Level Alchemy", "Superheat Item"]:
        t = pages[name]
        spells[name] = {"level": int(infobox_field(t, "level")), "xp": float(infobox_field(t, "exp")),
                        "members": (infobox_field(t, "members") or "").lower() == "yes", "runes": rune_req(t)}
    bolt_spells = {}  # output bolt name -> rune dict
    for row in pages["Enchant Crossbow Bolt"].split("\n|-"):
        rr = rune_req(row)
        if not rr:
            continue
        cells = row.split("\n|")
        if len(cells) < 4:
            continue
        for bolt in re.findall(r"\[\[([^]|]+)\]\]", cells[3]):
            bolt_spells[bolt.lower()] = rr
    enchant_by_level = {v["level"]: (k, v["runes"]) for k, v in spells.items() if k in ENCHANT_SPELLS}

    # Semi-precious gems that can be crushed when cut (level-dependent chance, no fixed rate)
    cg = pages["Crushed gem"]
    intro = cg[cg.index("is produced when"):].split("\n")[0]
    crushable = {n.lower() for n in re.findall(r"\[\[(uncut [^]|]+)", intro, re.I)}

    # ---------- elemental staves ----------
    st = pages["Staves"]
    sec = st[st.index("==Elemental staves=="):st.index("==God staves==")]
    staff_names = []
    for block in re.findall(r"\{\{Infotable Bonuses\|([^}]*)\}\}", sec):
        staff_names += [x for x in block.split("|") if "=" not in x]
    staff_txt = page_wikitext(staff_names)
    staves = []
    for name in staff_names:
        t = staff_txt.get(name, "")
        m = re.search(r"provides unlimited amounts of (.*?)(?: as well as|\.)", t)
        runes = sorted({RUNE_ITEM(r) for r in re.findall(r"\b(air|water|earth|fire)\b", m.group(1).lower())}) if m else []
        if runes and all(find(r) for r in runes):
            staves.append({"name": name, "runes": [find(r)["id"] for r in runes], "tradeable": bool(find(name))})

    # ---------- items the wiki says cannot be alchemised (excluded from High Alchemy routes) ----------
    no_alch = sorted({find(n)["id"] for n in category_members("Items that cannot be alchemised") if find(n)})

    # ---------- recipes ----------
    rows = bucket_recipes()
    skipped = collections.Counter()
    recipes, seen = [], set()
    for r in rows:
        if r.get("source_template") != "recipe":
            continue
        p = json.loads(r["production_json"])
        skills = [s for s in p.get("skills", []) if s.get("name")]
        names = {s["name"].capitalize() for s in skills}
        if not names & SKILLS:
            continue
        out = p.get("output") or {}
        if out.get("quantitynote"):
            skipped["success chance (quantitynote)"] += 1
            continue
        fac = p.get("facilities") or ""
        if "blast furnace" in fac.lower():
            skipped["Blast Furnace (coffer fee not modelled)"] += 1
            continue
        try:
            mats = [(m["name"], float(m.get("quantity") or 1)) for m in p.get("materials", [])]
            oq = float(out.get("quantity") or 1)
        except ValueError:
            skipped["non-numeric quantity"] += 1
            continue
        if any(n.lower() in crushable for n, _ in mats):
            skipped["gem can be crushed (no fixed success rate)"] += 1
            continue
        oi = find(out.get("name", ""))
        ins, bad = [], False
        for n, q in mats:
            if n.lower() == "coins":
                ins.append({"coins": True, "qty": q})
                continue
            it = find(n)
            if not it:
                bad = True
                break
            ins.append({"id": it["id"], "qty": q})
        if not mats or bad or not oi:
            skipped["untradeable input or output"] += 1
            continue
        if any(x.get("id") == oi["id"] for x in ins):
            skipped["output is also an input"] += 1
            continue
        # category
        variant = (out.get("subtxt") or "").strip()
        verified = None
        runes = {n: q for n, q in mats if n.lower().endswith(" rune")}
        if "Magic" in names and "Smithing" in names and runes == spells["Superheat Item"]["runes"]:
            cat, verified = "Superheat", "Superheat Item"
        elif "Magic" in names and "Smithing" not in names:
            lvl = next(int(float(s["level"])) for s in skills if s["name"].capitalize() == "Magic")
            if out["name"].lower() in bolt_spells:
                if runes != bolt_spells[out["name"].lower()]:
                    skipped["bolt enchant runes differ from spell page"] += 1
                    continue
                cat, verified = "Enchanting", "Enchant Crossbow Bolt"
            elif lvl in enchant_by_level and runes == enchant_by_level[lvl][1]:
                cat, verified = "Enchanting", enchant_by_level[lvl][0]
            else:
                cat = "Magic (other spells)"
        elif "Smithing" in names and "furnace" in fac.lower():
            cat = "Smelting"
        else:
            cat = sorted((names & SKILLS) - {"Magic"} or (names & SKILLS))[0]
        key = (tuple(sorted((x.get("id", 0), x["qty"]) for x in ins)), oi["id"], oq)
        if key in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(key)
        num = lambda x: int(x) if float(x).is_integer() else float(x)
        rec = {
            "cat": cat, "page": r["page_name"],
            "skills": [[s["name"].capitalize(), num(s["level"]) if s.get("level") else None,
                        num(s["experience"]) if s.get("experience") not in (None, "") else None] for s in skills],
            "members": bool(p.get("members")),
            # inputs/outputs: [item id, quantity]; id 0 = coins
            "in": [[x.get("id", 0), num(x["qty"])] for x in ins], "out": [[oi["id"], num(oq)]],
        }
        for k, v in (("variant", variant), ("ticks", p.get("ticks")), ("tools", p.get("tools")),
                     ("facilities", fac), ("verified", verified)):
            if v:
                rec[k] = v
        recipes.append(rec)

    # A variant whose inputs are a strict subset of another variant of the same page/output
    # (e.g. a spell listed without its elemental runes, i.e. assuming a staff) is dropped:
    # the page's staff toggle models that explicitly instead.
    ELEMENTAL = {find(RUNE_ITEM(x))["id"] for x in ("air", "water", "earth", "fire")}

    def inset(r):
        return {tuple(x) for x in r["in"]}
    keep = []
    for r in recipes:
        if any(o is not r and o["page"] == r["page"] and o["out"] == r["out"] and inset(r) < inset(o)
               and {i for i, _ in inset(o) - inset(r)} <= ELEMENTAL for o in recipes):
            skipped["variant listed without some runes (staff modelled by toggle)"] += 1
            if os.environ.get("DEBUG"):
                print("drop", r["cat"], r["page"], r.get("variant"), r["in"])
            continue
        keep.append(r)
    recipes = keep
    recipes.sort(key=lambda x: (x["cat"], x["page"]))
    counts = collections.Counter(x["cat"] for x in recipes)
    data = {
        "builtAt": today,
        "sources": {
            "recipes": "https://oldschool.runescape.wiki/w/Bucket:Recipe (data behind {{Recipe}} infoboxes)",
            "spells": {k: "https://oldschool.runescape.wiki/w/" + k.replace(" ", "_") for k in list(spells) + ["Enchant Crossbow Bolt"]},
            "staves": "https://oldschool.runescape.wiki/w/Staves#Elemental_staves",
            "crushable": "https://oldschool.runescape.wiki/w/Crushed_gem",
            "noAlch": "https://oldschool.runescape.wiki/w/Category:Items_that_cannot_be_alchemised",
        },
        "spells": {k: {**v, "runes": [{"id": find(n)["id"], "qty": q} for n, q in v["runes"].items()]} for k, v in spells.items()},
        "staves": staves,
        "noAlch": no_alch,
        "counts": dict(counts),
        "skipped": dict(skipped),
        "recipes": recipes,
    }
    with open(OUT, "w") as f:
        f.write("// Generated by tools/build_recipes.py on " + today + " from the OSRS Wiki. Do not edit by hand.\n")
        f.write("window.RV_RECIPES = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print("recipes:", len(recipes), dict(sorted(counts.items())))
    print("skipped:", dict(skipped))
    print("crushable:", crushable)
    print("staves:", [(s["name"], s["runes"]) for s in staves])
    print("spells:", {k: (v["level"], v["runes"]) for k, v in spells.items()})


if __name__ == "__main__":
    main()
