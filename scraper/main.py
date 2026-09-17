"""
Orchestrator: runs both scrapers, merges results, compares against
yesterday's snapshot to compute a "trending score", and writes:

  data/snapshots/YYYY-MM-DD.json   (raw daily snapshot, kept for history)
  data/latest.json                 (what the dashboard reads)

Trending score logic (since true search-volume data isn't public):
  - New entry into a bestseller list          -> high score
  - Rank improved vs yesterday (moved up)      -> score based on jump size
  - Review count increased vs yesterday        -> score based on growth
  - Rank unchanged / dropped                   -> low score
"""

import json
import os
from datetime import datetime, timezone

from amazon_scraper import scrape_all as scrape_amazon
from noon_scraper import scrape_all as scrape_noon

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")


def _key(p):
    return f"{p['source']}::{p.get('category')}::{p.get('title')}"


def load_yesterday():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json"))
    if not files:
        return {}
    with open(os.path.join(SNAPSHOT_DIR, files[-1])) as f:
        prev = json.load(f)
    return {_key(p): p for p in prev.get("products", [])}


def _parse_reviews(val):
    if not val:
        return 0
    digits = "".join(c for c in str(val) if c.isdigit())
    return int(digits) if digits else 0


def compute_trending(products, previous_by_key):
    for p in products:
        prev = previous_by_key.get(_key(p))
        if prev is None:
            p["trend"] = "new"
            p["trend_score"] = 80
            continue

        rank_delta = (prev.get("rank") or 999) - (p.get("rank") or 999)
        review_delta = _parse_reviews(p.get("review_count")) - _parse_reviews(prev.get("review_count"))

        score = max(0, rank_delta) * 3 + max(0, review_delta) * 0.5
        p["trend_score"] = round(min(score, 100), 1)
        p["trend"] = "up" if score > 5 else ("flat" if score >= -5 else "down")

    return products


def run():
    print("Starting daily product hunt...")
    products = []
    products.extend(scrape_amazon())
    products.extend(scrape_noon())

    previous_by_key = load_yesterday()
    products = compute_trending(products, previous_by_key)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_products": len(products),
        "products": products,
    }

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(os.path.join(SNAPSHOT_DIR, f"{today}.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"Done. {len(products)} products saved for {today}.")


if __name__ == "__main__":
    run()
