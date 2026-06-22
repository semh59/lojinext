# Excel Şablonları — Üretim Veri Yükleme Rehberi

Bu doküman LojiNext'e ilk veri yüklemesi için **doğru sıra** ve her şablonun
**kolon listesini** içerir. Sıra önemli: Sefer Excel'i yüklenirken araç ve
şoför kayıtlı olmalı (FK eşleşme).

## Yükleme Sırası

```
1) Araçlar       → /vehicles/template          → POST /vehicles/excel/upload
2) Dorseler      → /trailers/template          → POST /trailers/import
3) Şoförler      → /drivers/excel/template     → POST /drivers/excel/upload
4) Güzergahlar   → /locations/excel/template   → POST /locations/upload
5) Seferler      → /trips/excel/template       → POST /trips/upload?async_mode=true
6) Yakıt Fişleri → /fuel/excel/template        → POST /fuel/excel/upload?async_mode=true
```

> ⚠️ 5 ve 6 sıralaması önemli değil — ama **5'ten ÖNCE 1-4 tamamlanmış olmalı**.

---

## 1. Araçlar — `/vehicles/template`

| Kolon | Tip | Zorunlu | Örnek |
|---|---|---|---|
| Plaka | Text | ✓ | `34 ABC 001` |
| Marka | Text | ✓ | Mercedes |
| Model | Text |  | Actros 2645 |
| Yil | 1990-2100 | ✓ | 2022 |
| Tank_Kapasitesi | L (default 600) |  | 600 |
| Bos_Agirlik_KG | kg |  | 8200 |
| Maks_Yuk_Kapasitesi_KG | kg |  | 26000 |
| Dingil_Sayisi | 1-8 |  | 2 |
| Motor_Verimliligi | 0..1 (default 0.38) |  | 0.38 |
| Hava_Direnc_Katsayisi | float (default 0.7) |  | 0.7 |
| On_Kesit_Alani_m2 | m² (default 8.5) |  | 8.5 |
| Lastik_Direnc_Katsayisi | float (default 0.007) |  | 0.007 |
| Hedef_Tuketim | L/100km |  | 32.0 |
| Yakit_Tipi | DIZEL/BENZIN/LPG/ELEKTRIK |  | DIZEL |
| Muayene_Tarihi | YYYY-MM-DD |  | 2027-06-15 |
| Notlar | Text |  |  |

## 2. Dorseler — `/trailers/template`

Plaka, Marka, Model, Yil, Dorse_Tipi (Tenteli/Frigo/...), Bos_Agirlik_KG,
Lastik_Sayisi, Rolling_Resistance, Drag_Coefficient.

## 3. Şoförler — `/drivers/excel/template`

| Kolon | Tip | Zorunlu | Örnek |
|---|---|---|---|
| Ad_Soyad | Text | ✓ | Ahmet Yılmaz |
| Telefon | Text |  | 0555 123 45 67 |
| Ise_Baslama | YYYY-MM-DD |  | 2023-01-01 |
| Ehliyet_Sinifi | B/C/D/E/CE |  | CE |
| Telegram_ID | Chat ID |  |  |
| Notlar | Text |  |  |

> ⚠️ **Sefer Excel'inde şoför adı buradaki Ad_Soyad ile BİREBİR eşleşmelidir** (büyük/küçük harf hariç). "Ahmet Yılmaz" vs "Ahmet YILMAZ" — fark etmez, ama "Ahmet" yazarsan eşleşmez.

## 4. Güzergahlar — `/locations/excel/template`

| Kolon | Tip | Zorunlu | Örnek |
|---|---|---|---|
| Çıkış Yeri | Text | ✓ | İstanbul Kadıköy |
| Varış Yeri | Text | ✓ | Ankara Sincan |
| Çıkış Lat | -90..+90 |  | 40.9924 |
| Çıkış Lon | -180..+180 |  | 29.0271 |
| Varış Lat | float |  | 39.9709 |
| Varış Lon | float |  | 32.5816 |
| Mesafe (KM) | Number > 0 | ✓ | 450 |
| Tahmini Süre (saat) | Number |  | 5.5 |
| Tırmanış (m) | Number |  | 320 |
| İniş (m) | Number |  | 180 |
| Düz Mesafe (KM) | Number |  | 420 |
| Otoban Mesafe (KM) | Number |  | 380 |
| Şehir İçi Mesafe (KM) | Number |  | 70 |
| Tahmini Yakıt (L) | Number |  | 145 |
| Zorluk | Kolay/Normal/Zor |  | Normal |
| Notlar | Text |  |  |

> ⚠️ Sefer Excel'inde `Çıkış Yeri + Varış Yeri` ikilisi burada kayıtlı bir güzergahla eşleşmeli; sistem ascent/descent gibi alanları otomatik dolduracak. UNIQUE constraint var → aynı pair için tek satır.

## 5. Seferler — `/trips/excel/template`

| Kolon | Tip | Zorunlu | Örnek |
|---|---|---|---|
| Tarih | YYYY-MM-DD | ✓ | 2026-01-01 |
| Saat | HH:MM |  | 09:00 |
| Çıkış Yeri | birebir güzergah | ✓ | İstanbul Kadıköy |
| Varış Yeri | birebir güzergah | ✓ | Ankara Sincan |
| Mesafe (KM) | Number > 0 | ✓ | 450 |
| Yük (KG) | Number |  | 15000 |
| Plaka | sistemdeki araç | ✓ | 34 ABC 001 |
| Dorse Plakası | varsa |  | 34 XYZ 099 |
| Şoför Adı | Ad_Soyad birebir | ✓ | Ahmet Yılmaz |
| Durum | enum | önerilir | Tamamlandı |
| Tırmanış (m) | GPS varsa |  | 320 |
| İniş (m) | GPS varsa |  | 180 |
| Düz Mesafe (KM) | GPS varsa |  | 300 |
| Sefer No | varsa |  | SEF-2026-001 |
| Notlar | varsa |  |  |

**Durum değerleri** (canonical): `Planlandı`, `Atandı`, `Yolda`, `Tamamlandı`, `İptal`. Excel'de bu değerlerden birini yaz; yoksa varsayılan **Planlandı**.

> ⚠️ Tarih boş bırakılırsa **o satır errors[]'a düşer** (eskisi gibi bugün damgalamıyoruz).
> ⚠️ Ascent/Descent boş bırakırsan, güzergah kaydından otomatik doldurulur.

## 6. Yakıt Fişleri — `/fuel/excel/template`

| Kolon | Tip | Zorunlu | Örnek |
|---|---|---|---|
| Tarih | YYYY-MM-DD | ✓ | 2026-02-10 |
| Plaka | sistemdeki araç | ✓ | 34 ABC 123 |
| İstasyon | Text | önerilir | Shell Maslak |
| Litre | Number > 0 | ✓ | 500 |
| Fiyat | ₺/L | ✓ | 42.50 |
| Toplam Tutar | ₺ (litre×fiyat) |  | 21250 |
| KM Sayacı | Number (monoton) | ✓ | 120500 |
| Fiş No | Text |  | FIS-001 |
| Depo Durumu | Doldu/Dolu/Kısmi/Bilinmiyor |  | Doldu |

> ⚠️ **KM sayacı kritik** — yakıt periyot hesabı (km'den tüketim türetme) bu alana dayanır. Monoton artmalı (yeni fiş eski fişin km'sinden büyük olmalı), aksi halde **satır atılır** (`Odometer error (Skipped)`).
> ⚠️ Yakıt yüklemesi tamamlandıktan sonra **otomatik olarak** `yakit_periyotlari` tablosu güncellenir; sefer tüketim ortalaması bu periyotlardan hesaplanır.

---

## Yükleme Yöntemi

**Tek tek (UI):** her domain için Excel/yükle ekranı var.

**Toplu (büyük dosya, 1000+ satır):**

```bash
curl -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@seferler.xlsx" \
  "https://api.lojinext.com/api/v1/trips/upload?async_mode=true"
# → { "status": "PROCESSING", "task_id": "..." }

# Polling:
curl -H "Authorization: Bearer ${TOKEN}" \
  "https://api.lojinext.com/api/v1/trips/tasks/{task_id}/status"
```

## Hata Yönetimi

Yanıt formatı:
```json
{
  "status": "partial_success",
  "processed": 1000,
  "saved": 985,
  "failed": 15,
  "errors": [
    {"row": 23, "reason": "Araç bulunamadı: '99 NULL 1'"},
    {"row": 87, "reason": "Tarih boş — geçmiş seferler için tarih sütunu zorunlu."}
  ]
}
```

`saved` kadar satır insert edildi (atomic transaction içinde). `failed` satırların hataları **detaylı listelenir**; düzeltip yeniden yükleyebilirsin.

## Production öncesi TRUNCATE

Test verisini temizleyip sıfırdan başlamak için:

```bash
docker compose exec backend python scripts/reset_business_data.py --confirm
```

Korunur: kullanıcılar, roller, migration. Silinir: tüm iş verisi (araç,
şoför, sefer, yakıt, anomali, bakım, lokasyon).
