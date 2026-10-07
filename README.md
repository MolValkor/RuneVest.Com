# RuneVest hub · OSRS, RS3 and Dragonwilds (RuneVest.Com)

A static hub with one section per game, served on GitHub Pages:
**https://molvalkor.github.io/RuneVest.Com/**

| Page | Path | What it has |
|---|---|---|
| Hub | `/` | One card per game with its tools and next announced items, plus a cross-game Update Watch |
| Old School RuneScape | `/osrs/` | The full OSRS GE toolset (described below) plus the OSRS roadmap |
| RuneScape 3 | `/rs3/` | GE guide prices, volumes and buy limits, a flip/tax calculator, guide-price movers, High Alchemy and the RS3 roadmap |
| RuneScape: Dragonwilds | `/dragonwilds/` | Roadmap, patch tracker, crafting reference with raw-material trees, resources and bosses (the game has no GE or market, so no prices) |

The old `/osrs_invest_app.html` URL redirects to `/osrs/`.

## Update Watch (all games)
`data/roadmaps.js` holds what Jagex has announced for each game, rendered by `assets/roadmap.js`. Every item links to its sources and carries a basis tag:
**official** (timing stated in an official Jagex post or press release), **released**, **in poll**, **roadmap graphic** (read off Jagex's roadmap image, as transcribed by the game's official wiki) or **under review**.
An exact day is shown only when Jagex gave one; otherwise only the month or season, or "unannounced". Edit the file by hand and update `checkedAt` when you re-check.

## RuneScape 3
- Data: the RuneScape Wiki's GE modules (`Module:GEPrices`, `GEVolumes`, `GELimits` as `data.json?action=raw`), which copy Jagex's official GE database and are fetched live by your browser. Item ids, members flags and high-alch values are in `data/rs3_items.js`, built by `python3 tools/build_rs3_items.py`. The 90-day history behind Movers and the item chart comes from the Weird Gloop exchange API (`api.weirdgloop.org/exchange/history/rs/last90d`), loaded on demand.
- RS3 has **one guide price per item** and no public feed of instant-buy / instant-sell prices, so there are no live flip margins. The calculator does the tax math on prices you check in-game.
- GE tax: 2% per item, rounded down, paid by the seller (since 9 Jan 2023). Items under 50 gp and bonds are exempt. No cap is documented for RS3, so none is applied. Source: [RuneScape Wiki, Grand Exchange](https://runescape.wiki/w/Grand_Exchange).
- `data/rs3_news.js`: a dated snapshot of official RS3 news posts and the tradeable items they mention, built by `python3 tools/fetch_rs3_news.py`.

## Dragonwilds
- `data/dragonwilds.js`: a dated snapshot built by `python3 tools/build_dragonwilds.py` from the [Dragonwilds Wiki](https://dragonwilds.runescape.wiki/)'s structured data (Bucket: recipes, items, drops, NPCs) and Jagex's official Steam announcements for app 1374490 (patch tracker). Re-run the script and commit to update it.
- The wiki's recipe data has materials, facility, output and XP but no level requirements, so the page doesn't show levels. The raw-material tree uses the first listed recipe for each intermediate item.

## Old School RuneScape
### What it shows
- **Market**: after-tax margins (buy at the latest instant-sell price, sell at the latest instant-buy price, minus GE tax) for items that pass an adjustable **liquidity filter**. Defaults: min daily volume 500 units (last full UTC day), max spread 10%, max price age 30 min, min buy price 100 gp.
- **Trending → Movers**: biggest 24h / 7d changes in average traded price and volume, computed from full UTC days (`/24h?timestamp=`), with a 7-day hourly sparkline (`/timeseries`) for each item. Only liquid items count.
- **Trending → Arbitrage**: live after-tax profit for conversion routes parsed from the OSRS Wiki: GE item sets (both directions), potion decanting at Bob Barter (4×(3) ↔ 3×(4)) and Herblore recipes (grimy → clean herb, herb + vial → unfinished potion, unfinished potion + secondary → potion). Shows buy cost, sell value, tax, profit, ROI and how many routes the GE buy limits allow per 4 hours.
- **Crafting Profits**: buy the inputs, process them (enchant jewellery/bolts, fletch, cook, smelt, smith, craft, Superheat, High Alchemy, other spells, Herblore) and sell the output. For each wiki recipe: inputs with quantities, output quantity, input cost, sell value, GE tax, profit per action, ROI, skill level and XP, members flag, buy-limit-capped actions and profit per 4h, and price age. It has an elemental staff toggle (the staff's runes cost 0), Offers/Instant pricing, search, skill chips, a members/F2P filter and sorting. The same liquidity filter applies per leg; spread is only checked on legs priced at or above the min price, since a 1 gp tick on a 5 gp rune is already a 20% spread. Not financial advice.
- **Trending → Update Watch**: recent official OSRS news posts, the tradeable items each post names, and what those items' prices did since. *What the news mentions and what the price did since. Not a prediction, not financial advice.*

### GE tax
2% of the sale price per item, rounded down (so items under 50 gp pay nothing), capped at 5,000,000 gp per item. Items in the wiki's exempt category pay none. Source: [OSRS Wiki, Grand Exchange: convenience fee](https://oldschool.runescape.wiki/w/Grand_Exchange#Convenience_fee_and_item_sink) and [Items exempt from Grand Exchange tax](https://oldschool.runescape.wiki/w/Category:Items_exempt_from_Grand_Exchange_tax).

### Data
- Prices, volumes and buy limits: [OSRS Wiki real-time prices API](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices) (`/latest`, `/5m`, `/24h`, `/timeseries`, `/mapping`), fetched by your browser. Responses are reused for as long as their cache headers allow. Browsers can't set a User-Agent; the scripts below send a descriptive one, as the wiki asks.
- `data/routes.js`: tax exemptions, item sets, decantable potions and Herblore recipes, built by `python3 tools/build_routes.py` from wiki pages.
- `data/recipes.js`: processing recipes for the Crafting Profits section, built by `python3 tools/build_recipes.py` from the wiki's structured recipe data (Bucket:Recipe, the data behind `{{Recipe}}` infoboxes), with enchanting runes cross-checked against the Lvl-1 to Lvl-7 Enchant and Enchant Crossbow Bolt pages, Superheat/High Alchemy rune costs from their spell pages, and elemental staves from the Staves page. Recipes with a success chance, Blast Furnace recipes and untradeable legs are skipped (counts are shown on the page). Cooking assumes no burns.
- `data/news.js`: a **dated snapshot** of the official news RSS feed, built by `python3 tools/fetch_news.py`. The feed doesn't send CORS headers, so browsers can't read it directly. Re-run the script and commit to update it. The page shows the fetch date.


## Run locally
```
python3 -m http.server 8000   # then open http://localhost:8000/
```

The look is a parchment-and-gold theme in `assets/base.css`: textures are CSS gradients and inline SVG noise, with no game art or Jagex assets. Headings use [Cinzel](https://github.com/NDISCOVER/Cinzel), self-hosted in `assets/fonts/` under the SIL Open Font License (`OFL-Cinzel.txt`).

The scripts use only the Python standard library. No build step, trackers, cookies or third-party scripts. Filters and watchlists are stored in your browser's localStorage.

Not affiliated with Jagex or the RuneScape / OSRS / Dragonwilds wikis. Nothing here is financial advice. Always check prices in-game before trading.
