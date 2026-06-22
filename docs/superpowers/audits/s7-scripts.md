# S7 — Scripts + Microservices Bulguları

Kapsam: scripts/** (27) + telegram_bot/** (3) + ocr_service/** (2) = 32 dosya. Plan S7.

## S7 — scripts(27) + telegram_bot(3) + ocr_service(2) — 6 bulgu (high 1)

Temiz/örnek: `e2e_pilot_smoke` (env-zorunlu şifre, default REDDEDER — doğru desen); `p51_real_world_validation`/
`calibrate_physics`/`validate_tractive_offline` (idempotent validation harness, overfit guard, Open-Meteo PACE);
`train_elite_ensemble`/`train_model_with_route_features` (production `service.train_for_vehicle` kullanır);
`driver_bot` (Telegram-auth kimlik, html.escape, internal-token); `ocr_processor` (asyncio.to_thread); mapbox
probe'ları (Phase-0 dökümantasyon — road_class 422 bulgusu zaten production'da düzeltilmiş).

### AUDIT-166 — ops_bot /yeniden_baslat per-user yetkilendirme YOK → bot'a ulaşan herkes docker servis restart edebilir (DoS); webhook server (8080) kimlik doğrulamasız
- Şiddet: medium
- Sınıf: security
- Konum: ops_bot.py:78-105,113-193
- Durum: confirmed
- Kanıt:
    ```python
    async def cmd_yeniden_baslat(update, context):
        servis = context.args[0]
        IZIN_VERILEN = {"backend","worker","redis",...}   # HANGİ servis sınırlı
        # ... AMA update.effective_user.id authz kontrolü YOK
        subprocess.run(["docker","restart", container_pattern], ...)   # docker socket mount
    @webhook_app.post("/webhook/error")   # token yok — 8080'e ulaşan herkes ops kanalına mesaj enjekte eder
    ```
  `/yeniden_baslat` komutu hangi servisi (allowlist) kısıtlıyor ama KİM'i kısıtlamıyor — botu bulan herhangi
  bir Telegram kullanıcısı backend/worker/redis/ocr restart edebilir (mounted docker socket → DoS). Güvenlik
  yalnız bot'un gizliliğine dayanıyor (security-by-obscurity). Ayrıca webhook server'ın (port 8080)
  `/webhook/error|feedback|alertmanager` uçları kimlik doğrulamasız → 8080'e ulaşan herhangi biri ops
  Telegram kanalına sahte alarm/spam enjekte eder (notification injection).
- Önerilen düzeltme: cmd handler'larda `update.effective_user.id` allowlist (OPS_USER_IDS env) kontrolü;
  webhook'lara shared-secret header (INTERNAL_API_SECRET) ekle.
- Bağımlılık: telegram_notifier (webhook çağıran), internal.py (shared-secret deseni).

### AUDIT-167 — ocr_service /ocr/process kimlik doğrulamasız + upload boyut/tip limiti yok → erişilebilirse kaynak suistimali/DoS
- Şiddet: medium
- Sınıf: security
- Konum: ocr_service/main.py:19-26
- Durum: needs-verification
- Kanıt:
    ```python
    @app.post("/ocr/process")
    async def process_image(file: UploadFile = File(...), belge_tipi: str = Form(...)):
        image_bytes = await file.read()           # boyut limiti yok
        return await _processor.process(image_bytes, belge_tipi)   # easyocr CPU-ağır
    ```
  OCR endpoint kimlik doğrulaması yok (shared-secret/token); docker-network içi olsa da port maruz kalırsa
  herkes CPU-ağır easyocr'ı tetikleyebilir. Upload boyut/MIME kontrolü yok → dev bir görsel OOM/DoS (AUDIT-124
  ailesi). Ağ izolasyonu doğrulanmalı.
- Önerilen düzeltme: shared-secret header doğrulaması (telegram bot zaten X-Internal-Token gönderiyor); max
  upload boyutu + MIME doğrulaması ekle.
- Bağımlılık: AUDIT-124 (upload doğrulama), ocr_tasks (çağıran).

### AUDIT-168 — Script'lerde SABİT-KODLANMIŞ düz-metin parolalar (repo'da): aynı parola ×3 dosya + süper-admin şifresi stress_import default'unda
- Şiddet: high
- Sınıf: security
- Konum: reset_password.py:15, create_db.py:14, elite_audit_backend.py:21, stress_import.py:32, fix_partitions.py:9
- Durum: confirmed
- Kanıt:
    ```python
    # reset_password.py / elite_audit_backend.py
    NEW_PASSWORD = "<sabit-parola>"        # USERNAME = "skara"
    # create_db.py
    password="<sabit-parola>"              # postgres SUPERUSER parolası (aynı string)
    # stress_import.py
    ADMIN_PASS = os.getenv("SUPER_ADMIN_PASSWORD", "<gercek-super-admin-pw>")   # env yoksa default
    # fix_partitions.py
    password = "lojinext_pass_2026"  # pragma: allowlist secret  (kabul edilmiş dev cred)
    ```
  Aynı düz-metin parola üç committed script'te (postgres superuser + 'skara' kullanıcı parolası); stress_import
  süper-admin parolasını env yoksa default olarak gömüyor. Bunlar version control'da → repo erişimi olan
  herkese kredansiyel sızıntısı; detect-secrets bu string'leri yakalamadı (pattern eşleşmiyor, pragma yok).
  e2e_pilot_smoke.py DOĞRU deseni gösteriyor (env zorunlu, default reddediyor: `raise SystemExit`).
- Önerilen düzeltme: tüm sabit parolaları env'den oku, default verme; sızan parolaları rotate et;
  detect-secrets baseline'ını güncelle. (Gerçek değerler bu dosyada tekrar yazılmadı.)
- Bağımlılık: AUDIT-115 (super-admin backdoor), AUDIT-022 (reset-token), 0002 seed (ADMIN_PASSWORD).

### AUDIT-169 — seed_demo_data Türkçe durum ('Tamam'/'Bekliyor') 0022 sonrası İngilizce CHECK'i ihlal eder → demo seed kırık
- Şiddet: low
- Sınıf: bug
- Konum: seed_demo_data.py:167-169,271
- Durum: confirmed
- Kanıt:
    ```python
    # Valid values from check_sefer_durum_enum: Bekliyor, Yolda, Tamam, ...  ← ESKİ (pre-0022) yorum
    DURUM_CHOICES = ["Tamam", "Tamam", "Tamam", "Bekliyor"]
    ... durum=random.choice(DURUM_CHOICES)   # 0022 sonrası CHECK yalnız Planned/Completed/Cancelled
    ```
  Sefer seed `durum='Tamam'/'Bekliyor'` (Türkçe) yazıyor; 0022 CHECK'i İngilizce-only yaptı → INSERT CHECK
  ihlali → demo seed patlar. yakit seed `durum='Onaylandi'` (ASCII) 0006 CHECK ile tutarlı (bu kısım doğru).
- Önerilen düzeltme: DURUM_CHOICES → ['Completed','Completed','Completed','Planned']; yorumu güncelle.
- Bağımlılık: AUDIT-164 (durum default), AUDIT-163, trip_status canonical.

### AUDIT-170 — Çok sayıda ops/dev script bozuk veya şema-ıraksak (çalıştırılırsa hata/no-op/veri bozar)
- Şiddet: low
- Sınıf: bug/dead-code
- Konum: enrich_existing_data.py:86,96,117,54; train_model_with_route_features.py:33; init_ml_db.py:28; cleanup_locations_normalization.py:39; e2e_error_smoke.py:24+
- Durum: confirmed
- Kanıt:
    ```python
    # enrich_existing_data: ASYNC client metotları AWAIT'siz → coroutine, sonra origin[0] → TypeError
    origin = client.geocode(sefer.cikis_yeri)         # await YOK (geocode async)
    analysis = client.get_distance(...)               # await YOK
    stmt = select(Sefer).where(Sefer.durum == "Tamam")  # 0022 sonrası 0 satır
    # train_model_with_route_features: .where(Sefer.durum == "Tamam") → 0 araç (sessiz no-op)
    # init_ml_db: CREATE TABLE model_versions  (ORM 'model_versiyonlar' kullanır → phantom tablo, alembic bypass)
    # cleanup_locations_normalization: new_cikis = old.strip().title()  (Türkçe İ/ı bozar — AUDIT-074)
    # e2e_error_smoke: headers={"Authorization":"Bearer valid_token"}  (sahte → her şey 401; AssertionError
    #   yutulur, exit hep 0 → yanıltıcı smoke)
    ```
  Bir grup dev/ops script latent tuzak: `enrich_existing_data` async client'ı await etmiyor → çalıştırılınca
  çöker (+ obsolet 'Tamam' filtresi); `train_model_with_route_features` 'Tamam' filtresiyle 0 araç bulur
  (sessiz no-op); `init_ml_db` ORM şemasıyla çelişen phantom `model_versions` tablosu yaratır (alembic
  baypas); `cleanup_locations_normalization` .title() ile Türkçe lokasyon adlarını bozar (DB'ye yazar);
  `e2e_error_smoke` sahte token'larla tüm istekleri 401'e düşürür, hataları yutar, hep exit 0 (yanıltıcı).
- Önerilen düzeltme: enrich_existing_data'ya await ekle + durum'u canonical'a çevir; init_ml_db'yi sil (alembic
  var); cleanup'ı Türkçe-güvenli normalize ile değiştir; e2e_error_smoke'a gerçek auth + nonzero exit ekle ya
  da pytest'e taşı. Kullanılmayanları arşivle/sil.
- Bağımlılık: AUDIT-164 (durum), AUDIT-074/109 (.title() Türkçe), AUDIT-009 (create_all bypass), openroute async.

### AUDIT-171 — Manuel retrain→deploy pipeline'ı doğrulama kapısı yok: v3 pkl'leri production model yoluna körlemesine kopyalar + production ensemble akışından ıraksak
- Şiddet: low
- Sınıf: reliability
- Konum: retraining/retrain_models.py:64-78, retraining/deploy_new_models.py:32-37
- Durum: needs-verification
- Kanıt:
    ```python
    # retrain_models: standalone XGBoost, cv=min(len(X),5) küçük veride güvenilmez R²
    joblib.dump(model, f"app/core/ml/models/vehicle_{vehicle_id}_v3.pkl")
    # deploy_new_models: v3 → production adı, KALİTE KAPISI YOK
    for v3_file in glob(".../vehicle_*_v3.pkl"):
        shutil.copy(v3_file, dest)   # R²/sanity kontrolü olmadan production'a aktar
    ```
  `retrain_models.py` standalone XGBoost ile per-araç model eğitir (production `ensemble_service` akışından
  ıraksak; küçük veride cv R² güvenilmez), `deploy_new_models.py` bu `_v3.pkl`'leri production model adına
  doğrulama kapısı OLMADAN kopyalar → kötü/overfit model sessizce production'a düşebilir. Ayrıca production
  loader checksum/meta sidecar bekliyorsa (ensemble_core SHA256) bu manuel pkl'ler reddedilip physics
  fallback'e düşebilir (verify gerek).
- Önerilen düzeltme: deploy öncesi R²/sanity eşiği + holdout doğrulaması; production `train_for_vehicle` akışına
  birleştir (train_elite_ensemble gibi); checksum sidecar üret.
- Bağımlılık: ensemble_service/ensemble_core (AUDIT-126), train_elite_ensemble (doğru desen).

> **S7 TAMAMLANDI: 32 dosya (27 script + 3 telegram + 2 ocr). Bulgular AUDIT-166..171 (6 bulgu, high 1=AUDIT-168 sabit-kodlu parolalar). Validation/training harness'leri ve e2e_pilot_smoke örnek kalitede; ana sorunlar: committed kredansiyeller, microservice authz boşlukları, durum-drift'ten kırık dev script'ler.**
