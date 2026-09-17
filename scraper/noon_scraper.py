"""
Noon.sa scraper.

Noon renders most content via JavaScript, so plain requests+BeautifulSoup
often returns incomplete HTML. This script tries Noon's internal catalog
API first (used by their own site, endpoint/params may change over time),
falling back to nothing if it fails. If this breaks, the fix is usually:
open noon.sa in a browser, open DevTools > Network > XHR, reload a
category/search page, and find the JSON endpoint it's actually calling.

Like Amazon, Noon does not publicly expose real "search volume" — we use
their trending/best-seller listing order and review counts as a proxy.
"""

import time
import random
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Noon's catalog search API (used by noon.sa itself). Query params /
# response shape may drift — verify with browser DevTools if this stops
# returning data.
CATALOG_API = "https://www.noon.com/_svc/catalog/api/v3/sa-en/catalog"

CATEGORIES = ["electronics", "home", "beauty", "grocery", "toys-kids-babies"]


def scrape_category(category: str):
    products = []
    try:
        params = {
            "categoryIdentifier": category,
            "sort[by]": "popularity",
            "sort[dir]": "desc",
            "page_size": 30,
        }
        resp = requests.get(CATALOG_API, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        hits = payload.get("hits") or payload.get("products") or []
        for idx, p in enumerate(hits, start=1):
            # Noon's API sometimes returns a relative "url" field, sometimes a
            # "url_key"/"sku" you build a link from. Try the likely fields;
            # verify against a real response and adjust once you see actual data.
            raw_url = p.get("url") or p.get("product_url")
            if not raw_url and p.get("url_key"):
                raw_url = f"/saudi-en/{p['url_key']}/p/"
            url = None
            if raw_url:
                url = raw_url if raw_url.startswith("http") else f"https://www.noon.com{raw_url}"

            # Image field name varies by Noon's API version — check a real
            # response in data/latest.json and adjust the key below if images
            # don't show up (common alternatives: 'image_key', 'thumbnail').
            image = p.get("image") or p.get("image_url")

            products.append({
                "category": category,
                "rank": idx,
                "title": p.get("name") or p.get("title"),
                "price": p.get("sale_price") or p.get("price"),
                "rating": p.get("rating") or p.get("average_rating"),
                "review_count": p.get("num_reviews") or p.get("review_count"),
                "url": url,
                "image": image,
                "source": "noon.sa",
            })
    except Exception as e:
        print(f"[noon] Failed to scrape {category}: {e}")

    return products


def scrape_all():
    all_products = []
    for cat in CATEGORIES:
        print(f"[noon] Scraping: {cat}")
        all_products.extend(scrape_category(cat))
        time.sleep(random.uniform(3, 6))
    return all_products


if __name__ == "__main__":
    data = scrape_all()
    print(f"Scraped {len(data)} products from Noon.sa")
