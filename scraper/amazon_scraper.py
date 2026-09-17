"""
Amazon.sa Best Sellers scraper.

NOTE: Amazon's HTML structure changes often and they actively block
automated requests. This script uses polite headers + delays, but you
should expect to need to tweak the CSS selectors below after your first
run (view page source on amazon.sa and adjust if items come back empty).

Amazon does NOT expose real "search volume" data publicly. What we
collect here is the Best Sellers rank, price, rating, and review count —
these are the best public proxies for "what's hot" that exist without
paid seller-central/ads access.
"""

import time
import random
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SA,en;q=0.9,ar;q=0.8",
}

# General "all categories" best-seller pages on amazon.sa
CATEGORY_URLS = {
    "All / Electronics": "https://www.amazon.sa/gp/bestsellers/electronics",
    "All / Home": "https://www.amazon.sa/gp/bestsellers/kitchen",
    "All / Beauty": "https://www.amazon.sa/gp/bestsellers/beauty",
    "All / Grocery": "https://www.amazon.sa/gp/bestsellers/grocery",
    "All / Toys": "https://www.amazon.sa/gp/bestsellers/toys",
}


def scrape_category(name: str, url: str):
    products = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("div.p13n-desc, div.zg-grid-general-faceout")
        for idx, item in enumerate(items, start=1):
            title_el = item.select_one("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, .p13n-sc-truncate, span.a-size-small")
            price_el = item.select_one(".p13n-sc-price, .a-price .a-offscreen")
            rating_el = item.select_one(".a-icon-alt")
            reviews_el = item.select_one(".a-size-small.a-color-secondary")
            link_el = item.find("a", href=True)
            img_el = item.find("img")

            url = None
            if link_el:
                href = link_el["href"]
                url = href if href.startswith("http") else f"https://www.amazon.sa{href}"

            image = img_el.get("src") if img_el else None

            products.append({
                "category": name,
                "rank": idx,
                "title": title_el.get_text(strip=True) if title_el else None,
                "price": price_el.get_text(strip=True) if price_el else None,
                "rating": rating_el.get_text(strip=True) if rating_el else None,
                "review_count": reviews_el.get_text(strip=True) if reviews_el else None,
                "url": url,
                "image": image,
                "source": "amazon.sa",
            })
    except Exception as e:
        print(f"[amazon] Failed to scrape {name}: {e}")

    return products


def scrape_all():
    all_products = []
    for name, url in CATEGORY_URLS.items():
        print(f"[amazon] Scraping: {name}")
        all_products.extend(scrape_category(name, url))
        time.sleep(random.uniform(3, 6))  # be polite, avoid rate-limiting
    return all_products


if __name__ == "__main__":
    data = scrape_all()
    print(f"Scraped {len(data)} products from Amazon.sa")
