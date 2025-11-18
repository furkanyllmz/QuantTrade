import requests
import pandas as pd
import json
import sys
import time
from pathlib import Path

# Project root ve config
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "split_ratio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols, get_stock_date_range
from datetime import datetime

URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetSermayeArttirimlari"

def get_split_data(symbol):
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.isyatirim.com.tr",
        "Referer": f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}",
        "Connection": "keep-alive",
    }

    payload = {
        "hisseKodu": symbol,
        "hisseTanimKodu": "",
        "yil": 0,
        "zaman": "HEPSI",
        "endeksKodu": "09",
        "sektorKodu": ""
    }

    try:
        r = session.post(URL, headers=headers, data=json.dumps(payload), timeout=10, verify=True)
        r.raise_for_status()

        raw_json = r.json()["d"]
        
        # StringIO kullanarak FutureWarning'i düzelt
        from io import StringIO
        df = pd.read_json(StringIO(raw_json))

        # Split oranı hesaplama
        if not df.empty and "HSP_BOLUNME_ONCESI_SERMAYE" in df.columns and "HSP_BOLUNME_SONRASI_SERMAYE" in df.columns:
            df["SPLIT_RATIO"] = df["HSP_BOLUNME_SONRASI_SERMAYE"] / df["HSP_BOLUNME_ONCESI_SERMAYE"]

        return df
    except Exception as e:
        print(f"❌ Hata: {e}")
        return pd.DataFrame()


def filter_by_date_range(df, start_date, end_date):
    """Tarih aralığına göre filtrele"""
    if df.empty:
        return df
    
    try:
        # Tarih kolonu: SHHE_TARIH
        if 'SHHE_TARIH' not in df.columns:
            return df
        
        # Tarihi timestamp'den datetime'a çevir (milliseconds)
        df['SHHE_TARIH'] = pd.to_datetime(df['SHHE_TARIH'], unit='ms', errors='coerce')
        
        # Start ve end date'i datetime'a çevir
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Filtrele
        mask = (df['SHHE_TARIH'] >= start_dt) & (df['SHHE_TARIH'] <= end_dt)
        filtered_df = df[mask].copy()
        
        return filtered_df
    except Exception as e:
        print(f"⚠ Tarih filtreleme hatası: {e}")
        return df


if __name__ == "__main__":
    print("=" * 70)
    print("SPLIT RATIO SCRAPER")
    print("=" * 70)
    
    # Config'ten semboller ve tarih aralığı
    print("\n📋 Semboller ve tarih aralığı yükleniyor...")
    symbols = get_stock_symbols()
    start_date, end_date = get_stock_date_range()
    
    print(f"   ✓ {len(symbols)} sembol yüklendi")
    print(f"   ✓ Tarih aralığı: {start_date} - {end_date}")
    
    # Her sembol için split ratio çek
    print("\n🔍 Split ratio verileri çekiliyor...\n")
    
    success_count = 0
    fail_count = 0
    
    for symbol in symbols:
        print(f"   {symbol}...", end=" ", flush=True)
        
        try:
            df = get_split_data(symbol)
            
            if not df.empty:
                # Tarih aralığına göre filtrele
                df_filtered = filter_by_date_range(df, start_date, end_date)
                
                if not df_filtered.empty:
                    csv_file = OUTPUT_DIR / f"{symbol}_split.csv"
                    df_filtered.to_csv(csv_file, index=False, encoding="utf-8-sig")
                    
                    print(f"✓ {len(df_filtered)}/{len(df)} kayıt (filtrelenmiş)")
                    success_count += 1
                else:
                    # Tarih aralığında veri yoksa tümünü kaydet
                    csv_file = OUTPUT_DIR / f"{symbol}_split.csv"
                    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
                    
                    print(f"✓ {len(df)} kayıt (tamamı kaydedildi, tarih aralığı dışı)")
                    success_count += 1
            else:
                print("⚠ Veri yok")
                fail_count += 1
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Hata: {e}")
            fail_count += 1
            time.sleep(2)
    
    # Özet
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Toplam sembol: {len(symbols)}")
    print(f"Başarılı: {success_count}")
    print(f"Başarısız/Boş: {fail_count}")
    print(f"Tarih aralığı: {start_date} - {end_date}")
    print(f"Klasör: {OUTPUT_DIR}")
    print("=" * 70)
