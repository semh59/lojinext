# LojiNext Production Readiness — Kapsamlı Fix Planı

> **Durum:** 6 alandan paralel denetim tamamlandı (2026-06-21). Bu belge tüm açık bulgular için somut fix adımlarını içerir.
> **Uygulama:** `superpowers:executing-plans` veya `superpowers:subagent-driven-development` ile yürütülür.

**Hedef:** LojiNext'i staging + production VPS'e güvenli, otomatik ve geri dönüşlü şekilde deploy edilebilir hale getirmek.

**Kapsam dışı:** VPS fiziksel kurulumu, domain/TLS, KVKK hukuk onayı, VAPID push teslimi — bunlar dış kaynak gerektirir.

---

## Zaten Tamamlananlar (Commit 83c9d3e2 + 3173154d, 2026-06-21)

| Bulgu | Dosya | Durum |
|-------|-------|-------|
| docker.sock unrestricted mount | docker-compose.yml | ✅ :ro |
| Root user in container | Dockerfile | ✅ appuser UID 1001 |
| No CSP header | frontend/nginx.conf | ✅ Eklendi |
| Duplicate X-Frame-Options | vps-lojinext.conf | ✅ proxy_hide_header + DENY |
| npm ci \|\| npm install fallback | frontend/Dockerfile | ✅ Kaldırıldı |
| JobManager _tasks memory leak | job_manager.py | ✅ done_callback |
| Healthcheck no start_period | Dockerfile | ✅ 30s |
| Alert debounce 0m (fatigue) | alert_rules.yml | ✅ 5m, warning |
| Smoke test fixed sleep | ci.yml | ✅ Retry loop |

---

## Global Kısıtlar

- `fastapi==0.136.0` sabit — 0.137 instrumentator'ı kırıyor
- Coverage gate: `--cov-fail-under=92`
- Tüm secret'lar GitHub Secrets veya `.env.prod`'dan — kaynak kodda sıfır düz metin
- Pre-commit: ruff + ruff-format + detect-secrets — `--no-verify` yasak

---

## Faz 1 — Güvenlik (HIGH öncelik, ~2 saat)

### Task 1-A: SEC-001 — Admin permission key mismatch

**Sorun:** `scripts/create_admin.py` admin rolünü eski key'lerle seed'liyor (`kullanici_yonetimi`, `arac_yonetimi` vb.). Yeni granular endpoint'ler (`bakim_ekle`, `model_egit`, `attribution_duzenle`, `circuit_breaker_reset`, `notification_rule_goruntule`) bu key'leri kontrol ediyor ama admin `yetkiler` dict'inde yok. Sonuç: normal admin kullanıcılar bu 5+ endpoint'e erişemiyor, sadece super_admin erişebiliyor.

**Etkilenen endpoint'ler:**
- `POST /admin/maintenance/*` → `require_yetki('bakim_ekle')`
- `POST /admin/ml/train` → `require_yetki('model_egit')`
- `POST /admin/attribution/override` → `require_yetki('attribution_duzenle')`
- `POST /admin/health/circuit-breaker/reset` → `require_yetki('circuit_breaker_reset')`
- `GET /admin/notifications/rules` → `require_yetki('notification_rule_goruntule')`

**Dosyalar:**
- Modify: `scripts/create_admin.py`
- Modify: `alembic/versions/` — yeni migration (mevcut admin roller için yetkiler güncelle)

**Adımlar:**

- [ ] `scripts/create_admin.py` oku — `yetkiler` dict'ini bul

- [ ] `scripts/create_admin.py`'daki admin yetkilerini güncelle:
```python
yetkiler = {
    # Eski key'ler (backward compat)
    "kullanici_yonetimi": True,
    "arac_yonetimi": True,
    "sofor_yonetimi": True,
    "raporlama": True,
    "ayarlar": True,
    "admin_panel": True,
    # Yeni granular key'ler
    "bakim_ekle": True,
    "bakim_duzenle": True,
    "model_egit": True,
    "attribution_duzenle": True,
    "circuit_breaker_reset": True,
    "notification_rule_goruntule": True,
    "notification_rule_ekle": True,
    "kalibrasyon_duzenle": True,
}
```

- [ ] Mevcut admin rollerini güncellemek için migration yaz:
```python
# alembic/versions/0031_fix_admin_yetkiler.py
def upgrade():
    op.execute("""
        UPDATE roller SET yetkiler = yetkiler || '{
            "bakim_ekle": true,
            "bakim_duzenle": true,
            "model_egit": true,
            "attribution_duzenle": true,
            "circuit_breaker_reset": true,
            "notification_rule_goruntule": true,
            "notification_rule_ekle": true,
            "kalibrasyon_duzenle": true
        }'::jsonb
        WHERE ad = 'admin'
    """)
```

- [ ] `alembic upgrade head` ile test et

- [ ] Commit: `fix(security): admin role granular permission keys + migration 0031`

---

### Task 1-B: SEC-005 — password-reset-confirm rate limit yok

**Sorun:** `POST /auth/password-reset-request` 2/min rate-limited ama `POST /auth/password-reset-confirm` (token + yeni şifre) rate-limit'siz. Token space küçükse brute-force mümkün.

**Dosyalar:**
- Modify: `app/api/v1/endpoints/auth.py`

**Adımlar:**

- [ ] `app/api/v1/endpoints/auth.py` oku — `password_reset_confirm` endpoint'ini bul

- [ ] Rate limit ekle (request'ten daha sıkı — 5/min):
```python
@router.post("/password-reset-confirm")
@rate_limited("pw_reset_confirm", rate=5.0, period=60.0)
async def password_reset_confirm(...):
```

- [ ] Commit: `fix(security): rate limit password-reset-confirm endpoint`

---

### Task 1-C: SEC-002 — Dual JWT import path (test vs. production)

**Sorun:** `auth.py` → `jwt_handler.create_access_token`; `conftest.py:614` → `app.core.security.create_access_token`. İki implementasyon farklı import path'te. Claim shape farklıysa integration testlerde token rejection riski.

**Adımlar:**

- [ ] Her iki `create_access_token` fonksiyonunu oku ve claim shape'lerini karşılaştır (`typ`, `aud`, `iss`, `jti` var mı her ikisinde?)

- [ ] Eğer identikse: `app/core/security.py`'deki fonksiyon `app/infrastructure/security/jwt_handler.py`'yi re-export etsin:
```python
# app/core/security.py
from app.infrastructure.security.jwt_handler import create_access_token  # tek kaynak
```

- [ ] `conftest.py`'daki import'u doğrula — `from app.core.security import create_access_token` hâlâ çalışıyor mu?

- [ ] Commit: `refactor(security): unify JWT token creation — single source via jwt_handler`

---

## Faz 2 — Test Suite (HIGH öncelik, ~1.5 saat)

### Task 2-A: Coverage gap — email_service + backup_tasks

**Sorun:** `email_service.py` (111 satır) ve `backup_tasks.py` (63 satır) commit `b58feaf3`'te eklendi, sıfır test var. Bu ~174 uncovered satır %0.1 coverage gap'ini açıklıyor.

**Dosyalar:**
- Create: `app/tests/unit/test_email_service.py`
- Create: `app/tests/unit/test_backup_tasks.py`

**Adımlar:**

- [ ] `app/core/services/email_service.py` oku — public API neler?

- [ ] `app/tests/unit/test_email_service.py` yaz:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.core.services.email_service import EmailService

pytestmark = pytest.mark.unit

class TestEmailService:
    def test_no_smtp_host_skips_send(self):
        """SMTP_HOST boşsa email göndermez, hata vermez."""
        with patch("app.core.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            svc = EmailService()
            result = svc.send_password_reset(to="test@x.com", token="abc")
            assert result is False  # veya None — gerçek dönüş tipine göre

    def test_send_password_reset_smtp_error_returns_false(self):
        """SMTP hatası session'ı çöküştürmez."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = ConnectionRefusedError()
            with patch("app.core.services.email_service.settings") as s:
                s.SMTP_HOST = "smtp.example.com"
                s.SMTP_PORT = 587
                s.SMTP_USERNAME = "user"
                s.SMTP_PASSWORD = MagicMock(get_secret_value=lambda: "pass")
                svc = EmailService()
                result = svc.send_password_reset(to="test@x.com", token="abc")
                assert result is False
```

- [ ] `app/workers/tasks/backup_tasks.py` oku — hangi fonksiyonlar var?

- [ ] `app/tests/unit/test_backup_tasks.py` yaz:
```python
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit

def test_backup_task_success():
    """Backup task pg_dump komutunu doğru çağırır."""
    with patch("app.workers.tasks.backup_tasks.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        from app.workers.tasks.backup_tasks import run_database_backup
        result = run_database_backup.run()
        assert mock_run.called

def test_backup_task_pg_dump_failure_does_not_crash():
    """pg_dump başarısız olursa task crash'lemiyor, hata logluyor."""
    with patch("app.workers.tasks.backup_tasks.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
        from app.workers.tasks.backup_tasks import run_database_backup
        # Exception fırlatmamalı
        run_database_backup.run()
```
> **Not:** Gerçek fonksiyon imzaları okuduktan sonra güncellenecek.

- [ ] `pytest app/tests/unit/test_email_service.py app/tests/unit/test_backup_tasks.py -v` koş

- [ ] Coverage: `pytest --cov=app --cov-report=term-missing -m "unit or not integration"` ile %92 geçtiğini doğrula

- [ ] Commit: `test(coverage): unit tests for email_service + backup_tasks — close 0.1% gap`

---

### Task 2-B: 13 FAILED test — EventBus Redis bağımlılığı

**Sorun:** `@publishes` decorator, EventBus üzerinden Redis'e yayın yapar. Redis yoksa (Docker olmadan) 500 döner. `test_admin_can_create_vehicle` gibi admin success path testleri 201 yerine 500 alır.

**Dosyalar:**
- Modify: `app/tests/conftest.py`

**Adımlar:**

- [ ] Mevcut `mock_event_bus` fixture'ını gözden geçir — autouse değil, sadece `sefer_service` fixture'ında kullanılıyor

- [ ] `conftest.py`'a autouse EventBus mock fixture ekle:
```python
@pytest.fixture(autouse=True)
def mock_event_bus_publish(monkeypatch):
    """@publishes decorator'ını izole et — unit/API testleri Redis'e ihtiyaç duymasın."""
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.infrastructure.events.event_bus.EventBus.publish_simple_async",
        _noop,
    )
    monkeypatch.setattr(
        "app.infrastructure.events.event_bus.EventBus.publish",
        lambda *a, **kw: None,
    )
```

> **Dikkat:** Integration testleri gerçek event flow'u test ediyorsa bu fixture'dan exclude edilmeli (`@pytest.mark.integration` için skip).

- [ ] `pytest app/tests/security/test_rbac.py -xvs` ile doğrula

- [ ] Commit: `fix(tests): mock EventBus publish in autouse fixture — isolate from Redis`

---

## Faz 3 — Altyapı ve Güvenilirlik (~2 saat)

### Task 3-A: OPS-007 — Backup off-site (S3)

**Sorun:** `docker-compose.prod.yml` backup'ı aynı VPS'in local disk'ine yazıyor. Host disk dolunca veya sunucu yanınca backup'lar kaybolur.

**Dosyalar:**
- Modify: `docker-compose.prod.yml`
- Modify: `.env.example`

**Adımlar:**

- [ ] `docker-compose.prod.yml` db-backup servisini değiştir:
```yaml
  db-backup:
    image: postgres:16-alpine@sha256:d845e7f0ac8517b9d9868b6d20379f9688ba3676595e50ca7c0b664964b2a760
    depends_on:
      - db
    environment:
      - PGPASSWORD=${POSTGRES_PASSWORD:?}
      - POSTGRES_USER=${POSTGRES_USER:-lojinext_user}
      - POSTGRES_DB=${POSTGRES_DB:-lojinext_db}
      - RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
      - AWS_ACCESS_KEY_ID=${BACKUP_S3_KEY_ID:-}
      - AWS_SECRET_ACCESS_KEY=${BACKUP_S3_SECRET:-}
      - BACKUP_S3_BUCKET=${BACKUP_S3_BUCKET:-}
      - BACKUP_S3_REGION=${BACKUP_S3_REGION:-eu-central-1}
    volumes:
      - ./backups:/backup/lojinext
    entrypoint: >
      sh -c '
        apk add --no-cache aws-cli 2>/dev/null || true;
        echo "0 2 * * * set -e && FNAME=lojinext_\$$(date +\%Y\%m\%d_\%H\%M\%S).dump && pg_dump -h db -U \$$POSTGRES_USER -d \$$POSTGRES_DB --no-owner --no-privileges --format=custom -f /backup/lojinext/\$$FNAME && echo \"dump OK\" && if [ -n \"\$$BACKUP_S3_BUCKET\" ]; then aws s3 cp /backup/lojinext/\$$FNAME s3://\$$BACKUP_S3_BUCKET/lojinext/\$$FNAME --region \$$BACKUP_S3_REGION && echo \"s3 upload OK\"; fi && find /backup/lojinext -name \"*.dump\" -mtime +\$$RETENTION_DAYS -delete" | crontab - &&
        crond -f -l 8
      '
    mem_limit: 256m
    cpus: '0.25'
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "3"
```

- [ ] `.env.example`'a ekle:
```
# Off-site backup (S3/compatible) — boş bırakılırsa sadece local backup
BACKUP_S3_BUCKET=
BACKUP_S3_KEY_ID=
BACKUP_S3_SECRET=
BACKUP_S3_REGION=eu-central-1
```

- [ ] Commit: `feat(ops): optional S3 off-site backup in db-backup service`

---

### Task 3-B: OPS-010 — CPU limitleri eksik servisler

**Dosyalar:**
- Modify: `docker-compose.prod.yml`

**Adımlar:**

- [ ] `docker-compose.prod.yml`'e şu blokları ekle (mevcut servislerin altına):
```yaml
  celery-beat:
    mem_limit: 256m
    cpus: '0.5'
    restart: always

  prometheus:
    mem_limit: 512m
    cpus: '0.5'

  grafana:
    mem_limit: 512m
    cpus: '0.5'

  alertmanager:
    mem_limit: 128m
    cpus: '0.25'

  celery-exporter:
    mem_limit: 128m
    cpus: '0.25'

  redis-exporter:
    mem_limit: 64m
    cpus: '0.1'

  postgres-exporter:
    mem_limit: 64m
    cpus: '0.1'

  telegram-ops-bot:
    mem_limit: 256m
    cpus: '0.25'

  telegram-driver-bot:
    mem_limit: 256m
    cpus: '0.25'
```

- [ ] Commit: `feat(ops): add resource limits for all prod services`

---

### Task 3-C: OPS-011 — celery-beat healthcheck

**Sorun:** celery-beat healthcheck `disable: true`. Beat'in `celerybeat-schedule` dosyasını güncellediğini ölçerek canlılık testi yapılabilir.

**Dosyalar:**
- Modify: `docker-compose.yml`

**Adımlar:**

- [ ] `docker-compose.yml`'de celery-beat servisinin healthcheck'ini değiştir:
```yaml
  celery-beat:
    healthcheck:
      test: >
        CMD-SHELL sh -c 'test -f /tmp/celerybeat-schedule &&
          python3 -c "import os,time; age=time.time()-os.path.getmtime(\"/tmp/celerybeat-schedule\"); exit(0 if age < 300 else 1)"'
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 90s
```

- [ ] Commit: `feat(ops): celery-beat healthcheck via schedule file mtime`

---

### Task 3-D: OPS-013 — Trivy container image scanning

**Dosyalar:**
- Modify: `.github/workflows/ci.yml`

**Adımlar:**

- [ ] `.github/workflows/ci.yml`'de `publish` job'ının sonuna, image push'tan SONRA ekle:
```yaml
      - name: Security scan — Trivy (backend)
        uses: aquasecurity/trivy-action@0.30.0
        with:
          image-ref: ghcr.io/${{ github.repository_owner }}/lojinext-backend:${{ steps.tag.outputs.IMAGE_TAG }}
          format: table
          exit-code: '1'
          ignore-unfixed: true
          severity: 'CRITICAL,HIGH'
        env:
          TRIVY_USERNAME: ${{ github.actor }}
          TRIVY_PASSWORD: ${{ secrets.GHCR_TOKEN || github.token }}

      - name: Security scan — Trivy (frontend)
        uses: aquasecurity/trivy-action@0.30.0
        with:
          image-ref: ghcr.io/${{ github.repository_owner }}/lojinext-frontend:${{ steps.tag.outputs.IMAGE_TAG }}
          format: table
          exit-code: '1'
          ignore-unfixed: true
          severity: 'CRITICAL,HIGH'
        env:
          TRIVY_USERNAME: ${{ github.actor }}
          TRIVY_PASSWORD: ${{ secrets.GHCR_TOKEN || github.token }}
```

- [ ] Commit: `ci: add Trivy container scanning for backend + frontend images`

---

### Task 3-E: OPS-015 — Alembic migration lock-timeout

**Dosyalar:**
- Modify: `.github/workflows/ci.yml`

**Adımlar:**

- [ ] `ci.yml`'deki her iki deploy job'unda `alembic upgrade head` satırını değiştir:
```yaml
            docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm \
              -e PGOPTIONS="-c lock_timeout=3s -c statement_timeout=120s" \
              backend alembic upgrade head
```
`lock_timeout=3s`: 3 saniyede kilit alamazsa migration abort → trafik etkilenmez.

- [ ] Commit: `fix(ops): alembic migration with lock_timeout=3s + statement_timeout=120s`

---

### Task 3-F: RELI-002 — DB pool boyutu prod'da küçült

**Dosyalar:**
- Modify: `docker-compose.prod.yml`
- Modify: `.env.example`

**Adımlar:**

- [ ] `.env.example`'a ekle:
```
# DB connection pool per process (backend + worker + celery-beat = 3 processes)
# 3 × (15 + 5) = 60 connections — well below postgres max_connections=200
DB_POOL_SIZE=15
DB_MAX_OVERFLOW=5
```

- [ ] `docker-compose.prod.yml` backend ve worker servislerine ekle:
```yaml
      - DB_POOL_SIZE=${DB_POOL_SIZE:-15}
      - DB_MAX_OVERFLOW=${DB_MAX_OVERFLOW:-5}
```

- [ ] Commit: `fix(ops): reduce DB pool size in prod — 3×60 vs 200 max_connections`

---

### Task 3-G: OPS-009 — CVE suppression review tarih belgesi

**Dosyalar:**
- Modify: `.github/workflows/ci.yml`

**Adımlar:**

- [ ] `ci.yml`'deki pip-audit bloğuna yorum ekle:
```yaml
      - name: Security scan — Python (pip-audit)
        # SUPPRESSION REVIEW DATE: 2026-09-21 (90 days from 2026-06-21)
        # CVE-2025-3000 + PYSEC-2025-{185..218}: torch 2.x transitive chain.
        #   Exploit = untrusted model load, not applicable in our deployment.
        #   Remove suppression when torch releases a fix.
        # PYSEC-2026-161: starlette<1.0.1 — blocked by prometheus-fastapi-instrumentator.
        #   Remove when instrumentator releases starlette>=1.0.1 support.
```

- [ ] Commit: `docs(ci): add CVE suppression review date + rationale comments`

---

## Faz 4 — Frontend İyileştirmeler (~30 dk)

### Task 4-A: FE-PERF-001 — axios global timeout düşür

**Dosyalar:**
- Modify: `frontend/src/services/api/axios-instance.ts`
- Modify: Upload çağrılarının bulunduğu servis dosyaları

**Adımlar:**

- [ ] `frontend/src/services/api/axios-instance.ts` oku — `timeout` nerede?

- [ ] Global timeout'u 30s'e düşür:
```typescript
timeout: 30_000,  // 30s default; file upload endpoints override with 120s
```

- [ ] `grep -rn "upload\|import\|ocr" frontend/src/services/api/` — upload endpoint'lerini bul

- [ ] Her upload çağrısına per-request timeout override ekle:
```typescript
axiosInstance.post('/trips/upload', formData, { timeout: 120_000 })
axiosInstance.post('/fuel/ocr-preview', formData, { timeout: 60_000 })
```

- [ ] `npx vitest --run` ile mevcut testlerin hâlâ geçtiğini doğrula

- [ ] Commit: `fix(frontend): axios default timeout 120s→30s, upload endpoints keep 120s`

---

### Task 4-B: FE-TEST-001 — TripsModuleResilience test-utils

**Dosyalar:**
- Modify: `frontend/src/__tests__/TripsModuleResilience.test.tsx` (veya benzeri path)

**Adımlar:**

- [ ] `grep -rn "TripsModuleResilience" frontend/src/` ile dosyayı bul

- [ ] Import'u `@testing-library/react` → `../../../test/test-utils` olarak değiştir

- [ ] Manuel `QueryClientProvider` + `MemoryRouter` wrapper'larını kaldır (test-utils bunları sağlıyor)

- [ ] `npx vitest --run` ile testi doğrula

- [ ] Commit: `fix(tests): TripsModuleResilience use project test-utils wrapper`

---

## Faz 5 — CI/CD Güvenlik Tarama (~30 dk)

### Task 5-A: Gitleaks secret scanning ekle

**Dosyalar:**
- Modify: `.github/workflows/ci.yml`

**Adımlar:**

- [ ] `ci.yml`'de `lint` job'ının başına ekle (test'ten önce çalışsın):
```yaml
      - name: Secret scan — gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}  # community edition: boş bırakılabilir
```

- [ ] Commit: `ci: add gitleaks secret scanning`

---

## Özet Tablo

| Task | Bulgu | Öncelik | Süre | Etki |
|------|-------|---------|------|------|
| 1-A | SEC-001 admin permission keys | HIGH | 30dk | Admin 5+ endpoint erişim fix |
| 1-B | SEC-005 reset-confirm rate limit | MEDIUM | 10dk | Brute-force koruması |
| 1-C | SEC-002 dual JWT unify | MEDIUM | 20dk | Test/prod token uyumu |
| 2-A | Coverage %92 gap | HIGH | 30dk | CI gate geçişi |
| 2-B | 13 FAILED EventBus mock | HIGH | 20dk | Suite yeşile |
| 3-A | OPS-007 S3 backup | HIGH | 15dk | Off-site veri koruması |
| 3-B | OPS-010 CPU limits | MEDIUM | 10dk | Kaynak sınırları |
| 3-C | OPS-011 beat healthcheck | MEDIUM | 10dk | Beat failure tespiti |
| 3-D | OPS-013 Trivy scan | MEDIUM | 20dk | OS-layer CVE tespiti |
| 3-E | OPS-015 migration timeout | MEDIUM | 5dk | Zero-downtime migration |
| 3-F | RELI-002 DB pool | MEDIUM | 10dk | Connection marjı |
| 3-G | OPS-009 CVE review date | LOW | 5dk | Teknik borç tespiti |
| 4-A | FE-PERF-001 axios timeout | LOW | 15dk | İstemci timeout doğruluğu |
| 4-B | FE-TEST-001 test-utils | LOW | 10dk | Test konvansiyonu |
| 5-A | Secret scanning | MEDIUM | 10dk | Sızıntı önleme |

**Toplam: ~3.5 saat**

---

## Production Checklist (Deploy öncesi)

- [ ] Faz 1-5 tüm task'lar tamamlandı
- [ ] `pytest --cov=app --cov-fail-under=92` → PASS (0 failed, 0 error)
- [ ] `npx vitest --run` → PASS
- [ ] `npm run build` → SUCCESS
- [ ] `alembic check` → "No new upgrade operations detected"
- [ ] `ruff check app` → temiz
- [ ] GitHub Secrets set edildi: `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`, `STAGING_DEPLOY_PATH`, `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, `PROD_DEPLOY_PATH`
- [ ] `.env.prod` dosyası VPS'te mevcut (tüm `?:` zorunlu değişkenler dolu)
- [ ] `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `GF_SECURITY_ADMIN_PASSWORD` gerçek değerler
- [ ] `IMAGE_TAG` VPS `.env.prod`'a set edildi
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` hatasız
- [ ] Backup restore tatbikatı yapıldı (docs/operations/runbook.md §4)
