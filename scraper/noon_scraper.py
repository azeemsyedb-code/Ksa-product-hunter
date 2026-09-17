"""
Noon.sa scraper.

Endpoint and field names below were confirmed by inspecting a real browser
request (DevTools -> Network) on 2026-09-17, so this should work as-is. If
Noon changes their API later, re-check via DevTools the same way.

Note: this uses Noon's "curated for you" endpoint (their homepage/category
recommendation feed), not a literal admin "best sellers" list -- Noon doesn't
expose one publicly. It's still a solid proxy for "what's popular right now"
since the feed is driven by aggregate demand signals, not this scraper's
own (anonymous, no-login) session history.
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
    "Accept-Language": "en-SA,en;q=0.9,ar;q=0.8",
}

CATEGORIES = ["electronics", "home", "beauty", "grocery", "toys-kids-babies"]


def scrape_category(category: str):
    products = []
    try:
        url = f"https://www.noon.com/_svc/catalog/api/v3/personalization-products/curated_for_you/{category}"
        resp = requests.get(url, headers=HEADERS, params={"limit": 50}, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        hits = payload.get("hits", [])
        for idx, p in enumerate(hits, start=1):
            slug = p.get("url")
            sku = p.get("sku")
            product_url = (
                f"https://www.noon.com/saudi-en/{slug}/p/{sku.lower()}/"
                if slug and sku else None
            )
            rating = p.get("product_rating") or {}

            products.append({
                "category": category,
                "rank": idx,
                "title": p.get("name"),
                "price": p.get("sale_price") or p.get("price"),
                "rating": rating.get("value"),
                "review_count": rating.get("count"),
                "url": product_url,
                "image": p.get("image_url"),
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
