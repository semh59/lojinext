# S3 — API endpoints denetimi (authz yüzeyi)

Hedef: her hassas endpoint'te authz (`require_yetki`/`get_current_active_admin`) var mı, IDOR, token/refresh
akışı, hata zarfı, audit log. Authz **endpoint-düzeyinde** (router-düzeyi admin guard YOK — api.py) →
tek eksik `require_yetki` = açık uç.

## S3a-1 — auth + RBAC çekirdek (9 dosya)

Okunan: `api.py` (144), `auth.py` (225), `admin_users.py` (96), `admin_roles.py` (52), `admin_config.py`
(111), `admin_notifications.py` (100), `admin_ws.py` (145), `admin_attribution.py` (107, s2b'de okundu),
`admin_calibration.py` (54, s2b'de okundu).
Temiz/authz tam: `admin_users` (her route require_yetki + audit log), `admin_config` (require_yetki + rate
limit 30/h + audit), `admin_notifications` (admin route'lar require_yetki; /my,/mark-read kullanıcı
route'ları `get_current_active_user` ile owner-scoped — mark_as_read IDOR-guard'lı), `admin_attribution`
(require_yetki attribution_duzenle; mantık AUDIT-081), `admin_calibration` (require_yetki; AUDIT-068/072/075).
Bulgular AUDIT-115…118.

### AUDIT-115 — Süper admin env backdoor: düz-metin env parolası → tüm RBAC + kullanıcı DB baypası, oturum iptali yok
- Şiddet: medium
- Sınıf: security
- Konum: auth.py:64-104
- Durum: confirmed
- Kanıt:
    ```python
    super_admin_pass = settings.SUPER_ADMIN_PASSWORD.get_secret_value() if ... else ADMIN_PASSWORD...
    if super_admin_pass and form_data.username == super_admin_user \
       and secrets.compare_digest(form_data.password, super_admin_pass):
        access_token = jwt_handler.create_access_token(
            data={"sub": super_admin_user, "role": "super_admin", "is_super": True})
    ```
  Tek bir env parolası (`SUPER_ADMIN_PASSWORD`/`ADMIN_PASSWORD`) tüm RBAC'ı ve kullanıcı veritabanını baypas
  eder; `is_super=True` token üretir. `compare_digest` timing-safe (iyi) ama: (1) parola env'de **düz-metin**
  (hash yok), (2) bu hesap DB'de yok → kullanıcı-disable/oturum-iptali ile **revoke edilemez**, (3) MFA yok,
  (4) sızarsa/zayıfsa **tam sistem ele geçirme**. Tek-tenant ops aracı için kasıtlı ama yüksek-değerli sır.
- Önerilen düzeltme: süper admin'i gerçek bir DB kullanıcısına çevir (hash'li parola + revoke edilebilir) ya
  da en azından parolayı hash'le sakla + IP allowlist + MFA + her kullanımı zorunlu audit'le.

### AUDIT-116 — `password-reset-request` non-prod'da reset token'ı yanıtta döndürüyor → hesap ele geçirme
- Şiddet: medium
- Sınıf: security
- Konum: auth.py:197-211
- Durum: confirmed
- Kanıt:
    ```python
    token = await auth_service.request_password_reset(data.email)
    if token and settings.ENVIRONMENT != "prod":
        return {"detail": "Reset token generated", "token": token}
    ```
  `ENVIRONMENT != "prod"` (dev/staging/test) iken sıfırlama token'ı **doğrudan API yanıtında** dönüyor →
  internet'e açık bir staging'de herhangi biri herhangi bir e-posta için token alıp `password-reset-confirm`
  ile **hesabı ele geçirebilir**. AUDIT-022 (token düz-metin saklanıyor) ile birleşince zayıflık katmerlenir.
  (Prod'da doğru: email enumeration'a karşı her zaman 200.)
- Önerilen düzeltme: token'ı hiçbir ortamda yanıtta döndürme; testlerde mock/log üzerinden al. Staging'i
  prod gibi davrandır.

### AUDIT-117 — `create_role` `rol_yaz` ile keyfi-yetkili rol üretebiliyor (privilege escalation) + audit log YOK
- Şiddet: medium
- Sınıf: security / audit-gap
- Konum: admin_roles.py:40-52
- Durum: confirmed
- Kanıt:
    ```python
    @router.post("/", ... dependencies yok; current_user=Depends(require_yetki("rol_yaz")))
    async def create_role(payload: RolCreate, ...):
        return await repo.create(ad=payload.ad, yetkiler=payload.yetkiler)   # yetkiler = keyfi dict
        # log_audit_event çağrısı YOK
    ```
  `rol_yaz` yetkisi olan bir admin, **kendi yetkilerinin üst-kümesini** içeren bir rol oluşturabilir (subset
  kontrolü yok); admin_users.update_user ile bunu bir kullanıcıya (kendine) atayıp **yetki yükseltebilir**.
  Yani `rol_yaz` fiilen süper-yetki. Ayrıca rol oluşturma (güvenlik-kritik) **audit'lenmiyor** (admin_users
  audit'lerken). `create_rule` (admin_notifications) da audit'siz (low).
- Önerilen düzeltme: oluşturulan/atanan yetkileri granter'ın yetki kümesiyle sınırla (subset kontrolü);
  rol create/update'i `log_audit_event` ile audit'le.

### AUDIT-118 — WebSocket auth: token query-param'da (URL log sızıntısı) + blacklist kontrolü yok (revoke token bağlanır) + /training admin-yetkili değil
- Şiddet: medium
- Sınıf: security
- Konum: admin_ws.py:67-101, 118-132
- Durum: confirmed
- Kanıt:
    ```python
    token = websocket.query_params.get("token")     # JWT URL'de → access log/proxy/history'ye sızar
    ...
    payload = jwt.decode(token, get_decode_key(), algorithms=[...], audience=..., issuer=...)
    email = payload.get("sub")     # yalnız imza+aud/iss; token_blacklist KONTROL EDİLMİYOR
    # /training: email doğrulandıktan sonra yetki kontrolü YOK (herhangi bir authenticated kullanıcı)
    ```
  Üç sorun: (1) JWT access token **query param**'da geçiyor → access log, reverse-proxy log, tarayıcı
  geçmişi ve Referer'a sızar. (2) `verify_ws_token` yalnız imza + aud/iss doğruluyor; `token_blacklist`'i
  (logout/revoke) **kontrol etmiyor** → çıkış yapmış/iptal edilmiş bir token ile WS'e bağlanılabilir.
  (3) `/admin/ws/training` ML eğitim ilerlemesini yayınlıyor ama **yetki kontrolü yok** — geçerli token'lı
  herhangi bir kullanıcı bağlanabilir (admin değil).
- Önerilen düzeltme: token'ı ilk mesajda (subprotocol/body) al, query'den çıkar; `verify_ws_token`'a
  blacklist kontrolü ekle; `/training` için admin yetkisi doğrula.

> Notlar (low / iz):
> - `auth.login` rate limit 5/s (300/dk) brute-force için gevşek; `auth.refresh` rate-limit'siz. (low)
> - api.py: tüm admin authz endpoint-düzeyinde (router-düzeyi admin guard yok) → bir endpoint require_yetki
>   unutursa açık kalır; bu yüzden her admin endpoint tek tek doğrulanıyor (S3a-2'de devam). (iz)
> - `admin_attribution`/`admin_calibration` endpoint authz'ı tam; iş mantığı bulguları AUDIT-081/068/072/075.

## S3a-2 — operasyonel admin endpoint'leri (7 dosya)

Okunan: `admin_imports.py` (147), `admin_maintenance.py` (258), `admin_ml.py` (81), `admin_health.py` (54),
`admin_fuel_accuracy.py` (174), `admin_pilot.py` (88), `admin_predictions.py` (24).
Authz tam: hepsi `require_yetki`/`get_current_active_admin`. `admin_fuel_accuracy` raw SQL parametreli
(f-string yalnız placeholder enjekte ediyor, değer params'tan → enjeksiyon yok), `admin_pilot` hardcoded SQL.
Not: `admin_maintenance.get_upcoming_alerts` AUDIT-093'e (tz crash) düşer; `admin_health.trigger_manual_backup`
AUDIT-091 (sahte task_id). Bulgular AUDIT-119…120.

### AUDIT-119 — `trigger_prediction_backfill` inline çalışıyor, limit≤500 → çok-dakikalık senkron HTTP isteği
- Şiddet: medium
- Sınıf: performance / availability
- Konum: admin_predictions.py:13-23
- Durum: confirmed
- Kanıt:
    ```python
    @router.post("/predictions/backfill")
    async def trigger_prediction_backfill(limit: int = Query(50, ge=1, le=500), _admin=...):
        return await PredictionBackfillService().backfill(limit=limit)   # INLINE, await ile bekler
    ```
  Backfill servisi (AUDIT-096) sefer başına çok-saniyelik estimator (Mapbox+Open-Meteo) + 0.5s throttle
  uyguluyor; `limit` **500'e kadar** olabilir → tek HTTP isteği ~500 × (saniyeler + 0.5s) = **30+ dakika**
  senkron çalışır. İstek timeout'a düşer, worker bloke olur, UoW/bağlantı tüm süre boyunca açık kalır
  (AUDIT-096 amplifiye). CLAUDE.md async-job pattern (202 + task_id) burada uygulanmamış.
- Önerilen düzeltme: `BackgroundJobManager.submit(...)` ile 202 + task_id döndür; gece beat task'i zaten var.

### AUDIT-120 — Admin yazma/operasyon endpoint'lerinde tutarsız audit kapsamı
- Şiddet: low
- Sınıf: audit-gap
- Konum: admin_maintenance.py:65,253; admin_ml.py:24; admin_health.py:34,48; admin_predictions.py:14; admin_notifications.py:47
- Durum: confirmed
- Kanıt:
    ```python
    # log_audit_event ÇAĞRISI YOK olan mutasyonlar:
    create_maintenance (admin_maintenance.py:65), mark_complete (:253),
    trigger_training (admin_ml.py:24), reset_circuit_breaker (admin_health.py:34),
    trigger_manual_backup (admin_health.py:48), trigger_prediction_backfill (admin_predictions.py:14),
    create_rule (admin_notifications.py:47)
    ```
  admin_users/admin_config/admin_imports state değiştiren işlemlerini `log_audit_event` ile audit'lerken,
  yukarıdaki güvenlik/operasyon-kritik mutasyonlar (bakım kaydı, model eğitim tetik, circuit-breaker reset,
  backup, backfill, bildirim kuralı) **audit'lenmiyor** → tutarsız iz kaydı, olay-müdahalede boşluk.
  (AUDIT-117 rol create/update audit'i bunun bir alt-kümesi.)
- Önerilen düzeltme: tüm admin write/op endpoint'lerine standart `log_audit_event` ekle (dekoratör veya
  ortak dependency ile zorla).

## S3b-1 — domain endpoints: internal/users/ws_ticket/health/feedback/predictions/ai (7 dosya)

Authz/güvenlik **örnek** olanlar: `internal.py` (router-düzeyi `_require_internal_token` + belge upload'da
allowlist + boyut + **magic-byte sniff** → AUDIT-097'nin endpoint enforcement'ı burada doğru), `health.py`
(public endpoint `error`/AI-internals'i `_PUBLIC_COMPONENT_FIELDS` ile sıyırıyor → AUDIT-110 leak'ini public'te
önler), `ws_ticket.py` (tek-kullanımlık Redis ticket — admin_ws'in token-query'sinin tersine **doğru** WS-auth
deseni), `feedback.py` (auth + bounded). Bulgu AUDIT-121.

### AUDIT-121 — `GET /users/` tüm kullanıcı dizinini (email + rol+yetkiler + son_giris_ip) herhangi bir authenticated kullanıcıya açıyor
- Şiddet: medium
- Sınıf: security / info-disclosure
- Konum: users.py:83-91 ↔ schemas/user.py KullaniciRead
- Durum: confirmed
- Kanıt:
    ```python
    @router.get("/", response_model=List[KullaniciRead])
    async def list_users(current_user: ...Depends(get_current_active_user)..., skip, limit):
        return await service.list_users(skip=skip, limit=limit)   # YETKİ KONTROLÜ YOK
    ```
  `/admin/users` `require_yetki("kullanici_goruntule")` ile korunurken, `/users/` aynı `list_users`'ı
  **yalnız authentication** ile sunar. `KullaniciRead` email, `rol` (RolRead → **yetkiler dict**),
  `son_giris_ip`, son_giris, sifre_degisim_tarihi içerir → düşük-yetkili herhangi bir kullanıcı (ör. bir
  sürücü hesabı) **tüm kullanıcı dizinini + herkesin yetki setini + son login IP'lerini** çekebilir. RBAC
  keşfi + PII ifşası.
- Önerilen düzeltme: `/users/` listesini `require_yetki("kullanici_goruntule")` ile koru ya da kaldır
  (admin_users zaten var); en azından response'u minimal alanlara (id, ad_soyad) indir.

> Notlar (low / iz):
> - `internal._require_internal_token` token'ı `!=` ile karşılaştırıyor (constant-time değil) → timing
>   sızıntısı (iç ağ, düşük). (low)
> - `predictions.prediction_status`/`/stream` `task_id`'yi ownership kontrolü olmadan okur (celery UUID =
>   capability; sızarsa başka kullanıcının tahmin yanıtı görülür). (low)
> - `ai.chat`/`query` her authenticated kullanıcıya RAG/DB üzerinden filo verisi sunar (per-user data scoping
>   yok) — tek-tenant veri modeliyle tutarlı (AUDIT-121 ile aynı kök); AI prompt sanitizasyonu AUDIT-064. (iz)
> - `feedback.submit_feedback` username'i `kullanici_adi`/`username` attr'ından alıyor ama Kullanici'de bu
>   alanlar yok (email/ad_soyad var) → OPS'a giden feedback'te username hep boş. (low)
> - `predictions.train_vehicle_model` admin-gated (doğru); kalan predict/forecast/explain authenticated.

## S3b-2 — fuel + drivers (2 dosya)

Authz **doğru** ayrılmış (read=`get_current_active_user`, write=`get_current_active_admin`/
`require_permissions`). `fuel.py` temiz: OCR önizleme + Excel upload'da MIME + magic-byte + boyut +
streaming-chunk limit; delete_yakit endpoint'te `log_audit_event` (AUDIT-032'nin servis-katmanı boşluğunu
endpoint'te kapatıyor). Bulgu AUDIT-122.

### AUDIT-122 — `SoforResponse` ham `telefon`'u (PII) döndürüyor → `telefon_masked` kozmetik kalıyor
- Şiddet: medium
- Sınıf: security / pii
- Konum: drivers.py:37-77,280-289 ↔ schemas/sofor.py SoforResponse (telefon + telefon_masked)
- Durum: confirmed
- Kanıt:
    ```python
    # SoforResponse(SoforBase) → SoforBase.telefon: Optional[str]  (HAM telefon serialize edilir)
    #                          + @computed_field telefon_masked     (maskeli)
    # drivers.read_soforler / read_sofor → SoforResponse döner (her authenticated kullanıcı)
    ```
  `SoforResponse` hem miras alınan **ham `telefon`** alanını hem de `telefon_masked` computed alanını
  serialize eder → liste/detay JSON yanıtlarında şoför telefon numarası (PII) **tam** görünür; maskeleme
  fiilen işe yaramıyor. Excel export (drivers.py:213-225) telefon'u açıkça çıkarıyor → JSON ile export
  tutarsız, JSON sızdırıyor. Her authenticated kullanıcı tüm şoför telefonlarını çekebilir (AUDIT-121 ile
  aynı sınıf, PII).
- Önerilen düzeltme: `SoforResponse`'tan ham `telefon` alanını çıkar (yalnız `telefon_masked` döndür) ya da
  `field_serializer`/`exclude` ile ham alanı yanıttan gizle; tam telefon yalnız yetki gerektiren bir
  endpoint'te dönsün.

## S3b-3 — anomalies / investigations / vehicles (3 dosya) — 0 yeni bulgu (temiz)

- `anomalies.py`: read'ler `get_current_active_user`, action'lar (acknowledge/resolve) `require_permissions
  ("anomali:yonet")` + `log_audit_event`. Authz ayrımı doğru. (Not: `/fleet/insights` AUDIT-012'ye
  (kartezyen maliyet) düşer — veri yanlış ama authz doğru.)
- `investigations.py`: **örnek modül** — tüm endpoint'ler `require_permissions` (read/write ayrı) +
  `_ensure_enabled` feature flag + `log_audit_event`; raw SQL parametreli; OPS Telegram bildiriminde
  `html.escape(plaka/sofor)` (HTML injection önlenir); IntegrityError ile race handling; route ordering
  (/patterns, /{id}'den önce) doğru. 0 bulgu.
- `vehicles.py`: read=user, write(create/update/delete/clear-all/upload)=admin + audit; upload MIME+ext+
  boyut+chunked-read; inspection-alerts/fleet-stats parametreli SQL. (Not: `read_arac` → AracResponse →
  AUDIT-105 heal_yil 500; `/clear-all` mass-delete admin-gated+audit, dikkat.) 0 yeni bulgu.

## S3b-4 — advanced_reports / error_stream / executive / analytics / coaching / fleet_insights (6 dosya)

Örnek/temiz: `error_stream.py` (SSE auth: admin-only **tek-kullanımlık 90s Redis token**, ilk kullanımda
silinir + DB'den admin yeniden doğrulanır + semafor cap + disconnect/cleanup → admin_ws/AUDIT-118'in
izlemesi gereken desen), `executive.py` (her endpoint require_yetki + feature flag + audit + singleton Redis
client; what-if endpoint variant-eşleşmesini doğruluyor → **AUDIT-112 endpoint'te mitige**; bus-factor PII-anon),
`analytics.py`, `coaching.py` (require_permissions + HTML-escape Telegram + audit), `fleet_insights.py`
(audit + flag; AUDIT-089 servis-tarafı). Bulgu AUDIT-123.

### AUDIT-123 — `advanced_reports` finansal raporları yalnız authentication ile açık (executive permission-gated iken)
- Şiddet: medium
- Sınıf: security / authz-inconsistency
- Konum: advanced_reports.py:204-298 (cost/period, cost/roi, cost/savings-potential, cost/vehicle-comparison)
- Durum: confirmed
- Kanıt:
    ```python
    @router.get("/cost/roi", response_model=ROIResponse)
    async def get_roi_analysis(..., current_user: ...Depends(get_current_active_user)...):  # yalnız authn
    # karşılaştır: executive.py her endpoint require_yetki(["super_admin","fleet_manager","yonetim_rapor"])
    ```
  `advanced_reports`'taki maliyet/ROI/tasarruf/araç-karşılaştırma finansal raporları **yalnız
  authentication** ile korunuyor → herhangi bir authenticated kullanıcı (ör. düşük-yetkili sürücü hesabı)
  filo maliyet/ROI/tasarruf analizlerine erişebilir. Aynı sınıf finansal rapor `executive.py`'de
  `yonetim_rapor`/`fleet_manager` yetkisi gerektiriyor → **tutarsız yetkilendirme**. AUDIT-121/122 ile aynı
  "authenticated = her şeyi görür" kök sorunu.
- Önerilen düzeltme: finansal/yönetim raporlarına `require_yetki(["...","yonetim_rapor"])` ekle (executive
  ile tutarlı).

> Notlar (low / iz):
> - `advanced_reports./pdf/vehicle` → `ReportService.generate_vehicle_report` gather → **AUDIT-099** (canlı
>   crash); excel export'lar → **AUDIT-087** (formül enjeksiyonu); `/excel/template` FileResponse →
>   **AUDIT-088** (yerel dosya). Hepsi filed.
> - `advanced_reports.get_vehicle_report_pdf` filename'i sanitize ediyor (header injection guard) — iyi.
> - `coaching.get_coaching_insights` / `fleet_insights` herhangi authenticated kullanıcıya açık (tek-tenant
>   veri modeli, AUDIT-121 kökü). (iz)

## S3b-5 — kalan 12 endpoint (preferences/push/reports_studio/today_triage/reports/weather/system/trailers/routes/locations/trips/utils) — 1 bulgu

Temiz/örnek:
- `trips.py` (22 route — **en iyi modül**): her endpoint `require_permissions(sefer:read/write/onayla)` +
  IDOR-isolation (`service.get_by_id(sefer_id, current_user=...)`) + audit + bulk 500-limit + rate limit;
  upload MIME+ext+boyut+chunked. 0 bulgu.
- `locations.py`: write'lar admin + audit (pre/post snapshot); `search_by_route` ILIKE `%`/`_` escape; hydrate
  admin-gated (yorum quota gerekçeli). `routes.py`: rate-limit + transactional persist (AUDIT-071'in tersine
  doğru). `system.py`: admin-gated, enum-allowlist + parametreli SQL. `reports.py`: paylaşılan session'da
  **sıralı await** (AUDIT-099'un doğru çözümü — service gather'larına uygulanmamış). `preferences`/`push`
  owner-scoped (AUDIT-076/079/113/114 zaten filed). `today_triage`/`reports_studio`/`weather`/`utils` temiz.

### AUDIT-124 — Upload endpoint'lerinde tutarsız doğrulama: trailers + locations upload MIME/boyut kontrolsüz
- Şiddet: medium
- Sınıf: security / dos
- Konum: trailers.py:146-156 (import_trailers), locations.py:454-465 (upload_guzergahlar)
- Durum: confirmed
- Kanıt:
    ```python
    # trailers.import_trailers / locations.upload_guzergahlar:
    content = await file.read()            # MIME yok, boyut yok, chunked yok → sınırsız
    result = await service.import_trailers(content)
    ```
  `trips`/`vehicles`/`drivers`/`fuel` upload'ları MIME allowlist + 10MB + chunked-read doğruluyor (örnek),
  ama `trailers.import_trailers` ve `locations.upload_guzergahlar` dosyayı **hiç doğrulamadan** `file.read()`
  ile tümüyle belleğe alıyor → sınırsız upload (RAM tüketimi/DoS) + tip doğrulaması yok (admin-gated olsa da).
- Önerilen düzeltme: diğer upload'lardaki MIME+boyut+chunked-read kontrolünü bu iki endpoint'e de uygula
  (ortak `validate_excel_upload(file)` helper'ı ile tek kaynak).

> Not: `trips.create_sefer` SeferResponse.model_validate'i try/except ile sarıp ValidationError'ı 500'e
> mapliyor → AUDIT-105/108 healing-500'leri burada gözlemlenebilir (ekip farkında).
> **S3 (API yüzeyi) tamamlandı: 44 endpoint + api.py + utils.py.** Authz genel olarak güçlü; bulgular
> AUDIT-115→124 (auth/WS/users-dizini/PII/upload/authz-tutarsızlık) + healing-500 (AUDIT-105) yüzeyi.
