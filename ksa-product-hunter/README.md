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

## Project structure

```
ksa-product-hunter/
├── scraper/
│   ├── amazon_scraper.py   # Amazon.sa best-sellers
│   ├── noon_scraper.py     # Noon.sa trending/popular
│   └── main.py             # runs both, computes trend scores, saves data
├── data/
│   ├── latest.json         # what the dashboard reads
│   └── snapshots/          # one file per day, kept for history
├── dashboard/
│   └── index.html          # the web dashboard
├── .github/workflows/
│   └── daily-scrape.yml    # the automation — runs main.py every 24h
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
