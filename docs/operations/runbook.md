# LojiNext Operasyonel Runbook

> Faz 11 — pilot/prod operasyon kılavuzu. Tek-VPS docker-compose kurulumu içindir.
> Kısa, eyleme dönük. Komutlar repo kökünden çalıştırılır.

## 0. Servisler (15)

`docker compose config --services`:
`db redis redis-exporter ocr-service postgres-exporter prometheus grafana
backend telegram-driver-bot worker alertmanager frontend telegram-ops-bot
celery-beat celery-exporter`

Prod compose: `docker compose -f docker-compose.prod.yml up -d`.

## 1. Sağlık kontrolü

| Endpoint | Anlam | Beklenen |
|----------|-------|----------|
| `GET /health/liveness` | Süreç ayakta | 200 her zaman |
| `GET /health/readiness` | DB + Redis bağlı | 200; DB/Redis down → 503 |

Dış uptime izleme (UptimeRobot / healthchecks.io) **`/health/liveness`**'e bağlanır.
Hızlı kontrol:
```bash
curl -fsS http://localhost:8000/health/liveness && echo OK
docker compose ps           # tüm servisler "Up (healthy)"
```

## 2. Restart prosedürleri

```bash
# Tek servis (kod değişikliği YOK, sadece restart)
docker compose restart backend

# Kod değişikliği sonrası (image rebuild — backend image volume mount YOK)
docker compose up -d --build backend

# Tüm stack
docker compose -f docker-compose.prod.yml up -d
```
Backend healthy olana kadar bekle: `docker inspect -f '{{.State.Health.Status}}' lojinext-backend-1`.

## 3. Migration prosedürü

```bash
docker compose exec backend alembic check          # drift var mı (CI gate)
docker compose exec backend alembic upgrade head    # pending'leri uygula
docker compose exec backend alembic current         # mevcut revizyon
```
⚠️ **Asla** `Base.metadata.create_all` ile prod şeması kurma — yalnız `alembic upgrade head`.
⚠️ `alembic stamp` yaparken HEDEF revizyonun kendi DDL marker'ını doğrula (bkz.
release_remediation: yanlış stamp sessizce migration atlatır).

## 4. Yedekleme + geri dönüş (RESTORE TATBİKATI)

PostgreSQL verisi `db` servisinin volume'ünde. Mantıksal yedek:
```bash
# Yedek al
docker compose exec -T db pg_dump -U lojinext_user lojinext | gzip > backup_$(date +%F).sql.gz

# GERİ DÖNÜŞ TATBİKATI (staging/throwaway DB'de doğrula, prod'a dokunmadan):
gunzip -c backup_YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U lojinext_user -d lojinext_restore_test
# Doğrula: tablo sayısı + son sefer kaydı + alembic_version eşleşmeli
```
`BACKUP_RETENTION_DAYS=30` (config). Yedekleri stack dışında bir konuma kopyala
(VPS diski kaybolursa yedek de gider).

**Kabul (Faz 11):** En az bir kez gerçek yedekten geri dönüş tatbikatı yapılmış +
sonucu (tablo/satır sayısı eşleşmesi) bu runbook'a not düşülmüş olmalı.

## 5. Pilot veri yükleme + smoke

```bash
# Sadece iş verisini temizle (auth + alembic_version korunur)
docker compose exec backend python scripts/reset_business_data.py --confirm

# E2E smoke (Excel pipeline: 5 entity yükle → dashboard probe; saved>=expected, errors==[])
docker compose exec -e PYTHONIOENCODING=utf-8 backend python -m scripts.e2e_pilot_smoke
```

## 6. Alerting zinciri doğrulama

Telegram OPS bot (`telegram-ops-bot:8080`) hata + feedback alır.
```bash
# Sahte CRITICAL → OPS kanalına düşmeli (alarm zinciri kanıtı)
docker compose exec backend python -c "import asyncio; from app.infrastructure.notifications.telegram_notifier import notify_error; asyncio.run(notify_error(level='critical', message='runbook test', path='/runbook'))"
# Pilot feedback kanalı: UI'daki feedback butonu → POST /feedback/ → OPS kanalı
```
Alertmanager → ops_bot `/webhook/alertmanager` (Prometheus alarm kuralları).

## 7. Open-Meteo / Mapbox kota gözlemi

- **Open-Meteo (free tier):** dakikalık ~600, ama saturated minute'da 429; **günlük
  kota** da var (elevation). Sefer tahmini + segment sim 429 alırsa
  `GET /admin/fuel-accuracy` `coverage_pct` düşer. Retry pattern mevcut
  (Retry-After/1.5s + tek retry).
- **Mapbox Directions:** 24h response cache var → tekrar eden güzergahlar ucuz.
  Pilot trafiğinde aylık istek sayısını Mapbox dashboard'dan izle.

## 8. Sık arızalar

| Belirti | Olası neden | Çözüm |
|---------|-------------|-------|
| Backend crash-loop, `DuplicateTable` | `alembic_version` yok ama şema var | `alembic stamp <doğru-rev>` + `upgrade head` (marker doğrula) |
| readiness 503 | DB/Redis erişilemez | `docker compose ps`; db/redis restart; bağlantı env'i kontrol |
| Tahmin `coverage_pct` düşük | Open-Meteo 429 (kota) | pacing/retry; gece düşük tempo; kota reset bekle |
| Pool exhaustion / takılı sorgu | runaway query | `DB_COMMAND_TIMEOUT_S` (default 60s) per-statement keser |
| OPS bildirimi gelmiyor | ops_bot down / token | `docker compose logs telegram-ops-bot`; `TELEGRAM_OPS_BOT_URL` |

## 9. Loglar

```bash
docker compose logs -f backend          # backend akışı
docker compose logs --tail=100 worker   # Celery worker
docker compose logs celery-beat         # zamanlanmış task'lar
```
Sentry: EU region (`de.sentry.io`); 4xx + bilinen gürültü `_sentry_before_send`'de
filtreleniyor. Grafana/Prometheus: `prometheus`/`grafana` servisleri.
