"""
Noon.sa scraper.

Uses Noon's curated-for-you endpoint as a proxy for currently popular products.
The scraper is defensive: persistent session, browser-like headers, retries,
separate connection/read timeouts, and graceful per-category failures.
"""

import random
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.noon.com"
API_PATH = "/_svc/catalog/api/v3/personalization-products/curated_for_you"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-SA,en;q=0.9,ar;q=0.8",
    "Referer": "https://www.noon.com/saudi-en/",
    "Origin": BASE_URL,
    "Connection": "keep-alive",
}

CATEGORIES = [
    "electronics",
    "home",
    "beauty",
    "grocery",
    "toys-kids-babies",
]

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 45
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)
MAX_RETRIES = 3
RETRY_BACKOFF = 2
PRODUCT_LIMIT = 50


def create_session() -> requests.Session:
    """Create a persistent HTTP session with automatic retries."""
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=5,
        pool_maxsize=5,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def build_product_url(slug: Optional[str], sku: Optional[str]) -> Optional[str]:
    if not slug or not sku:
        return None
    return f"{BASE_URL}/saudi-en/{slug}/p/{str(sku).lower()}/"


def scrape_category(
    category: str,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """Scrape one Noon category without stopping the overall run on failure."""
    products: List[Dict[str, Any]] = []
    own_session = session is None
    if own_session:
        session = create_session()

    url = f"{BASE_URL}{API_PATH}/{category}"

    try:
        print(f"[noon] Requesting: {url}")
        response = session.get(
            url,
            params={"limit": PRODUCT_LIMIT},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code in (403, 429):
            print(
                f"[noon] {category}: Noon returned HTTP "
                f"{response.status_code} (possible blocking/rate limiting)."
            )
            return products

        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            print(f"[noon] {category}: response was not valid JSON.")
            return products

        if not isinstance(payload, dict):
            print(f"[noon] {category}: unexpected API response format.")
            return products

        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            print(f"[noon] {category}: 'hits' was not a list.")
            return products

        for idx, product in enumerate(hits, start=1):
            if not isinstance(product, dict):
                continue

            rating = product.get("product_rating") or {}
            if not isinstance(rating, dict):
                rating = {}

            products.append({
                "category": category,
                "rank": idx,
                "title": product.get("name"),
                "price": product.get("sale_price") or product.get("price"),
                "rating": rating.get("value"),
                "review_count": rating.get("count"),
                "url": build_product_url(product.get("url"), product.get("sku")),
                "image": product.get("image_url"),
                "source": "noon.sa",
            })

        print(f"[noon] {category}: {len(products)} products received.")

    except requests.exceptions.ConnectTimeout:
        print(
            f"[noon] Failed to scrape {category}: "
            f"connection timed out after {CONNECT_TIMEOUT}s."
        )
    except requests.exceptions.ReadTimeout:
        print(
            f"[noon] Failed to scrape {category}: "
            f"Noon did not respond within {READ_TIMEOUT}s."
        )
    except requests.exceptions.RequestException as exc:
        print(f"[noon] Failed to scrape {category}: {exc}")
    except Exception as exc:
        print(f"[noon] Unexpected error scraping {category}: {exc}")
    finally:
        if own_session:
            session.close()

    return products


def scrape_all() -> List[Dict[str, Any]]:
    """Scrape all configured Noon categories."""
    all_products: List[Dict[str, Any]] = []
    session = create_session()

    try:
        for index, category in enumerate(CATEGORIES):
            print(f"[noon] Scraping: {category}")
            all_products.extend(scrape_category(category, session=session))

            if index < len(CATEGORIES) - 1:
                delay = random.uniform(4, 8)
                print(f"[noon] Waiting {delay:.1f}s before next category...")
                time.sleep(delay)
    finally:
        session.close()

    print(f"[noon] Total products scraped: {len(all_products)}")
    return all_products


if __name__ == "__main__":
    data = scrape_all()
    print(f"Scraped {len(data)} products from Noon.sa")
