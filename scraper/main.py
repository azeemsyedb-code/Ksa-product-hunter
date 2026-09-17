"""
Orchestrator: runs both scrapers, merges results, compares against
yesterday's snapshot to compute a "trending score", finds simple
cross-platform price matches, and writes:

  data/snapshots/YYYY-MM-DD.json   (raw daily snapshot, kept for history)
  data/snapshots/index.json        (list of all snapshot dates, for charts)
  data/latest.json                 (what the dashboard reads)

Trending score logic (since true search-volume data isn't public):
  - New entry into a bestseller list          -> high score
  - Rank improved vs yesterday (moved up)      -> score based on jump size
  - Review count increased vs yesterday        -> score based on growth
  - Rank unchanged / dropped                   -> low score
"""

import json
import os
import re
import difflib
import requests
from datetime import datetime, timezone

from amazon_scraper import scrape_all as scrape_amazon
from noon_scraper import scrape_all as scrape_noon

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")

# Alert threshold: products with trend_score >= this get a Telegram ping.
ALERT_THRESHOLD = 60

# How similar two titles must be (0-1) to be treated as "the same product"
# across Amazon and Noon for the price-compare feature. This is a rough
# heuristic (no shared product IDs exist across platforms) — expect some
# false positives/negatives.
MATCH_SIMILARITY = 0.72

# Names that count as "no real brand" even if a brand field is present.
GENERIC_BRAND_NAMES = {"generic", "no brand", "unbranded", "n/a", "other", ""}

# Recognizable brand names to catch in the title when no explicit brand
# field exists (mainly needed for Amazon). Not exhaustive — extend this
# list any time you notice a well-known brand getting misclassified.
KNOWN_BRANDS = [
    "apple", "samsung", "sony", "lg", "xiaomi", "huawei", "oppo", "vivo", "oneplus",
    "nokia", "jbl", "bose", "anker", "logitech", "hp", "dell", "lenovo", "asus",
    "acer", "microsoft", "nintendo", "philips", "panasonic", "bosch", "braun",
    "dyson", "tefal", "kenwood", "black+decker", "nike", "adidas", "puma",
    "reebok", "under armour", "loreal", "l'oreal", "nivea", "dove", "gillette",
    "olay", "maybelline", "nescafe", "nestle", "lego", "hasbro", "fisher-price",
    "mattel", "barbie", "hot wheels", "canon", "nikon", "gopro", "fitbit",
    "garmin", "xbox", "playstation",
]


def classify_brand(product: dict) -> str:
    """Returns 'branded' or 'non-branded' — a heuristic, not a certainty.
    Uses the explicit brand field when present (Noon), otherwise checks
    for a known brand name inside the title (mainly for Amazon)."""
    brand = (product.get("brand") or "").strip().lower()
    if brand and brand not in GENERIC_BRAND_NAMES:
        return "branded"

    title = (product.get("title") or "").lower()
    for known in KNOWN_BRANDS:
        if known in title:
            return "branded"

    return "non-branded"


def _key(p):
    return f"{p['source']}::{p.get('category')}::{p.get('title')}"


def load_yesterday():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(SNAPSHOT_DIR) if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f))
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


def _parse_price(val):
    if val is None:
        return None
    digits = re.sub(r"[^\d.]", "", str(val))
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def compute_trending(products, previous_by_key):
    for p in products:
        p["product_type"] = classify_brand(p)

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


def find_cross_platform_matches(products):
    """
    Naive title-similarity match between Amazon and Noon products in the
    same category, to surface likely price differences for the same item.
    Not a real product-ID match (none exists across platforms) — treat
    results as suggestions to verify manually, not certainties.
    """
    amazon_products = [p for p in products if p["source"] == "amazon.sa" and p.get("title")]
    noon_products = [p for p in products if p["source"] == "noon.sa" and p.get("title")]

    matches = []
    for a in amazon_products:
        best = None
        best_ratio = 0
        for n in noon_products:
            if a.get("category") != n.get("category"):
                continue
            ratio = difflib.SequenceMatcher(None, a["title"].lower(), n["title"].lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = n

        if best and best_ratio >= MATCH_SIMILARITY:
            a_price = _parse_price(a.get("price"))
            n_price = _parse_price(best.get("price"))
            if a_price and n_price:
                matches.append({
                    "amazon_title": a["title"],
                    "noon_title": best["title"],
                    "category": a.get("category"),
                    "amazon_price": a_price,
                    "noon_price": n_price,
                    "price_diff": round(a_price - n_price, 2),
                    "cheaper_on": "noon.sa" if n_price < a_price else "amazon.sa",
                    "amazon_url": a.get("url"),
                    "noon_url": best.get("url"),
                    "similarity": round(best_ratio, 2),
                })

    matches.sort(key=lambda m: abs(m["price_diff"]), reverse=True)
    return matches


def update_snapshot_index(today):
    """Keeps data/snapshots/index.json up to date — a plain list of dates
    that exist, so the dashboard can fetch price history without needing
    a directory listing (static hosting can't list files itself)."""
    index_path = os.path.join(SNAPSHOT_DIR, "index.json")
    dates = []
    if os.path.exists(index_path):
        with open(index_path) as f:
            dates = json.load(f)
    if today not in dates:
        dates.append(today)
    dates.sort()
    with open(index_path, "w") as f:
        json.dump(dates, f)


def category_hot_list(products, top_n=3):
    """Top N trending products per category, for the dashboard summary."""
    by_category = {}
    for p in products:
        cat = p.get("category") or "Unknown"
        by_category.setdefault(cat, []).append(p)

    summary = {}
    for cat, items in by_category.items():
        top = sorted(items, key=lambda p: p.get("trend_score") or 0, reverse=True)[:top_n]
        summary[cat] = [
            {"title": p.get("title"), "trend_score": p.get("trend_score"), "source": p.get("source"), "url": p.get("url")}
            for p in top
        ]
    return summary


def send_telegram_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[alert] Telegram not configured — skipping.")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        print(f"[alert] Telegram message sent, status: {resp.status_code}")
    except Exception as e:
        print(f"[alert] Failed to send Telegram message: {e}")


def send_run_summary(snapshot):
    """Sent on EVERY run, regardless of whether anything is trending —
    just a heads-up that fresh data is in."""
    lines = [
        "✅ Souq Signal updated",
        f"📅 {snapshot['date']}",
        f"📦 {snapshot['total_products']} products (Amazon: {snapshot['amazon_count']}, Noon: {snapshot['noon_count']})",
        f"🏷 Branded: {snapshot['branded_count']} · Non-branded: {snapshot['non_branded_count']}",
    ]
    hot_count = sum(1 for p in snapshot["products"] if (p.get("trend_score") or 0) >= ALERT_THRESHOLD)
    if hot_count:
        lines.append(f"🔥 {hot_count} product(s) trending today — see below")
    send_telegram_message("\n".join(lines))


def send_trend_alert(products):
    hot = [p for p in products if (p.get("trend_score") or 0) >= ALERT_THRESHOLD]
    if not hot:
        print("[alert] No products crossed the alert threshold today.")
        return

    hot.sort(key=lambda p: p["trend_score"], reverse=True)
    lines = [f"🔥 Souq Signal — {len(hot)} trending product(s) today:"]
    for p in hot[:10]:
        tag = "NEW" if p.get("trend") == "new" else f"+{p['trend_score']}"
        lines.append(f"• [{tag}] {p.get('title', 'Unknown')[:60]} ({p.get('source')})")
    send_telegram_message("\n".join(lines))


def send_failure_alert(amazon_count, noon_count):
    problems = []
    if amazon_count == 0:
        problems.append("Amazon.sa returned 0 products")
    if noon_count == 0:
        problems.append("Noon.sa returned 0 products")
    if not problems:
        return
    text = "⚠️ Souq Signal scrape issue:\n" + "\n".join(f"• {p}" for p in problems) + \
        "\n\nThe site's page/API structure may have changed — selectors likely need updating."
    send_telegram_message(text)


def compute_weekly_bestsellers(min_days_threshold=None):
    """
    Looks at the last 7 daily snapshots and keeps only products that showed
    up consistently (appeared on at least half of the tracked days) —
    this is the "stays put for a week" list, instead of the daily
    all-products view where things constantly come and go.
    """
    files = sorted(f for f in os.listdir(SNAPSHOT_DIR) if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f))[-7:]
    if not files:
        return []

    tally = {}
    for fname in files:
        with open(os.path.join(SNAPSHOT_DIR, fname)) as f:
            snap = json.load(f)
        for p in snap.get("products", []):
            k = _key(p)
            entry = tally.setdefault(k, {
                "title": p.get("title"), "source": p.get("source"), "category": p.get("category"),
                "brand": p.get("brand"), "product_type": p.get("product_type"),
                "url": p.get("url"), "image": p.get("image"),
                "days_seen": 0, "ranks": [], "prices": [],
            })
            entry["days_seen"] += 1
            if p.get("rank") is not None:
                entry["ranks"].append(p["rank"])
            price = _parse_price(p.get("price"))
            if price:
                entry["prices"].append(price)

    threshold = min_days_threshold or max(2, len(files) // 2)
    results = []
    for entry in tally.values():
        if entry["days_seen"] >= threshold:
            results.append({
                "title": entry["title"], "source": entry["source"], "category": entry["category"],
                "brand": entry["brand"], "product_type": entry["product_type"],
                "url": entry["url"], "image": entry["image"],
                "days_seen": entry["days_seen"], "days_tracked": len(files),
                "avg_rank": round(sum(entry["ranks"]) / len(entry["ranks"]), 1) if entry["ranks"] else None,
                "latest_price": entry["prices"][-1] if entry["prices"] else None,
            })

    results.sort(key=lambda r: (-r["days_seen"], r["avg_rank"] if r["avg_rank"] is not None else 999))
    return results


HEALTH_LOG_PATH = os.path.join(DATA_DIR, "health.json")
MAX_HEALTH_ENTRIES = 40  # ~20 days at twice-daily runs


def record_health(amazon_count, noon_count, per_category_amazon=None, per_category_noon=None):
    """Appends this run's per-source result to a rolling health log, so the
    health.html dashboard page can show a success/fail history over time —
    useful for spotting when a site's page structure broke vs. a one-off
    blip."""
    history = []
    if os.path.exists(HEALTH_LOG_PATH):
        try:
            with open(HEALTH_LOG_PATH) as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amazon_count": amazon_count,
        "noon_count": noon_count,
        "amazon_ok": amazon_count > 0,
        "noon_ok": noon_count > 0,
    })
    history = history[-MAX_HEALTH_ENTRIES:]

    with open(HEALTH_LOG_PATH, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def run():
    print("Starting daily product hunt...")
    amazon_products = scrape_amazon()
    noon_products = scrape_noon()
    products = amazon_products + noon_products

    previous_by_key = load_yesterday()
    products = compute_trending(products, previous_by_key)
    matches = find_cross_platform_matches(products)
    hot_list = category_hot_list(products)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_products": len(products),
        "amazon_count": len(amazon_products),
        "noon_count": len(noon_products),
        "branded_count": sum(1 for p in products if p["product_type"] == "branded"),
        "non_branded_count": sum(1 for p in products if p["product_type"] == "non-branded"),
        "products": products,
        "price_matches": matches,
        "category_hot_list": hot_list,
    }

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(os.path.join(SNAPSHOT_DIR, f"{today}.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    update_snapshot_index(today)

    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    weekly = compute_weekly_bestsellers()
    with open(os.path.join(DATA_DIR, "weekly.json"), "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "days_tracked": weekly[0]["days_tracked"] if weekly else 0,
            "products": weekly,
        }, f, ensure_ascii=False, indent=2)

    send_run_summary(snapshot)
    send_trend_alert(products)
    send_failure_alert(len(amazon_products), len(noon_products))
    record_health(len(amazon_products), len(noon_products))

    print(f"Done. {len(products)} products saved for {today} "
          f"(Amazon: {len(amazon_products)}, Noon: {len(noon_products)}).")


if __name__ == "__main__":
    run()
