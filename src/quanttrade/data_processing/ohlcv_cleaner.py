"""
OHLCV Data Cleaner
==================
Ham OHLCV verilerini temizler ve standart formata çevirir.

Görev:
- data/raw/ohlcv/ altındaki tüm CSV'leri okur
- Tip dönüşümleri ve validasyonları yapar
- Temiz verileri data/processed/ohlcv/ altına yazar

Kullanım:
    python ohlcv_cleaner.py
"""

import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path
from typing import Optional

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ohlcv_cleaner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_OHLCV_DIR = PROJECT_ROOT / "data" / "raw" / "ohlcv"
PROCESSED_OHLCV_DIR = PROJECT_ROOT / "data" / "processed" / "ohlcv"

# Kolon eşleştirme sözlüğü (farklı isimlendirmeleri standart isimlere map et)
COLUMN_MAPPING = {
    # Tarih
    'date': 'date',
    'Date': 'date',
    'DATE': 'date',
    'Tarih': 'date',
    'TARIH': 'date',
    'HGDG_TARIH': 'date',
    
    # Açılış
    'open': 'open',
    'Open': 'open',
    'OPEN': 'open',
    'Açılış': 'open',
    'Acilis': 'open',
    'HGDG_AOF': 'open',
    
    # Yüksek
    'high': 'high',
    'High': 'high',
    'HIGH': 'high',
    'Yüksek': 'high',
    'Yuksek': 'high',
    'HGDG_MAX': 'high',
    
    # Düşük
    'low': 'low',
    'Low': 'low',
    'LOW': 'low',
    'Düşük': 'low',
    'Dusuk': 'low',
    'HGDG_MIN': 'low',
    
    # Kapanış
    'close': 'close',
    'Close': 'close',
    'CLOSE': 'close',
    'Kapanış': 'close',
    'Kapanis': 'close',
    'HGDG_KAPANIS': 'close',
    
    # Hacim
    'volume': 'volume',
    'Volume': 'volume',
    'VOLUME': 'volume',
    'Hacim': 'volume',
    'HGDG_HACIM': 'volume',
    
    # Sembol
    'symbol': 'symbol',
    'Symbol': 'symbol',
    'SYMBOL': 'symbol',
    'ticker': 'symbol',
    'Ticker': 'symbol',
}

# Standart kolon sırası
STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'symbol']


class OHLCVCleaner:
    """OHLCV verilerini temizler ve standartlaştırır."""
    
    def __init__(self, raw_dir: Path, processed_dir: Path):
        """
        Args:
            raw_dir: Ham veri klasörü
            processed_dir: İşlenmiş veri klasörü
        """
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        
        # Çıktı klasörünü oluştur
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("="*80)
        logger.info("OHLCV DATA CLEANER")
        logger.info("="*80)
        logger.info(f"Ham veri klasörü: {self.raw_dir}")
        logger.info(f"İşlenmiş veri klasörü: {self.processed_dir}")
    
    def extract_symbol_from_filename(self, filename: str) -> Optional[str]:
        """
        Dosya adından sembol çıkarır.
        
        Args:
            filename: Dosya adı (örn: ASELS_ohlcv_isyatirim.csv)
        
        Returns:
            str: Sembol (örn: ASELS) veya None
        """
        try:
            # Dosya adını alt çizgiye göre böl
            parts = filename.split('_')
            if parts:
                symbol = parts[0].upper()
                return symbol
            return None
        except Exception as e:
            logger.warning(f"Sembol çıkarılamadı ({filename}): {e}")
            return None
    
    def standardize_columns(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        DataFrame kolonlarını standart formata çevirir.
        
        Args:
            df: Ham DataFrame
            symbol: Hisse sembolü
        
        Returns:
            pd.DataFrame: Standartlaştırılmış DataFrame
        """
        # Kolon eşleştirmesi yap
        rename_dict = {}
        for col in df.columns:
            if col in COLUMN_MAPPING:
                rename_dict[col] = COLUMN_MAPPING[col]
        
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.debug(f"{symbol}: Kolonlar yeniden adlandırıldı: {rename_dict}")
        
        # Gerekli kolonları kontrol et
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(f"{symbol}: Eksik kolonlar: {missing_cols}")
            logger.error(f"{symbol}: Mevcut kolonlar: {list(df.columns)}")
            return pd.DataFrame()
        
        # Symbol kolonu ekle veya güncelle
        df['symbol'] = symbol.upper()
        
        # Sadece standart kolonları seç
        df = df[STANDARD_COLUMNS].copy()
        
        return df
    
    def clean_data_types(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Veri tiplerini temizler ve dönüştürür.
        
        Args:
            df: DataFrame
            symbol: Hisse sembolü
        
        Returns:
            pd.DataFrame: Temizlenmiş DataFrame
        """
        # Date kolonunu datetime'a çevir
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # NaN tarihli satırları sil
        before_count = len(df)
        df = df[df['date'].notna()].copy()
        after_count = len(df)
        
        if before_count > after_count:
            logger.warning(f"{symbol}: {before_count - after_count} adet geçersiz tarih silindi")
        
        if df.empty:
            logger.error(f"{symbol}: Tarih dönüşümü sonrası tüm veriler geçersiz")
            return pd.DataFrame()
        
        # Numerik kolonları float'a çevir
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # OHLC (Open/High/Low/Close) tamamen NaN olan satırları sil
        ohlc_cols = ['open', 'high', 'low', 'close']
        before_count = len(df)
        df = df[df[ohlc_cols].notna().any(axis=1)].copy()
        after_count = len(df)
        
        if before_count > after_count:
            logger.warning(f"{symbol}: {before_count - after_count} adet OHLC tamamen boş satır silindi")
        
        if df.empty:
            logger.error(f"{symbol}: OHLC kontrolü sonrası tüm veriler geçersiz")
            return pd.DataFrame()
        
        # Volume negatifse NaN yap (ama satırı silme)
        negative_volume_count = (df['volume'] < 0).sum()
        if negative_volume_count > 0:
            logger.warning(f"{symbol}: {negative_volume_count} adet negatif volume değeri NaN yapıldı")
            df.loc[df['volume'] < 0, 'volume'] = np.nan
        
        return df
    
    def sort_and_deduplicate(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Tarihe göre sıralar ve duplike satırları temizler.
        
        Args:
            df: DataFrame
            symbol: Hisse sembolü
        
        Returns:
            pd.DataFrame: Sıralanmış ve deduplike edilmiş DataFrame
        """
        # Tarihe göre artan sırala
        df = df.sort_values('date').reset_index(drop=True)
        
        # Duplike tarihleri kontrol et
        duplicate_dates = df['date'].duplicated().sum()
        if duplicate_dates > 0:
            logger.warning(f"{symbol}: {duplicate_dates} adet duplike tarih bulundu")
            # Duplikeleri kaldır (ilk oluşumu tut)
            df = df.drop_duplicates(subset='date', keep='first')
        
        return df
    
    def validate_ohlc(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        OHLC verilerinin mantıksal tutarlılığını kontrol eder.
        
        Kontroller:
        - high >= low
        - high >= open
        - high >= close
        - low <= open
        - low <= close
        
        Args:
            df: DataFrame
            symbol: Hisse sembolü
        
        Returns:
            pd.DataFrame: Valide edilmiş DataFrame (geçersiz satırlar silinir)
        """
        before_count = len(df)
        
        # OHLC değerleri olan satırları filtrele
        ohlc_mask = df[['open', 'high', 'low', 'close']].notna().all(axis=1)
        
        # Validasyon maskeleri
        valid_mask = (
            (df['high'] >= df['low']) &
            (df['high'] >= df['open']) &
            (df['high'] >= df['close']) &
            (df['low'] <= df['open']) &
            (df['low'] <= df['close'])
        )
        
        # Sadece OHLC değerleri olan satırlarda validasyon uygula
        df = df[~ohlc_mask | valid_mask].copy()
        
        after_count = len(df)
        
        if before_count > after_count:
            logger.warning(
                f"{symbol}: {before_count - after_count} adet OHLC mantıksal hatası olan satır silindi"
            )
        
        return df
    
    def clean_file(self, file_path: Path) -> bool:
        """
        Tek bir dosyayı temizler.
        
        Args:
            file_path: Ham CSV dosyasının yolu
        
        Returns:
            bool: Başarılı ise True
        """
        filename = file_path.name
        symbol = self.extract_symbol_from_filename(filename)
        
        if not symbol:
            logger.error(f"Sembol çıkarılamadı: {filename}")
            return False
        
        logger.info(f"İşleniyor: {symbol} ({filename})")
        
        try:
            # CSV'yi oku
            df = pd.read_csv(file_path)
            
            if df.empty:
                logger.warning(f"{symbol}: Boş dosya")
                return False
            
            original_rows = len(df)
            logger.debug(f"{symbol}: {original_rows} satır okundu")
            
            # 1. Kolonları standartlaştır
            df = self.standardize_columns(df, symbol)
            if df.empty:
                return False
            
            # 2. Veri tiplerini temizle
            df = self.clean_data_types(df, symbol)
            if df.empty:
                return False
            
            # 3. Sırala ve deduplike et
            df = self.sort_and_deduplicate(df, symbol)
            if df.empty:
                return False
            
            # 4. OHLC validasyonu
            df = self.validate_ohlc(df, symbol)
            if df.empty:
                return False
            
            final_rows = len(df)
            
            # Tarih aralığını kontrol et
            date_min = df['date'].min().date()
            date_max = df['date'].max().date()
            
            # Çıktı dosyası
            output_file = self.processed_dir / f"{symbol}_ohlcv_clean.csv"
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(
                f"✓ {symbol}: {final_rows} satır kaydedildi "
                f"({original_rows - final_rows} satır temizlendi) "
                f"[{date_min} - {date_max}]"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Hata - {e}", exc_info=True)
            return False
    
    def clean_all(self) -> None:
        """Tüm OHLCV dosyalarını temizler."""
        # CSV dosyalarını listele
        csv_files = sorted(self.raw_dir.glob("*_ohlcv_*.csv"))
        
        if not csv_files:
            logger.warning(f"Ham veri klasöründe CSV dosyası bulunamadı: {self.raw_dir}")
            return
        
        logger.info(f"Toplam {len(csv_files)} dosya bulundu")
        logger.info("="*80)
        
        # İstatistikler
        success_count = 0
        error_count = 0
        errors = []
        
        # Her dosyayı işle
        for i, file_path in enumerate(csv_files, 1):
            logger.info(f"[{i}/{len(csv_files)}] {file_path.name}")
            
            if self.clean_file(file_path):
                success_count += 1
            else:
                error_count += 1
                errors.append(file_path.name)
        
        # Özet rapor
        logger.info("="*80)
        logger.info("TEMİZLEME TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"✓ Başarılı: {success_count}/{len(csv_files)}")
        logger.info(f"✗ Hata: {error_count}/{len(csv_files)}")
        
        if errors:
            logger.info("\nHatalı Dosyalar:")
            for error_file in errors:
                logger.info(f"  - {error_file}")
        
        logger.info(f"\nTemiz veriler: {self.processed_dir}")
        logger.info("="*80)


def main():
    """Ana fonksiyon"""
    logger.info("OHLCV Data Cleaner başlatılıyor...")
    
    # Klasörleri kontrol et
    if not RAW_OHLCV_DIR.exists():
        logger.error(f"Ham veri klasörü bulunamadı: {RAW_OHLCV_DIR}")
        logger.error("Lütfen önce OHLCV verilerini indirin (isyatirim_ohlcv_downloader.py)")
        return 1
    
    # Cleaner'ı oluştur ve çalıştır
    cleaner = OHLCVCleaner(raw_dir=RAW_OHLCV_DIR, processed_dir=PROCESSED_OHLCV_DIR)
    cleaner.clean_all()
    
    logger.info("\nİşlem tamamlandı!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
