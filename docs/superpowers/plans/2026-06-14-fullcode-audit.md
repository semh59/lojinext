# LojiNext Tam Satır-Satır Kod Denetimi — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **NOT — bu bir denetim kampanyasıdır, özellik geliştirme değil.** "Task" = bir denetim oturumu; çıktısı **kod değil, kanıta dayalı bulgu kaydıdır**. Faz 1'de hiçbir üretim kodu değiştirilmez. Düzeltme (Faz 2) ayrı bir plandır.

**Goal:** LojiNext'in ~110.250 satırlık üretim kodu (653 dosya) + 603 test dosyasını istisnasız satır-satır denetleyip her bulguyu `dosya:satır` + kod alıntısı + öneri ile merkezi bir kayda işlemek; kapsamı bir ledger ile kanıtlamak.

**Architecture:** Tek ajan, sıralı okuma. Her dosya `Read` ile baştan sona okunur, §5 hata-sınıfı kontrol listesi uygulanır, bağımlılıklar çapraz-doğrulanır, bulgular `docs/superpowers/audits/` altındaki modül dosyalarına §6 şemasıyla yazılır, `AUDIT-PROGRESS.md` ledger'ında dosya `[x]` işaretlenir. Risk-ağırlıklı 10 sıra (S1→S10), 20–25 oturuma bölünür.

**Tech Stack:** Backend FastAPI/SQLAlchemy 2 async/Alembic/Celery; Frontend React+TS/Vite/React Query/Zustand; statik araçlar ruff, mypy, eslint. Denetim aracı: `Read`, `Grep`, `Bash` (git ls-files enumerasyon).

**Kaynaklar:**
- Spec: `docs/superpowers/specs/2026-06-14-fullcode-audit-design.md` (§5 kontrol listesi, §6 bulgu şeması, §3 demir kurallar burada tanımlı — her task bunlara uyar).
- Demir kural hatırlatma: okumadan bulgu yok · her bulgu kanıt (dosya:satır + alıntı) taşır · uydurma kod yok · doğrulanamayan = `needs-verification`, "bug" değil.

**Git politikası:** Denetim dokümanları **additive**'dir (yalnız `docs/superpowers/audits/` altına yazar, üretim kodu değişmez) — commit güvenlidir. `main`'de çalışıyorsak commit'ten önce `git switch -c audit/fullcode-2026-06-14` ile dal aç. Commit'ler yalnızca kullanıcı onayıyla atılır; aksi halde her task sonunda dokümanlar diskte birikir.

---

## Task 0: Bootstrap — denetim iskeleti + baseline

**Files:**
- Create: `docs/superpowers/audits/AUDIT-PROGRESS.md`
- Create: `docs/superpowers/audits/AUDIT-INDEX.md`
- Create: `docs/superpowers/audits/_baseline-ruff.txt`, `_baseline-mypy.txt`, `_baseline-eslint.txt`

- [ ] **Step 1: Audit dizinini oluştur ve kapsam ledger'ını gerçek dosya listesinden üret**

```bash
mkdir -p docs/superpowers/audits
{
  echo "# AUDIT-PROGRESS — Kapsam Ledger'ı (2026-06-14)"
  echo ""
  echo "Bir dosya tam okunup §5 kontrol listesi uygulanınca \`- [ ]\` → \`- [x]\` yapılır."
  echo "Tüm satırlar \`[x]\` olmadan ilgili S-grubu BİTTİ sayılmaz."
  echo ""
  echo "## Üretim kodu (S1–S9)"
  git ls-files 'app/**/*.py' | grep -v '/tests/' | sort | sed 's/^/- [ ] /'
  git ls-files 'frontend/src/**/*.ts' 'frontend/src/**/*.tsx' | grep -v '__tests__' | grep -vE '\.test\.tsx?$' | sort -u | sed 's/^/- [ ] /'
  git ls-files 'alembic/versions/*.py' 'scripts/*.py' 'telegram_bot/**/*.py' 'ocr_service/**/*.py' | sort | sed 's/^/- [ ] /'
  echo ""
  echo "## Test kodu (S10)"
  git ls-files 'app/tests/**/*.py' | sort | sed 's/^/- [ ] /'
  git ls-files 'frontend/src/**/*.ts' 'frontend/src/**/*.tsx' | grep -E '__tests__|\.test\.tsx?$' | sort -u | sed 's/^/- [ ] /'
} > docs/superpowers/audits/AUDIT-PROGRESS.md
echo "Ledger satır sayısı: $(grep -c '^- \[ \]' docs/superpowers/audits/AUDIT-PROGRESS.md)"
```

Expected: Ledger satır sayısı = **1274** (661 üretim + 613 test). NOT: `app/*.py` kullan
(`app/**/*.py` kök dosyaları kaçırır — T0'da bu hata yakalandı + düzeltildi). Sayı saparsa dur, glob'ları doğrula.

- [ ] **Step 2: AUDIT-INDEX.md iskeletini oluştur**

```bash
cat > docs/superpowers/audits/AUDIT-INDEX.md <<'EOF'
# AUDIT-INDEX — Bulgu Özeti

Şiddet yalnız düzeltme sırası içindir; kullanıcı kuralı gereği **her bulgu kritiktir**.

| ID | Şiddet | Sınıf | Konum (dosya:satır) | Başlık | Durum |
|----|--------|-------|---------------------|--------|-------|
EOF
echo "index oluşturuldu"
```

- [ ] **Step 3: Statik araç baseline'ı yakala (hızlı, DB gerektirmez)**

Run:
```bash
ruff check app --select E,F,W,I 2>&1 | tee docs/superpowers/audits/_baseline-ruff.txt | tail -3
mypy app --ignore-missing-imports --no-strict-optional 2>&1 | tee docs/superpowers/audits/_baseline-mypy.txt | tail -3
(cd frontend && npm run lint) 2>&1 | tee docs/superpowers/audits/_baseline-eslint.txt | tail -3
```
Expected: üç dosya yazılır. Çıktıdaki gerçek uyarı/hatalar (yanlış pozitif elenerek) ilgili S-grubunda bulguya dönüştürülür. **pytest/vitest baseline'ı** burada koşulmaz — lokal DB-test gotcha'sı var (bkz. memory `local_test_db_execution`); test davranışı S10'da statik okumayla denetlenir, runtime gerektiren şüpheler `needs-verification`.

- [ ] **Step 4: Commit (kullanıcı onayıyla)**

```bash
git switch -c audit/fullcode-2026-06-14 2>/dev/null || true
git add docs/superpowers/audits/ docs/superpowers/specs/2026-06-14-fullcode-audit-design.md docs/superpowers/plans/2026-06-14-fullcode-audit.md
git commit -m "audit: bootstrap full-code audit ledger + index"
```

---

## Denetim oturumu standart akışı (Task 1–23 hepsi bunu izler)

Her task için tekrarlanan 5 adım — kod bloğu yerine **mekanik prosedür**:

1. **Oku:** Task'ın "Files" listesindeki her dosyayı `Read` ile **baştan sona** aç. Büyük gruplar için listeyi üreten `git ls-files` komutu verilmiştir; çıktının her satırını sırayla oku. Skim yok.
2. **Tara:** Her dosyada spec §5'in ilgili kontrol listesini (Backend / Frontend / Migration / Test) uygula. Bağımlı dosya gerekiyorsa aç ve teyit et (demir kural 3).
3. **Yaz:** Bulunan her şeyi task'ın hedef bulgu dosyasına §6 şemasıyla ekle (ID = AUDIT-NNN, artan). Aynı satırı `AUDIT-INDEX.md` tablosuna bir satır olarak ekle.
4. **İşaretle:** Okunan her dosyayı `AUDIT-PROGRESS.md`'de `[x]` yap.
5. **Commit (onayla):** `git add docs/superpowers/audits/ && git commit -m "audit(sN): <grup> denetimi — <K> bulgu"`.

**Bitiş koşulu (her task):** Task'ın kapsadığı tüm dosyalar ledger'da `[x]`. Hiç bulgu çıkmazsa bile dosya `[x]` işaretlenir ve bulgu dosyasına `<grup>: temiz, N dosya okundu, 0 bulgu` notu düşülür (negatif kanıt da kayıttır).

---

## Task 1 — S1: Backend çekirdek

**Hedef bulgu dosyası:** `docs/superpowers/audits/s1-backend-core.md`
**Files (14 — hepsi varlık-teyitli, sırayla oku):**
- `app/config.py` (324)
- `app/main.py` (688) — exception handler'lar, `_sentry_before_send`, CORS, middleware sırası
- `app/core/security.py` (116) — JWT, hash, token
- `app/api/deps.py` (303) — `get_current_active_user/admin`, `require_permissions`
- `app/api/middleware/rate_limiter.py` (50)
- `app/core/container.py` (569) — DI singleton'lar, lazy-load thread-safety
- `app/database/unit_of_work.py` (260) — transaction sınırı, repo property'leri
- `app/database/base_repository.py` (422) — generic CRUD, `get_all` kwarg tutarlılığı
- `app/database/connection.py` — `create_async_engine`, pool ayarları
- `app/database/db_session.py` — session factory
- `app/database/init_db.py`
- `app/database/models.py` (1772) — ORM, constraint'ler (`ck_seferler_check_sefer_net_kg_calc`), nullable
- `app/core/entities/models.py` (669) — Pydantic domain entity'leri
- `app/core/exceptions.py` (116) — `DomainError` hiyerarşisi

**Odak (bu grupta yüksek getiri):** secret/JWT yönetimi, exception handler'ların hata zarfı uyumu, CORS (`settings.cors_origins` doğru mu), DI thread-safety, UoW commit/rollback, `models.py` ↔ migration drift, `base_repository.get_all` kwarg sapması (`sadece_aktif`/`include_inactive`).

- [ ] Standart akış adım 1–5 (yukarı). Çıktı: `s1-backend-core.md` + index satırları + 14 dosya `[x]`.

---

## Task 2 — S2a: Repository katmanı

**Hedef:** `docs/superpowers/audits/s2-domain.md` (bölüm: Repositories)
**Files (22, enumerasyon):**
```bash
git ls-files 'app/database/repositories/*.py' | grep -v __init__
```
**Odak:** session'sız singleton'da raw-SQL (`execute_query`, `get_all_with_stats_paged`), `get_all` kwarg uyumsuzluğu, ham SQL string interpolasyonu (SQL injection), soft-delete filtre tutarlılığı, N+1.

- [ ] Standart akış adım 1–5. Çıktı: s2-domain.md (Repositories bölümü) + 22 dosya `[x]`.

## Task 3 — S2b: Domain servisleri (core/services, 1. yarı)

**Hedef:** `s2-domain.md` (bölüm: Services A–M)
**Files (enumerasyonun ilk yarısı):**
```bash
git ls-files 'app/core/services/*.py' | grep -v __init__ | sort | head -31
```
**Odak:** transaction yönetimi (UoW paylaşımı), domain kuralı (yakıt/maliyet/skor formülleri, sıfıra bölme), sessiz fallback (örn. `sefer_fuel_estimator` timeout), `SafeColumnMapper` two-pass, `net_kg` hesabı, yutulmuş exception.

- [ ] Standart akış adım 1–5.

## Task 4 — S2c: Domain servisleri (core/services, 2. yarı) + schemas

**Hedef:** `s2-domain.md` (bölüm: Services N–Z + Schemas)
**Files:**
```bash
git ls-files 'app/core/services/*.py' | grep -v __init__ | sort | tail -n +32
git ls-files 'app/schemas/*.py' | grep -v __init__
```
**Odak (schemas):** Pydantic validator doğruluğu, mass-assignment (`extra`/`model_config`), entity↔schema dönüşüm tutarsızlığı (ARCH-004 mypy epic'in riskli dilimi), eksik validasyon.

- [ ] Standart akış adım 1–5. Bitişte `core/services` (62) + `schemas` (25) + `repositories` (22) tümü `[x]`.

---

## Task 5 — S3a: API endpoints (admin_* + auth)

**Hedef:** `docs/superpowers/audits/s3-api-endpoints.md`
**Files:**
```bash
git ls-files 'app/api/v1/endpoints/admin_*.py' 'app/api/v1/endpoints/auth.py' 'app/api/v1/api.py'
```
**Odak (authz yüzeyi — en kritik):** her hassas endpoint'te `require_permissions`/`get_current_active_admin` var mı, yetki string'i doğru mu, IDOR (kullanıcı kendi kaynağı mı), token/refresh akışı, hata zarfı standardı, `log_audit_event` çağrıları.

- [ ] Standart akış adım 1–5.

## Task 6 — S3b: API endpoints (domain endpoints)

**Hedef:** `s3-api-endpoints.md` (devam)
**Files (kalan ~28):**
```bash
git ls-files 'app/api/v1/endpoints/*.py' | grep -v __init__ | grep -vE '/(admin_|auth\.py)'
```
**Odak:** authz, input validasyonu, async job pattern doğruluğu (202 + task_id), `BackgroundJobManager` kullanımı, SSE/websocket auth, response shape.

- [ ] Standart akış adım 1–5. Bitişte `api/v1/endpoints` (44) + `api/v1/api.py` tümü `[x]`.

---

## Task 7 — S4a: ML alt sistemi

**Hedef:** `docs/superpowers/audits/s4-ml-ai.md` (bölüm: ML)
**Files:**
```bash
git ls-files 'app/core/ml/*.py' 'app/core/ml/predictors/*.py' | grep -v __init__
```
**Odak:** ensemble ağırlık normalizasyonu (R²), cold-start `DEFAULT_WEIGHTS`, sıfıra bölme/NaN/inf, `asyncio.to_thread` atlanmış bloklayan çağrı, ARIMA min-gözlem fallback, Kalman, `.pkl` yükleme hata yönetimi, MAX_REALISTIC clamp log gürültüsü.

- [ ] Standart akış adım 1–5.

## Task 8 — S4b: AI/RAG + orkestrasyon servisleri

**Hedef:** `s4-ml-ai.md` (bölüm: AI + services/)
**Files:**
```bash
git ls-files 'app/core/ai/*.py' | grep -v __init__
git ls-files 'app/services/*.py' 'app/services/api/*.py' | grep -v __init__
```
**Odak:** Groq/LLM çağrı hata yönetimi & timeout, FAISS index persist/yükleme, prompt injection yüzeyi, dış API (Mapbox/Open-Meteo) retry pattern (429/Retry-After, demir kural: 4xx sessizce None'a düşmesin), `sefer_import_service` net_kg/dolu_agirlik hesabı.

- [ ] Standart akış adım 1–5. Bitişte `core/ml`(28+2) + `core/ai`(12) + `services`(10) tümü `[x]`.

---

## Task 9 — S5a: Altyapı (events, audit, cache, resilience)

**Hedef:** `docs/superpowers/audits/s5-infrastructure.md`
**Files:**
```bash
git ls-files 'app/infrastructure/events/*.py' 'app/infrastructure/audit/*.py' 'app/infrastructure/cache/*.py' 'app/infrastructure/resilience/*.py' | grep -v __init__
```
**Odak:** outbox transactional pattern (at-least-once, idempotency), event_bus Redis pub/sub hata yolu, `admin_audit_log` çift-yazım (Türkçe kolonlar, `begin_nested` SAVEPOINT izolasyonu, FK-violation kaçınma id≤0→NULL), cache invalidation, retry/circuit breaker doğruluğu.

- [ ] Standart akış adım 1–5.

## Task 10 — S5b: Altyapı (background, monitoring, notifications) + workers

**Hedef:** `s5-infrastructure.md` (devam)
**Files:**
```bash
git ls-files 'app/infrastructure/background/*.py' 'app/infrastructure/monitoring/*.py' 'app/infrastructure/notifications/*.py' 'app/workers/tasks/*.py' | grep -v __init__
```
**Odak:** Celery task idempotency/retry, beat schedule, `BackgroundJobManager` task lifecycle & hata yakalama, monitoring prob'larının sessiz-fallback tespiti, SSE token, telegram notifier hata yolu.

- [ ] Standart akış adım 1–5. Bitişte tüm `infrastructure/*` + `workers/tasks`(14) `[x]`.

---

## Task 11 — S6: Alembic migration'ları

**Hedef:** `docs/superpowers/audits/s6-migrations.md`
**Files (27, kronolojik oku):**
```bash
git ls-files 'alembic/versions/*.py' | sort
```
**Odak:** `downgrade` tersinirliği & veri kaybı, nullable→not-null veri-dolumsuz geçiş, `op.execute` ham SQL, index/constraint adı çakışması, tek-head garantisi (`alembic check` mantığı), `models.py` ile drift. Ayrıca `alembic/env.py`'yi de oku.

```bash
git ls-files 'alembic/env.py'
```

- [ ] Standart akış adım 1–5.

## Task 12 — S7: scripts + mikroservisler

**Hedef:** `docs/superpowers/audits/s7-scripts-microservices.md`
**Files:**
```bash
git ls-files 'scripts/*.py' | sort
git ls-files 'telegram_bot/**/*.py' 'ocr_service/**/*.py' | sort
```
**Odak:** TRUNCATE/reset script'lerinde güvenlik kapısı (`--confirm`, DB adı koruması), e2e smoke doğruluğu, telegram bot input validasyonu/komut auth, OCR path traversal & dosya tipi doğrulama, hardcoded secret.

- [ ] Standart akış adım 1–5.

---

## Task 13 — S8a: Frontend çekirdek (HTTP + auth + state)

**Hedef:** `docs/superpowers/audits/s8-frontend-core.md`
**Files:**
```bash
git ls-files 'frontend/src/services/api/*.ts' 'frontend/src/services/*.ts' 'frontend/src/context/*.tsx' 'frontend/src/stores/*.ts' 'frontend/src/lib/*.ts' | grep -v __tests__
```
**Odak:** `axiosInstance` interceptor refresh döngüsü, `fetchWithAuth` yalnız `/auth/*` kuralı, token saklama/sızıntı, Zustand persist serileştirme, `AuthContext` token lifecycle, domain servislerinin `axiosInstance` kullanımı (kural ihlali var mı).

- [ ] Standart akış adım 1–5.

## Task 14 — S8b: Frontend hooks + features

**Hedef:** `s8-frontend-core.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/hooks/*.ts' 'frontend/src/hooks/*.tsx' 'frontend/src/features/**/*.ts' 'frontend/src/features/**/*.tsx' | grep -v __tests__
```
**Odak:** React Query `queryKey` prefix çakışması, `useEffect` bağımlılık dizileri/stale closure, `useTaskStatus` polling auto-stop, async yarış, hata yayılımı.

- [ ] Standart akış adım 1–5. Bitişte S8 dosyaları `[x]`.

---

## Task 15 — S9a: Frontend components (admin, alerts, auth, coaching)

**Hedef:** `docs/superpowers/audits/s9-frontend-components.md`
**Files:**
```bash
git ls-files 'frontend/src/components/admin/**' 'frontend/src/components/alerts/**' 'frontend/src/components/auth/**' 'frontend/src/components/coaching/**' | grep -vE '__tests__|\.test\.' | grep -E '\.tsx?$'
```
**Odak:** `RequirePermission` doğru sarmalama, XSS (`dangerouslySetInnerHTML`), eksik error/empty state, hardcoded renk/px (token ihlali), erişilebilirlik.

- [ ] Standart akış adım 1–5.

## Task 16 — S9b: components (dashboard, drivers, executive, fleet, fleet-insights)

**Hedef:** `s9-frontend-components.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/components/dashboard/**' 'frontend/src/components/drivers/**' 'frontend/src/components/executive/**' 'frontend/src/components/fleet/**' 'frontend/src/components/fleet-insights/**' | grep -vE '__tests__|\.test\.' | grep -E '\.tsx?$'
```
- [ ] Standart akış adım 1–5.

## Task 17 — S9c: components (fuel, locations, monitoring, modules)

**Hedef:** `s9-frontend-components.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/components/fuel/**' 'frontend/src/components/locations/**' 'frontend/src/components/monitoring/**' 'frontend/src/components/modules/**' | grep -vE '__tests__|\.test\.' | grep -E '\.tsx?$'
```
- [ ] Standart akış adım 1–5.

## Task 18 — S9d: components (trips, vehicles, common, ui + kalan)

**Hedef:** `s9-frontend-components.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/components/trips/**' 'frontend/src/components/vehicles/**' 'frontend/src/components/common/**' 'frontend/src/components/ui/**' | grep -vE '__tests__|\.test\.' | grep -E '\.tsx?$'
# kalan kapsanmamış component klasörleri:
git ls-files 'frontend/src/components/**/*.tsx' 'frontend/src/components/**/*.ts' | grep -vE '__tests__|\.test\.' | grep -vE '/(admin|alerts|auth|coaching|dashboard|drivers|executive|fleet|fleet-insights|fuel|locations|monitoring|modules|trips|vehicles|common|ui)/'
```
**Odak (trips):** `TripTable` virtualization (`@tanstack/react-virtual`) key/index doğruluğu, `BulkActionBar`, `use-trip-store` persist.

- [ ] Standart akış adım 1–5.

## Task 19 — S9e: pages + resources

**Hedef:** `s9-frontend-components.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/pages/**/*.tsx' 'frontend/src/pages/**/*.ts' 'frontend/src/resources/**/*.ts' | grep -vE '__tests__|\.test\.'
git ls-files 'frontend/src/*.tsx' 'frontend/src/*.ts' | grep -vE '__tests__|\.test\.'
```
**Odak:** sayfa kompozisyonu ince mi (ağır mantık feature'da mı), router/guard, `resources/tr` tutarlılığı (eksik/fazla string, `t()` yerine resource kuralı). `App.tsx`/`main.tsx`/router'ı da kapsa.

- [ ] Standart akış adım 1–5. Bitişte tüm S9 (`components` 152 + `pages` 30 + `features` 5 + `resources` 18) `[x]`. **Üretim kodu = %100 okundu.**

---

## Task 20 — S10a: Backend unit testleri

**Hedef:** `docs/superpowers/audits/s10-tests.md`
**Files:**
```bash
git ls-files 'app/tests/unit/**/*.py' | grep -v __init__ | sort
```
**Odak:** sahte test (yalnız mock'u doğrulayan), tautolojik assertion, `skip`/`xfail` artıkları, zayıf assertion, paylaşılan state sızıntısı.

- [ ] Standart akış adım 1–5.

## Task 21 — S10b: Backend integration + diğer testler

**Hedef:** `s10-tests.md` (devam)
**Files:**
```bash
git ls-files 'app/tests/**/*.py' | grep -v '/unit/' | grep -v __init__ | sort
```
**Odak:** status-code-only doğrulama (body parse etmeyen), conftest fixture sızıntısı, `CELERY_EAGER` varsayımı, stale-test regresyon riski (CLAUDE.md/memory'de geçmişi var).

- [ ] Standart akış adım 1–5.

## Task 22 — S10c: Frontend testleri (1. yarı)

**Hedef:** `s10-tests.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/**/*.test.ts' 'frontend/src/**/*.test.tsx' 'frontend/src/**/__tests__/**' | sort -u | head -75
```
**Odak:** `vi.mock` ile gerçek davranışın maskelenmesi, Türkçe büyük harf case-fold gotcha'sı (yanlış geçen testler), `getByText` çoklu-eşleşme, mock passthrough'un bug gizlemesi (`RequirePermission`).

- [ ] Standart akış adım 1–5.

## Task 23 — S10d: Frontend testleri (2. yarı)

**Hedef:** `s10-tests.md` (devam)
**Files:**
```bash
git ls-files 'frontend/src/**/*.test.ts' 'frontend/src/**/*.test.tsx' 'frontend/src/**/__tests__/**' | sort -u | tail -n +76
```
- [ ] Standart akış adım 1–5. Bitişte **tüm test dosyaları `[x]` — ledger %100.**

---

## Task 24 — Kapatma: kapsam doğrulama + index rollup

**Files:** `docs/superpowers/audits/AUDIT-INDEX.md` (finalize)

- [ ] **Step 1: Kapsam %100 doğrula**

Run:
```bash
echo "Kalan okunmamış dosya: $(grep -c '^- \[ \]' docs/superpowers/audits/AUDIT-PROGRESS.md)"
```
Expected: **0**. Sıfır değilse → eksik dosyalar var, ilgili S-task'a dön.

- [ ] **Step 2: Denetim sonrası kod kayması kontrolü**

Run:
```bash
git log --oneline --since="2026-06-14" -- app frontend/src alembic scripts | head
```
Denetim başladıktan sonra değişmiş üretim dosyası varsa ledger'da `[ ]`'e geri al ve yeniden denetle (spec §11).

- [ ] **Step 3: Index istatistiği üret**

`AUDIT-INDEX.md` başına özet ekle: toplam bulgu, şiddet dağılımı (blocker/high/medium/low), sınıf dağılımı, `needs-verification` sayısı. Sayıların index tablosuyla tutarlılığını gözle doğrula.

- [ ] **Step 4: Öz-denetim (rastgele örnekleme)**

Index'ten rastgele 5 bulgu seç; her birinin `dosya:satır` referansını `Read` ile aç ve kanıt alıntısının gerçekten o satırlarda olduğunu teyit et. Tutmayan varsa → demir kural ihlali, ilgili bulguyu düzelt/çıkar. (Bu, "uydurma yok" garantisinin son kontrolü.)

- [ ] **Step 5: Commit + Faz 2 devri**

```bash
git add docs/superpowers/audits/
git commit -m "audit: full-code line-by-line audit complete — <N> bulgu, kapsam %100"
```
Faz 2 (düzeltme) için ayrı spec + plan: bulguları şiddet sırasına göre triyaj, TDD ile grupla düzelt.

---

## Self-Review (plan yazımı sonrası — spec'e karşı kontrol)

- **Spec kapsama:** Spec §8 sıraları S1–S10 → Task 1–23 birebir eşleşiyor; S1(T1), S2(T2–4), S3(T5–6), S4(T7–8), S5(T9–10), S6(T11), S7(T12), S8(T13–14), S9(T15–19), S10(T20–23) + bootstrap(T0) + kapatma(T24). §3 demir kurallar her task'ın standart akışında zorunlu. §6 şema + §7 ledger T0'da kuruldu. §9 Faz 2 devri T24'te. **Boşluk yok.**
- **Placeholder taraması:** TBD/TODO/"handle edge cases" yok; her task somut dosya listesi veya deterministik `git ls-files` komutu + odak + hedef dosya taşıyor. Denetim doğası gereği "kod bloğu" yerine mekanik prosedür var (özellik değil, denetim).
- **Tutarlılık:** Dosya yolları varlık-teyitli (S1 14 dosya, `connection.py`/`db_session.py`/`init_db.py` `session.py` yerine düzeltildi). Hedef bulgu dosyası adları index/spec ile aynı (`s1-backend-core.md` … `s10-tests.md`). Ledger üretim+test ayrımı T0 ile T24 doğrulaması arasında tutarlı.
