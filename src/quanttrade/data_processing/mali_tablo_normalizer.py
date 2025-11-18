"""
Mali Tablo Normalizasyon Agent'ı
==================================
Ham finansal tablo verilerini temizler ve uzun formata (long format) normalleştirir.

Görev:
- data/raw/mali_tablo/ altındaki her hisse CSV'sini okur
- Dönem kolonlarını satırlara melt eder (wide → long)
- Veri tiplerini düzeltir ve temizler
- Normalize edilmiş verileri data/processed/mali_tablo/ altına yazar

Kullanım:
    python mali_tablo_normalizer.py
"""

import pandas as pd
import numpy as np
import logging
import sys
import re
from pathlib import Path
from typing import List, Optional

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mali_tablo_normalizer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_MALI_DIR = PROJECT_ROOT / "data" / "raw" / "mali_tablo"
PROCESSED_MALI_DIR = PROJECT_ROOT / "data" / "processed" / "mali_tablo"

# Standart kolon isimleri
STANDARD_COLUMNS = ['symbol', 'period', 'item_code', 'item_name_tr', 'item_name_en', 'value']


class MaliTabloNormalizer:
    """Finansal tablo verilerini normalize eder."""
    
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
        logger.info("MALİ TABLO NORMALİZASYON AGENT'I")
        logger.info("="*80)
        logger.info(f"Ham veri klasörü: {self.raw_dir}")
        logger.info(f"İşlenmiş veri klasörü: {self.processed_dir}")
    
    def extract_symbol_from_filename(self, filename: str) -> Optional[str]:
        """
        Dosya adından sembol çıkarır.
        
        Args:
            filename: Dosya adı (örn: ASELS.csv)
        
        Returns:
            str: Sembol (örn: ASELS) veya None
        """
        try:
            # .csv uzantısını kaldır
            symbol = filename.replace('.csv', '').upper()
            return symbol
        except Exception as e:
            logger.warning(f"Sembol çıkarılamadı ({filename}): {e}")
            return None
    
    def identify_period_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Dönem kolonlarını tespit eder (YYYY/Q formatında).
        
        Args:
            df: DataFrame
        
        Returns:
            List[str]: Dönem kolon isimleri
        """
        # YYYY/Q formatı (örn: 2022/3, 2024/12)
        period_pattern = re.compile(r'^\d{4}/\d{1,2}$')
        
        period_cols = []
        for col in df.columns:
            if period_pattern.match(str(col)):
                period_cols.append(col)
        
        # Dönem kolonlarını kronolojik sırala
        period_cols = sorted(period_cols, key=lambda x: (int(x.split('/')[0]), int(x.split('/')[1])))
        
        return period_cols
    
    def clean_numeric_value(self, value) -> Optional[float]:
        """
        Numeric değeri temizler.
        
        Args:
            value: Ham değer (string veya numeric)
        
        Returns:
            float veya None
        """
        if pd.isna(value) or value is None:
            return None
        
        # Zaten numeric ise
        if isinstance(value, (int, float)):
            return float(value)
        
        # String ise temizle
        if isinstance(value, str):
            # Boşlukları, virgülleri, tire, parantez vb. temizle
            value = value.strip()
            value = value.replace(',', '')
            value = value.replace(' ', '')
            value = value.replace('(', '-')
            value = value.replace(')', '')
            
            # Boş string kontrolü
            if value == '' or value == '-' or value == 'N/A':
                return None
            
            try:
                return float(value)
            except ValueError:
                return None
        
        return None
    
    def normalize_file(self, file_path: Path) -> bool:
        """
        Tek bir finansal tablo dosyasını normalize eder.
        
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
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            if df.empty:
                logger.warning(f"{symbol}: Boş dosya")
                return False
            
            original_rows = len(df)
            logger.debug(f"{symbol}: {original_rows} satır (kalem) okundu")
            
            # Gerekli kolonları kontrol et
            required_cols = ['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.error(f"{symbol}: Eksik kolonlar: {missing_cols}")
                return False
            
            # Dönem kolonlarını tespit et
            period_cols = self.identify_period_columns(df)
            
            if not period_cols:
                logger.error(f"{symbol}: Dönem kolonu bulunamadı")
                return False
            
            logger.debug(f"{symbol}: {len(period_cols)} dönem bulundu: {period_cols[:3]}...{period_cols[-3:]}")
            
            # SYMBOL kolonunu ekle/güncelle (eğer yoksa)
            if 'SYMBOL' not in df.columns:
                df['SYMBOL'] = symbol
            else:
                df['SYMBOL'] = df['SYMBOL'].fillna(symbol)
            
            # Veri tiplerini düzelt
            df['FINANCIAL_ITEM_CODE'] = df['FINANCIAL_ITEM_CODE'].astype(str)
            df['FINANCIAL_ITEM_NAME_TR'] = df['FINANCIAL_ITEM_NAME_TR'].astype(str)
            df['FINANCIAL_ITEM_NAME_EN'] = df['FINANCIAL_ITEM_NAME_EN'].astype(str)
            df['SYMBOL'] = df['SYMBOL'].astype(str).str.upper()
            
            # Dönem kolonlarını numeric'e çevir
            for period_col in period_cols:
                df[period_col] = df[period_col].apply(self.clean_numeric_value)
            
            # Wide format'tan long format'a çevir (melt)
            # id_vars: sabit kolonlar
            # value_vars: dönem kolonları
            # var_name: dönem kolonunun adı → 'period'
            # value_name: değer kolonunun adı → 'value'
            
            df_long = pd.melt(
                df,
                id_vars=['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL'],
                value_vars=period_cols,
                var_name='period',
                value_name='value'
            )
            
            # Kolon adlarını standartlaştır
            df_long = df_long.rename(columns={
                'SYMBOL': 'symbol',
                'FINANCIAL_ITEM_CODE': 'item_code',
                'FINANCIAL_ITEM_NAME_TR': 'item_name_tr',
                'FINANCIAL_ITEM_NAME_EN': 'item_name_en',
            })
            
            # NaN değerleri filtrele
            before_filter = len(df_long)
            df_long = df_long[df_long['value'].notna()].copy()
            after_filter = len(df_long)
            
            if before_filter > after_filter:
                logger.debug(f"{symbol}: {before_filter - after_filter} adet NaN değer silindi")
            
            if df_long.empty:
                logger.warning(f"{symbol}: Tüm değerler NaN")
                return False
            
            # Kolon sırasını düzenle
            df_long = df_long[STANDARD_COLUMNS]
            
            # Dönem'e göre sırala
            df_long = df_long.sort_values(by=['period', 'item_code']).reset_index(drop=True)
            
            # İstatistikler
            unique_periods = df_long['period'].nunique()
            unique_items = df_long['item_code'].nunique()
            final_rows = len(df_long)
            
            # Çıktı dosyası
            output_file = self.processed_dir / f"{symbol}_financials_long.csv"
            df_long.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(
                f"✓ {symbol}: {final_rows} satır kaydedildi "
                f"({unique_items} kalem × {unique_periods} dönem)"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Hata - {e}", exc_info=True)
            return False
    
    def normalize_all(self) -> None:
        """Tüm mali tablo dosyalarını normalize eder."""
        # CSV dosyalarını listele
        csv_files = sorted(self.raw_dir.glob("*.csv"))
        
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
            
            if self.normalize_file(file_path):
                success_count += 1
            else:
                error_count += 1
                errors.append(file_path.name)
        
        # Özet rapor
        logger.info("="*80)
        logger.info("NORMALİZASYON TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"✓ Başarılı: {success_count}/{len(csv_files)}")
        logger.info(f"✗ Hata: {error_count}/{len(csv_files)}")
        
        if errors:
            logger.info("\nHatalı Dosyalar:")
            for error_file in errors:
                logger.info(f"  - {error_file}")
        
        logger.info(f"\nNormalize veriler: {self.processed_dir}")
        logger.info("="*80)


def main():
    """Ana fonksiyon"""
    logger.info("Mali Tablo Normalizasyon Agent'ı başlatılıyor...")
    
    # Klasörleri kontrol et
    if not RAW_MALI_DIR.exists():
        logger.error(f"Ham veri klasörü bulunamadı: {RAW_MALI_DIR}")
        logger.error("Lütfen önce mali tablo verilerini indirin (mali_tablo.py)")
        return 1
    
    # Normalizer'ı oluştur ve çalıştır
    normalizer = MaliTabloNormalizer(raw_dir=RAW_MALI_DIR, processed_dir=PROCESSED_MALI_DIR)
    normalizer.normalize_all()
    
    logger.info("\nİşlem tamamlandı!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
