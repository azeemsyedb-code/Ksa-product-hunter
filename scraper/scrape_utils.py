"""Shared helpers: retry logic + rotating User-Agent to reduce block risk."""

import time
import random
import requests

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def random_headers(extra: dict | None = None) -> dict:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-SA,en;q=0.9,ar;q=0.8",
    }
    if extra:
        headers.update(extra)
    return headers


def get_with_retry(url, headers=None, params=None, max_attempts=3, timeout=20):
    """GET with retries + exponential backoff. Raises on final failure."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(
                url,
                headers=headers or random_headers(),
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"  retry {attempt}/{max_attempts} after error ({e}), waiting {wait:.1f}s")
                time.sleep(wait)
    raise last_error
