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
import requests
from datetime import datetime, timezone

from amazon_scraper import scrape_all as scrape_amazon
from noon_scraper import scrape_all as scrape_noon

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")

# Alert threshold: products with trend_score >= this get a WhatsApp ping.
ALERT_THRESHOLD = 60


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


def send_whatsapp_alert(products):
    """
    Sends a WhatsApp message via CallMeBot (free) if credentials are set as
    environment variables (CALLMEBOT_PHONE, CALLMEBOT_APIKEY). Silently does
    nothing if they're not configured — see README for one-time setup.
    """
    phone = os.environ.get("CALLMEBOT_PHONE")
    apikey = os.environ.get("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        print("[alert] CallMeBot not configured — skipping WhatsApp alert.")
        return

    hot = [p for p in products if (p.get("trend_score") or 0) >= ALERT_THRESHOLD]
    if not hot:
        print("[alert] No products crossed the alert threshold today.")
        return

    hot.sort(key=lambda p: p["trend_score"], reverse=True)
    lines = [f"🔥 Souq Signal — {len(hot)} trending product(s) today:"]
    for p in hot[:10]:
        tag = "NEW" if p.get("trend") == "new" else f"+{p['trend_score']}"
        lines.append(f"• [{tag}] {p.get('title', 'Unknown')[:60]} ({p.get('source')})")
    message = "\n".join(lines)

    try:
        resp = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": phone, "text": message, "apikey": apikey},
            timeout=15,
        )
        print(f"[alert] WhatsApp alert sent, status: {resp.status_code}")
    except Exception as e:
        print(f"[alert] Failed to send WhatsApp alert: {e}")


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

    send_whatsapp_alert(products)

    print(f"Done. {len(products)} products saved for {today}.")


if __name__ == "__main__":
    run()
