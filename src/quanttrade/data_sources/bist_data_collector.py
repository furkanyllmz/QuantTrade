"""
BIST Hisse Veri Toplama Pipeline
isyatirimhisse kütüphanesi kullanarak BIST'teki tüm hisseler için kapsamlı veri toplar.

Gerekli kurulum:
pip install isyatirimhisse pandas numpy

Kullanım:
python bist_data_collector.py
"""

import pandas as pd
import numpy as np
import logging
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

try:
    from isyatirimhisse import fetch_stock_data, fetch_financials
except ImportError:
    print("HATA: isyatirimhisse kütüphanesi bulunamadı!")
    print("Lütfen şu komutu çalıştırın: pip install isyatirimhisse")
    exit(1)


# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bist_data_collector.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Popüler BIST hisseleri listesi (Manuel)
BIST_SYMBOLS = [
    'AKBNK', 'AKSEN', 'ALARK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL',
    'EKGYO', 'ENKAI', 'EREGL', 'FROTO', 'GARAN', 'GUBRF', 'HEKTS',
    'ISCTR', 'KCHOL', 'KOZAL', 'KOZAA', 'KRDMD', 'LOGO', 'PETKM',
    'PGSUS', 'SAHOL', 'SASA', 'SISE', 'TAVHL', 'TCELL', 'THYAO',
    'TKFEN', 'TOASO', 'TTKOM', 'TUPRS', 'VAKBN', 'YKBNK', 'VESTL',
    'SOKM', 'MGROS', 'HALKB', 'TTRAK', 'KONTR', 'ULKER', 'AEFES',
    'CCOLA', 'OTKAR', 'TOASO', 'ANACM', 'AYGAZ', 'BRSAN', 'BRYAT',
    'CEMAS', 'DOAS', 'DYOBY', 'EGEEN', 'ENJSA', 'GENIL', 'GOODY',
    'IHLGM', 'IHLAS', 'INDES', 'IPEKE', 'ITTFH', 'KARSN', 'KLMSN',
    'KONKA', 'KONYA', 'KORDS', 'KUTPO', 'MAVI', 'MPARK', 'NTHOL',
    'ODAS', 'OYAKC', 'PARSN', 'PENGD', 'PRKME', 'SANKO', 'SARKY',
    'SELEC', 'SILVR', 'TBORG', 'TKNSA', 'TMSN', 'TRCAS', 'TURSG',
    'ULUUN', 'YATAS', 'YEOTK', 'ZOREN'
]


class BISTDataCollector:
    """
    BIST hisse senetleri için kapsamlı veri toplama sistemi.
    """
    
    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Collector'ı başlat
        
        Args:
            symbols: Hisse sembolleri listesi (opsiyonel, yoksa BIST_SYMBOLS kullanılır)
        """
        logger.info("="*80)
        logger.info("BIST Veri Toplama Pipeline Başlatılıyor")
        logger.info("="*80)
        
        self.symbols = symbols if symbols else BIST_SYMBOLS
        self.results = []
        
        logger.info(f"Toplam {len(self.symbols)} hisse işlenecek")
    
    def get_financial_data(self, symbol: str) -> Dict[str, Any]:
        """
        Bir hisse için finansal verileri getir.
        
        Args:
            symbol: Hisse sembolü
            
        Returns:
            Dict: Finansal veriler
        """
        try:
            current_year = datetime.now().year
            start_year = current_year - 3  # Son 4 yıl
            
            # Önce financial_group='1' dene (sanayi şirketleri)
            financials = None
            try:
                financials = fetch_financials(
                    symbols=symbol,
                    start_year=start_year,
                    end_year=current_year,
                    exchange='TRY',
                    financial_group='1'
                )
            except Exception as e:
                logger.debug(f"{symbol}: financial_group=1 hatası: {e}")
            
            # Eğer boşsa financial_group='2' dene (bankalar)
            if financials is None or (hasattr(financials, 'empty') and financials.empty):
                try:
                    financials = fetch_financials(
                        symbols=symbol,
                        start_year=start_year,
                        end_year=current_year,
                        exchange='TRY',
                        financial_group='2'
                    )
                except Exception as e:
                    logger.debug(f"{symbol}: financial_group=2 hatası: {e}")
            
            # Hala boşsa vazgeç
            if financials is None or (hasattr(financials, 'empty') and financials.empty):
                logger.warning(f"{symbol}: Finansal veri bulunamadı")
                return {}
            
            # Format: Satırlar = kalemler, Sütunlar = dönemler (2020/3, 2020/6, ...)
            # FINANCIAL_ITEM_NAME_TR sütununda Türkçe kalem adları var
            
            result = {
                'period': None,
                'net_profit': None,
                'sales': None,
                'total_debt': None,
                'total_equity': None,
            }
            
            # Dönem sütunlarını bul (2020/3, 2020/6 formatında)
            period_cols = [c for c in financials.columns if isinstance(c, str) and '/' in c]
            
            if not period_cols:
                logger.warning(f"{symbol}: Dönem sütunları bulunamadı")
                return {}
            
            # En son dönemi al
            latest_period = sorted(period_cols, key=lambda x: tuple(map(int, x.split('/'))))[-1]
            result['period'] = latest_period
            
            logger.debug(f"{symbol}: En son dönem: {latest_period}")
            
            # FINANCIAL_ITEM_NAME_TR veya FINANCIAL_ITEM_NAME_EN sütununu bul
            item_name_col = None
            for col in ['FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN']:
                if col in financials.columns:
                    item_name_col = col
                    break
            
            if item_name_col is None:
                logger.warning(f"{symbol}: Kalem adı sütunu bulunamadı")
                return result
            
            # DataFrame'i set_index yap
            df = financials.set_index(item_name_col)
            
            # Kalem arama fonksiyonu
            def find_item_value(aliases: List[str]) -> Optional[float]:
                """Verilen aliaslardan birini içeren satırı bul ve değeri döndür"""
                for alias in aliases:
                    for idx in df.index:
                        if pd.notna(idx) and alias.upper() in str(idx).upper():
                            try:
                                val = df.loc[idx, latest_period]
                                numeric_val = self._safe_numeric(val)
                                if numeric_val is not None:
                                    logger.debug(f"{symbol}: {alias} bulundu: {idx} = {numeric_val}")
                                    return numeric_val
                            except Exception as e:
                                logger.debug(f"{symbol}: {alias} parse hatası: {e}")
                                continue
                return None
            
            # Net Kar (Net Dönem Karı/Zararı)
            result['net_profit'] = find_item_value([
                'NET DÖNEM KARI',
                'NET DÖNEM ZARARI', 
                'NET KAR',
                'NET PROFIT',
                'NET INCOME',
                'DÖNEM KARI',
                'DÖNEM NET KARI'
            ])
            
            # Satışlar (Net Satışlar, Hasılat) - Bankalar için Faiz Geliri de ekle
            result['sales'] = find_item_value([
                'NET SATIŞLAR',
                'SATIŞLAR',
                'HASILAT',
                'SALES',
                'REVENUE',
                'NET SALES',
                'BRÜT SATIŞLAR',
                'NET FAİZ GELİRİ',  # Bankalar için
                'FAİZ GELİRİ',
                'TOPLAM GELİRLER',
                'TOPLAM FAİZ GELİRİ',
                'NET INTEREST INCOME'
            ])
            
            # Toplam Borç (Kısa + Uzun Vadeli Borçlanmalar)
            result['total_debt'] = find_item_value([
                'TOPLAM BORÇLAR',
                'FINANSAL BORÇLAR',
                'TOPLAM YÜKÜMLÜLÜKLER',
                'KISA VADELİ BORÇLAR',
                'UZUN VADELİ BORÇLAR',
                'TOTAL DEBT',
                'TOTAL LIABILITIES',
                'BORÇLAR TOPLAMI'
            ])
            
            # Özkaynak
            result['total_equity'] = find_item_value([
                'ÖZKAYNAKLAR',
                'ANA ORTAKLIK PAYINA AİT ÖZKAYNAKLAR',
                'EQUITY',
                'SHAREHOLDERS EQUITY',
                'ÖZKAYNAK TOPLAMI',
                'TOPLAM ÖZKAYNAKLAR'
            ])
            
            logger.debug(f"{symbol}: Finansal veriler parse edildi: {result}")
            return result
            
        except Exception as e:
            logger.warning(f"{symbol}: Finansal veri hatası - {e}")
            return {}
    
    def get_price_data(self, symbol: str) -> Dict[str, Any]:
        """
        Bir hisse için fiyat verilerini ve getiri hesaplamalarını getir.
        
        Args:
            symbol: Hisse sembolü
            
        Returns:
            Dict: Fiyat getirileri
        """
        try:
            # Son 5 yıllık veri al
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5*365)
            
            # Tarih formatını DD-MM-YYYY'ye çevir
            start_str = start_date.strftime("%d-%m-%Y")
            end_str = end_date.strftime("%d-%m-%Y")
            
            prices = fetch_stock_data(
                symbols=symbol,
                start_date=start_str,
                end_date=end_str
            )
            
            if prices is None or prices.empty:
                logger.warning(f"{symbol}: Fiyat verisi bulunamadı")
                return {
                    'return_1y': None,
                    'return_3y': None,
                    'return_5y': None,
                    'current_price': None
                }
            
            # Tarih sütununu bul ve parse et
            date_col = None
            for col in prices.columns:
                if 'TARIH' in str(col).upper() or 'DATE' in str(col).upper():
                    date_col = col
                    break
            
            if date_col:
                prices[date_col] = pd.to_datetime(prices[date_col], errors='coerce')
                prices = prices.sort_values(by=date_col)
                prices = prices.set_index(date_col)
            
            # Kapanış fiyatı sütununu bul
            close_col = None
            for col in prices.columns:
                col_upper = str(col).upper()
                if 'KAPANIS' in col_upper or 'CLOSE' in col_upper:
                    close_col = col
                    break
            
            if close_col is None:
                logger.warning(f"{symbol}: Kapanış fiyatı sütunu bulunamadı")
                return {
                    'return_1y': None,
                    'return_3y': None,
                    'return_5y': None,
                    'current_price': None
                }
            
            # Güncel fiyat
            current_price = self._safe_numeric(prices[close_col].iloc[-1])
            
            # Getiri hesaplamaları
            return_1y = self._calculate_return(prices, close_col, years=1)
            return_3y = self._calculate_return(prices, close_col, years=3)
            return_5y = self._calculate_return(prices, close_col, years=5)
            
            result = {
                'return_1y': return_1y,
                'return_3y': return_3y,
                'return_5y': return_5y,
                'current_price': current_price
            }
            
            logger.debug(f"{symbol}: Fiyat verileri alındı")
            return result
            
        except Exception as e:
            logger.warning(f"{symbol}: Fiyat verisi hatası - {e}")
            return {
                'return_1y': None,
                'return_3y': None,
                'return_5y': None,
                'current_price': None
            }
    
    def _calculate_return(self, prices: pd.DataFrame, close_col: str, years: int) -> Optional[float]:
        """
        Belirli bir süre için getiri hesapla.
        
        Args:
            prices: Fiyat dataframe'i
            close_col: Kapanış fiyatı sütun adı
            years: Kaç yıl geriye bakılacak
            
        Returns:
            float: Yüzde getiri veya None
        """
        try:
            if len(prices) < 2:
                return None
            
            current_date = prices.index[-1]
            target_date = current_date - pd.DateOffset(years=years)
            
            # Hedef tarihe en yakın veriyi bul
            past_prices = prices[prices.index <= target_date]
            
            if past_prices.empty:
                return None
            
            past_price = self._safe_numeric(past_prices[close_col].iloc[-1])
            current_price = self._safe_numeric(prices[close_col].iloc[-1])
            
            if past_price is None or current_price is None or past_price == 0:
                return None
            
            return_pct = ((current_price - past_price) / past_price) * 100
            return round(return_pct, 2)
            
        except Exception as e:
            logger.debug(f"Getiri hesaplama hatası ({years}y): {e}")
            return None
    
    def _safe_numeric(self, value: Any) -> Optional[float]:
        """
        Bir değeri güvenli şekilde numeric'e çevir.
        
        Args:
            value: Çevrilecek değer
            
        Returns:
            float veya None
        """
        try:
            if value is None or pd.isna(value):
                return None
            
            # String ise temizle
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '').strip()
                if value == '' or value == '-':
                    return None
            
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def collect_stock_data(self, symbol: str) -> Dict[str, Any]:
        """
        Bir hisse için tüm verileri topla.
        
        Args:
            symbol: Hisse sembolü
            
        Returns:
            Dict: Tüm veriler
        """
        logger.info(f"İşleniyor: {symbol}")
        
        # Başlangıç verileri
        stock_data = {
            'ticker': symbol,
            'period': None,
            'net_profit': None,
            'sales': None,
            'total_debt': None,
            'total_equity': None,
            'return_1y': None,
            'return_3y': None,
            'return_5y': None,
            'current_price': None
        }
        
        try:
            # Finansal verileri al
            financial_data = self.get_financial_data(symbol)
            stock_data.update(financial_data)
            
            # Rate limiting
            time.sleep(1)
            
            # Fiyat verileri al
            price_data = self.get_price_data(symbol)
            stock_data.update(price_data)
            
            logger.info(f"✓ {symbol}: Veriler toplandı")
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Genel hata - {e}")
        
        return stock_data
    
    def run(self, output_file: str = "bist_isyatirimhisse_full_dataset.csv"):
        """
        Tüm pipeline'ı çalıştır.
        
        Args:
            output_file: Çıktı dosyası adı
        """
        start_time = time.time()
        
        logger.info(f"Toplam {len(self.symbols)} hisse için veri toplanacak")
        logger.info("="*80)
        
        # Her hisse için veri topla
        for idx, symbol in enumerate(self.symbols, 1):
            logger.info(f"[{idx}/{len(self.symbols)}] {symbol} işleniyor...")
            
            stock_data = self.collect_stock_data(symbol)
            self.results.append(stock_data)
            
            # Her 10 hissede bir ilerleme raporu
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = (len(self.symbols) - idx) * avg_time
                logger.info(f"İlerleme: {idx}/{len(self.symbols)} - Kalan süre: ~{remaining/60:.1f} dakika")
            
            # Rate limiting - API'yi yormamak için
            time.sleep(2)
        
        # DataFrame oluştur
        df = pd.DataFrame(self.results)
        
        # Çıktı dizini
        output_dir = "/Users/furkanyilmaz/Desktop/QuantTrade/data/raw/stocks"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_file)
        
        # CSV'ye kaydet
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        elapsed_time = time.time() - start_time
        
        # Özet rapor
        logger.info("="*80)
        logger.info("İŞLEM TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"Toplam hisse: {len(self.symbols)}")
        logger.info(f"Başarılı: {len(df)}")
        logger.info(f"Toplam süre: {elapsed_time/60:.2f} dakika")
        logger.info(f"Çıktı dosyası: {output_path}")
        logger.info("="*80)
        
        # Özet istatistikler
        logger.info("\nVERİ ÖZETİ:")
        logger.info(f"- Finansal verisi olan: {df['net_profit'].notna().sum()} hisse")
        logger.info(f"- Fiyat verisi olan: {df['current_price'].notna().sum()} hisse")
        logger.info(f"- 1Y getiri verisi olan: {df['return_1y'].notna().sum()} hisse")
        logger.info(f"- 3Y getiri verisi olan: {df['return_3y'].notna().sum()} hisse")
        logger.info(f"- 5Y getiri verisi olan: {df['return_5y'].notna().sum()} hisse")
        logger.info("="*80)
        
        # İlk birkaç satırı göster
        logger.info("\nÖRNEK VERİLER:")
        logger.info(f"\n{df.head(10).to_string()}")


def main():
    """Ana fonksiyon"""
    logger.info("BIST Veri Toplama Pipeline başlatılıyor...")
    
    # Collector'ı başlat ve çalıştır
    collector = BISTDataCollector()
    collector.run()
    
    logger.info("\nİşlem tamamlandı!")


if __name__ == "__main__":
    main()
