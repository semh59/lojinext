# LojiNext — Tam Prod Hazırlık Denetimi
**Tarih:** 2026-06-21
**Kapsam:** Security · Reliability · DB/ORM · Frontend · CI/CD · Ops

---

## ÖZET PUAN TABLOSU

| Alan | Durum | Kritik Sorun |
|------|-------|--------------|
| Frontend testler | ✅ 150/150 PASS | — |
| Frontend build/lint | ✅ Temiz | — |
| Backend security | ✅ İyi | — |
| DB şema + index | ⚠️ 2 eksik index | PredictionResult.status, Anomaly compound |
| Alembic drift | ✅ CI'da kontrol | — |
| CI/CD pipeline | ⚠️ Var ama VPS secrets boş | GitHub Secrets ayarlanmamış |
| E-posta servisi | ❌ YOK | Şifre sıfırlama prod'da çalışmıyor |
| Otomatik DB yedek | ❌ YOK | Celery beat'te zamanlanmış yedek görevi yok |
| Rate limiting | ✅ Auth/upload/AI'da | — |
| Hata sınırı (frontend) | ✅ App.tsx'te | — |
| Sentry | ⚠️ Config eksik | .env.prod'da SENTRY_DSN yok |
| Yedek off-site | ❌ Yalnız lokal dizin | Bulut yedek yok |

---

## BULGULAR — DERİNLEMESİNE

### SEKSİYON 1: GÜVENLİK

**SEC-001 ✅ JWT token blacklist — fail-secure**
`app/infrastructure/security/token_blacklist.py`: Redis unavailable olduğunda `is_blacklisted()` → `True` döner (token revoked kabul edilir). Bu doğru yöntem; Redis outage sırasında logout edilmiş token'ların geçerli görünmesini engeller.

**SEC-002 ✅ CORS prod validation**
`app/config.py:300`: Prod'da `CORS_ORIGINS='*'` yasaklı; `settings.cors_origins` boşsa `ValueError` fırlatır.

**SEC-003 ✅ Rate limiting — auth endpoints**
Login: 5/sn, password-reset-request: 2/dakika, password-reset-confirm: 5/dakika. Nginx'te auth zone: 10r/m ekstra.

**SEC-004 ✅ Dosya upload validasyonu**
`locations.py`, `fuel.py`, `drivers.py` tüm upload endpoint'lerinde: content-type whitelist + filename uzantı kontrolü + max boyut (413).

**SEC-005 ✅ Şifre sıfırlama güvenliği**
`auth_service.py:228-260`: `secrets.token_urlsafe(32)` (256-bit), DB'de SHA-256 hash, 1 saatlik geçerlilik, sıfırlamadan sonra tüm oturumlar iptal, e-posta enumeration koruması (her zaman 200 döner).

**SEC-006 ✅ SQL injection yok**
`system.py:209-213` raw SQL kullanıyor ama `conditions` listesi hardcoded sabit string'lerden, değerler parameterized `params` dict'te. Güvenli.

**SEC-007 ✅ subprocess güvenli**
`backup_manager.py:65-78`: `pg_dump` list form kullanıyor (shell injection yok), parola PGPASSWORD env var ile (argüman değil).

**SEC-008 ✅ Super admin bypass — sabit zamanlı karşılaştırma**
`auth.py:73`: `secrets.compare_digest()` — timing attack yok.

---

### SEKSİYON 2: GÜVENİLİRLİK

**REL-001 ✅ Celery task limit'leri**
`soft_time_limit=70s`, `time_limit=90s`, `acks_late=True`, `prefetch_multiplier=1`. Doğru yapılandırma.

**REL-002 ✅ DB bağlantı havuzu matematiksel güvenli**
`pool_size=40 + max_overflow=5 = 45 bağlantı/worker × 4 UVICORN_WORKERS = 180`.
`max_connections=200` (docker-compose.yml:129). Güvenli marj: 20 bağlantı.

**REL-003 ✅ Circuit breaker / outbox relay**
`relay-outbox-events-every-60s` Celery task mevcut. Transactional outbox pattern doğru implement edilmiş.

**REL-004 ✅ Background task GC koruması (AUDIT-130)**
`model_training_handler.py:30,83-85`: `_bg_tasks: set` + done callback. Task'lar GC'den korunuyor.

**REL-005 ⚠️ PredictionResult.status — index yok**
`app/database/models.py:1300`: `status` kolonu `String(32)`, `nullable=False`, index yok.
`admin_predictions.py`'de polling sorgularında tam table scan yapılıyor. Yük altında yavaşlar.
**Fix:** Alembic migration ekle — `Index("ix_prediction_results_status", "status")`.

---

### SEKSİYON 3: VERİTABANI ŞEMASI

**DB-001 ✅ Anomaly tablosu birincil index'ler**
`tarih` (index), `tip` (index), `kaynak_id` (index), composite `(kaynak_tip, kaynak_id)` (idx_anomaly_kaynak).

**DB-002 ⚠️ Anomaly — eksik composite filtre index'i**
Dashboard'da `?status=open|acknowledged|resolved` filtresi `acknowledged_at IS NULL AND resolved_at IS NULL` kombinasyonu kullanıyor. `acknowledged_at` ve `resolved_at` bağımsız index'lere sahip ama `(resolved_at, acknowledged_at)` compound index yok. Büyük tablolarda iki index'in merge'ü yavaş.
**Fix:** `Index("idx_anomaly_status_combo", "resolved_at", "acknowledged_at")` migration.

**DB-003 ✅ Sefer tablosu index kapsamı**
`(durum, tarih)`, `(arac_id, tarih DESC)`, `(sofor_id, tarih DESC)`, `(arac_id, durum)` — sık sorgulanan kombinasyonlar kapsanmış.

**DB-004 ✅ OutboxEvent index'leri**
`processed` ve `created_at` bağımsız index'ler — relay task için yeterli.

**DB-005 ✅ FK ondelete doğru**
RESTRICT (sefer→arac, sefer→sofor), CASCADE (log→sefer, belge→sofor), SET NULL (sefer→lokasyon, created_by) — iş kurallarıyla uyumlu.

**DB-006 ✅ 32 Alembic migration, CI'da `alembic check`**
Drift koruması var. Son migration: `0029_sefer_durum_dual_fix.py`.

---

### SEKSİYON 4: FRONTEND

**FE-001 ✅ Test kapsamı — 150/150 dosya PASS**
1196 test, 0 fail, 0 error. `npm run lint` ve `npm run build` temiz.

**FE-002 ✅ Error boundary**
`App.tsx:65,175`: `<ErrorBoundary>` tüm rota ağacını kaplıyor. `componentDidCatch` implement edilmiş.

**FE-003 ✅ Bundle büyüklüğü**
Vite build başarılı. En büyük chunk: `CategoricalChart-D1k1H5Ql.js` 303KB (gzip: 93KB) — kabul edilebilir.

**FE-004 ⚠️ React Router v6 future flag uyarıları**
Test output'unda:
```
⚠️ React Router: v7_startTransition future flag
⚠️ React Router: v7_relativeSplatPath future flag
```
Şu an kırılmıyor ama React Router v7'ye geçildiğinde breaking change.
**Fix:** `MemoryRouter` test wrapper'ına `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}` ekle.

---

### SEKSİYON 5: CI/CD PİPELİNE

**CI-001 ✅ Pipeline aşamaları tam**
Lint → mypy → alembic check → pytest (unit+security+integration) → vitest+build → npm audit → publish → deploy-staging → deploy-production.

**CI-002 ✅ Coverage gate**
`--cov-fail-under=92` — doğrulanmış.

**CI-003 ⚠️ VPS GitHub Secrets ayarlanmamış**
`deploy-staging` ve `deploy-production` job'ları `STAGING_HOST`, `STAGING_SSH_KEY`, `STAGING_USER`, `STAGING_DEPLOY_PATH`, `PROD_HOST`, `PROD_SSH_KEY`, `PROD_USER`, `PROD_DEPLOY_PATH` bekliyor. Bu secret'lar GitHub repository Settings → Secrets'a girilmedikçe deploy job'ları başarısız olur.
**Fix:** VPS kurulumu + secret'ların GitHub'a girilmesi gerekiyor.

**CI-004 ✅ Docker image publish**
`IMAGE_TAG` output olarak geçiriliyor, `publish` job`da `continue-on-error` kaldırılmış.

---

### SEKSİYON 6: OPERASYONEl HAZIRLIK

**OPS-001 ❌ E-posta servisi YOK (KRİTİK)**
`app/api/v1/endpoints/auth.py:200`: `auth_service.request_password_reset(data.email)` bir token üretiyor ama bu token'ı hiçbir yere GÖNDERMİYOR. `app/config.py`'de SMTP konfigürasyonu yok. Prod'da token sadece dev log'una yazılıyor (`if settings.ENVIRONMENT != "prod"`) — prod'da sessizce atılıyor.

Sonuç: **Prod'da kullanıcılar şifrelerini sıfırlayamıyor.** Birisi parolasını unutursa admin müdahale etmek zorunda.

**Fix seçenekleri (öncelik sırasıyla):**
1. `resend.com` veya `sendgrid` entegrasyonu (async, SMTP yok)
2. `fastapi-mail` + SMTP (gmail/SES)
3. Geçici çözüm: Super admin reset endpoint'i → admin kullanıcıya bildirim

**OPS-002 ❌ Otomatik veritabanı yedeği YOK (KRİTİK)**
`app/infrastructure/background/celery_app.py:35-101`: 11 zamanlanmış Celery görevi var — coaching, ML, anomaly, outbox, vs. Hiçbirisi veritabanı yedeği almıyor.

`DatabaseBackupManager` ve `/admin/health/backup/trigger` endpoint'i var ama zamanlanmış çalıştırılmıyor.

Sonuç: **Veri kaybına karşı koruma yok.** Prod'da veri bozulması/silinmesi durumunda restore imkânı belirsiz.

**Fix:** Celery beat'e `backup-daily-at-midnight: {task: "infrastructure.db_backup", schedule: crontab(hour=0, minute=30)}` ekle + backup task worker'ı yaz.

**OPS-003 ❌ Off-site yedek yok**
`backup_manager.py:21`: `backup_dir = "storage/backups"` — aynı sunucuya yazıyor (volume mount `./backups`). Sunucu çökmesi veya disk hatası durumunda yedekler de kaybolur.

**Fix:** S3/R2/Backblaze B2 upload — backup sonrası `boto3` ile push.

**OPS-004 ⚠️ Sentry DSN konfigüre edilmemiş**
`.env.example`'da `SENTRY_DSN` yok, `.env.prod` dosyasında doldurulmamış. `app/main.py:195` DSN varsa Sentry'yi init ediyor ama prod'da yoksa error tracking tamamen kapalı.

**Fix:** Sentry proje oluştur (sentry.io/de.sentry.io EU), DSN'yi `.env.prod` ve GitHub Secrets'a ekle.

**OPS-005 ⚠️ VPS nginx SSL kurulmamış**
`infra/nginx/vps-lojinext.conf` oluşturuldu ama VPS'e deploy edilmedi. `certbot` çalıştırılmadı. Domain olmadan HTTPS yok.

**Fix sırası:** Domain DNS → certbot install → VPS nginx config deploy → `nginx -t && systemctl reload nginx`.

---

## FİX PLANI — ÖNCELİK SIRASI

### 🔴 P0 — Prod'da temel işlevsellik kırık (≤1 gün)

**P0-A: E-posta servisi** (OPS-001)
En hızlı yol: `resend.com` API key (ücretsiz tier 3000 e-posta/ay).
1. `pip install resend` → `app/requirements.txt`
2. `app/config.py`'e `RESEND_API_KEY: Optional[SecretStr] = None` ekle
3. `app/core/services/email_service.py` yaz (15 satır)
4. `auth.py:200` — token dönüşünden sonra email gönder
5. `.env.example` + `.env.prod` güncelle

**P0-B: Otomatik DB yedek** (OPS-002)
1. `app/workers/tasks/backup_task.py` yaz — `celery_app.task` decorator ile `DatabaseBackupManager.create_backup()` çağır
2. `celery_app.py` beat schedule'a ekle: `crontab(hour=0, minute=30)`
3. Worker task import'unu celery_app.py sonuna ekle

### 🟠 P1 — Prod altyapısı kurulumu (≤3 gün)

**P1-A: VPS kurulumu**
1. VPS al (Hetzner CX21 ≈ €5/ay başlangıç için yeterli)
2. Domain DNS → VPS IP
3. `sudo apt install nginx certbot python3-certbot-nginx`
4. `certbot --nginx -d DOMAIN` → SSL otomatik provision
5. `infra/nginx/vps-lojinext.conf` → `/etc/nginx/conf.d/lojinext.conf` kopyala
6. Docker + docker-compose-plugin kur
7. `.env.prod` dosyasını VPS'e kopyala (`scp`)
8. GitHub Secrets doldur: `PROD_HOST`, `PROD_SSH_KEY`, `PROD_USER`, `PROD_DEPLOY_PATH`

**P1-B: Sentry aktif et** (OPS-004)
1. sentry.io'da yeni proje oluştur (EU region seç)
2. DSN'yi `.env.prod`'a ekle
3. Sentry'de `ENVIRONMENT=production` ve release tracking'i ayarla

**P1-C: Off-site yedek** (OPS-003)
1. `pip install boto3` → `app/requirements.txt`
2. `backup_manager.py`'e `upload_to_s3()` metodu ekle
3. `backup_task.py`'de backup sonrası S3 push çağır
4. `config.py`'e `BACKUP_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` ekle

### 🟡 P2 — DB performans ve teknik borç (≤1 hafta)

**P2-A: Eksik DB index'leri** (DB-002, REL-005)
```python
# alembic revision --autogenerate -m "add_missing_indexes"
# Sonra elle düzelt veya direkt yaz:

def upgrade():
    op.create_index("ix_prediction_results_status", "prediction_results", ["status"])
    op.create_index("idx_anomaly_status_combo", "anomalies", ["resolved_at", "acknowledged_at"])

def downgrade():
    op.drop_index("ix_prediction_results_status", "prediction_results")
    op.drop_index("idx_anomaly_status_combo", "anomalies")
```

**P2-B: React Router v6 future flags** (FE-004)
`frontend/src/test/test-utils.tsx`:
```tsx
<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
```
Uyarıları temizler, v7 geçişi için hazır hale getirir.

---

## MEVCUT DURUMU DOĞRULAYAN İYİ NOKTALAR

- **Frontend**: 150 test dosyası / 1196 test — 100% PASS, lint temiz, build temiz
- **JWT güvenliği**: Token blacklist fail-secure, CORS prod'da validate edilmiş, constant-time şifre karşılaştırması
- **Dosya upload**: 4 endpoint'te content-type whitelist + boyut limiti
- **Rate limiting**: Login, şifre reset, import, AI, route sim endpoint'lerinde
- **Şifre sıfırlama mantığı** (teslimat dışı her şey): SHA-256 hash, 1 saat TTL, post-reset session invalidation
- **Celery**: 11 zamanlanmış görev (outbox, ML retrain, anomaly, coaching, compliance push)
- **Alembic**: 32 migration, CI'da drift check, prod'da head deploy
- **Prometheus + Grafana + Alertmanager**: 136 satır alert rules mevcut
- **docker-compose.prod.yml**: Resource limits, log rotation, Redis auth, restart: always
- **nginx (frontend)**: Rate limiting, security headers, SPA fallback, Docker DNS resolver
