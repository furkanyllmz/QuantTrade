"""
EVDS Client - TCMB EVDS API ile veri çekme işlemlerini yönetir
"""

import pandas as pd
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging

try:
    from evds import evdsAPI
except ImportError:
    # evds kurulu değilse, kullanıcıya bilgi ver
    evdsAPI = None

from quanttrade.config import (
    get_evds_api_key, 
    get_evds_settings, 
    MACRO_DATA_DIR
)


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EVDSClient:
    """
    TCMB EVDS API ile etkileşim için client sınıfı.
    
    Bu sınıf EVDS API'den makroekonomik veri çekme, işleme ve 
    kaydetme işlemlerini gerçekleştirir.
    
    Attributes:
        api_key (str): EVDS API anahtarı
        client: evdspy API client nesnesi
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        EVDSClient'ı başlatır.
        
        Args:
            api_key (str, optional): EVDS API anahtarı. 
                                     Verilmezse .env'den okunur.
                                     
        Raises:
            ImportError: evds paketi kurulu değilse
            ValueError: API anahtarı geçersizse
        
        Not:
            5 Nisan 2024 tarihinde EVDS API güncellemesi yapılmıştır.
            API anahtarı artık HTTP header içinde gönderilmektedir.
        """
        if evdsAPI is None:
            raise ImportError(
                "evds paketi kurulu değil. Lütfen 'pip install evds --upgrade' komutunu çalıştırın."
            )
        
        self.api_key = api_key or get_evds_api_key()
        
        if not self.api_key:
            raise ValueError(
                "EVDS API anahtarı bulunamadı. Lütfen .env dosyasında EVDS_API_KEY tanımlayın."
            )
        
        try:
            # evds API client'ını oluştur
            # Not: API anahtarı constructor'da parametre olarak verilir
            # 5 Nisan 2024 güncellemesi: API anahtarı artık HTTP header'da gönderiliyor
            self.client = evdsAPI(self.api_key)
            logger.info("EVDS Client başarıyla oluşturuldu")
        except Exception as e:
            logger.error(f"EVDS Client oluşturulurken hata: {e}")
            raise
    
    def fetch_series(
        self, 
        series_codes: Union[str, List[str]], 
        start_date: str,
        end_date: str,
        aggregation_types: Optional[Union[str, List[str]]] = None,
        formulas: Optional[Union[str, List[int]]] = None,
        frequency: Optional[int] = None
    ) -> pd.DataFrame:
        """
        EVDS'ten belirtilen serileri çeker.
        
        Args:
            series_codes (str or List[str]): EVDS seri kodu veya kodları listesi
                Örnek: 'TP.DK.USD.A.YTL' veya ['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL']
            start_date (str): Başlangıç tarihi (YYYY-MM-DD veya DD-MM-YYYY formatında)
            end_date (str): Bitiş tarihi (YYYY-MM-DD veya DD-MM-YYYY formatında)
            aggregation_types (str or List[str], optional): Toplululaştırma yöntemi
                Seçenekler: 'avg', 'min', 'max', 'first', 'last', 'sum'
            formulas (str or List[int], optional): Formül
                1: Yüzde Değişim, 2: Fark, 3: Yıllık Yüzde Değişim
                4: Yıllık Fark, 5: Bir Önceki Yılın Sonuna Göre Yüzde Değişim
                6: Bir Önceki Yılın Sonuna Göre Fark, 7: Hareketli Ortalama, 8: Hareketli Toplam
            frequency (int, optional): Veri frekansı
                1: Günlük, 2: İşgünü, 3: Haftalık, 4: Ayda 2 Kez
                5: Aylık, 6: 3 Aylık, 7: 6 Aylık, 8: Yıllık
        
        Returns:
            pd.DataFrame: Tarih index'li DataFrame. Kolonlar seri kodlarıdır.
        
        Raises:
            ValueError: Geçersiz tarih formatı veya seri kodu
            
        Not:
            EVDS resmi paketi get_data() fonksiyonu DataFrame döndürür.
            Ham JSON verisine erişmek için client.data kullanılabilir.
        """
        # Tek bir string ise liste haline getir
        if isinstance(series_codes, str):
            series_codes = [series_codes]
        
        # Boş liste kontrolü
        if not series_codes or all(not code for code in series_codes):
            logger.warning("Çekilecek seri kodu bulunamadı")
            return pd.DataFrame()
        
        # Boş seri kodlarını filtrele
        series_codes = [code for code in series_codes if code]
        
        # Tarih formatını EVDS API için dönüştür (DD-MM-YYYY)
        try:
            # İki formatı da destekle
            if "-" in start_date and len(start_date.split("-")[0]) == 4:
                # YYYY-MM-DD formatı
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                evds_start = start_dt.strftime("%d-%m-%Y")
                evds_end = end_dt.strftime("%d-%m-%Y")
            else:
                # DD-MM-YYYY formatı (zaten EVDS formatında)
                evds_start = start_date
                evds_end = end_date
        except ValueError as e:
            raise ValueError(
                f"Geçersiz tarih formatı. YYYY-MM-DD veya DD-MM-YYYY formatında olmalı. Hata: {e}"
            )
        
        logger.info(
            f"EVDS'ten {len(series_codes)} seri çekiliyor: "
            f"{', '.join(series_codes)} ({evds_start} - {evds_end})"
        )
        
        try:
            # EVDS API'den veri çek
            # Resmi evds paketi kullanımı:
            # get_data(series, startdate, enddate, aggregation_types, formulas, frequency)
            # NOT: Opsiyonel parametreler None yerine boş string ('') almalı
            df = self.client.get_data(
                series_codes,
                startdate=evds_start,
                enddate=evds_end,
                aggregation_types=aggregation_types if aggregation_types else '',
                formulas=formulas if formulas else '',
                frequency=frequency if frequency else ''
            )
            
            if df is None or df.empty:
                logger.warning("EVDS'ten veri çekilemedi veya sonuç boş")
                return pd.DataFrame()
            
            # Tarih sütununu düzenle
            # evds paketi genellikle 'Tarih' sütunu döndürür
            if 'Tarih' in df.columns:
                df = df.rename(columns={'Tarih': 'date'})
                df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
                df = df.set_index('date')
                df = df.sort_index()
            
            # Numerik olmayan değerleri temizle
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Başarıyla {len(df)} satır veri çekildi")
            return df
            
        except Exception as e:
            logger.error(f"EVDS'ten veri çekilirken hata: {e}")
            raise
    
    def fetch_and_save_default_macro(
        self,
        output_filename: str = "evds_macro_daily.csv"
    ) -> str:
        """
        settings.toml'da tanımlanan varsayılan makro serileri çeker ve kaydeder.
        
        Bu metod:
        1. settings.toml'dan EVDS ayarlarını okur
        2. Tanımlanan tüm serileri çeker
        3. Tek bir DataFrame'de birleştirir
        4. data/raw/macro/ dizinine CSV olarak kaydeder
        
        Args:
            output_filename (str): Çıktı dosya adı. Varsayılan: "evds_macro_daily.csv"
        
        Returns:
            str: Kaydedilen dosyanın tam yolu
            
        Raises:
            ValueError: EVDS ayarları eksikse
        """
        logger.info("Varsayılan makro veriler çekiliyor...")
        
        # EVDS ayarlarını oku
        evds_settings = get_evds_settings()
        
        if not evds_settings:
            raise ValueError(
                "EVDS ayarları config/settings.toml dosyasında bulunamadı"
            )
        
        start_date = evds_settings.get("start_date")
        end_date = evds_settings.get("end_date")
        series_dict = evds_settings.get("series", {})
        
        if not start_date or not end_date:
            raise ValueError(
                "start_date ve end_date config/settings.toml dosyasında tanımlanmalı"
            )
        
        if not series_dict:
            raise ValueError(
                "Çekilecek seri bulunamadı. config/settings.toml içinde [evds.series] "
                "bölümünü kontrol edin"
            )
        
        # Seri kodlarını ve isimlerini ayır
        series_mapping = {}  # friendly_name -> evds_code
        for friendly_name, evds_code in series_dict.items():
            if evds_code:  # Boş olmayan kodları al
                series_mapping[friendly_name] = evds_code
        
        if not series_mapping:
            logger.warning("Çekilecek geçerli seri kodu bulunamadı")
            return ""
        
        logger.info(f"Toplam {len(series_mapping)} seri çekilecek")
        
        # Tüm serileri çek
        all_series_codes = list(series_mapping.values())
        df = self.fetch_series(
            series_codes=all_series_codes,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            logger.warning("Hiç veri çekilemedi")
            return ""
        
        # Kolon isimlerini düzenle (EVDS kod -> friendly name)
        # evdspy genellikle seri kodlarını TP_DK_USD_A_YTL gibi underscore'lu döndürür
        reverse_mapping = {code: name for name, code in series_mapping.items()}
        
        # Mevcut kolonları kontrol et ve yeniden adlandır
        rename_dict = {}
        for col in df.columns:
            # EVDS kodu ile eşleşme ara
            for evds_code, friendly_name in reverse_mapping.items():
                # Kolon adı EVDS kodu ile eşleşiyorsa
                if col == evds_code or evds_code in col:
                    rename_dict[col] = friendly_name
                    break
        
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.info(f"Kolonlar yeniden adlandırıldı: {list(rename_dict.values())}")
        
        # Dosya yolunu oluştur
        output_path = MACRO_DATA_DIR / output_filename
        
        # CSV olarak kaydet
        df.to_csv(output_path, encoding="utf-8")
        logger.info(f"Veri başarıyla kaydedildi: {output_path}")
        logger.info(f"Toplam {len(df)} satır, {len(df.columns)} kolon")
        
        # İlk birkaç satırı göster
        logger.info(f"\nİlk 3 satır:\n{df.head(3)}")
        
        return str(output_path)
