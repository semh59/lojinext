# Pilot Playbook (Faz 12) — Go-live + 2 Hafta İzleme

> Operatör onboarding + 2 haftalık pilot gözlem kılavuzu. Faz 11 runbook
> (`docs/operations/runbook.md`) ile birlikte kullanılır.

## 1. Operatör hesapları + onboarding

### Hesap oluşturma (admin)
Operatör hesapları admin tarafından açılır:
- UI: **Sistem Yönetimi → Kullanıcılar** (`/admin/kullanicilar`) → yeni kullanıcı
  (email + ad-soyad + rol).
- API: `POST /api/v1/admin/users` (admin yetkisi).

### Roller
- `operator` / `fleet_manager` → günlük operasyon (seferler, yakıt, anomaliler,
  güzergah lab, raporlar). `İçgörü` + `Operasyon` + `Filo` grupları görünür.
- `admin` / `super_admin` → tüm yukarısı + `Sistem` grubu (kullanıcılar, ML,
  sağlık, veri yönetimi, analitik).
- Süper admin: `SUPER_ADMIN_USERNAME`/`PASSWORD` env (DB-user'sız acil erişim).

### Kısa onboarding (operatör)
1. `/login` → email + şifre.
2. **Bugün** (`/today`) — günün triyaj listesi (öncelikli işler).
3. **Seferler** (`/trips`) — sefer girişi/takibi; yakıt (`/fuel`).
4. **Güzergah Lab** (`/route-lab`) — çıkış-varış → segment-bazlı tüketim simülasyonu.
5. **Anomaliler** (`/alerts`) — uyarıları onayla/çöz.
6. **Geri bildirim:** sağ-altta sabit 💬 buton → mesaj → doğrudan OPS ekibine
   (Telegram) düşer.

## 2. İzleme metrikleri — nerede bakılır

| Metrik | Yüzey | Eşik / dikkat |
|--------|-------|----------------|
| **Veri girişi hacmi** | `GET /admin/pilot-status` → `data_volume` | Her gün artmalı (kesintisiz giriş) |
| **Tahmin coverage** | `GET /admin/pilot-status` → `prediction_coverage_pct` + `GET /admin/fuel-accuracy` | Düşerse Open-Meteo 429 / estimator sorunu |
| **Anomali durumu** | `GET /admin/pilot-status` → `anomalies` + `/alerts` | `open` birikmesi = operatör takip etmiyor; çok `resolved-as-false` = FP yüksek |
| **Sistem sağlığı** | `/admin/saglik` (SistemSaglikPage) + `GET /health/readiness` | readiness 503 → DB/Redis sorunu |
| **Sentry hataları** | de.sentry.io (EU region) | **Çözülmemiş kritik = kabul ihlali** |
| **Open-Meteo 429** | backend logları / Prometheus | Artış → tahmin coverage düşer |
| **Pilot feedback** | Telegram OPS kanalı (💬 → `POST /feedback`) | Günlük gözden geçir |

## 3. Gözlem kadansı

- **Günlük (5 dk):** `pilot-status` snapshot (hacim artıyor mu, open anomali
  birikiyor mu); Sentry yeni kritik var mı; OPS kanalında feedback/hata.
- **Haftalık:** `fuel-accuracy` MAPE/RMSE trendi (kalibrasyon kararı için);
  feedback temaları; 429 sıklığı.
- **Yedek:** runbook §4 — en az 1 kez gerçek restore tatbikatı.

## 4. Kabul kriteri (Faz 12)

- [ ] 2 hafta **kesintisiz veri girişi** (`pilot-status.data_volume` sürekli artış).
- [ ] **Çözülmemiş kritik Sentry hatası yok** (2 hafta sonunda).
- [ ] readiness 2 hafta boyunca 200 (kesinti yok / kesintiler runbook'la çözüldü).

## 5. Sınırlar (dış kaynak / bu oturumda yapılamayan)

- VPS + domain + TLS kurulumu (Faz 11 dış kaynak).
- Gerçek operatör hesapları (gerçek isim/email gerektirir).
- 2 haftalık gerçek gözlem süresi.
- Pilot feedback şu an Telegram'a düşer ama DB'de saklanmaz → sayısal trend için
  ileride `pilot_feedback` tablosu eklenebilir (kapsam dışı, opsiyonel).
