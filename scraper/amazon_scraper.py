"""
Amazon.sa Best Sellers scraper.

Uses http_utils.get_with_retry (rotating User-Agents + retries) since Amazon
also blocks/rate-limits data-center IPs sometimes. Amazon's HTML structure
changes often, so if this comes back with 0 results, view-source a bestseller
page and update the CSS selectors below.
"""

import time
import random
from bs4 import BeautifulSoup
from scrape_utils import get_with_retry

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
        resp = get_with_retry(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("div.p13n-desc, div.zg-grid-general-faceout")
        for idx, item in enumerate(items, start=1):
            title_el = item.select_one("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, .p13n-sc-truncate, span.a-size-small")
            price_el = item.select_one(".p13n-sc-price, .a-price .a-offscreen")
            rating_el = item.select_one(".a-icon-alt")
            reviews_el = item.select_one(".a-size-small.a-color-secondary")
            link_el = item.find("a", href=True)
            img_el = item.find("img")

            url_out = None
            if link_el:
                href = link_el["href"]
                url_out = href if href.startswith("http") else f"https://www.amazon.sa{href}"

            image = img_el.get("src") if img_el else None

            products.append({
                "category": name,
                "rank": idx,
                "title": title_el.get_text(strip=True) if title_el else None,
                "brand": None,  # Amazon's bestseller listing doesn't expose a separate brand field; classified from title instead (see main.py)
                "price": price_el.get_text(strip=True) if price_el else None,
                "rating": rating_el.get_text(strip=True) if rating_el else None,
                "review_count": reviews_el.get_text(strip=True) if reviews_el else None,
                "url": url_out,
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
        result = scrape_category(name, url)
        print(f"[amazon]   -> {len(result)} products")
        all_products.extend(result)
        time.sleep(random.uniform(3, 6))
    return all_products


if __name__ == "__main__":
    data = scrape_all()
    print(f"Scraped {len(data)} products from Amazon.sa")
