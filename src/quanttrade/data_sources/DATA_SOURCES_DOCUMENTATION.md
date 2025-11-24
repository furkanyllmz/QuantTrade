# QuantTrade Data Sources Dokumentasyonu

Bu dokümanda `data_sources` klasöründeki her bir script'in detaylı açıklaması, çalıştırılma şekli, input/output yolları ve bağımlılıkları yer almaktadır.

---

## 📋 İçindekiler

1. [BIST Data Collector (bist_data_collector_all_periods.py)](#1-bist-data-collector-all-periodsscript)
2. [EVDS Client (evds_client.py)](#2-evds-client--macro_downloaderscript)
3. [Makro Downloader (macro_downloader.py)](#2-evds-client--macro_downloaderscript)
4. [İş Yatırım OHLCV (isyatirim_ohlcv.py ve isyatirim_ohlcv_downloader.py)](#3-isyatirim-ohlcv-isyatirim_ohlcvpy-ve-isyatirim_ohlcv_downloaderscript)
5. [Mali Tablo (mali_tablo.py)](#4-mali-tablo-mali_tabloscript)
6. [KAP Announcement Scraper (kap_announcement_scraper.py)](#5-kap-announcement-scraper-kap_announcement_scraperscript)
7. [Split Ratio (split_ratio.py)](#6-split-ratio-split_ratioscript)
8. [Temettü Scraper (temettü_scraper.py)](#7-temettü-scraper-temettü_scraperscript)
9. [Parquet to CSV (parquet_to_csv.py)](#8-parquet-to-csv-parquet_to_csvscript)
10. [Parquet to XLSX (parquet_to_xlsx.py)](#9-parquet-to-xlsx-parquet_to_xlsxscript)

---

## 1. BIST Data Collector (bist_data_collector_all_periods.py)

### Açıklama
BIST hisse senetlerinin **TÜM dönemlerin finansal verilerini** çeken ve her hisse için ayrı CSV dosyasında kaydeden bir script'tir. İş Yatırım `isyatirimhisse` kütüphanesini kullanarak gelir tablosu, bilançodan veriler almaktadır.

### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/bist_data_collector_all_periods.py

# Yöntemi 2: Module olarak çalıştırma
python -m src.quanttrade.data_sources.bist_data_collector_all_periods

# Yöntemi 3: PowerShell'den (Windows)
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\bist_data_collector_all_periods.py
```

### Input Kaynağı
- **Semboller**: `config/settings.toml` dosyasındaki `[stocks]` bölümünden okunur
  ```toml
  [stocks]
  symbols = ["AEFES", "AGHOL", "AKCNS", "AKFGY", "AKSEN", ...]
  start_date = "2020-01-01"
  end_date = "2025-12-31"
  ```
- **Veri Kaynağı**: İş Yatırım (`isyatirimhisse` kütüphanesi)
  - Her hisse için finansal tabloları çeker (gelir tablosu, bilanço, etc.)
  - Tüm çeyreklik dönemleri (2015'ten günümüze) toplar

### Output Yolları

```
data/raw/financials/
  ├── AEFES_financials_all_periods.csv
  ├── AGHOL_financials_all_periods.csv
  ├── AKCNS_financials_all_periods.csv
  ├── AKFGY_financials_all_periods.csv
  └── ... (her hisse için ayrı dosya)
```

### Output Format (CSV)
```csv
ticker,period,net_profit,sales,total_debt,total_equity,return_1y,return_3y,return_5y,current_price
AEFES,2024/12,1000000,5000000,2000000,3000000,15.5,25.3,45.2,87.50
AEFES,2024/9,950000,4800000,1950000,2950000,NULL,NULL,NULL,NULL
```

### Bağımlılıklar (Dependencies)
```python
import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
# Harici kütüphaneler:
from isyatirimhisse import fetch_stock_data, fetch_financials
from quanttrade.config import get_stock_symbols, get_stock_date_range
```

### Gerekli Paketler
```bash
pip install isyatirimhisse pandas numpy
```

### Log Dosyası
```
bist_data_collector_all_periods.log  # Aynı dizinde
```

### Zaman Tahmini
- ~50-100 hisse için: 30-45 dakika
- Rate limiting: 1-2 saniye hisse başına

### Önemli Notlar
- ⚠️ **Rate limiting**: API'yi yormamak için otomatik bekleme dönemleri vardır
- ✓ Hisse başına ayrı CSV dosyası oluşturur
- ✓ Finansal_group parametresini otomatik dener (Sanayi → Bankalar)
- ✓ Fiyat getirileri hesaplar (1y, 3y, 5y)

---

## 2. EVDS Client & Macro Downloader


### 2.2 Macro Downloader (macro_downloader.py)

#### Açıklama
`EVDSClient`'ı kullanan wrapper script'tir. Komut satırından doğrudan çalıştırılabilir ve `settings.toml`'da tanımlı serileri otomatik olarak çeker.

#### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/macro_downloader.py

# Yöntemi 2: Module olarak
python -m src.quanttrade.data_sources.macro_downloader

# Yöntemi 3: Python'dan import edip kullanma
from quanttrade.data_sources.macro_downloader import main
main()
```

#### Input Kaynağı
- **API Anahtarı**: `.env` dosyasında `EVDS_API_KEY` olarak tanımlı olmalı
- **Seri Kodları**: `config/settings.toml` içinde
  ```toml
  [evds]
  start_date = "2020-01-01"
  end_date = "2025-12-31"
  
  [evds.series]
  USD_TL = "TP.DK.USD.A.YTL"
  EUR_TL = "TP.DK.EUR.A.YTL"
  TUFE = "TP.FG.J0"
  BIST100 = "TP.MK.F.BILESIK"
  ```

#### Output Yolu
```
data/raw/macro/evds_macro_daily.csv
```

#### Output Format (CSV)
```csv
date,USD_TL,EUR_TL,TUFE,BIST100,Para_Arzı,Faiz_Oranı
2020-01-02,5.99,6.52,55.23,12500.45,123456.78,8.75
2020-01-03,6.02,6.55,55.24,12480.23,123789.12,8.75
```

#### İşlem Adımları
1. EVDS API client oluşturur
2. `settings.toml`'dan seri kodlarını ve tarih aralığını okur
3. Her seriyi belirtilen frekansla çeker
4. Aylık/yıllık serileri günlük aralıklara forward-fill ile doldurur
5. Tüm serileri tek bir DataFrame'de birleştirir
6. `data/raw/macro/` dizinine CSV olarak kaydeder

#### Return Değeri
```python
# 0: Başarılı
# 1: Hata
exit_code = main()
```

#### Bağımlılıklar
```python
from quanttrade.data_sources.evds_client import EVDSClient
from quanttrade.config import get_evds_settings, MACRO_DATA_DIR
```

#### Önemli Notlar
- ✓ Günlük tarih aralığı otomatik oluşturulur
- ✓ Forward-fill ile eksik veriler doldurulur
- ✓ Hata varsa input() ile kullanıcıdan bilgi alır
- ⚠️ EVDS_API_KEY .env'de tanımlı olmalı

---

## 3. İş Yatırım OHLCV (isyatirim_ohlcv.py ve isyatirim_ohlcv_downloader.py)



### 3.2 İş Yatırım OHLCV Downloader (isyatirim_ohlcv_downloader.py)

#### Açıklama
`isyatirim_ohlcv.py` modülünü wrapper'layan komut satırı script'i. `config/settings.toml`'dan otomatik olarak sembol listesi ve tarih aralığını okuyor.

#### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py

# Yöntemi 2: Module olarak
python -m src.quanttrade.data_sources.isyatirim_ohlcv_downloader

# Windows PowerShell'den
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\isyatirim_ohlcv_downloader.py
```

#### Input Kaynağı
- **Semboller**: `config/settings.toml` içinde `[stocks].symbols`
- **Tarih Aralığı**: `config/settings.toml` içinde `[stocks].start_date` ve `[stocks].end_date`

#### Output Yolu
```
data/raw/ohlcv/
  └── {SYMBOL}_ohlcv_isyatirim.csv
```

#### İşlem Adımları
1. `config/settings.toml`'dan sembol listesi ve tarih aralığını okur
2. Tarih aralığını "YYYY-MM-DD" formatında kontrol eder
3. İş Yatırım'dan her hisse için OHLCV verisi çeker
4. Rate limiting (0.5 saniye) uygulanır
5. Her hisse için ayrı CSV dosyası oluşturur

#### Return Değeri
```python
# 0: Başarılı
# 1: Hata (import veya config sorunu)
exit_code = main()
```

#### Bağımlılıklar
```python
from quanttrade.data_sources.isyatirim_ohlcv import fetch_ohlcv_from_isyatirim
from quanttrade.config import ROOT_DIR, get_stock_symbols, get_stock_date_range
```

#### Önemli Notlar
- ✓ Otomatik olarak `config/settings.toml`'dan ayarları okuyor
- ✓ Hisse başına ayrı CSV dosyası oluşturur
- ✓ Detaylı logging sağlıyor (başarı/hata sayıları)
- ⚠️ IP ban riskini azaltmak için rate limiting vardır

---

## 4. Mali Tablo (mali_tablo.py)

### Açıklama
BIST hisselerinin **Gelir Tablosu (Income Statement)** verilerini çeken script'tir. İş Yatırım `fetch_financials` API'sini kullanarak her hisse için tüm yılların verilerini toplayıp single CSV dosyasında kaydeder.

### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/mali_tablo.py

# Yöntemi 2: Windows PowerShell'den
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\mali_tablo.py
```

### Input Kaynağı
- **Semboller**: `config/settings.toml` içinde `[stocks].symbols`
- **Tarih Aralığı**: `config/settings.toml` içinde `[stocks].start_date` ve `[stocks].end_date`
- **Veri Kaynağı**: İş Yatırım API (`fetch_financials` fonksiyonu)
- **Mali Grup**: `FINANCIAL_GROUP = "1"` (Gelir Tablosu)

### İş Akışı
```
config/settings.toml → sembol listesi
        ↓
        Her hisse için (örn: AEFES):
        ↓
        → Başlangıç yılından bitiş yılına kadar for döngüsü
        ↓
        → Her yıl için: fetch_financials(AEFES, 2020, ...) çağrısı
        ↓
        → Tüm yılların verileri birleştir
        ↓
        → data/raw/mali_tablo/AEFES.csv dosyasına kaydet
        ↓
        Bir sonraki hisseye geç
```

### Output Yolu
```
data/raw/mali_tablo/
  ├── AEFES.csv
  ├── AGHOL.csv
  ├── AKCNS.csv
  └── ... (her hisse için ayrı dosya)

data/raw/mali_tablo_no_data_symbols.csv  # Veri alınamayan hisseler
```

### Output Format (CSV)
```csv
FINANCIAL_ITEM_CODE,FINANCIAL_ITEM_NAME_TR,FINANCIAL_ITEM_NAME_EN,SYMBOL,2020/1,2020/2,2020/3,2020/4,2021/1,...
10000,Satışlar,Net Sales,AEFES,1234567890,1345678901,1456789012,1567890123,1678901234,...
10100,Satış Maliyeti,Cost of Sales,AEFES,987654321,1098765432,1209876543,1320987654,...
```

### Bağımlılıklar
```python
from isyatirimhisse import fetch_financials
import pandas as pd
import tomllib  # Python 3.11+
import logging
import time
import random
import sys
from pathlib import Path
from datetime import datetime
```

### Gerekli Paketler
```bash
pip install isyatirimhisse pandas
# Python 3.11+ için tomllib dahili
# Python 3.10 ve altı için: pip install tomli
```

### İşlem Detayları
- **Yeniden Deneme Mekanizması**: Her yıl için 3 defa deneme
- **Bekleme Süresi**: 1.5-3 saniye (random) yıl başına
- **Veri Birleştirme**: İlk yıldan itibaren tüm çeyrek sütunları toplayıp birleştirir
- **Hata Yönetimi**: Hiç veri alınamayan hisseler `mali_tablo_no_data_symbols.csv` dosyasına yazılır

### Zaman Tahmini
- ~100 hisse × 5 yıl ≈ 8-12 saat (API yavaşlığı nedeniyle)

### Log Dosyası
Konsola log yazılır (file'a yazılmaz)

### Önemli Notlar
- ⚠️ İlk çalıştırmada çok zaman alabilir
- ✓ Duplikat verileri otomatik çıkarır
- ✓ Random bekleme ile API ban riskini azaltır
- ✓ Hata sahibi hisseleri raporlar

---

## 5. KAP Announcement Scraper (kap_announcement_scraper.py)

### Açıklama
KAP.org.tr sitesinden hisselerin **finansal rapor duyurularını** (Financial Report / Finansal Rapor) scrape eden script'tir.

### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/kap_announcement_scraper.py

# Yöntemi 2: Windows PowerShell'den
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\kap_announcement_scraper.py
```

### Input Kaynağı
- **Semboller**: `config/settings.toml` içinde `[stocks].symbols`
- **OID Mapping**: `config/kap_symbols_oids_mapping.json` dosyasından (Hisse → KAP OID)
- **Veri Kaynağı**: KAP API (`https://www.kap.org.tr/tr/api/disclosure/members/byCriteria`)
- **Tarih Aralığı**: Script'te hardcoded
  ```python
  START_YEAR = 2020
  END_YEAR = 2025
  ```

### İş Akışı
```
1. config/settings.toml → sembol listesi
2. config/kap_symbols_oids_mapping.json → Sembol-OID eşlemesi
3. Her hisse-OID çifti için:
   → 2020-2025 yılları için for döngüsü
   → KAP API'sine POST request (finansal raporlar için)
   → Başarısız ise retry mekanizması (3 deneme)
   → IP ban varsa: kullanıcı input() ile elle bekleme
   → CSV dosyasına yazma
```

### Output Yolu
```
data/raw/announcements/
  ├── AEFES_announcements.csv
  ├── AGHOL_announcements.csv
  ├── AKCNS_announcements.csv
  └── ... (her hisse için ayrı dosya)
```

### Output Format (CSV)
```csv
index,publishDate,ruleType,summary,url
123456,2024-12-20,"Yıllık","31.12.2024 Tarihli Mali Tabloları","https://www.kap.org.tr/tr/Bildirim/123456"
123455,2024-09-30,"9 Aylık","30.09.2024 Tarihli Mali Tabloları","https://www.kap.org.tr/tr/Bildirim/123455"
```

### Bağımlılıklar
```python
import requests
import json
import csv
import time
from pathlib import Path
from quanttrade.config import get_stock_symbols, get_stock_date_range
```

### Gerekli Paketler
```bash
pip install requests pandas
```

### Önemli Detaylar

**KAP Mapping Dosyası Örneği** (`config/kap_symbols_oids_mapping.json`):
```json
{
  "companies": {
    "AEFES": {"oid": 12345678},
    "AGHOL": {"oid": 23456789},
    "AKCNS": {"oid": 34567890}
  }
}
```

**API Parametreleri**:
```python
payload = {
    "fromDate": "2024-01-01",
    "toDate": "2024-12-31",
    "memberType": "IGS",
    "disclosureClass": "FR",  # Finansal Rapor
    "mkkMemberOidList": [oid],
    "bdkMemberOidList": [],
    # ... diğer parametreler
}
```

**Retry Mekanizması**:
- 429, 403, timeout hatalarında 3 deneme
- Her deneme arasında 2 saniye bekleme
- IP ban varsa: kullanıcı ENTER'a basana kadar bekle

### Zaman Tahmini
- ~100 hisse × 6 yıl ≈ 20-30 dakika

### Önemli Notlar
- ⚠️ KAP.org.tr sık blok edebilir → IP ban riski yüksek
- ✓ Manual IP değişim sonrası devam etme seçeneği vardır
- ✓ Browser headers ve cookies eklenmiştir
- ✗ Mapping dosyası eksikse hisseler atlanır

---

## 6. Split Ratio (split_ratio.py)

### Açıklama
İş Yatırım sitesinden hisselerin **hisse bölünmesi (split) verilerini** çeken script'tir.

### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/split_ratio.py

# Yöntemi 2: Windows PowerShell'den
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\split_ratio.py
```

### Input Kaynağı
- **Semboller**: `config/settings.toml` içinde `[stocks].symbols`
- **Tarih Aralığı**: `config/settings.toml` içinde `[stocks].start_date` ve `[stocks].end_date`
- **Veri Kaynağı**: İş Yatırım API (`https://www.isyatirim.com.tr/.../GetSermayeArttirimlari`)

### İş Akışı
```
1. Config'ten semboller ve tarih aralığı oku
2. Her hisse için:
   → API'ye POST request (Sermaye Artırımları)
   → JSON response'ı parse et
   → Split oranı hesapla (Sonrası / Öncesi)
   → Tarih aralığına göre filtrele
   → CSV dosyasına kaydet
   → 1 saniye bekleme (rate limiting)
```

### Output Yolu
```
data/raw/split_ratio/
  ├── AEFES_split.csv
  ├── AGHOL_split.csv
  └── ... (her hisse için ayrı dosya)
```

### Output Format (CSV)
```csv
HSP_TARIH,HSP_BOLUNME_ONCESI_SERMAYE,HSP_BOLUNME_SONRASI_SERMAYE,SPLIT_RATIO,SHHE_TARIH
2020-05-15,1000000,2000000,2.0,2020-05-15T00:00:00.000Z
2021-03-10,2000000,4000000,2.0,2021-03-10T00:00:00.000Z
```

### Bağımlılıklar
```python
import requests
import pandas as pd
import json
from pathlib import Path
from io import StringIO
from quanttrade.config import get_stock_symbols, get_stock_date_range
from datetime import datetime
```

### Gerekli Paketler
```bash
pip install requests pandas
```

### API Payload
```python
payload = {
    "hisseKodu": "AEFES",
    "hisseTanimKodu": "",
    "yil": 0,
    "zaman": "HEPSI",  # Tüm zamanlar
    "endeksKodu": "09",
    "sektorKodu": ""
}
```

### Zaman Tahmini
- ~100 hisse ≈ 5-10 dakika

### Önemli Notlar
- ✓ Tarih aralığına göre otomatik filtreler
- ✓ Tarih dönüşümü (milliseconds → datetime)
- ✓ FutureWarning'ı StringIO ile çözer

---

## 7. Temettü Scraper (temettü_scraper.py)

### Açıklama
İş Yatırım sitesinden hisselerin **temettü dağıtım verilerini** (dividend history) scrape eden script'tir.

### Çalıştırılma Şekli

```bash
# Yöntemi 1: Doğrudan çalıştırma
python src/quanttrade/data_sources/temettü_scraper.py

# Yöntemi 2: Windows PowerShell'den
cd C:\Users\90552\OneDrive\Belgeler\GitHub\QuantTrade
python .\src\quanttrade\data_sources\temettü_scraper.py

# Yöntemi 3: Türkçe encoding ile çalıştırma (gerekli olabilir)
$env:PYTHONIOENCODING = "utf-8"
python .\src\quanttrade\data_sources\temettü_scraper.py
```

### Input Kaynağı
- **Semboller**: `config/settings.toml` içinde `[stocks].symbols`
- **Tarih Aralığı**: `config/settings.toml` içinde `[stocks].start_date` ve `[stocks].end_date`
- **Veri Kaynağı**: İş Yatırım website HTML tablosu (`https://www.isyatirim.com.tr/...?hisse={symbol}`)

### İş Akışı
```
1. Config'ten semboller ve tarih aralığı oku
2. Her hisse için:
   → HTTP GET request (İş Yatırım hisse sayfası)
   → BeautifulSoup ile HTML parse
   → Temettü tablosundan satırları çıkart
   → Tarih aralığına göre filtrele
   → CSV dosyasına kaydet
   → 1 saniye bekleme (rate limiting)
```

### Output Yolu
```
data/raw/dividend/
  ├── AEFES_dividends.csv
  ├── AGHOL_dividends.csv
  └── ... (her hisse için ayrı dosya)
```

### Output Format (CSV)
```csv
Kod,Dagitim_Tarihi,Temettu_Verim,Hisse_Basi_TL,Brut_Oran,Net_Oran,Toplam_Temettu_TL,Dagitma_Orani
AEFES,20.12.2024,%2.50,2.50,19.00%,15.20%,500000000,50%
AEFES,15.06.2024,%1.75,1.75,13.00%,10.40%,350000000,35%
```

### Bağımlılıklar
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path
from datetime import datetime
from quanttrade.config import get_stock_symbols, get_stock_date_range
```

### Gerekli Paketler
```bash
pip install requests beautifulsoup4 pandas
```

### BeautifulSoup Selector
```python
# Temettü tablosu satırlarını seçme
rows = soup.select("tbody.temettugercekvarBody.hepsi tr.temettugercekvarrow")
```

### Zaman Tahmini
- ~100 hisse ≈ 3-8 dakika

### Önemli Notlar
- ⚠️ HTML yapısı değişirse script çalışmayabilir
- ✓ Tarih formatı: DD.MM.YYYY (otomatik parse)
- ✓ Başarısız hisseler otomatik atlanır
- ✗ Veri yoksa hisse atlanır (başarısız sayılır)

---


## 📊 Veri Bağımlılık Grafiği


---

## 🔄 Önerilen Çalıştırma Sırası

İlk kez setup yapıyorsanız bu sırada çalıştırın:

1. **İş Yatırım OHLCV Downloader**
   ```bash
   python .\src\quanttrade\data_sources\isyatirim_ohlcv_downloader.py
   ```
   ⏱️ ~15-30 dakika | Output: `data/raw/ohlcv/`

2. **Mali Tablo**
   ```bash
   python .\src\quanttrade\data_sources\mali_tablo.py
   ```
   ⏱️ ~8-12 saat | Output: `data/raw/mali_tablo/`

3. **BIST Data Collector (Finansal Veriler)**
   ```bash
   python .\src\quanttrade\data_sources\bist_data_collector_all_periods.py
   ```
   ⏱️ ~30-45 dakika | Output: `data/raw/financials/`

4. **KAP Announcement Scraper** (Opsiyonel)
   ```bash
   python .\src\quanttrade\data_sources\kap_announcement_scraper.py
   ```
   ⏱️ ~20-30 dakika | Output: `data/raw/announcements/`

5. **Split Ratio Scraper**
   ```bash
   python .\src\quanttrade\data_sources\split_ratio.py
   ```
   ⏱️ ~5-10 dakika | Output: `data/raw/split_ratio/`

6. **Temettü Scraper**
   ```bash
   python .\src\quanttrade\data_sources\temettü_scraper.py
   ```
   ⏱️ ~3-8 dakika | Output: `data/raw/dividend/`

7. **Makro Downloader** (.env'de EVDS_API_KEY olmalı)
   ```bash
   python .\src\quanttrade\data_sources\macro_downloader.py
   ```
   ⏱️ ~2-5 dakika | Output: `data/raw/macro/evds_macro_daily.csv`

---

## ⚙️ Konfigürasyon Dosyaları

### config/settings.toml
```toml
[stocks]
symbols = ["AEFES", "AGHOL", "AKCNS", ...]
start_date = "2020-01-01"
end_date = "2025-12-31"

[evds]
start_date = "2020-01-01"
end_date = "2025-12-31"

[evds.series]
USD_TL = "TP.DK.USD.A.YTL"
EUR_TL = "TP.DK.EUR.A.YTL"
TUFE = "TP.FG.J0"
```

### .env
```env
EVDS_API_KEY=your_api_key_here
```

### config/kap_symbols_oids_mapping.json
```json
{
  "companies": {
    "AEFES": {"oid": 12345678},
    "AGHOL": {"oid": 23456789}
  }
}
```

---

## 🛠️ Troubleshooting

| Sorun | Çözüm |
|-------|-------|
| `ImportError: No module named 'isyatirimhisse'` | `pip install isyatirimhisse` |
| `ImportError: No module named 'evds'` | `pip install evds --upgrade` |
| `FileNotFoundError: config/settings.toml` | Settings.toml dosyasını oluşturun |
| `ValueError: EVDS_API_KEY bulunamadı` | .env dosyasında EVDS_API_KEY tanımlayın |
| `429 Too Many Requests` | Rate limiting zaten vardır, IP değiştirilmesi önerilir |
| `ConnectionError` | İnternet bağlantısını kontrol edin |
| Parquet dosyası açılamıyor | `pip install pyarrow` |

---

## 📝 Notlar

- ✓ Tüm script'ler otomatik olarak `data/raw/` dizini oluşturur
- ✓ Hata durumunda log dosyaları kaydedilir
- ✓ Rate limiting mekanizmaları API ban riskini azaltır
- ⚠️ İlk çalıştırmalar uzun zaman alabilir
- ✗ İnternet kesilirse script'ler baştan başlaması gerekebilir

---

# Data Processing & Feature Engineering Scripts

Bu bölümde `data_processing` ve `feature_engineering` klasörlerindeki script'ler detaylı olarak açıklanmıştır.

## 📊 Data Processing Scripts

### 1. OHLCV Cleaner (ohlcv_cleaner.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/ohlcv_cleaner.py
```

**Input:**
- `data/raw/ohlcv/*_ohlcv_*.csv` (İş Yatırım'dan indirilen ham OHLCV verileri)

**Output:**
- `data/processed/ohlcv/{SYMBOL}_ohlcv_clean.csv`

**Zorunlu Kolonlar (Output):**
```
[date, open, high, low, close, volume, symbol]
```

**İşlemler:**
- Kolon adlarını standartlaştırma (Türkçe → İngilizce)
- Tarih dönüşümü (datetime)
- Numerik veri tipi dönüşümü
- Duplikat tarihlerin kaldırılması
- OHLC logik validasyonu (high≥low, high≥open, vb.)
- Negatif volume kontrolü

---

### 2. Macro Cleaner (macro_cleaner.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/macro_cleaner.py
```

**Input:**
- `data/raw/macro/evds_macro_daily.csv` (EVDS API'den indirilen ham makro veriler)

**Output:**
- `data/processed/macro/evds_macro_daily_clean.csv`

**Zorunlu Kolonlar (Output):**
```
[date, usd_try, eur_try, tufe, bist100, para_arzı, faiz_oranı, ...]
```

**İşlemler:**
- Kolon adlarını normalize etme (lowercase)
- Tarih formatı dönüşümü (YYYY-MM-DD)
- Numerik dönüştürme (string → float)
- Forward-fill ile eksik değerleri doldurma
- Binlik ayırıcı temizleme (virgül → nokta)

---

### 3. Mali Tablo Converter (mali_tablo_converter.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/mali_tablo_converter.py
```

**Input:**
- `data/raw/mali_tablo/*.csv` (İş Yatırım'dan indirilen finansal tablolar - wide format)

**Output:**
- `data/processed/mali_tablo/{SYMBOL}_financials_long.csv` (long format)

**Zorunlu Kolonlar (Output):**
```
[symbol, period, item_code, item_name_tr, item_name_en, value]
```

**Dönüşüm:** Wide format (sütunlar = çeyrekler: 2020/3, 2020/6, ...) → Long format

---

### 4. Mali Tablo Normalizer (mali_tablo_normalizer.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/mali_tablo_normalizer.py
```

**Input:**
- `data/raw/mali_tablo/*.csv`

**Output:**
- `data/processed/mali_tablo/{SYMBOL}_financials_long.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, period, item_code, item_name_tr, item_name_en, value]
```

**İşlemler:**
- Dönem kolonlarını otomatik tespit (YYYY/Q formatı)
- Numeric değerleri temizleme
- Wide → Long dönüştürme

**Log:** `mali_tablo_normalizer.log`

---

### 5. Dividend Cleaner (dividend_cleaner.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/dividend_cleaner.py
```

**Input:**
- `data/raw/dividend/*_dividends.csv`

**Output:**
- `data/processed/dividend/{SYMBOL}_dividends_clean.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, ex_date, dividend_yield_pct, dividend_per_share, gross_pct, net_pct, total_dividend_tl, payout_ratio_pct]
```

---

### 6. Split Cleaner (split_cleaner.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/split_cleaner.py
```

**Input:**
- `data/raw/split_ratio/*_split.csv`

**Output:**
- `data/processed/split/{SYMBOL}_split_clean.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, split_date, split_factor, cumulative_split_factor]
```

**Log:** `split_cleaner.log`

---

### 7. Announcement Cleaner (announcement_cleaner.py)

**Çalıştırma:**
```bash
python src/quanttrade/data_processing/announcement_cleaner.py
```

**Input:**
- `data/raw/announcements/*_announcements.csv`

**Output:**
- `data/processed/announcements/{SYMBOL}_announcements_clean.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, announcement_date, rule_type, summary, url]
```

**İşlemler:**
- Finansal rapor (3M, 6M, 9M, Yıllık) duyurularını filtreleme
- Tarih formatı dönüşümü

---

## 🔧 Feature Engineering Scripts

### 1. Price Feature Engineer (price_feature_engineer.py)

**Çalıştırma:**
```bash
python src/quanttrade/feature_engineering/price_feature_engineer.py
```

**Input:**
- `data/processed/ohlcv/{SYMBOL}_ohlcv_clean.csv`
- `data/processed/split/{SYMBOL}_split_clean.csv`
- `data/processed/dividend/{SYMBOL}_dividends_clean.csv`

**Output:**
- `data/features/price/{SYMBOL}_price_features.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, date, adj_close, adj_open, adj_high, adj_low, return_1d, return_5d, return_20d, vol_20d, vol_60d, sma_20, sma_50, sma_200, rsi_14, macd, macd_signal, is_dividend_day, distance_from_ma200, future_return_10d, future_return_20d, y_triclass_10d]
```

**Target Variables:**
```
future_return_10d, future_return_20d, future_return_30d, ..., future_return_120d
y_triclass_10d (±2% threshold ile tri-class: -1/0/+1)
```

---

### 2. Fundamental Feature Engineer (fundamental_features.py)

**Çalıştırma:**
```bash
python src/quanttrade/feature_engineering/fundamental_features.py
```

**Input:**
- `data/processed/mali_tablo/{SYMBOL}_financials_long.csv`
- `data/processed/announcements/{SYMBOL}_announcements_clean.csv`

**Output:**
- `data/features/fundamental/{SYMBOL}_fundamental_period_features.csv`

**Zorunlu Kolonlar (Output):**
```
[symbol, period, announcement_date, net_profit, net_sales, total_assets, total_liabilities, total_equity, roe, roa, net_margin, debt_to_equity, current_ratio, revenue_growth_yoy, profit_growth_yoy]
```

**İşlemler:**
- Finansal kalemlerini standart forma dönüştürme
- ROE, ROA, Net Margin, Debt-to-Equity oranlarını hesaplama
- YoY büyüme hesaplama
- Duyuru tarihlerini finansal tablolara eşleme

---

### 3. Macro Feature Engineer (macro_features.py)

**Çalıştırma:**
```bash
python src/quanttrade/feature_engineering/macro_features.py
```

**Input:**
- `data/processed/macro/evds_macro_daily_clean.csv`

**Output:**
- `data/features/macro/macro_features_daily.csv`

**Zorunlu Kolonlar (Output):**
```
[date, usd_try, usdtry_roc_1d, usdtry_roc_5d, usdtry_roc_20d, usdtry_ma200, usdtry_distance_ma200, usdtry_vol_20d, usdtry_vol_60d, usdtry_vol_regime, eur_try, eurtry_roc_1d, eurtry_roc_5d, eurtry_roc_20d, bist100, bist100_roc_1d, bist100_roc_5d, bist100_roc_20d, bist100_roc_60d, bist100_ma200, bist100_distance_ma200]
```

**Feature Kategorileri:**
- **USD/TRY**: ROC, MA200, distance, volatilite
- **EUR/TRY**: ROC
- **BIST100**: ROC, MA200, distance, volatilite
- Diğer makro seriler (M2, CPI, Faiz, vs.)

---

### 4. Master Builder (master_builder.py)

**Çalıştırma:**
```bash
python src/quanttrade/feature_engineering/master_builder.py
```

**Input:**
- `data/features/price/{SYMBOL}_price_features.csv` (hisse başına)
- `data/features/fundamental/{SYMBOL}_fundamental_period_features.csv` (hisse başına)
- `data/features/macro/macro_features_daily.csv` (tek dosya)

**Output:**
- `data/master/master_df.parquet`

**Zorunlu Kolonlar (Output):**
```
[symbol, date, price_adj_close, price_return_1d, price_return_5d, price_return_20d, price_vol_20d, price_sma_200, price_distance_from_ma200, price_rsi_14, price_macd, macro_usd_try, macro_usdtry_roc_1d, macro_bist100, fund_net_profit, fund_net_sales, fund_roe, fund_debt_to_equity, future_return_10d, y_triclass_10d]
```

**Join Logic:**
- Price + Macro: date'e göre
- + Fundamental: symbol + date'e göre, announcement_date şartıyla

---

## 🔄 Bütün Pipeline Sırası

**Stage 1: Data Collection** → **Stage 2: Data Processing** → **Stage 3: Feature Engineering**

```
data_sources/ 
  ↓
data_processing/ (cleaner scripts)
  ↓
feature_engineering/ (feature scripts)
  ↓
master_df.parquet ✓
```


