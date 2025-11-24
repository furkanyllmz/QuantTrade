"""
İş Yatırım OHLCV Data Source - BIST hisseleri için günlük OHLCV verisi (ROBUST 60sn MOD)

Bu modül İş Yatırım sitesinden BIST hisseleri için OHLCV verilerini çeker
ve QuantTrade'in standart formatına dönüştürür.
Hata durumunda 60 saniye bekleyerek IP ban riskini aşar.
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import time
import random  # Rastgelelik için

try:
    from isyatirimhisse import fetch_stock_data
except ImportError:
    fetch_stock_data = None

from quanttrade.config import ROOT_DIR


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Varsayılan OHLCV veri dizini
DEFAULT_OHLCV_DIR = ROOT_DIR / "data" / "raw" / "ohlcv"


def convert_date_format(date_str: str, from_fmt: str = "%Y-%m-%d", to_fmt: str = "%d-%m-%Y") -> str:
    dt = datetime.strptime(date_str, from_fmt)
    return dt.strftime(to_fmt)


def standardize_ohlcv_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    
    column_mapping = {
        'Tarih': 'date', 'Date': 'date', 'DATE': 'date', 'HGDG_TARIH': 'date',
        'Açılış': 'open', 'Open': 'open', 'OPEN': 'open', 'HGDG_AOF': 'open',
        'Yüksek': 'high', 'High': 'high', 'HIGH': 'high', 'HGDG_MAX': 'high',
        'Düşük': 'low', 'Low': 'low', 'LOW': 'low', 'HGDG_MIN': 'low',
        'Kapanış': 'close', 'Close': 'close', 'CLOSE': 'close', 'HGDG_KAPANIS': 'close',
        'Hacim': 'volume', 'Volume': 'volume', 'VOLUME': 'volume', 'HGDG_HACIM': 'volume',
    }
    
    rename_dict = {}
    for old_col in df.columns:
        if old_col in column_mapping:
            rename_dict[old_col] = column_mapping[old_col]
    
    df = df.rename(columns=rename_dict)
    
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        return pd.DataFrame()
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    
    if df.empty: return pd.DataFrame()
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()
    
    if df.empty: return pd.DataFrame()
    
    df['symbol'] = symbol
    df = df.sort_values('date').reset_index(drop=True)
    df = df.set_index('date')
    df = df[['open', 'high', 'low', 'close', 'volume', 'symbol']]
    
    return df


def fetch_ohlcv_from_isyatirim(
    symbols: List[str],
    start_date: str,
    end_date: str,
    output_dir: str = None,
    rate_limit_delay: float = 0.5,
) -> None:
    
    if fetch_stock_data is None:
        raise ImportError("isyatirimhisse paketi kurulu değil.")
    
    if output_dir is None:
        output_dir = DEFAULT_OHLCV_DIR
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Geçersiz tarih formatı: {e}")
    
    start_str = start_dt.strftime("%d-%m-%Y")
    end_str = end_dt.strftime("%d-%m-%Y")
    
    logger.info(f"{'='*60}")
    logger.info(f"İş Yatırım OHLCV Veri Çekme (60sn RETRY MODU)")
    logger.info(f"Semboller: {len(symbols)} adet")
    logger.info(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    errors = []
    
    # --- GÜNCELLENMİŞ RETRY AYARLARI ---
    MAX_RETRIES = 3       # 3 kere dene
    BASE_WAIT = 60        # 🛑 BURAYI DEĞİŞTİRDİK: Hata alırsa en az 60 saniye bekle!
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] {symbol} çekiliyor...")
        
        success = False
        last_error = None
        
        # --- RETRY LOOP ---
        for attempt in range(MAX_RETRIES):
            try:
                # Veri Çekme
                df = fetch_stock_data(
                    symbols=symbol,
                    start_date=start_str,
                    end_date=end_str,
                    save_to_excel=False,
                )
                
                if df is None or df.empty:
                     # "No data found" durumu
                     raise ValueError("Boş veri döndü (Olası Rate Limit).")

                df_standard = standardize_ohlcv_dataframe(df, symbol)
                
                if df_standard.empty:
                    raise ValueError("Veri standardize edilemedi.")
                
                # Kaydet
                output_file = output_path / f"{symbol}_ohlcv_isyatirim.csv"
                df_standard.to_csv(output_file, index=True, encoding='utf-8')
                logger.info(f"✓ {symbol}: OK ({len(df_standard)} satır)")
                
                success = True
                success_count += 1
                break  # Başarılıysa çık
            
            except Exception as e:
                last_error = str(e)
                
                # Hata alınca 60 saniye + rastgele 1-5 sn bekle
                # Her denemede biraz daha arttır (60s, 70s, 80s gibi)
                wait_time = BASE_WAIT + (attempt * 10) + random.uniform(1, 5)
                
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"⚠️ {symbol} Hata (Deneme {attempt+1}/{MAX_RETRIES}): {e}")
                    logger.warning(f"⏳ {wait_time:.1f}s bekleniyor (Rate Limit Soğuması)...")
                    time.sleep(wait_time) # 1 dakika bekle
                else:
                    logger.error(f"✗ {symbol}: BAŞARISIZ! (Son Hata: {e})")
        
        if not success:
            error_count += 1
            errors.append((symbol, last_error))
        
        # Başarılı olsa bile her hisse arasında 2-3 saniye bekle (Koruma)
        if i < len(symbols):
            time.sleep(rate_limit_delay + random.uniform(1.0, 3.0))
    
    logger.info(f"{'='*60}")
    logger.info(f"Tamamlandı. Başarılı: {success_count} | Hata: {error_count}")
    if errors:
        logger.info(f"Hatalı Hisseler: {', '.join([e[0] for e in errors])}")