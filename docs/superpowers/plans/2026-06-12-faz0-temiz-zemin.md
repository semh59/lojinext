# Faz 0 — Temiz Zemin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ARCH serisi branch'ini `main`'e merge et, `scripts/`'in container'a girmesini sağla (`.dockerignore` düzeltmesi), conftest'teki dev-DB-silme mayınını etkisizleştir ve CLAUDE.md drift'lerini gider — sonraki tüm fazlar temiz `main`'den açılsın.

**Architecture:** Dört bağımsız iş: (1) git hijyeni — branch'i fast-forward merge + push; (2) build düzeltmesi — `.dockerignore`'dan `scripts/` satırını kaldırıp image'ı doğrula; (3) test güvenliği — `TEST_DATABASE_URL` zorunlu kılınır, dev DB fallback'i kaldırılır; (4) dokümantasyon — CLAUDE.md gerçeklikle eşitlenir. Yalnız Task 4 kod değiştirir (TDD'li); diğerlerinde her task'in kendi doğrulama komutu var.

**Tech Stack:** git, docker compose, pytest, Markdown. Yeni bağımlılık yok.

**Önkoşul bilgiler (plan yazımı + derin review sırasında doğrulandı, 2026-06-12):**
- `chore/arch005-sefer-model-unify` → `main`'den ~28 commit ileride (spec/plan commit'leriyle artar), 0 commit geride → fast-forward mümkün.
- Remote'lar: `neworigin` (github.com/semh59/lojinext-v2 — aktif) ve `origin` (eski LOJINEXT repo — kullanılmıyor). `neworigin/main` mevcut (`136e9660`). Branch'in ilk 26 commit'i zaten pushlanmış.
- `Dockerfile` zaten `COPY . .` yapıyor; `scripts/`'i dışarıda bırakan şey `.dockerignore:74`'teki `scripts/` satırı. Compose backend volume'ları (`app_data:/app/app/data`, `model_data:/app/models`, hf_cache, backups) `/app/scripts`'i GÖLGELEMEZ.
- `scripts/__init__.py` repo'da mevcut; `scripts/__pycache__` `.dockerignore`'daki `__pycache__/` pattern'iyle zaten dışarıda kalır.
- `scripts/e2e_pilot_smoke.py` sample Excel'leri pandas ile **kendisi üretir** (repo'dan .xlsx fixture okumaz → `.dockerignore`'daki `*.xlsx` engel değil). `SUPER_ADMIN_PASSWORD` env zorunlu — `.env`'de mevcut ve backend container `env_file: .env` ile alıyor.
- **MAYIN (Task 4'ün gerekçesi):** `app/tests/conftest.py::temp_db_url`, `TEST_DATABASE_URL` yoksa fallback olarak **dev DB'yi** (`lojinext_db@localhost:5432`) kurar; `async_db_engine` bu DB'de `pg_terminate_backend` (tüm bağlantılar) + `DROP SCHEMA public CASCADE` çalıştırır. Compose `db` servisi `5432:5432` host'a açık → stack ayaktayken düz `pytest` koşmak dev veriyi siler. CI her zaman `TEST_DATABASE_URL` set ediyor (ci.yml:66) → fallback'i kaldırmak CI-güvenli.
- conftest `pytest_collection_modifyitems` localhost:5432 kapalıysa integration testleri otomatik skip eder; `-m "unit or not integration"` ifadesi integration'ı her durumda deselect eder.

---

### Task 1: Branch'i pushla ve `main`'e merge et

**Files:**
- Yok (yalnız git işlemleri)

- [ ] **Step 1: Çalışma ağacının temiz olduğunu doğrula**

Run: `git status -sb`
Expected: `## chore/arch005-sefer-model-unify...neworigin/chore/arch005-sefer-model-unify [ahead N]` ve altında hiçbir kirli dosya yok. Kirli dosya varsa DUR — kullanıcıya sor.

- [ ] **Step 2: Lokal gate'leri koş (merge öncesi son kontrol)**

Run: `ruff check app --select E,F,W,I && mypy app --ignore-missing-imports --no-strict-optional`
Expected: ruff `All checks passed!`, mypy `Success: no issues found` (0 hata — ARCH-004 sonrası bilinen durum).

- [ ] **Step 3: Unit testleri koş**

Önce mayını kapat (Task 4 henüz merge olmadı): `docker compose stop db 2>/dev/null; export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/lojinext_test"`
Run: `pytest -m "unit or not integration" -q --no-header 2>&1 | tail -5`
Expected: Son satırda `passed` ve `failed` YOK; süre birkaç dakika olabilir (~6k test).
⚠️ GÜVENLİK: `-m` filtresini ASLA çıkarma VE yukarıdaki stop/export'u atlama — `not integration`, integration-işaretsiz ama DB'ye dokunan bir test'i deselect ETMEZ; stack ayaktayken + `TEST_DATABASE_URL` boşken o test dev şemayı düşürebilir (bkz. önkoşul MAYIN notu). Collection hatası görürsen DUR ve hatayı raporla.

- [ ] **Step 4: Branch'i remote'a pushla**

Run: `git push neworigin chore/arch005-sefer-model-unify`
Expected: `To ... chore/arch005-sefer-model-unify` başarı satırı. Push reddedilirse (billing/auth): hatayı not et, Step 5'e devam et — merge lokal olarak yine yapılır.

- [ ] **Step 5: main'e geç ve güncel olduğunu doğrula**

Run: `git checkout main && git fetch neworigin && git log main..neworigin/main --oneline | head -5`
Expected: checkout başarılı; son komut BOŞ çıktı verir (remote main'de bizde olmayan commit yok). Boş değilse DUR — önce `git pull --ff-only neworigin main` dene; çakışma varsa kullanıcıya sor.

- [ ] **Step 6: Fast-forward merge**

Run: `git merge --ff-only chore/arch005-sefer-model-unify`
Expected: `Fast-forward` satırı, ardından dosya istatistikleri. `fatal: Not possible to fast-forward` görürsen DUR — main'e beklenmeyen commit girmiş demektir, kullanıcıya sor.

- [ ] **Step 7: main'i pushla**

Run: `git push neworigin main`
Expected: Başarı satırı. Reddedilirse hatayı not et ve devam et (push, fazın bloklayıcısı değil).

- [ ] **Step 8: Doğrula**

Run: `git log main -1 --oneline && git status -sb`
Expected: En üst commit bu planın commit'i veya sonrası; status temiz, `## main...neworigin/main` (push başarılıysa ahead-0).

---

### Task 2: `.dockerignore`'dan `scripts/` çıkar ve image'ı doğrula

**Files:**
- Modify: `.dockerignore:74` (`scripts/` satırı silinir)
- Modify: `CLAUDE.md:328` civarı ("Container'da `/app/scripts/` klasörü yok" gotcha bölümü)

- [ ] **Step 1: Faz 0 çalışma branch'ini aç**

Run: `git checkout -b chore/faz0-temiz-zemin main`
Expected: `Switched to a new branch 'chore/faz0-temiz-zemin'`

- [ ] **Step 2: `.dockerignore`'dan `scripts/` satırını kaldır**

`.dockerignore` dosyasında şu bloğu bul:

```
# ── One-time audit / planning scripts ─────────────────────────
deep_audit.py
final_audit.py
run_final_audit.py
super_audit.py
targeted_audit.py
PROD_READINESS.md
FRONTEND_REVIEW.md
docs/
scripts/
```

`scripts/` satırını SİL (diğer satırlar kalır). Sonuç:

```
# ── One-time audit / planning scripts ─────────────────────────
deep_audit.py
final_audit.py
run_final_audit.py
super_audit.py
targeted_audit.py
PROD_READINESS.md
FRONTEND_REVIEW.md
docs/
```

- [ ] **Step 3: Backend image'ı yeniden build et**

Run: `docker compose build backend 2>&1 | tail -3`
Expected: Başarı satırı (`naming to ...` benzeri), hata yok. (İlk build birkaç dakika sürebilir.)

- [ ] **Step 4: Container'da scripts/'in varlığını doğrula**

Run: `docker compose up -d backend && docker compose exec backend ls /app/scripts/ | head -5`
Expected: `__init__.py`, `e2e_pilot_smoke.py` dahil dosya listesi (db+redis healthy olana kadar backend'in başlaması ~30sn sürebilir). `No such file or directory` görürsen DUR — `.dockerignore` değişikliği etki etmemiş demektir (cache: `docker compose build --no-cache backend` dene).

- [ ] **Step 5: Smoke script'in import edilebildiğini doğrula (TRUNCATE ETMEDEN)**

Run: `docker compose exec backend python -c "import scripts.e2e_pilot_smoke" 2>&1 | tail -2`
Expected: `SystemExit: SUPER_ADMIN_PASSWORD env var zorunlu...` HARİÇ hata yok — modül import'ta şifre kontrolü yapar; container .env'den aldığı için temiz çıkış da olabilir. `ModuleNotFoundError` görürsen DUR. (Tam koşu iş verisini TRUNCATE eder — kullanıcı onayıyla Task 5'te yapılır.)

- [ ] **Step 6: CLAUDE.md gotcha bölümünü güncelle**

`CLAUDE.md`'de şu bölümü bul (satır ~328):

```markdown
### Container'da `/app/scripts/` klasörü yok

Backend image build sırasında `scripts/` paketlenmedi. Repo'da var ama container'da yok. Script çalıştırmadan önce:

```bash
docker compose exec backend bash -c "mkdir -p /app/scripts"
docker cp scripts/<file>.py lojinext-backend-1:/app/scripts/<file>.py
docker compose exec backend touch /app/scripts/__init__.py
docker compose exec backend python -m scripts.<file>
```

Tek seferlik onarım: `Dockerfile`'a `COPY scripts /app/scripts` eklenmesi (henüz yapılmadı). `scripts/e2e_pilot_smoke.py` ve `scripts/p51_real_world_validation.py` bu yolu kullanır.
```

Şununla DEĞİŞTİR:

```markdown
### Container'da script çalıştırma

`scripts/` klasörü image'a dahildir (2026-06-12'den beri; `.dockerignore`'dan çıkarıldı — `Dockerfile` zaten `COPY . .` yapıyor). Çalıştırma:

```bash
docker compose exec backend python -m scripts.<file>
```

Yeni yazılmış/henüz build edilmemiş tek bir script'i rebuild'siz denemek için `docker cp` pattern'i hâlâ geçerli (bkz. Docker bölümü).
```

- [ ] **Step 7: Commit**

```bash
git add .dockerignore CLAUDE.md
git commit -m "fix(docker): scripts/ klasörünü image'a dahil et

.dockerignore scripts/'i build context'ten çıkarıyordu; Dockerfile'daki
COPY . . bu yüzden klasörü hiç görmüyordu. Satır kaldırıldı, CLAUDE.md
gotcha bölümü güncellendi. e2e_pilot_smoke ve p51 validation artık
docker cp olmadan koşar."
```

---

### Task 3: CLAUDE.md drift düzeltmeleri

**Files:**
- Modify: `CLAUDE.md:74` (Docker bölümü — servis sayısı)

- [ ] **Step 1: Servis sayısını düzelt**

`CLAUDE.md`'de şu satırı bul (satır 74):

```bash
docker-compose up -d                  # Start all 8 services
```

Şununla DEĞİŞTİR:

```bash
docker-compose up -d                  # Start all 14 services (backend, frontend, worker, celery-beat, db, redis, ocr-service, telegram-ops-bot, prometheus, grafana, alertmanager, 3x exporter)
```

- [ ] **Step 2: Doğrula — başka "8 servis" referansı kalmadı**

Run: `grep -rn "8 services\|8 servis" CLAUDE.md docs/onboarding/ 2>/dev/null`
Expected: Boş çıktı (onboarding'de varsa onu da aynı şekilde düzelt ve bu adımı tekrarla).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): servis sayısı drift düzeltmesi (8 -> 15)"
```

---

### Task 4: conftest dev-DB mayınını etkisizleştir (TEST_DATABASE_URL zorunlu)

**Gerekçe:** `temp_db_url` fixture'ı `TEST_DATABASE_URL` yoksa **dev DB'ye** (`lojinext_db@localhost:5432`) düşüyor ve `async_db_engine` orada `DROP SCHEMA public CASCADE` çalıştırıyor. Compose `db` servisi 5432'yi host'a açtığı için, stack ayaktayken filtresiz `pytest` pilot dev verisini siler. CI her zaman `TEST_DATABASE_URL` set ettiğinden (ci.yml:66) fallback'in kaldırılması CI'ı etkilemez.

**Files:**
- Modify: `app/tests/conftest.py` (`temp_db_url` fixture, satır ~126)
- Create: `app/tests/unit/test_conftest_db_guard.py`
- Modify: `CLAUDE.md` (Testing notes — default URL iddiası düzeltilir)

- [ ] **Step 1: Failing test yaz**

`app/tests/unit/test_conftest_db_guard.py` dosyasını oluştur:

```python
"""conftest'in test-DB çözümleme guard'ı — dev DB'ye DROP SCHEMA atılmasını önler.

Gerekçe: TEST_DATABASE_URL yokken fallback dev DB'yi (lojinext_db) gösteriyordu;
async_db_engine bu DB'de pg_terminate_backend + DROP SCHEMA public CASCADE
çalıştırır. Guard: URL zorunlu VE veritabanı adı 'test' içermek zorunda.
"""

import pytest

from app.tests.conftest import resolve_test_db_url


@pytest.mark.unit
def test_missing_url_raises():
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL"):
        resolve_test_db_url(None)


@pytest.mark.unit
def test_non_test_db_name_rejected():
    # Dev/prod adlı DB'lere işaret eden URL kabul edilmez — 'test' şartı
    with pytest.raises(RuntimeError, match="test"):
        resolve_test_db_url(
            "postgresql+asyncpg://u:p@localhost:5432/lojinext_db"
        )


@pytest.mark.unit
def test_valid_test_url_passes_through():
    url = "postgresql+asyncpg://postgres:postgres@localhost:5432/lojinext_test"
    assert resolve_test_db_url(url) == url
```

- [ ] **Step 2: Testin FAIL ettiğini doğrula**

Run: `pytest app/tests/unit/test_conftest_db_guard.py -v 2>&1 | tail -5`
Expected: FAIL / ERROR — `ImportError: cannot import name 'resolve_test_db_url'`

- [ ] **Step 3: Guard'ı implemente et**

`app/tests/conftest.py`'de mevcut `temp_db_url` fixture'ını bul:

```python
@pytest.fixture(scope="session")
def temp_db_url():
    # Read TEST_DATABASE_URL from the environment or construct from .env variables.
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        user = os.getenv("POSTGRES_USER", "lojinext_user")
        password = os.getenv("POSTGRES_PASSWORD", "lojinext_pass_2026")
        db = os.getenv("POSTGRES_DB", "lojinext_db")
        url = f"postgresql+asyncpg://{user}:{password}@localhost:5432/{db}?ssl=disable"
    return url
```

Şununla DEĞİŞTİR:

```python
def resolve_test_db_url(url: str | None) -> str:
    """Integration test DB URL'ini doğrula.

    Guard 1: TEST_DATABASE_URL zorunlu — dev DB'ye (lojinext_db) düşen eski
    fallback kaldırıldı; async_db_engine bağlandığı DB'de DROP SCHEMA public
    CASCADE çalıştırdığı için yanlış hedef veri kaybı demek.
    Guard 2: veritabanı adı 'test' içermeli — dev/prod'a yanlışlıkla işaret
    eden explicit URL'leri de reddeder.
    """
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL env var zorunlu — integration testler explicit "
            "bir TEST veritabanı ister (örn. postgresql+asyncpg://postgres:"
            "postgres@localhost:5432/lojinext_test). Dev DB fallback'i veri "
            "kaybına yol açtığı için kaldırıldı."
        )
    from sqlalchemy.engine import make_url

    db_name = make_url(url).database or ""
    if "test" not in db_name.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL '{db_name}' veritabanına işaret ediyor — adı "
            "'test' içermeyen DB'lere şema reset'i reddedilir (DROP SCHEMA "
            "public CASCADE koruması)."
        )
    return url


@pytest.fixture(scope="session")
def temp_db_url():
    return resolve_test_db_url(os.getenv("TEST_DATABASE_URL"))
```

- [ ] **Step 4: Testlerin PASS ettiğini doğrula**

Run: `pytest app/tests/unit/test_conftest_db_guard.py -v 2>&1 | tail -6`
Expected: 3 passed

- [ ] **Step 5: Mevcut suite'in etkilenmediğini doğrula**

Run: `pytest -m "unit or not integration" -q --no-header 2>&1 | tail -3`
Expected: Önceki koşuyla aynı sayıda `passed`, 0 failed. (Integration testler bu filtreyle deselect; TEST_DATABASE_URL set edilmiş ortamlarda da `lojinext_test` adı guard'dan geçer.)

- [ ] **Step 6: CLAUDE.md Testing notes'u düzelt**

`CLAUDE.md`'de şu satırı bul:

```markdown
- Test DB URL: `TEST_DATABASE_URL` env var (default `postgresql+asyncpg://postgres:...@localhost:5432/lojinext_test`).
```

Şununla DEĞİŞTİR:

```markdown
- Test DB URL: `TEST_DATABASE_URL` env var **zorunlu** (örn. `postgresql+asyncpg://postgres:postgres@localhost:5432/lojinext_test`); yoksa integration testler RuntimeError ile durur. DB adı 'test' içermek zorunda — conftest, bağlandığı DB'de `DROP SCHEMA public CASCADE` çalıştırdığı için dev/prod adlı hedefler reddedilir.
```

- [ ] **Step 7: ruff + mypy**

Run: `ruff check app/tests/conftest.py app/tests/unit/test_conftest_db_guard.py && mypy app --ignore-missing-imports --no-strict-optional 2>&1 | tail -2`
Expected: ruff temiz; mypy `Success: no issues found`.

- [ ] **Step 8: Commit**

```bash
git add app/tests/conftest.py app/tests/unit/test_conftest_db_guard.py CLAUDE.md
git commit -m "fix(test-safety): TEST_DATABASE_URL zorunlu + 'test' ad guard'ı

conftest fallback'i stack ayaktayken (db 5432:5432 host'a açık) düz
pytest koşusunda dev DB'ye DROP SCHEMA public CASCADE atabiliyordu.
Fallback kaldırıldı; URL zorunlu ve DB adı 'test' içermek zorunda.
CI etkilenmez (ci.yml TEST_DATABASE_URL'i zaten set ediyor)."
```

---

### Task 5: E2E smoke doğrulaması ve Faz 0 kapanışı

**Files:**
- Yok (doğrulama + merge)

- [ ] **Step 1: Kullanıcıdan TRUNCATE onayı al**

`scripts/e2e_pilot_smoke.py` iş verisini TRUNCATE eder (auth + alembic_version korunur). Lokal/dev ortamdaki veri feda edilebilir mi diye KULLANICIYA SOR. Onay yoksa bu task'in Step 2'sini atla, Step 3'ten devam et.

- [ ] **Step 2: Smoke'u container içinden koş (spec'in Faz 0 kabul kriteri)**

Run: `docker compose exec -e PYTHONIOENCODING=utf-8 backend python -m scripts.e2e_pilot_smoke 2>&1 | tail -15`
Expected: Çıktıda her entity için `saved >= expected` ve `errors == []`; süreç exit 0. (`SUPER_ADMIN_PASSWORD` container'a `.env` üzerinden geliyor — ayrıca geçmek gerekmez.) Başarısızsa DUR — hatayı raporla (muhtemel neden: servisler ayakta değil → `docker compose up -d`).

- [ ] **Step 3: Faz 0 branch'ini main'e merge et**

```bash
git checkout main
git merge --ff-only chore/faz0-temiz-zemin
git push neworigin main
```

Expected: `Fast-forward` + push başarı satırı (push reddedilirse not et, devam).

- [ ] **Step 4: Kapanış doğrulaması**

Run: `git log main --oneline -4 && git branch --merged main | grep faz0`
Expected: Son commit'ler Task 2-4'ün commit'leri; `chore/faz0-temiz-zemin` merged listesinde. Faz 0 TAMAM — yol haritasında sıradaki: Faz 1 (Tahmin backfill job).

---

## Self-Review Notu (derin review 2026-06-12 ile güncellendi)

- **Spec kapsaması:** Spec'in Faz 0 maddeleri — merge (Task 1), Dockerfile/scripts (Task 2; kök neden `.dockerignore` olarak düzeltildi), CLAUDE.md drift (Task 2 Step 6 + Task 3 + Task 4 Step 6), kabul kriteri smoke (Task 5). Task 4 spec'te yoktu — review'de bulunan veri-kaybı mayını; "çalışılan kodda rastlanan, işi etkileyen sorun" kapsamında eklendi.
- **Spec sapması (bilinçli):** Spec "Dockerfile'a COPY scripts" diyordu; kök neden `.dockerignore:74`. Plan doğru düzeltmeyi uygular; hedef ("container'da scripts çalışsın") değişmedi.
- **Review'de doğrulanan varsayımlar:** `neworigin/main` mevcut; compose volume'ları `/app/scripts`'i gölgelemiyor; smoke verisini pandas ile üretiyor (.xlsx fixture yok); `SUPER_ADMIN_PASSWORD` `.env`'de; CLAUDE.md hedef satırları (74, 328) birebir mevcut; CI `TEST_DATABASE_URL`'i explicit set ediyor → Task 4 CI-güvenli.
- **Placeholder taraması:** Yok — her adımda tam komut/kod var.
- **Tip/isim tutarlılığı:** `resolve_test_db_url` adı Task 4'ün test ve implementasyonunda aynı; başka task ona referans vermiyor.
- **Sıra bağımlılığı:** Task 1 (merge) önce — Faz 0 commit'leri temiz main üstüne oturur. Task 4, Task 1 Step 3'ün uyarısını kalıcı çözüme bağlar. Task 5 Step 2, Task 2'nin build'ine bağımlı.
