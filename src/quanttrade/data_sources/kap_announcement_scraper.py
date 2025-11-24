import requests
import json
import csv
import sys
import time
import random
from pathlib import Path

BASE_URL = "https://www.kap.org.tr"

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols

MAPPING_FILE = PROJECT_ROOT / "config" / "kap_symbols_oids_mapping.json"

# -----------------------------------------------------
# GLOBAL SESSION (Tek sefer)
# -----------------------------------------------------
session = requests.Session()
session.verify = True

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/tr/bildirim-sorgu",
    "X-Requested-With": "XMLHttpRequest"
}
session.headers.update(BASE_HEADERS)


# -----------------------------------------------------
# COOKIE + CSRF Token Toplama
# -----------------------------------------------------
def init_session():
    print("🔄 Oturum başlatılıyor...")
    session.get(BASE_URL)
    time.sleep(1)
    r = session.get(BASE_URL + "/tr/bildirim-sorgu")

    # Anti-bot tokenlar
    token = r.cookies.get("__RequestVerificationToken")
    xsrf = r.cookies.get("XSRF-TOKEN")

    if token:
        session.headers["RequestVerificationToken"] = token
    if xsrf:
        session.headers["X-XSRF-TOKEN"] = xsrf

    print("✅ Session hazır.")


# -----------------------------------------------------
# Finansal Raporları ÇEK (Stabil)
# -----------------------------------------------------
def fetch_financial_reports(from_date, to_date, oid):
    url = BASE_URL + "/tr/api/disclosure/members/byCriteria"

    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "memberType": "IGS",
        "disclosureClass": "FR",
        "mkkMemberOidList": [oid],
    }

    def handle_ban():
        print("⛔ Ban algılandı. 60 saniye bekleniyor...")
        time.sleep(60)
        print("🔄 Oturum yenileniyor...")
        init_session()

    # İlk deneme
    r = session.post(url, json=payload, timeout=30)

    # Ban tespiti
    if (
        r.status_code != 200 or 
        "<!DOCTYPE" in r.text or 
        "html" in r.text.lower()
    ):
        handle_ban()
        r = session.post(url, json=payload, timeout=30)

    # tekrar HTML ise vazgeç
    try:
        data = r.json()
    except:
        return []

    if not isinstance(data, list):
        return []

    results = []
    for item in data:
        if "Finansal" in (item.get("subject") or ""):
            results.append({
                "index": item.get("disclosureIndex"),
                "publishDate": item.get("publishDate"),
                "summary": item.get("summary"),
                "url": f"https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}"
            })

    return results


# -----------------------------------------------------
def load_symbol_oid_mapping():
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping = json.load(f)["companies"]

    result = {}
    for s in get_stock_symbols():
        s2 = s.upper()
        if s2 in mapping:
            result[s2] = mapping[s2]["oid"]
    return result


def generate_year_ranges(start_year, end_year):
    return [(f"{y}-01-01", f"{y}-12-31") for y in range(start_year, end_year + 1)]


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------
if __name__ == "__main__":
    print("KAP SCRAPER START")
    init_session()

    symbols = load_symbol_oid_mapping()
    year_ranges = generate_year_ranges(2020, 2025)

    for symbol, oid in symbols.items():
        print(f"\n📌 {symbol} çekiliyor...")

        all_data = []
        for d1, d2 in year_ranges:
            reports = fetch_financial_reports(d1, d2, oid)
            all_data.extend(reports)
            time.sleep(random.uniform(1.2, 2.5))

        if all_data:
            out_file = OUTPUT_DIR / f"{symbol}_announcements.csv"
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["index", "publishDate", "ruleType", "summary", "url"])
                w.writeheader()
                w.writerows(all_data)
            print(f"   ✓ {len(all_data)} rapor kaydedildi.")
        else:
            print("   ⚠ Veri yok.")
