"""
Look up full details for ONE product by pasting its Amazon.sa or Noon.sa URL.

Usage:
    python lookup_product.py "https://www.amazon.sa/dp/B0XXXXXXX"
    python lookup_product.py "https://www.noon.com/saudi-en/some-product/p/n123.../"

Prints the result and also saves it to data/lookups/<timestamp>.json
"""

import sys
import json
import os
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from scrape_utils import get_with_retry

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "lookups")


def lookup_amazon(url: str) -> dict:
    resp = get_with_retry(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    def text_of(selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    title = text_of("#productTitle")
    price = (
        text_of(".a-price .a-offscreen")
        or text_of("#priceblock_ourprice")
        or text_of("#priceblock_dealprice")
    )
    rating = text_of("#acrPopover .a-icon-alt") or text_of("span.a-icon-alt")
    review_count = text_of("#acrCustomerReviewText")
    brand = text_of("#bylineInfo")
    availability = text_of("#availability span")

    # Feature bullets
    bullets = [
        li.get_text(strip=True)
        for li in soup.select("#feature-bullets li span.a-list-item")
    ]

    # Main image
    img_el = soup.select_one("#landingImage, #imgBlkFront")
    image = img_el.get("src") if img_el else None

    # Basic spec table (varies a lot by listing type)
    specs = {}
    for row in soup.select("#productDetails_techSpec_section_1 tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            specs[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)

    return {
        "source": "amazon.sa",
        "url": url,
        "title": title,
        "brand": brand,
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "availability": availability,
        "image": image,
        "bullets": bullets,
        "specifications": specs,
    }


def lookup_noon(url: str) -> dict:
    # Noon product pages embed a Next.js data blob with the full product
    # payload -- much more reliable than scraping visible HTML.
    resp = get_with_retry(url)
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL
    )
    if not match:
        return {"source": "noon.sa", "url": url, "error": "Could not find embedded product data on page."}

    try:
        blob = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {"source": "noon.sa", "url": url, "error": "Failed to parse embedded product data."}

    # The exact path into this blob can shift with Noon's frontend version.
    # Walk common locations; fall back to returning the raw blob so you can
    # inspect it and tell me the right path if this misses.
    props = blob.get("props", {}).get("pageProps", {})
    product = props.get("product") or props.get("productDetails") or {}

    if not product:
        return {
            "source": "noon.sa",
            "url": url,
            "warning": "Could not locate product fields at the expected path — raw data included for inspection.",
            "raw": blob.get("props", {}).get("pageProps", {}),
        }

    return {
        "source": "noon.sa",
        "url": url,
        "title": product.get("name") or product.get("title"),
        "brand": product.get("brand"),
        "price": product.get("sale_price") or product.get("price"),
        "rating": (product.get("product_rating") or {}).get("value"),
        "review_count": (product.get("product_rating") or {}).get("count"),
        "image": product.get("image_url"),
        "specifications": product.get("plp_specifications") or {},
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python lookup_product.py "<product URL>"')
        sys.exit(1)

    url = sys.argv[1]

    if "amazon.sa" in url:
        result = lookup_amazon(url)
    elif "noon.com" in url:
        result = lookup_noon(url)
    else:
        print("URL must be from amazon.sa or noon.com")
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(DATA_DIR, f"{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
