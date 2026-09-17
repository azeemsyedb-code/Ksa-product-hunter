# KSA Product Hunter — Daily Trending Products (Amazon.sa + Noon.sa)

Automatically tracks trending products on Amazon.sa and Noon.sa every 24 hours,
and shows them on a simple dashboard. Runs for free using GitHub Actions
(scheduling) + GitHub Pages (hosting) — no server for you to manage.

## ⚠️ Read this first

1. **"Most searched" data doesn't exist publicly.** Amazon and Noon never
   expose their internal search-volume numbers outside paid seller/ads
   dashboards. This tool tracks the best public proxy: **Best Seller rank,
   rating, and review count**, and computes a **trend score** from how much
   those move day-to-day (new entries, rank jumps, review growth).
2. **Scraping technically violates both sites' Terms of Service.** This is
   common for personal/research tools, but understand the risk — your
   requests could get rate-limited or blocked. The scripts use polite
   delays and browser-like headers to reduce this.
3. **Selectors will need tweaking.** Amazon and Noon change their page
   structure often. I could not test-run this against the live sites from
   my side (network access is restricted here), so treat the first run as
   a "debug pass" — check `data/snapshots/` after the first Action run, and
   if a source comes back with 0 products, open that site in a browser,
   inspect the HTML/API response, and update the selectors in
   `scraper/amazon_scraper.py` or `scraper/noon_scraper.py` accordingly.

## Setup (10 minutes, one-time)

1. **Create a GitHub repo** (free account works) and push this folder to it:
   ```bash
   cd ksa-product-hunter
   git init
   git add .
   git commit -m "Initial setup"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/ksa-product-hunter.git
   git push -u origin main
   ```

2. **Enable GitHub Pages**: repo → Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder: `/dashboard` isn't selectable directly,
   so instead set folder to `/ (root)` and your dashboard will be at
   `https://YOUR-USERNAME.github.io/ksa-product-hunter/dashboard/`

3. **Enable Actions**: repo → Actions tab → you'll see "Daily Product Hunt
   (KSA)" — click "Enable workflow". It's already scheduled for 06:00 UTC
   daily (~9 AM Saudi time). To change the time, edit the `cron` line in
   `.github/workflows/daily-scrape.yml`.

4. **Trigger the first run manually** (don't wait 24 hours): Actions tab →
   "Daily Product Hunt (KSA)" → "Run workflow" button.

5. Once it finishes, check `data/latest.json` got created/updated in your
   repo, then open your dashboard URL from step 2.

## Optional: Telegram alerts for hot products

Get a free Telegram message whenever a product's trend score crosses 60
(new entries or big rank jumps). More reliable than shared WhatsApp bots.

1. In Telegram, message **@BotFather** → send `/newbot` → follow the
   prompts (pick any name/username) → it replies with a **bot token**
   (looks like `123456789:ABCdefGhIJKlmNoPQRstuVwxyz`).
2. Start a chat with your new bot (search its username, tap Start / send
   any message) so it's allowed to message you back.
3. Get your **chat ID**: message **@userinfobot** on Telegram, it replies
   with your numeric ID.
4. In your GitHub repo: Settings → Secrets and variables → Actions →
   "New repository secret". Add two secrets:
   - `TELEGRAM_BOT_TOKEN` — the token from step 1
   - `TELEGRAM_CHAT_ID` — the ID from step 3
5. Next scheduled or manual run will message you on Telegram if any
   product is trending. No setup = feature silently does nothing (safe to skip).

## New features

- **Product lookup by URL**: Actions tab → "Product Lookup (by URL)" →
  "Run workflow" → paste any Amazon.sa or Noon.sa product URL → full details
  (price, rating, specs, images) get saved to `data/lookups/<timestamp>.json`.
- **Cross-platform price compare**: each run tries to match similar products
  between Amazon and Noon (by title similarity) and shows which is cheaper —
  see the "Amazon vs Noon" section on the dashboard. This is a rough
  heuristic (no shared product IDs exist across sites), so double-check
  matches before acting on them.
- **Category hot list**: dashboard now shows the top 3 trending products per
  category at a glance.
- **Price history chart**: click any product row on the dashboard to see its
  price over the last 14 days (once enough daily runs have accumulated).
- **Search + Watchlist**: search box to filter products, and a star icon to
  save specific products to a personal watchlist (stored in your browser).
- **Retry + rotating headers**: both scrapers now retry failed requests
  with backoff and rotate between a few realistic browser User-Agents, to
  reduce the chance of being blocked.
- **Failure alerts**: if a source returns 0 products (structure likely
  changed), you get a Telegram warning instead of silently missing data.
- **Weekly Excel export**: every Friday, a `.xlsx` of the week's data is
  built and sent to you on Telegram (if configured) and saved to
  `data/exports/`.

## Project structure

```
ksa-product-hunter/
├── scraper/
│   ├── amazon_scraper.py   # Amazon.sa best-sellers
│   ├── noon_scraper.py     # Noon.sa trending/popular
│   ├── scrape_utils.py     # shared retry + rotating-header helpers
│   ├── lookup_product.py   # look up one product by URL
│   ├── weekly_export.py    # builds the weekly Excel file
│   └── main.py             # runs both scrapers, trend scores, matching, alerts
├── data/
│   ├── latest.json         # what the dashboard reads
│   ├── snapshots/          # one file per day, kept for history + index.json
│   ├── lookups/            # results from the URL lookup workflow
│   └── exports/            # weekly Excel files
├── dashboard/
│   └── index.html          # the web dashboard
├── .github/workflows/
│   ├── daily-scrape.yml       # runs main.py on a schedule
│   ├── lookup-product.yml     # on-demand product lookup by URL
│   └── weekly-export.yml      # weekly Excel export
└── requirements.txt
```

## Running locally (to test/debug selectors)

```bash
pip install -r requirements.txt
cd scraper
python main.py
```

Check the printed output — if it says "Scraped 0 products" for a source,
that source's selectors need updating.
