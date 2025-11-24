import requests
from requests.auth import HTTPBasicAuth
import json
import csv
from pathlib import Path
import sys
import time

# ==========================================
# ⚙️ GERÇEK BİLGİLERİNİ BURAYA GİR
# ==========================================

# Portaldan aldığın "Client ID" veya "API Key"
MY_API_KEY = "cb90bacc-6893-4e53-96bd-99eafdc9c72f"

# Portaldan aldığın "Client Secret" (Varsa)
# Yoksa buraya da API KEY'i yazmayı dene
MY_SECRET = "89685f13-776e-444f-bdce-c6e8098c9de5" 

BASE_URL = "https://apigw.mkk.com.tr"
# ==========================================

# Proje ayarları
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
try:
    from src.quanttrade.config import get_stock_symbols
except ImportError:
    def get_stock_symbols(): return ["THYAO", "GARAN"]

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class MKKApiClient:
    def __init__(self, api_key, secret, base_url):
        self.auth = HTTPBasicAuth(api_key, secret)
        self.base_url = base_url
        self.company_map = {}

    def load_company_map(self):
        print(f"🔄 Şirket Listesi Çekiliyor... ({self.base_url})")
        url = f"{self.base_url}/api/vyk/members"
        
        try:
            # Basic Auth gönderiyoruz
            response = requests.get(url, auth=self.auth, timeout=30)
            
            if response.status_code == 200:
                members = response.json()
                count = 0
                for m in members:
                    if "stockCode" in m and m["stockCode"]:
                        self.company_map[m["stockCode"].upper()] = str(m["id"])
                        count += 1
                print(f"✅ Bağlantı Başarılı! {count} şirket bulundu.")
                return True
            elif response.status_code == 401:
                print("❌ Yetki Hatası (401): Key veya Secret yanlış.")
                return False
            else:
                print(f"❌ Hata: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"💥 Bağlantı Hatası: {e}")
            return False

    def get_last_disclosure_index(self):
        """Son bildirim index'ini öğren"""
        url = f"{self.base_url}/api/vyk/lastDisclosureIndex"
        try:
            response = requests.get(url, auth=self.auth, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("lastDisclosureIndex")
            return None
        except:
            return None

    def fetch_disclosures(self, symbol, start_index=None):
        """
        Bildirim listesini çek
        start_index=None: En son bildirimleri getir
        start_index=X: X index'ten itibaren getir
        """
        company_id = self.company_map.get(symbol)
        if not company_id: 
            return []

        url = f"{self.base_url}/api/vyk/disclosures"
        
        # companyId array olarak göndermeli (API spec)
        params = {
            "companyId": [company_id]
        }
        
        # Eğer start_index verilmişse ekle
        if start_index is not None:
            params["disclosureIndex"] = str(start_index)
        else:
            # Son bildirimleri al - index verme
            params["disclosureIndex"] = "0"
        
        try:
            response = requests.get(url, params=params, auth=self.auth, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            else:
                # İlk 2 hatada detay göster
                if symbol in ["KCHOL", "SAHOL"]:
                    print(f"   ⚠️ {symbol} API Hatası: {response.status_code}")
                    print(f"      Yanıt: {response.text[:200]}")
                return []
        except Exception as e:
            print(f"   � {symbol} Hata: {e}")
            return []

    def get_disclosure_detail(self, disclosure_index):
        """
        Bildirim detayını çek (data formatında)
        """
        url = f"{self.base_url}/api/vyk/disclosureDetail/{disclosure_index}"
        params = {"fileType": "data"}
        
        try:
            response = requests.get(url, params=params, auth=self.auth, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

def main():
    print("="*60)
    print("MKK API - ANONS ÇEKME ARACI (TEST)")
    print("="*60)
    
    if "BURAYA" in MY_API_KEY:
        print("⚠️ Lütfen kodun başındaki MY_API_KEY alanına kendi anahtarını gir!")
        return

    client = MKKApiClient(MY_API_KEY, MY_SECRET, BASE_URL)
    
    if not client.load_company_map():
        print("\n🛑 Bağlantı başarısız!")
        return
    
    # Son bildirim index'ini öğren
    last_idx = client.get_last_disclosure_index()
    if last_idx:
        print(f"\n📌 Son Bildirim Index: {last_idx}")
    else:
        print("\n⚠️ Son index alınamadı")
        return
    
    # TEST: Önce detail endpoint'ini dene (belki bu çalışıyor)
    print(f"\n🧪 TEST: Disclosure detail endpoint test ediliyor (index: {last_idx})...")
    detail_url = f"{BASE_URL}/api/vyk/disclosureDetail/{last_idx}"
    detail_params = {"fileType": "data"}
    
    try:
        d = requests.get(detail_url, params=detail_params, auth=client.auth, timeout=30)
        print(f"   Status: {d.status_code}")
        if d.status_code == 200:
            detail_data = d.json()
            print(f"   ✅ Detay geldi!")
            print(f"   Title: {detail_data.get('subject', {}).get('tr', 'N/A')[:60]}")
            print(f"   Time: {detail_data.get('time', 'N/A')}")
        else:
            print(f"   ❌ Hata: {d.text[:200]}")
    except Exception as e:
        print(f"   💥 Hata: {e}")
    
    # TEST: Liste endpoint'i (companyId olmadan)
    print(f"\n🧪 TEST: Liste endpoint (companyId olmadan, sadece index)...")
    test_url = f"{BASE_URL}/api/vyk/disclosures"
    test_params = {"disclosureIndex": str(last_idx)}
    
    try:
        r = requests.get(test_url, params=test_params, auth=client.auth, timeout=30)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   ✅ {len(data)} bildirim geldi!")
            if data:
                print(f"   İlk bildirim: {data[0].get('title', 'N/A')[:60]}")
                
                # Bu bildirimleri kaydet
                all_announcements = []
                for item in data[:20]:
                    idx = item.get("disclosureIndex")
                    if idx:
                        detail = client.get_disclosure_detail(idx)
                        if detail:
                            record = {
                                "disclosure_index": idx,
                                "disclosure_type": item.get("disclosureType"),
                                "disclosure_class": item.get("disclosureClass"),
                                "title": item.get("title"),
                                "company_id": item.get("companyId"),
                                "subject_tr": detail.get("subject", {}).get("tr") if isinstance(detail.get("subject"), dict) else None,
                                "time": detail.get("time"),
                            }
                            all_announcements.append(record)
                            time.sleep(0.2)
                
                if all_announcements:
                    filename = OUTPUT_DIR / "test_announcements.csv"
                    keys = all_announcements[0].keys()
                    with open(filename, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=keys)
                        writer.writeheader()
                        writer.writerows(all_announcements)
                    print(f"\n✅ {len(all_announcements)} anons kaydedildi: {filename}")
        else:
            print(f"   ❌ Hata: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"   💥 Hata: {e}")

if __name__ == "__main__":
    main()