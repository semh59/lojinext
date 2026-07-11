# 3rd Party Provider Entegrasyonu

LojiNext, araç takip (AVL) ve akaryakıt kart sistemlerinden **read-only**
veri çekmek için plug-in altyapısına sahiptir. Stub adapter'lar hazır;
provider seçildiğinde `.env` ile aktif edilir.

## Mimari

```
[Provider]  →  [Adapter]  →  [Internal Normalize]  →  [DB upsert by external_id]
                              (AVLTrip / FuelTransaction)
```

Provider abstraction: `app/core/integrations/{avl,fuel}/base.py`.

## Şu an hazır adapter stub'ları

### AVL (Araç Takip)
| Provider | Key | Dosya | Durum |
|---|---|---|---|
| Mobiliz | `mobiliz` | `avl/mobiliz.py` | gerçek HTTP + api_stub'a karşı test edilmiş, **gerçek Mobiliz sözleşmesiyle doğrulanmamış** — endpoint dokümanı bekleniyor |
| Arvento | `arvento` | (planlandı) | yok |
| Vodafone Araç Takip | `vodafone` | (planlandı) | yok |

### Akaryakıt Kart
| Provider | Key | Dosya | Durum |
|---|---|---|---|
| OPET | `opet` | `fuel/opet.py` | gerçek HTTP + api_stub'a karşı test edilmiş, **gerçek OPET sözleşmesiyle doğrulanmamış** — endpoint dokümanı bekleniyor |
| Shell | `shell` | (planlandı) | yok |
| BP Truckmaster | `bp` | (planlandı) | yok |
| Petrol Ofisi | `po` | (planlandı) | yok |

## Aktivasyon

`.env` örneği:

```bash
# AVL
AVL_PROVIDER=mobiliz
AVL_BASE_URL=https://api.mobiliz.com
AVL_API_KEY=eyJh...
AVL_ACCOUNT_ID=12345
AVL_POLL_INTERVAL_SECONDS=900   # 15 dk default

# Fuel Card
FUEL_PROVIDER=opet
FUEL_BASE_URL=https://b2b.opet.com.tr/api
FUEL_API_KEY=...
FUEL_ACCOUNT_ID=...
FUEL_POLL_INTERVAL_SECONDS=3600  # 1 saat default
```

## Bir provider'ı production'a almak (kısa adım listesi)

1. ~~Adapter dosyasında `fetch_trips`/`fetch_transactions` içindeki
   `NotImplementedError`'ı **gerçek HTTP çağrısı** ile değiştir.~~ **Yapıldı**
   (2026-07-11) — ama aşağıdaki "gerçek sağlayıcı doğrulaması" hâlâ eksik,
   bkz. sınırlamalar.
1b. Sağlayıcı seçildiğinde: gerçek API dokümanı geldiğinde adapter'daki
    endpoint path'lerini/response mapping'ini gerçek şemaya göre güncelle
    (şu anki mapping `api_stub/main.py`'deki varsayım şemasına göre).
2. `.env`'i doldur.
3. Migration: `araclar.external_id` (provider'da bu aracın ID'si) ve
   `yakit_alimlari.external_transaction_id` (kart işlem ID) field'ları
   eklenir; UNIQUE constraint ile idempotent insert.
4. Celery beat task'ı aktive et (mevcut `app/workers/tasks/` altına eklenir):
   - `integrations.avl_poll` (15 dk)
   - `integrations.fuel_poll` (1 saat)
5. Healthcheck doğrula (Faz 0'dan beri admin panelde görünür — bkz.
   Entegrasyonlar sayfası "Planlanan Entegrasyonlar" bölümü):
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.lojinext.com/api/v1/admin/integrations/planned
   ```

## Veri Akışı: AVL → Sefer

```
Mobiliz Trip:
  trip_id=T-123, plate=34ABC, distance=120 km, ...
        ↓ (normalize)
AVLTrip:
  external_id=T-123, plaka=34ABC123, distance_km=120, ...
        ↓ (upsert by external_id)
Sefer:
  external_id=T-123 (yeni kolon), arac_id (plaka lookup),
  mesafe_km=120, durum=Tamamlandı, source=mobiliz
```

Dedup: `seferler.external_id` UNIQUE constraint sayesinde aynı trip iki
kez insert edilmez.

## Veri Akışı: Fuel Card → Yakıt Fişi

```
OPET Transaction:
  transactionId=Tx-456, plateNumber=34ABC, liters=200, ...
        ↓
FuelTransaction:
  external_transaction_id=Tx-456, plaka=34ABC123, ...
        ↓
YakitAlimi:
  external_transaction_id=Tx-456 (yeni kolon),
  fis_no=Tx-456, arac_id, litre, fiyat_tl, km_sayac, ...
        ↓
recalculate_vehicle_periods(arac_id)
  → yakit_periyotlari güncellenir
```

## Şu an için sınırlamalar (dürüst not)

- Adapter'lar (`mobiliz.py`/`opet.py`) artık gerçek HTTP çağrısı yapıyor ve
  `api_stub/main.py`'deki deterministik stub'a karşı test edilmiş (2026-07-11)
  — ama **gerçek Mobiliz/OPET API sözleşmesiyle hiç doğrulanmadı**. Şu anki
  request/response şekli adapter dosyalarının kendi TODO yorumlarından
  türetildi, gerçek sağlayıcı dokümanından değil.
- `get_avl_provider()`/`get_fuel_provider()` hâlâ uygulamada hiçbir yerde
  (endpoint/worker/servis) çağrılmıyor — sadece adapter+registry seviyesinde
  test edilebilir durumda.
- Migration eklenmedi: `external_id` field'ları henüz tablo schema'sında yok.
- Celery beat task'ları kayıtlı değil.
- Webhook desteği planlanmadı (provider push event'leri için).
- Admin panelde (Entegrasyonlar sayfası → "Planlanan Entegrasyonlar")
  Faz 0 görünürlüğü var: `AVL_PROVIDER`/`FUEL_PROVIDER` env durumu +
  "Uygulanmadı" rozeti — gerçek çalışma durumu değil.

Provider seçildiğinde ("Faz 1" — iş kararı) yukarıdaki maddeler
**birlikte** çalışılır; tek seferde tam akış kurulur.
