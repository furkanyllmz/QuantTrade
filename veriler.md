# QuantTrade Veri Kaynakları ve Kolonlar

Bu dokümanda QuantTrade projesinde kullanılan tüm veri kaynakları ve oluşturdukları kolonlar detaylı şekilde listelenmiştir.

---

## 📊 VERİ KAYNAKLARI ÖZETİ

| Veri Kaynağı | Dosya Sayısı | Kolon Sayısı | Güncelleme Sıklığı | Kayıt Yolu |
|--------------|--------------|--------------|-------------------|------------|
| **EVDS Macro** | 1 CSV | 6-8 kolon | Günlük | `data/raw/macro/` |
| **OHLCV (İş Yatırım)** | 49 CSV (hisse başına) | 7 kolon | Günlük | `data/raw/ohlcv/` |
| **Mali Tablo** | 49 CSV (hisse başına) | 47+ kolon (dönem bazlı) | 3 aylık | `data/raw/mali_tablo/` |
| **BIST Collector** | 1 CSV | 10 kolon | Günlük | `data/raw/stocks/` |
| **Temettü** | 49 CSV (hisse başına) | 8 kolon | Yıllık | `data/raw/dividend/` |
| **KAP Anons** | 49 CSV (hisse başına) | 5 kolon | Olay bazlı | `data/raw/announcements/` |

---

## 1️⃣ EVDS MACRO DATA (TCMB Makroekonomik Veriler)

### 📁 Dosya Konumu
```
data/raw/macro/evds_macro_daily.csv
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/macro_downloader.py`
- **Client**: `src/quanttrade/data_sources/evds_client.py`

### 📋 Kolonlar (6-8 kolon)

| Kolon Adı | Açıklama | EVDS Seri Kodu | Frekans | Veri Tipi |
|-----------|----------|----------------|---------|-----------|
| **date** | Tarih (index) | - | Günlük | datetime |
| **usd_try** | USD/TRY Döviz Kuru | TP.DK.USD.A.YTL | Günlük | float |
| **eur_try** | EUR/TRY Döviz Kuru | TP.DK.EUR.A.YTL | Günlük | float |
| **bist100** | BIST 100 Endeksi | TP.MK.F.BILESIK | Günlük | float |
| **m2** | Para Arzı (M2) | TP.PBD.H09 | Aylık → ffill | float |
| **cpi** | Tüketici Fiyat Endeksi | TP.FG.J0 | Aylık → ffill | float |
| **tcmb_rate** | TCMB Politika Faizi | TP.YSSK.A1 | Aylık → ffill | float |
| **us_cpi** (opsiyonel) | ABD Enflasyon | TP.IMFCPIND.USA | Aylık → ffill | float |
| **us_leading** (opsiyonel) | ABD Öncü Gösterge | TP.OECDONCU.USA | Aylık → ffill | float |

### 📝 Notlar
- Aylık veriler günlük aralıklara **forward-fill** ile doldurulur
- Başlangıçtaki NaN'lar **backward-fill** ile doldurulur
- API Anahtarı: `.env` dosyasında `EVDS_API_KEY` gereklidir
- Tarih aralığı: `config/settings.toml` içinde `[evds]` bölümünde tanımlanır

---

## 2️⃣ OHLCV DATA (İş Yatırım Günlük Fiyat Verileri)

### 📁 Dosya Konumu
```
data/raw/ohlcv/
├── AKBNK_ohlcv_isyatirim.csv
├── ARCLK_ohlcv_isyatirim.csv
├── ASELS_ohlcv_isyatirim.csv
└── ... (49 CSV dosyası)
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py`
- **Client**: `src/quanttrade/data_sources/isyatirim_ohlcv.py`

### 📋 Kolonlar (7 kolon)

| Kolon Adı | Açıklama | Veri Tipi | Örnek Değer |
|-----------|----------|-----------|-------------|
| **date** | Tarih (index) | datetime | 2023-01-15 |
| **open** | Açılış Fiyatı (TRY) | float | 45.50 |
| **high** | Gün İçi En Yüksek (TRY) | float | 46.20 |
| **low** | Gün İçi En Düşük (TRY) | float | 45.10 |
| **close** | Kapanış Fiyatı (TRY) | float | 45.80 |
| **volume** | İşlem Hacmi (adet) | float | 12500000 |
| **symbol** | Hisse Sembolü | string | THYAO |

### 📝 Notlar
- Her hisse için **ayrı CSV dosyası** oluşturulur
- Tarih index olarak kullanılır
- İş Yatırım API kolon isimleri (`HGDG_TARIH`, `HGDG_KAPANIS` vb.) standart formata çevrilir
- Rate limiting: 0.5 saniye (IP ban riskini azaltmak için)
- Kütüphane: `isyatirimhisse` (pip install isyatirimhisse)

---

## 3️⃣ MALİ TABLO (Finansal Tablo Verileri)

### 📁 Dosya Konumu
```
data/raw/mali_tablo/
├── AKBNK.csv
├── ARCLK.csv
├── ASELS.csv
└── ... (49 CSV dosyası)
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/mali_tablo.py`

### 📋 Kolonlar (47+ kolon - Dinamik Dönem Bazlı)

#### Sabit Kolonlar (3 kolon)
| Kolon Adı | Açıklama | Veri Tipi | Örnek Değer |
|-----------|----------|-----------|-------------|
| **FINANCIAL_ITEM_CODE** | Finansal Kalem Kodu | string | 1 |
| **FINANCIAL_ITEM_NAME_TR** | Kalem Adı (Türkçe) | string | Net Satışlar |
| **FINANCIAL_ITEM_NAME_EN** | Kalem Adı (İngilizce) | string | Net Sales |

#### Dinamik Kolonlar (Dönemler - 44+ kolon)
Her dönem için **bir kolon** oluşturulur. Format: `YYYY/Q` (Yıl/Çeyrek)

**Dönem Kolonları (2022-2026 arası):**
- `2022/3`, `2022/6`, `2022/9`, `2022/12`
- `2023/3`, `2023/6`, `2023/9`, `2023/12`
- `2024/3`, `2024/6`, `2024/9`, `2024/12`
- `2025/3`, `2025/6`, `2025/9`, `2025/12` (gelecek projeksiyonlar)
- `2026/3`, `2026/6`, `2026/9`, `2026/12` (gelecek projeksiyonlar)

**Son Kolon:**
| Kolon Adı | Açıklama | Veri Tipi | Örnek Değer |
|-----------|----------|-----------|-------------|
| **SYMBOL** | Hisse Sembolü | string | THYAO |

### 📊 Finansal Kalem Örnekleri (Satır Bazlı)

Veri **transpozedir**: Her satır bir finansal kalem, her kolon bir dönem.

**Örnek Kalemler:**
- Net Satışlar / Net Sales
- Brüt Kar / Gross Profit
- Esas Faaliyet Karı / Operating Profit
- Net Dönem Karı/Zararı / Net Profit/Loss
- Toplam Varlıklar / Total Assets
- Toplam Yükümlülükler / Total Liabilities
- Özkaynak / Equity
- Finansal Borçlar / Financial Debt
- Nakit ve Nakit Benzerleri / Cash and Cash Equivalents
- Ticari Alacaklar / Trade Receivables
- Stoklar / Inventories
- ... (toplam ~100+ finansal kalem)

### 📝 Notlar
- Veri yapısı: **Pivot Format** (satırlar=kalemler, kolonlar=dönemler)
- Dönem sütunları soldan sağa kronolojik sıradadır
- Her hisse için **ayrı CSV dosyası**
- Exchange: USD (dolar bazlı)
- Financial Group: 1 (sanayi şirketleri bilanço şablonu)
- Veri kaynağı: İş Yatırım API (`fetch_financials`)
- Boş dönemler NaN olabilir

---

## 4️⃣ BIST DATA COLLECTOR (Birleştirilmiş Fundamental + Fiyat Verileri)

### 📁 Dosya Konumu
```
data/raw/stocks/bist_isyatirimhisse_full_dataset.csv
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/bist_data_collector.py`

### 📋 Kolonlar (10 kolon)

| Kolon Adı | Açıklama | Veri Kaynağı | Veri Tipi | Örnek Değer |
|-----------|----------|--------------|-----------|-------------|
| **ticker** | Hisse Sembolü | - | string | THYAO |
| **period** | Finansal Dönem | Mali Tablo | string | 2024/9 |
| **net_profit** | Net Dönem Karı (TRY) | Mali Tablo | float | 1500000000 |
| **sales** | Net Satışlar / Hasılat (TRY) | Mali Tablo | float | 15000000000 |
| **total_debt** | Toplam Borç (TRY) | Mali Tablo | float | 8000000000 |
| **total_equity** | Özkaynak (TRY) | Mali Tablo | float | 12000000000 |
| **return_1y** | 1 Yıllık Getiri (%) | OHLCV | float | 45.2 |
| **return_3y** | 3 Yıllık Getiri (%) | OHLCV | float | 120.5 |
| **return_5y** | 5 Yıllık Getiri (%) | OHLCV | float | 230.8 |
| **current_price** | Güncel Fiyat (TRY) | OHLCV | float | 85.50 |

### 📝 Notlar
- **Tek bir CSV dosyası** içinde tüm hisseler
- Her satır bir hisse (49 satır)
- Mali tablo ve fiyat verilerini birleştirir
- Finansal kalem arama algoritması:
  - Net Kar: "NET DÖNEM KARI", "NET KAR", "NET PROFIT"
  - Satışlar: "NET SATIŞLAR", "HASILAT", "NET FAİZ GELİRİ" (bankalar için)
  - Borç: "TOPLAM BORÇLAR", "FİNANSAL BORÇLAR"
  - Özkaynak: "ÖZKAYNAKLAR", "ANA ORTAKLIK PAYINA AİT ÖZKAYNAKLAR"
- Getiri hesaplama: `((current_price - past_price) / past_price) * 100`
- Rate limiting: 2 saniye (her hisse arası)

---

## 5️⃣ TEMETTÜ VERİLERİ (Dividend Data)

### 📁 Dosya Konumu
```
data/raw/dividend/
├── AKBNK_dividends.csv
├── ARCLK_dividends.csv
├── ASELS_dividends.csv
└── ... (49 CSV dosyası)
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/temettü_scraper.py`

### 📋 Kolonlar (8 kolon)

| Kolon Adı | Açıklama | Veri Tipi | Örnek Değer |
|-----------|----------|-----------|-------------|
| **Kod** | Hisse Sembolü | string | THYAO |
| **Dagitim_Tarihi** | Dağıtım Tarihi | string | 15.04.2024 |
| **Temettu_Verim** | Temettü Verimi (%) | string | %5.2 |
| **Hisse_Basi_TL** | Hisse Başına Temettü (TL) | string | 2.50 |
| **Brut_Oran** | Brüt Oran (%) | string | %10 |
| **Net_Oran** | Net Oran (% - vergi sonrası) | string | %8.5 |
| **Toplam_Temettu_TL** | Toplam Dağıtılan Temettü (TL) | string | 500.000.000 |
| **Dagitma_Orani** | Dağıtma Oranı (kar içinde %) | string | %50 |

### 📝 Notlar
- Her hisse için **ayrı CSV dosyası**
- Veri kaynağı: İş Yatırım web sitesi (scraping)
- Tarih filtresi: `config/settings.toml` içinde `[stocks]` bölümünde tanımlı tarih aralığı
- Sayısal kolonlar string olarak saklanır (nokta, virgül, % işaretleri var)
- Sadece config'teki tarih aralığındaki dağıtımlar kaydedilir
- Rate limiting: 1 saniye (her hisse arası)

---

## 6️⃣ KAP ANONSLARI (Public Disclosure Platform Announcements)

### 📁 Dosya Konumu
```
data/raw/announcements/
├── AKBNK_announcements.csv
├── ARCLK_announcements.csv
├── ASELS_announcements.csv
└── ... (49 CSV dosyası)
```

### 🔧 Script
- **Dosya**: `src/quanttrade/data_sources/kap_announcement_scraper.py`

### 📋 Kolonlar (5 kolon)

| Kolon Adı | Açıklama | Veri Tipi | Örnek Değer |
|-----------|----------|-----------|-------------|
| **index** | KAP Bildirim Index No | string | 1234567 |
| **publishDate** | Yayın Tarihi | string | 2024-03-15T10:30:00 |
| **ruleType** | Dönem Tipi | string | 3 Aylık / Yıllık |
| **summary** | Bildiri Özeti | string | Finansal Tablo ve Bağımsız Denetim Raporu |
| **url** | KAP Bildirim Linki | string | https://www.kap.org.tr/tr/Bildirim/1234567 |

### 📝 Notlar
- Her hisse için **ayrı CSV dosyası**
- **Sadece finansal raporlar** çekilir (`disclosureClass: "FR"`)
- "Finansal" kelimesi içeren bildirimler filtrelenir
- Tarih aralığı: 2020-2025 (6 yıl, her yıl için ayrı API çağrısı)
- Her yıl için 1 saniye, her sembol için 2 saniye bekleme
- Veri kaynağı: KAP API (`https://www.kap.org.tr/tr/api/disclosure/members/byCriteria`)
- Config gereksinimi: `config/kap_symbols_oids_mapping.json` (sembol-OID eşleştirme)
- Headers ve cookies browser'dan alınır (bot detection bypass için)

---

## 📊 TOPLAM VERİ İSTATİSTİKLERİ

### Dosya Sayısı
- **EVDS Macro**: 1 dosya
- **OHLCV**: 49 dosya (hisse başına)
- **Mali Tablo**: 49 dosya (hisse başına)
- **BIST Collector**: 1 dosya (tüm hisseler)
- **Temettü**: 49 dosya (hisse başına)
- **KAP Anons**: 49 dosya (hisse başına)
- **TOPLAM**: ~198 CSV dosyası

### Kolon Sayısı (Toplam)
- EVDS Macro: 6-8 kolon
- OHLCV: 7 kolon × 49 hisse = 343 veri noktası
- Mali Tablo: 47+ kolon × 49 hisse = 2,303+ veri noktası (dönemsel)
- BIST Collector: 10 kolon
- Temettü: 8 kolon × 49 hisse = 392 veri noktası
- KAP Anons: 5 kolon × 49 hisse = 245 veri noktası

### Veri Büyüklüğü (Tahmini)
- **EVDS Macro**: ~100-500 KB (günlük, 3-5 yıllık veri)
- **OHLCV**: ~50-200 KB × 49 = **2.5-10 MB**
- **Mali Tablo**: ~20-70 KB × 49 = **1-3.5 MB**
- **BIST Collector**: ~10-50 KB
- **Temettü**: ~5-20 KB × 49 = **250 KB - 1 MB**
- **KAP Anons**: ~10-50 KB × 49 = **500 KB - 2.5 MB**
- **TOPLAM**: ~**5-20 MB** (ham CSV verileri)

---

## 🔄 VERİ GÜNCELLEME SIKLIĞI

| Veri Kaynağı | Önerilen Güncelleme Sıklığı | Kritik Dönemler |
|--------------|----------------------------|----------------|
| **EVDS Macro** | Günlük (hergün 16:00 sonrası) | TCMB faiz kararları |
| **OHLCV** | Günlük (seans sonrası 18:30+) | - |
| **Mali Tablo** | 3 ayda bir (bilançolar açıklandığında) | Mart, Mayıs, Ağustos, Kasım |
| **BIST Collector** | Haftalık | Bilançolar + fiyat değişimleri |
| **Temettü** | Aylık (Nisan-Mayıs yoğun) | Genel kurul sezonları |
| **KAP Anons** | Günlük / Olay bazlı | Finansal rapor açıklama tarihleri |

---

## 🛠️ TEKNİK DETAYLAR

### Kullanılan Kütüphaneler
```python
pandas>=2.0.0
numpy>=1.22.0
isyatirimhisse>=5.0.0
evds
requests
beautifulsoup4
```

### Config Dosyaları
- `config/settings.toml` - Sembol listesi, tarih aralıkları, EVDS serileri
- `.env` - API anahtarları (EVDS_API_KEY)
- `config/kap_symbols_oids_mapping.json` - KAP OID eşleştirme

### Tarih Formatları
- **EVDS API**: `DD-MM-YYYY` (örn: 15-01-2024)
- **İş Yatırım API**: `DD-MM-YYYY` (örn: 15-01-2024)
- **QuantTrade Internal**: `YYYY-MM-DD` (ISO 8601)
- **Mali Tablo Dönemler**: `YYYY/Q` (örn: 2024/3)

---

## 📝 NOTLAR VE UYARILAR

### Rate Limiting
- **EVDS**: Dakikada 100 istek limiti (resmi API limiti)
- **İş Yatırım**: 0.5-2 saniye arası bekleme (IP ban riski)
- **KAP**: 1-2 saniye arası bekleme (bot detection)

### Veri Kalitesi
- **Mali Tablo**: Bankalar ve holding şirketlerinde farklı bilanço formatları kullanılır
- **OHLCV**: Bölünme ve birleşme işlemlerinde fiyat düzeltmesi yoktur
- **EVDS**: Aylık veriler günlük aralıklara forward-fill ile yayılır (son değer taşınır)
- **Temettü**: Geçmiş dağıtımlar bazen güncellenir/düzeltilir

### Missing Data Handling
- **NaN değerler**: Finansal kalemlerde bulunmayan değerler None/NaN olarak kalır
- **Boş dönemler**: Mali tabloda bazı dönemler eksik olabilir
- **Yeni hisseler**: IPO sonrası hisseler için geçmiş veri kısıtlıdır

---

## 🎯 KULLANIM ÖRNEKLERİ

### Tüm Verileri Çekme
```powershell
# EVDS Makro
cd src\quanttrade\data_sources
python macro_downloader.py

# OHLCV
python isyatirim_ohlcv_downloader.py

# Mali Tablo
python mali_tablo.py

# BIST Collector
python bist_data_collector.py

# Temettü
python temettü_scraper.py

# KAP Anons
python kap_announcement_scraper.py
```

### Veri Okuma (Python)
```python
import pandas as pd

# EVDS Macro
macro_df = pd.read_csv('data/raw/macro/evds_macro_daily.csv', index_col='date', parse_dates=True)

# OHLCV (tek hisse)
ohlcv_df = pd.read_csv('data/raw/ohlcv/THYAO_ohlcv_isyatirim.csv', index_col='date', parse_dates=True)

# Mali Tablo (tek hisse)
mali_df = pd.read_csv('data/raw/mali_tablo/THYAO.csv')

# BIST Collector (tüm hisseler)
bist_df = pd.read_csv('data/raw/stocks/bist_isyatirimhisse_full_dataset.csv')

# Temettü (tek hisse)
dividend_df = pd.read_csv('data/raw/dividend/THYAO_dividends.csv')

# KAP Anons (tek hisse)
kap_df = pd.read_csv('data/raw/announcements/THYAO_announcements.csv')
```

---

## 📞 DESTEK VE GÜNCELLEMELER

Bu dokümanda eksiklik veya hata fark ederseniz:
1. İlgili script dosyasını kontrol edin
2. `get_errors` tool ile hata loglarını inceleyin
3. API dokümantasyonlarını gözden geçirin:
   - EVDS: https://evds2.tcmb.gov.tr/
   - İş Yatırım: https://www.isyatirim.com.tr/
   - KAP: https://www.kap.org.tr/

**Son Güncelleme**: 18 Kasım 2025
**Doküman Versiyonu**: 1.0
