"""
Noon.sa scraper.

Endpoint and field names below were confirmed by inspecting a real browser
request (DevTools -> Network) on 2026-09-17 for the "electronics" category.
The other category slugs (home, beauty, grocery, toys-kids-babies) are
guesses and may not match Noon's actual identifiers — if the logs show
0 products for a specific category while electronics works fine, open that
category on noon.sa, repeat the DevTools steps, and swap in the real slug
from the URL you find there.

If ALL categories return 0 (including electronics), Noon may be blocking
data-center IPs (like GitHub Actions runners) — this uses retry with
rotating User-Agents (scrape_utils.get_with_retry) to reduce that risk.

Note: this uses Noon's "curated for you" endpoint (their homepage/category
recommendation feed), not a literal admin "best sellers" list -- Noon doesn't
expose one publicly. It's still a solid proxy for "what's popular right now".
"""

import time
import random
from scrape_utils import get_with_retry, random_headers

CATEGORIES = ["electronics", "home", "beauty", "grocery", "toys-kids-babies"]


def scrape_category(category: str):
    products = []
    try:
        url = f"https://www.noon.com/_svc/catalog/api/v3/personalization-products/curated_for_you/{category}"
        resp = get_with_retry(
            url,
            headers=random_headers({"Accept": "application/json"}),
            params={"limit": 50},
        )
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
                "brand": p.get("brand"),
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
        result = scrape_category(cat)
        print(f"[noon]   -> {len(result)} products")
        all_products.extend(result)
        time.sleep(random.uniform(3, 6))
    return all_products


if __name__ == "__main__":
    data = scrape_all()
    print(f"Scraped {len(data)} products from Noon.sa")
