# EVDS API Kullanım Kılavuzu

Bu doküman, QuantTrade projesinde TCMB EVDS (Elektronik Veri Dağıtım Sistemi) API'sinin nasıl kullanıldığını açıklar.

## 📋 İçindekiler

1. [Kurulum](#kurulum)
2. [API Anahtarı Alma](#api-anahtarı-alma)
3. [Önemli Güncelleme (5 Nisan 2024)](#önemli-güncelleme-5-nisan-2024)
4. [Temel Kullanım](#temel-kullanım)
5. [Parametreler](#parametreler)
6. [Örnekler](#örnekler)
7. [Sorun Giderme](#sorun-giderme)

## 🔧 Kurulum

EVDS paketini yüklemek için:

```bash
pip install evds --upgrade
```

## 🔑 API Anahtarı Alma

1. [EVDS web sitesi](https://evds2.tcmb.gov.tr/) üzerinden hesap oluşturun
2. Profil sayfanıza girin
3. "API Anahtarı" butonuna tıklayın
4. Anahtarı kopyalayın
5. Proje kök dizininde `.env` dosyasına ekleyin:

```env
EVDS_API_KEY=sizin_api_anahtarınız
```

## ⚠️ Önemli Güncelleme (5 Nisan 2024)

**TCMB EVDS API'sinde kritik değişiklik yapılmıştır:**

- **Eski Yöntem:** API anahtarı URL parametresi olarak gönderiliyordu
- **Yeni Yöntem:** API anahtarı HTTP request header'ında gönderilmelidir

**Örnek (Eski - Çalışmaz):**
```python
url = "https://evds2.tcmb.gov.tr/service/evds/?key=API_KEY&series=..."
```

**Örnek (Yeni - Doğru):**
```python
import requests
headers = {'key': 'API_KEY'}
response = requests.get('https://evds2.tcmb.gov.tr/service/evds/', headers=headers)
```

**Not:** Resmi `evds` Python paketi (v0.3.2+) bu güncellemeyi içermektedir.

## 📚 Temel Kullanım

### 1. EVDSClient ile Kullanım (Önerilen)

```python
from quanttrade.data_sources.evds_client import EVDSClient

# Client oluştur (API anahtarı .env'den otomatik okunur)
client = EVDSClient()

# Tek seri çek
df = client.fetch_series(
    series_codes='TP.DK.USD.A.YTL',  # USD/TRY alış kuru
    start_date='2024-01-01',
    end_date='2024-02-01'
)

# Çoklu seri çek
df = client.fetch_series(
    series_codes=['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL'],
    start_date='2024-01-01',
    end_date='2024-02-01'
)
```

### 2. Ham API Kullanımı

```python
from evds import evdsAPI
import os

api_key = os.getenv('EVDS_API_KEY')
evds = evdsAPI(api_key)

# Veri çek
df = evds.get_data(
    ['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL'],
    startdate="01-01-2019",
    enddate="01-01-2020"
)

# Ham JSON verisine erişim
raw_data = evds.data
```

## ⚙️ Parametreler

### `series_codes` (Zorunlu)
EVDS seri kodu veya kodlar listesi.

**Örnekler:**
- `'TP.DK.USD.A.YTL'` - USD/TRY alış kuru
- `'TP.DK.EUR.A.YTL'` - EUR/TRY alış kuru
- `'TP.XU100'` - BIST100 endeksi
- `'TP.M2.YTL'` - M2 para arzı
- `'TP.FG.J0'` - TÜFE (Tüketici Fiyat Endeksi)

### `startdate` ve `enddate` (Zorunlu)
Tarih aralığı.

**Formatlar:**
- `"01-01-2024"` (DD-MM-YYYY) - EVDS API formatı
- `"2024-01-01"` (YYYY-MM-DD) - EVDSClient otomatik dönüştürür

### `frequency` (İsteğe Bağlı)
Veri sıklığı.

| Değer | Açıklama |
|-------|----------|
| 1 | Günlük |
| 2 | İşgünü |
| 3 | Haftalık |
| 4 | Ayda 2 Kez |
| 5 | Aylık |
| 6 | 3 Aylık |
| 7 | 6 Aylık |
| 8 | Yıllık |

**Örnek:**
```python
df = client.fetch_series(
    series_codes='TP.DK.USD.A.YTL',
    start_date='2023-01-01',
    end_date='2024-01-01',
    frequency=5  # Aylık
)
```

### `aggregation_types` (İsteğe Bağlı)
Toplululaştırma yöntemi.

| Değer | Açıklama |
|-------|----------|
| avg | Ortalama |
| min | En düşük |
| max | En yüksek |
| first | Başlangıç |
| last | Bitiş |
| sum | Kümülatif |

**Örnek:**
```python
df = client.fetch_series(
    series_codes='TP.DK.USD.A.YTL',
    start_date='2023-01-01',
    end_date='2024-01-01',
    frequency=5,
    aggregation_types='avg'  # Aylık ortalama
)
```

### `formulas` (İsteğe Bağlı)
Veri üzerinde uygulanacak formül.

| Değer | Açıklama |
|-------|----------|
| 1 | Yüzde Değişim |
| 2 | Fark |
| 3 | Yıllık Yüzde Değişim |
| 4 | Yıllık Fark |
| 5 | Bir Önceki Yılın Sonuna Göre Yüzde Değişim |
| 6 | Bir Önceki Yılın Sonuna Göre Fark |
| 7 | Hareketli Ortalama |
| 8 | Hareketli Toplam |

**Örnek:**
```python
df = client.fetch_series(
    series_codes='TP.DK.USD.A.YTL',
    start_date='2023-01-01',
    end_date='2024-01-01',
    formulas=1  # Yüzde değişim
)
```

## 💡 Örnekler

### Örnek 1: Günlük Döviz Kurları
```python
from quanttrade.data_sources.evds_client import EVDSClient

client = EVDSClient()

# Son 1 ayın USD ve EUR kurları
df = client.fetch_series(
    series_codes=['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL'],
    start_date='2024-01-01',
    end_date='2024-02-01'
)

print(df.head())
```

### Örnek 2: Aylık BIST100 Endeksi
```python
df = client.fetch_series(
    series_codes='TP.XU100',
    start_date='2020-01-01',
    end_date='2024-01-01',
    frequency=5,  # Aylık
    aggregation_types='last'  # Ay sonu değeri
)
```

### Örnek 3: settings.toml'dan Toplu Veri Çekme
```python
# Otomatik olarak config/settings.toml'dan tüm serileri çeker
output_path = client.fetch_and_save_default_macro()
print(f"Veri kaydedildi: {output_path}")
```

### Örnek 4: Makro Veri İndirme (Terminal)
```bash
# Virtual environment'ı aktif et
source .venv/bin/activate

# PYTHONPATH ayarla ve scripti çalıştır
PYTHONPATH=/Users/furkanyilmaz/Desktop/QuantTrade/src \
python src/quanttrade/data_sources/macro_downloader.py
```

## 🔍 Serileri Listeleme

### Ana Kategorileri Listeleme
```python
from evds import evdsAPI
import os

api_key = os.getenv('EVDS_API_KEY')
evds = evdsAPI(api_key)

# Ana kategoriler otomatik yüklenir
print(evds.main_categories)
```

### Alt Kategorileri Listeleme
```python
# Kategori ID ile
evds.get_sub_categories(6)

# Kategori adı ile
evds.get_sub_categories("KURLAR")
```

### Serileri Listeleme
```python
# Alt kategori adı ile
series_df = evds.get_series('bie_dbdborc')
print(series_df)
```

## 🐛 Sorun Giderme

### Problem: "Connection error, please check your API Key"

**Çözüm 1:** API anahtarınızı kontrol edin
```bash
cat .env
# EVDS_API_KEY=... olmalı
```

**Çözüm 2:** EVDS paketini güncelleyin
```bash
pip install evds --upgrade
```

**Çözüm 3:** API anahtarınızı EVDS web sitesinden yeniden alın

### Problem: "ModuleNotFoundError: No module named 'quanttrade'"

**Çözüm:** PYTHONPATH'i ayarlayın
```bash
export PYTHONPATH=/Users/furkanyilmaz/Desktop/QuantTrade/src
python src/quanttrade/data_sources/macro_downloader.py
```

### Problem: Tarihler NaT (Not a Time) olarak geliyor

**Sebep:** Aylık/yıllık frekans kullanıldığında tarih formatı farklı olabilir.

**Çözüm:** Günlük frekans kullanın veya tarih parse işlemini manuel yapın
```python
# Aylık veri için
df = client.fetch_series(
    series_codes='TP.M2.YTL',
    start_date='2020-01-01',
    end_date='2024-01-01',
    frequency=5  # Aylık
)

# Tarih sütununu manuel parse et
if df.index.name == 'date' and df.index.isna().any():
    # Özel işlem yapılabilir
    pass
```

### Problem: "externally-managed-environment" hatası

**Çözüm:** Virtual environment kullanın
```bash
# Virtual environment oluştur (sadece bir kez)
python3 -m venv .venv

# Aktif et
source .venv/bin/activate

# Paketleri yükle
pip install -r requirements.txt
```

## 📚 Kaynaklar

- [EVDS Web Sitesi](https://evds2.tcmb.gov.tr/)
- [EVDS Python Paketi (PyPI)](https://pypi.org/project/evds/)
- [TCMB Resmi Dokümantasyonu](https://evds2.tcmb.gov.tr/help/videos/EVDS_Python_Kullanim_Kilavuzu.pdf)

## 📝 Notlar

1. EVDS API'si ücretsizdir ancak kayıt gerektirir
2. API rate limit (istek sınırı) olabilir - çok fazla istek göndermeyin
3. Bazı seriler sadece belirli frekanslarda mevcuttur
4. Tatil günleri ve hafta sonları için veri olmayabilir (NaN)
5. API anahtarınızı GitHub'a push etmeyin - `.gitignore` dosyasında `.env` olmalı

## ✅ Yapılacaklar (TODO)

- [ ] Otomatik veri güncelleme (scheduler)
- [ ] Veri validasyonu ve temizleme
- [ ] Daha fazla EVDS seri kodu eklemek
- [ ] Veri görselleştirme özellikleri
- [ ] Cache mekanizması (tekrar indirmeyi önlemek için)
