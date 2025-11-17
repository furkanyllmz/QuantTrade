"""
EVDS Client test scripti
TCMB resmi evds paketi ile temel test
"""

import sys
from pathlib import Path

# Proje kök dizinini path'e ekle
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from quanttrade.data_sources.evds_client import EVDSClient
import pandas as pd

def test_basic_fetch():
    """Temel veri çekme testi"""
    print("=" * 60)
    print("EVDS Client Test - Temel Veri Çekme")
    print("=" * 60)
    
    try:
        # Client oluştur
        print("\n1. EVDS Client oluşturuluyor...")
        client = EVDSClient()
        print("✓ Client başarıyla oluşturuldu")
        
        # Tek bir seri çek (USD kurları)
        print("\n2. USD alış kurları çekiliyor (01-01-2024 - 01-02-2024)...")
        df = client.fetch_series(
            series_codes='TP.DK.USD.A.YTL',
            start_date='2024-01-01',
            end_date='2024-02-01'
        )
        
        if not df.empty:
            print(f"✓ Veri başarıyla çekildi: {len(df)} satır")
            print("\nİlk 5 satır:")
            print(df.head())
            print("\nSon 5 satır:")
            print(df.tail())
        else:
            print("✗ Veri çekilemedi (boş DataFrame)")
            
    except Exception as e:
        print(f"✗ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()

def test_multiple_series():
    """Çoklu seri çekme testi"""
    print("\n" + "=" * 60)
    print("EVDS Client Test - Çoklu Seri Çekme")
    print("=" * 60)
    
    try:
        client = EVDSClient()
        
        # Birden fazla seri çek (USD ve EUR kurları)
        print("\n1. USD ve EUR alış kurları çekiliyor...")
        series_codes = ['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL']
        df = client.fetch_series(
            series_codes=series_codes,
            start_date='2024-01-01',
            end_date='2024-01-15'
        )
        
        if not df.empty:
            print(f"✓ Veri başarıyla çekildi: {len(df)} satır, {len(df.columns)} kolon")
            print("\nKolonlar:", df.columns.tolist())
            print("\nİlk 5 satır:")
            print(df.head())
        else:
            print("✗ Veri çekilemedi (boş DataFrame)")
            
    except Exception as e:
        print(f"✗ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()

def test_with_parameters():
    """Parametre ile çekme testi (frequency, formulas)"""
    print("\n" + "=" * 60)
    print("EVDS Client Test - Parametreli Veri Çekme")
    print("=" * 60)
    
    try:
        client = EVDSClient()
        
        # Aylık frekans ile veri çek
        print("\n1. USD kurları (aylık frekans) çekiliyor...")
        df = client.fetch_series(
            series_codes='TP.DK.USD.A.YTL',
            start_date='2023-01-01',
            end_date='2024-01-01',
            frequency=5,  # 5 = Aylık
            aggregation_types='avg'  # Ortalama
        )
        
        if not df.empty:
            print(f"✓ Veri başarıyla çekildi: {len(df)} satır")
            print("\nVeriler:")
            print(df)
        else:
            print("✗ Veri çekilemedi (boş DataFrame)")
            
    except Exception as e:
        print(f"✗ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()

def test_raw_api():
    """Ham API kullanım testi (dokümandaki örnek)"""
    print("\n" + "=" * 60)
    print("EVDS Client Test - Ham API Kullanımı")
    print("=" * 60)
    
    try:
        from evds import evdsAPI
        import os
        from dotenv import load_dotenv
        
        # .env dosyasını yükle
        load_dotenv()
        api_key = os.getenv('EVDS_API_KEY')
        
        print(f"\n1. API Key: {api_key[:5]}..." if api_key else "API Key bulunamadı")
        
        # Dokümandaki örnek
        print("\n2. Dokümandaki örnek (01-01-2019 - 01-01-2020 USD/EUR kurları)...")
        evds = evdsAPI(api_key)
        df = evds.get_data(
            ['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL'],
            startdate="01-01-2019",
            enddate="01-01-2020"
        )
        
        if df is not None and not df.empty:
            print(f"✓ Veri başarıyla çekildi: {len(df)} satır, {len(df.columns)} kolon")
            print("\nKolonlar:", df.columns.tolist())
            print("\nİlk 3 satır:")
            print(df.head(3))
            print("\nSon 3 satır:")
            print(df.tail(3))
            
            # Ham JSON verisine erişim
            print("\n3. Ham JSON verisi (ilk kayıt):")
            if hasattr(evds, 'data') and evds.data:
                import json
                print(json.dumps(evds.data[:1], indent=2, ensure_ascii=False))
        else:
            print("✗ Veri çekilemedi")
            
    except Exception as e:
        print(f"✗ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Tüm testleri çalıştır
    test_basic_fetch()
    test_multiple_series()
    test_with_parameters()
    test_raw_api()
    
    print("\n" + "=" * 60)
    print("Test tamamlandı!")
    print("=" * 60)
