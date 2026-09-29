# RunePulse · OSRS Grand Exchange intel (RuneVest.Com)

A single static page for Old School RuneScape Grand Exchange prices, served on GitHub Pages:
**https://molvalkor.github.io/RuneVest.Com/**. The old `/osrs_invest_app.html` URL redirects there.

## What it shows
- **Market**: after-tax margins (buy at the latest instant-sell price, sell at the latest instant-buy price, minus GE tax) for items that pass an adjustable **liquidity filter**. Defaults: min daily volume 500 units (last full UTC day), max spread 10%, max price age 30 min, min buy price 100 gp.
- **Trending → Movers**: biggest 24h / 7d changes in average traded price and volume, computed from full UTC days (`/24h?timestamp=`), with a 7-day hourly sparkline (`/timeseries`) for each item. Only liquid items count.
- **Trending → Arbitrage**: live after-tax profit for conversion routes parsed from the OSRS Wiki: GE item sets (both directions), potion decanting at Bob Barter (4×(3) ↔ 3×(4)) and Herblore recipes (grimy → clean herb, herb + vial → unfinished potion, unfinished potion + secondary → potion). Shows buy cost, sell value, tax, profit, ROI and how many routes the GE buy limits allow per 4 hours.
- **Crafting Profits**: buy the inputs, process them (enchant jewellery/bolts, fletch, cook, smelt, smith, craft, Superheat, High Alchemy, other spells, Herblore) and sell the output. For each wiki recipe: inputs with quantities, output quantity, input cost, sell value, GE tax, profit per action, ROI, skill level and XP, members flag, buy-limit-capped actions and profit per 4h, and price age. It has an elemental staff toggle (the staff's runes cost 0), Offers/Instant pricing, search, skill chips, a members/F2P filter and sorting. The same liquidity filter applies per leg; spread is only checked on legs priced at or above the min price, since a 1 gp tick on a 5 gp rune is already a 20% spread. Not financial advice.
- **Trending → Update Watch**: recent official OSRS news posts, the tradeable items each post names, and what those items' prices did since. *What the news mentions and what the price did since. Not a prediction, not financial advice.*

## GE tax
2% of the sale price per item, rounded down (so items under 50 gp pay nothing), capped at 5,000,000 gp per item. Items in the wiki's exempt category pay none. Source: [OSRS Wiki, Grand Exchange: convenience fee](https://oldschool.runescape.wiki/w/Grand_Exchange#Convenience_fee_and_item_sink) and [Items exempt from Grand Exchange tax](https://oldschool.runescape.wiki/w/Category:Items_exempt_from_Grand_Exchange_tax).

## Data
- Prices, volumes and buy limits: [OSRS Wiki real-time prices API](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices) (`/latest`, `/5m`, `/24h`, `/timeseries`, `/mapping`), fetched by your browser. Responses are reused for as long as their cache headers allow. Browsers can't set a User-Agent; the scripts below send a descriptive one, as the wiki asks.
- `data/routes.js`: tax exemptions, item sets, decantable potions and Herblore recipes, built by `python3 tools/build_routes.py` from wiki pages.
- `data/recipes.js`: processing recipes for the Crafting Profits section, built by `python3 tools/build_recipes.py` from the wiki's structured recipe data (Bucket:Recipe, the data behind `{{Recipe}}` infoboxes), with enchanting runes cross-checked against the Lvl-1 to Lvl-7 Enchant and Enchant Crossbow Bolt pages, Superheat/High Alchemy rune costs from their spell pages, and elemental staves from the Staves page. Recipes with a success chance, Blast Furnace recipes and untradeable legs are skipped (counts are shown on the page). Cooking assumes no burns.
- `data/news.js`: a **dated snapshot** of the official news RSS feed, built by `python3 tools/fetch_news.py`. The feed doesn't send CORS headers, so browsers can't read it directly. Re-run the script and commit to update it. The page shows the fetch date.

The scripts use only the Python standard library. The page has no build step, no trackers, no cookies and no third-party scripts. Filters and the watchlist are stored in your browser's localStorage.

## Run locally
```
python3 -m http.server 8000   # then open http://localhost:8000/
```

Not affiliated with Jagex or the OSRS Wiki. Always check prices in-game before trading.
