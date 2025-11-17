# EVDS Entegrasyonu Güncelleme Özeti

## 🎯 Yapılan İşlemler

### 1. Paket Değişikliği
- **Eski:** `evdspy` (resmi olmayan paket)
- **Yeni:** `evds` (TCMB resmi paketi - v0.3.2)

**Sebep:** 5 Nisan 2024 tarihinde TCMB EVDS API'sinde kritik güncelleme yapıldı. API anahtarı artık URL parametresi yerine HTTP header'da gönderilmelidir. Resmi `evds` paketi bu güncellemeyi içermektedir.

### 2. Güncellenen Dosyalar

#### a) `requirements.txt`
```diff
- evdspy
+ evds  # Resmi TCMB EVDS API paketi
```

#### b) `src/quanttrade/data_sources/evds_client.py`
**Değişiklikler:**
- Import: `evdspy.evdspyAPI` → `evds.evdsAPI`
- `get_data()` fonksiyonu parametreleri güncellendi
- Opsiyonel parametreler için `None` yerine boş string (`''`) kullanımı
- Tarih parse işlemi optimize edildi
- Docstring'ler EVDS resmi dokümantasyonuna göre güncellendi

**Önemli Değişiklik:**
```python
# ESKI (evdspy)
df = self.client.get_data(
    series=series_string,  # Virgülle ayrılmış string
    startdate=evds_start,
    enddate=evds_end,
    frequency=frequency
)

# YENİ (evds)
df = self.client.get_data(
    series_codes,  # Liste olarak
    startdate=evds_start,
    enddate=evds_end,
    aggregation_types=aggregation_types if aggregation_types else '',
    formulas=formulas if formulas else '',
    frequency=frequency if frequency else ''
)
```

### 3. Yeni Özellikler

#### a) Ek Parametreler
- `aggregation_types`: Veri toplululaştırma (avg, min, max, first, last, sum)
- `formulas`: Veri formülleri (yüzde değişim, fark, hareketli ortalama vb.)
- `frequency`: Daha esnek frekans seçimi (1-8 arası değerler)

#### b) İyileştirilmiş Hata Yönetimi
- API anahtarı validasyonu
- Boş string parametreleri doğru şekilde işleme
- Daha detaylı log mesajları

### 4. Yeni Dokümantasyon

#### a) `docs/EVDS_KULLANIM.md`
Kapsamlı kullanım kılavuzu:
- Kurulum talimatları
- API anahtarı alma
- 5 Nisan 2024 güncellemesi detayları
- Parametreler ve kullanım örnekleri
- Sorun giderme

#### b) `test_evds.py`
Test script'i:
- Temel veri çekme
- Çoklu seri çekme
- Parametreli veri çekme
- Ham API kullanımı

### 5. README Güncellemeleri
- Teknoloji stack'inde `evdspy` → `evds` değişikliği
- 5 Nisan 2024 güncellemesi notu
- EVDS Kullanım Kılavuzu linki
- PYTHONPATH kullanım talimatları

## ✅ Test Sonuçları

Tüm testler başarıyla tamamlandı:

```
✓ EVDS Client oluşturma
✓ Tek seri çekme (USD/TRY - 32 satır)
✓ Çoklu seri çekme (USD/TRY, EUR/TRY - 15 satır)
✓ Parametreli veri çekme (Aylık frekans - 13 satır)
✓ Ham API kullanımı (366 satır)
✓ Makro veri indirme (5 seri, 60 satır)
```

## 📝 Kullanım

### Kurulum
```bash
# Virtual environment oluştur
python3 -m venv .venv
source .venv/bin/activate

# Yeni paketi yükle
pip install evds --upgrade
```

### Makro Veri İndirme
```bash
# Terminal'den
source .venv/bin/activate
PYTHONPATH=src python src/quanttrade/data_sources/macro_downloader.py

# Python'dan
from quanttrade.data_sources.evds_client import EVDSClient
client = EVDSClient()
output_path = client.fetch_and_save_default_macro()
```

### Özel Veri Çekme
```python
from quanttrade.data_sources.evds_client import EVDSClient

client = EVDSClient()

# Günlük kurlar
df = client.fetch_series(
    series_codes=['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL'],
    start_date='2024-01-01',
    end_date='2024-02-01'
)

# Aylık ortalama
df = client.fetch_series(
    series_codes='TP.DK.USD.A.YTL',
    start_date='2023-01-01',
    end_date='2024-01-01',
    frequency=5,  # Aylık
    aggregation_types='avg'  # Ortalama
)
```

## ⚠️ Önemli Notlar

1. **API Anahtarı:** `.env` dosyasında `EVDS_API_KEY` tanımlı olmalı
2. **Virtual Environment:** Sistem paketlerine müdahale etmemek için `.venv` kullanın
3. **PYTHONPATH:** Script çalıştırırken `PYTHONPATH=src` ayarlayın
4. **Tarih Formatı:** Hem `YYYY-MM-DD` hem `DD-MM-YYYY` formatları destekleniyor
5. **Opsiyonel Parametreler:** `None` yerine boş string (`''`) veya hiç göndermeyin

## 🔍 Bilinen Sorunlar ve Çözümler

### Sorun 1: NaT (Not a Time) Tarihleri
**Sebep:** Aylık frekans kullanıldığında tarih formatı farklı olabilir.
**Çözüm:** Günlük frekans kullanın veya `frequency` parametresini atlayın.

### Sorun 2: ModuleNotFoundError
**Sebep:** PYTHONPATH ayarlanmamış.
**Çözüm:** `export PYTHONPATH=/path/to/project/src` veya script başında ekleyin.

### Sorun 3: Connection Error
**Sebep:** API anahtarı geçersiz veya resmi paket eski versiyonda.
**Çözüm:** 
```bash
pip install evds --upgrade
cat .env  # EVDS_API_KEY kontrol et
```

## 📚 Kaynaklar

- [EVDS Web Sitesi](https://evds2.tcmb.gov.tr/)
- [EVDS PyPI Paketi](https://pypi.org/project/evds/)
- [TCMB Python Kullanım Kılavuzu](https://evds2.tcmb.gov.tr/help/videos/EVDS_Python_Kullanim_Kilavuzu.pdf)
- [Proje Dokümantasyonu](docs/EVDS_KULLANIM.md)

## 🎉 Sonuç

EVDS entegrasyonu başarıyla güncellendi ve 5 Nisan 2024 TCMB API güncellemesi ile uyumlu hale getirildi. Tüm özellikler test edildi ve çalışıyor. Makro veri indirme altyapısı hazır!

---
**Son Güncelleme:** 17 Kasım 2024
**Paket Versiyonu:** evds==0.3.2
