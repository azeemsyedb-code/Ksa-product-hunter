"""
Compiles the last 7 days of snapshots into a single Excel file
(data/exports/weekly-<date>.xlsx) and, if Telegram is configured, sends it
as a document so you get it directly without opening GitHub.
"""

import os
import json
import glob
import requests
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import Font

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")


def load_last_n_snapshots(n=7):
    files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "????-??-??.json")))[-n:]
    snapshots = []
    for f in files:
        with open(f) as fh:
            snapshots.append(json.load(fh))
    return snapshots


def build_workbook(snapshots):
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Data"

    headers = ["Date", "Source", "Rank", "Title", "Brand", "Type", "Category", "Price", "Rating", "Reviews", "Trend", "Trend Score", "URL"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for snap in snapshots:
        for p in snap.get("products", []):
            ws.append([
                snap.get("date"), p.get("source"), p.get("rank"), p.get("title"), p.get("brand"), p.get("product_type"),
                p.get("category"), p.get("price"), p.get("rating"), p.get("review_count"),
                p.get("trend"), p.get("trend_score"), p.get("url"),
            ])

    for col, width in zip("ABCDEFGHIJKLM", [12, 10, 6, 50, 14, 12, 16, 10, 8, 10, 8, 12, 40]):
        ws.column_dimensions[col].width = width

    return wb


def send_telegram_document(path):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[export] Telegram not configured — file saved to repo only.")
        return
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": "📊 Souq Signal — weekly export"},
                files={"document": f},
                timeout=30,
            )
        print(f"[export] Telegram document sent, status: {resp.status_code}")
    except Exception as e:
        print(f"[export] Failed to send Telegram document: {e}")


def run():
    snapshots = load_last_n_snapshots(7)
    if not snapshots:
        print("No snapshots found — nothing to export.")
        return

    wb = build_workbook(snapshots)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(EXPORT_DIR, f"weekly-{today}.xlsx")
    wb.save(out_path)
    print(f"Saved {out_path}")

    send_telegram_document(out_path)


if __name__ == "__main__":
    run()
