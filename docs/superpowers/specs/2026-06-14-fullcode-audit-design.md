# LojiNext Tam Satır-Satır Kod Denetimi — Tasarım (Design Spec)

- **Tarih:** 2026-06-14
- **Tip:** Denetim kampanyası (audit) — Faz 1 salt tespit, Faz 2 düzeltme
- **Durum:** Onay bekliyor → writing-plans'a devredilecek

---

## 1. Amaç ve bağlam

LojiNext kod tabanının **sistematik, satır düzeyinde** bir denetimini yürütmek ve
her bulguyu kanıta dayalı bir kayda işlemek. Kullanıcı kararı: **istisnasız her
dosya ve her satır eşit derinlikte** okunur (testler ve migration'lar dahil),
**tek ajan tarafından sıralı** yürütülür (subagent yok), bulgular **önce tespit
edilir, kod değiştirilmez**; düzeltme ayrı bir fazda yapılır.

Proje halihazırda bir prod-readiness denetim serisinin (ARCH-005→022, FAZ 0) içinde.
Bu kampanya o serinin **daha derin, tam-kapsam** bir turudur: amaç, makine
araçlarının (ruff/mypy/eslint) yakalayamadığı doğruluk, güvenlik, eşzamanlılık,
sessiz-hata ve mimari-sapma bulgularını insan-düzeyi okumayla çıkarmak.

## 2. Kapsam (ölçülmüş envanter)

`git ls-files` + `wc -l` ile ölçülmüştür (2026-06-14). Tahmin değil, gerçek sayım.

> **Düzeltme (audit T0 esnasında):** ilk sayım `app/**/*.py` glob'uyla yapıldığı için
> `app/` ve `frontend/src/` **kök** dosyaları (config.py, main.py, App.tsx, main.tsx…) kaçmıştı.
> `app/*.py` (git pathspec `*` zaten `/` geçer) ile düzeltilen gerçek sayımlar:

| Bölge | Dosya | Satır (~) |
|---|---:|---:|
| Backend üretim kodu (`app/*.py`, test hariç) | 316 | 64.657 |
| Backend testleri (`app/tests/*.py`) | 463 | — |
| Frontend üretim kodu (`frontend/src/*.ts(x)`, test hariç) | 286 | 44.980 |
| Frontend testleri (`*.test.ts(x)` + `__tests__`) | 150 | — |
| Alembic migration'ları (`alembic/versions/*.py`) | 27 | — |
| Bağımsız script'ler (`scripts/*.py`) | 27 | — |
| Mikroservisler (`telegram_bot/` 3 + `ocr_service/` 2) | 5 | 614 |
| **Üretim kodu toplamı** | **661** | **~110.250** |
| **Test kodu toplamı** | **613** | — |

Backend dizin dağılımı (non-test, satır):
`core/services` 62/16.422 · `api/v1/endpoints` 44/10.132 · `core/ml` 28/8.784 ·
`database/repositories` 22/4.127 · `schemas` 25/3.437 · `core/ai` 12/3.283 ·
`services` 8/2.433 · `infrastructure/monitoring` 12/2.130 · `core/entities` 3/1.183 ·
`workers/tasks` 14/1.277 · cache/resilience/events/audit/background/notifications ~2.800.

Frontend dizin dağılımı (non-test, satır):
`components` 152/25.878 · `pages` 30/6.943 · `services` 34/4.131 (içinde `services/api` 30/3.610) ·
`resources` 18/2.257 · `hooks` 22/2.168 · `features` 5/759 · `lib` 7/407 ·
`context` 2/362 · `stores` 2/260.

## 3. Demir kurallar (anti-halüsinasyon sözleşmesi)

Bu kurallar pazarlık konusu değildir; kullanıcının açık şartıdır.

1. **Okumadan bulgu yok.** Bir dosya hakkında bulgu yazabilmem için dosyayı bu
   oturumda `Read` ile baştan sona açmış olmam şarttır. Skim, parça okuma,
   "muhtemelen şöyledir" yasak.
2. **Her bulgu kanıt taşır:** gerçek `dosya:satır` referansı + dosyadan birebir
   **kod alıntısı**. Alıntı olmadan bulgu kayda girmez.
3. **Çapraz bağımlılık doğrulanır.** Bir bulgu başka dosyadaki bir gerçeğe
   dayanıyorsa (repo kwarg'ı, şema alanı, DB constraint, çağrı imzası), o dosya da
   açılıp teyit edilir. Varsayım yasak.
4. **Uydurma/hayali kod yasak.** Önerilen düzeltmeler **tarif** olarak yazılır
   (ne değişmeli, neden). Tam yama ancak ilgili gerçek kod okunduktan sonra ve
   Faz 2'de üretilir.
5. **Doğrulanamayan ≠ bug.** Runtime/veri gerektiren, statik okumayla
   kesinleştirilemeyen şüpheler `needs-verification` etiketiyle ayrı tutulur;
   "bug" diye sayılmaz.
6. **Makine sinyalleri zemindir, bulgu değildir.** ruff/mypy/eslint/pytest/vitest
   çıktıları gerçektir ve kayda alınır, ama her biri yine elle teyit edilir
   (yanlış pozitif olabilir).

## 4. Denetim metodolojisi (dosya başına protokol)

Her kaynak dosya için sabit, mekanik akış:

1. **Tam okuma** — dosyanın tüm satırları `Read` ile okunur.
2. **Kontrol listesi uygulanır** (§5).
3. **Çapraz doğrulama** — bağımlı dosyalar açılır (kural 3).
4. **Bulgu yazımı** — bulunan her şey §6 şemasıyla kayda eklenir.
5. **Ledger işaretlenir** — dosya `AUDIT-PROGRESS.md`'de `[x] tam okundu` yapılır.
6. **Devam** — sıradaki dosyaya geçilir.

**Oturum başı ısınma (yalnız ilk oturum / her büyük grup başı):**
`ruff check app`, `mypy app`, `cd frontend && npm run lint`, ve mevcut
`pytest` / `vitest --run` bir kez koşturulur. Çıktılar baseline olarak kaydedilir;
doğrulanan kalemler kayda alınır. Bu adım gerçek araç çıktısına dayandığı için
demir kurallara uygundur.

## 5. Hata-sınıfı kontrol listesi

Her dosyada aşağıdaki sınıflar taranır.

### Backend (.py)
- **Doğruluk:** `None`/`await` eksikleri, `async` fonksiyon içinde bloklayan
  senkron çağrı, transaction sınırı hataları (UoW commit/rollback eksiği,
  `begin_nested` yanlış kullanımı), N+1 sorgu, off-by-one, yanlış karşılaştırma/
  operatör, mutable default argümanlar, yanlış tip dönüşümü.
- **Eşzamanlılık:** race condition, paylaşılan singleton state mutasyonu,
  `asyncio.to_thread` atlanmış bloklayan ML/IO çağrısı, idempotent olmayan
  outbox/celery task.
- **Sessiz hata:** `except: pass`, geniş `except Exception` ile yutma, hatayı
  gizleyen fallback (örn. fuel-estimator silent timeout fallback), log'suz
  `return None`, swallowed `await`.
- **Güvenlik:** ham SQL string interpolasyonu / f-string SQL, eksik authz
  (`require_permissions` / `get_current_active_admin` olmayan hassas endpoint),
  JWT/secret/token sızıntısı, hardcoded kimlik bilgisi, CORS yanlış yapılandırması,
  Pydantic mass-assignment (aşırı geniş `model_config`), Excel/OCR/dosya yolu
  path traversal, regex DoS, SSRF (dış API URL'leri).
- **Veri bütünlüğü:** DB check/unique/FK constraint ihlali riski (örn.
  `ck_seferler_check_sefer_net_kg_calc`), nullable uyumsuzluğu, `models.py` ↔
  migration drift, soft-delete kwarg tutarsızlığı (`sadece_aktif` vs
  `include_inactive`).
- **Domain kuralı:** yakıt/maliyet/cashflow/skor formülleri; birim tutarlılığı
  (L, km, kg, ₺); sıfıra bölme; NaN/inf yayılımı.
- **Mimari sapma:** CLAUDE.md katman kuralları (HTTP→endpoint→service→repo),
  DI ihlali (`container` yerine `get_container()`), yanlış servis katmanı
  yerleşimi, session'sız singleton repo'da raw-SQL.
- **Bakım:** ölü kod, duplikasyon, çözülmemiş `TODO/FIXME`, terk edilmiş feature
  flag, tutarsız hata zarfı (`{"error": {...}}` standardına aykırı).

### Frontend (.ts/.tsx)
- **Doğruluk:** hatalı `useEffect`/`useMemo`/`useCallback` bağımlılık dizileri,
  stale closure, async effect'te cleanup/yarış, `queryKey` çakışması/prefix
  sızıntısı, liste `key` çakışması, eksik error boundary, eksik loading/empty state.
- **Tip güvenliği:** `any`, gereksiz `as` cast, `!` non-null assertion, `@ts-ignore`.
- **Güvenlik:** `dangerouslySetInnerHTML` (XSS), token'ın yanlış katmanda
  tutulması, `fetchWithAuth`'un `/auth/*` dışında kullanımı (CLAUDE.md kuralı),
  axios interceptor refresh döngüsü.
- **Tutarlılık:** hardcoded renk/px (tasarım token'ı yerine), `t()` yerine
  `resources/tr` kuralının ihlali, erişilebilirlik (aria/rol) eksikleri.
- **Bakım:** ölü kod, kopya bileşen/yardımcı, kullanılmayan import/prop.

### Migration (.py)
- Tersinirlik (`downgrade` doğru mu / veri kaybı), `op.execute` ham SQL'i,
  nullable→not-null veri-dolumsuz geçiş, index/constraint adı çakışması,
  tek-head garantisi, `models.py` ile drift.

### Test (.py / .test.tsx)
- Sahte testler (yalnız mock'un kendisini doğrulayan), tautolojik assertion,
  `skip`/`xfail`/`only` artıkları, zayıf assertion (status-code-only,
  body doğrulamayan), kapsanmayan branch, paylaşılan state sızıntısı,
  yanlış pozitif geçen test (CLAUDE.md'deki stale-test regresyonu gibi).

## 6. Bulgu kaydı

### Konum
`docs/superpowers/audits/` altında:
- `AUDIT-INDEX.md` — tüm bulguların özet tablosu (master index).
- Modül başına bulgu dosyası, örn:
  `s1-backend-core.md`, `s2-domain-services.md`, `s3-api-endpoints.md`,
  `s4-ml-ai.md`, `s5-infrastructure.md`, `s6-migrations.md`,
  `s7-scripts-microservices.md`, `s8-frontend-core.md`,
  `s9-frontend-components.md`, `s10-tests.md`.
- `AUDIT-PROGRESS.md` — kapsam ledger'ı (§7).

### Bulgu şeması (her kayıt)
```
### AUDIT-NNN — <kısa başlık>
- Şiddet: blocker | high | medium | low
- Sınıf: bug | security | silent-failure | concurrency | data-integrity |
         domain-rule | arch-drift | dead-code | duplication | validation-gap | test-gap
- Konum: <dosya:satır[-satır]>
- Durum: open | needs-verification | confirmed | wontfix
- Kanıt:
    ```<dil>
    <dosyadan birebir kod alıntısı>
    ```
- Sorun: <neden problem — somut etki>
- Önerilen düzeltme: <tarif; uydurma kod değil>
- Bağımlılık: <varsa diğer AUDIT-NNN / dosya>
```

### Şiddet taksonomisi
Kullanıcı kuralı gereği **her bulgu kritik sayılır**; şiddet yalnız
**düzeltme sırası** içindir, bulguyu önemsizleştirmez.
- **blocker** — veri kaybı, güvenlik açığı, prod crash, yanlış para/yakıt hesabı.
- **high** — yanlış davranış / sessiz hata / yetkisiz erişim riski, veri görünür
  ama yanlış.
- **medium** — sağlamlık/mimari sapma/validasyon boşluğu/test boşluğu.
- **low** — bakım, ölü kod, stil-ötesi tutarsızlık.

### Index satır formatı (`AUDIT-INDEX.md`)
`| AUDIT-NNN | şiddet | sınıf | dosya:satır | başlık | durum |`

## 7. Kapsam kanıtı — AUDIT-PROGRESS.md

Çok oturumlu "her dosya okundu" garantisinin kanıtı. **Elle değil, gerçekten
üretilir** — böylece tek dosya bile atlanamaz:

```bash
# Üretim kodu ledger'ı (audit başında bir kez üretilir):
git ls-files 'app/**/*.py' 'frontend/src/**/*.ts' 'frontend/src/**/*.tsx' \
  'alembic/versions/*.py' 'scripts/*.py' 'telegram_bot/**/*.py' 'ocr_service/**/*.py'
# Çıktı her satır için "- [ ] <path>" checkbox'ına dönüştürülür.
```

Bir dosya okunup kontrol listesi uygulanınca `- [x]` yapılır. Bir S-grubu, ledger'daki
tüm dosyaları `[x]` olmadan **bitti sayılmaz**. Oturum sonunda kalan
`[ ]` sayısı = kalan iş; bu, oturumlar arası kaldığımız yerden devam mekanizmasıdır.

## 8. Sıralama (S1–S10)

Derinlik her yerde eşit; yalnız **sıra** risk-ağırlıklıdır (yüksek blast-radius önce).
Her grup ayrı bir bulgu dosyasına yazar; büyük gruplar oturumlara bölünür.

| Sıra | Kapsam | Dosya (~) | Bölünme |
|---|---|---:|---|
| **S1** | Backend çekirdek: `config.py`, `main.py`, `core/security.py`, `api/deps.py`, `api/middleware/rate_limiter.py`, `core/container.py`, `database/unit_of_work.py`, `database/base_repository.py`, `database/connection.py`, `database/db_session.py`, `database/init_db.py`, `database/models.py`, `core/entities/models.py`, `core/exceptions.py` | 14 | 1 oturum |
| **S2** | Domain: `core/services/` (62) + `database/repositories/` (22) + `schemas/` (25) | ~109 | 3–4 oturum |
| **S3** | API yüzeyi: `api/v1/endpoints/` (44) + `api/v1/api.py` | ~45 | 2 oturum (authz odak) |
| **S4** | Orkestrasyon/ML/AI: `services/` (10) + `core/ml/` (28+2) + `core/ai/` (12) | ~52 | 2 oturum |
| **S5** | Altyapı: events/audit/cache/resilience/background/monitoring/notifications + `workers/tasks/` (14) | ~57 | 2 oturum |
| **S6** | Alembic migration'ları (27) — drift + tersinirlik | 27 | 1 oturum |
| **S7** | `scripts/` (27) + mikroservisler (`telegram_bot/` 3, `ocr_service/` 2) | ~32 | 1 oturum |
| **S8** | Frontend çekirdek: `services/api/` (30) + `services/` kök + axios/auth interceptor + `context/` (2) + `stores/` (2) + `lib/` (7) + `hooks/` (22) | ~70 | 2 oturum |
| **S9** | Frontend bileşenler: `components/` (152) + `pages/` (30) + `features/` (5) + `resources/` (18) — domain domain (admin, alerts, auth, coaching, dashboard, drivers, executive, fleet, fuel, locations, trips, vehicles, monitoring, ui, common…) | ~205 | 4–5 oturum |
| **S10** | Testler: backend (453) + frontend (150) — sahte/zayıf test avı | ~603 | 3–4 oturum |

Toplam tahmini **~20–25 oturum**. Sıra kesin değildir; bir grupta bulunan
yüksek-riskli bağımlılık erken ele alınabilir, ama hiçbir dosya ledger'dan düşmez.

## 9. Faz 2 devri (düzeltme — bu spec'in kapsamı dışında, ayrı plan)

Faz 1 (bu kampanya) bittiğinde veya modül bittikçe:
1. Bulgular kullanıcıyla triyaj edilir (şiddet sırasına göre).
2. Düzeltmeler **TDD** ile (önce kırmızı test) gruplar halinde uygulanır.
3. Pre-commit yeniden stage (ruff/format/detect-secrets), `pytest`/`vitest` ile
   doğrulanır.
4. Her commit ilgili `AUDIT-NNN` ID'lerini referanslar; bulgu `confirmed→fixed`.

Faz 2 ayrı bir spec + writing-plans turu gerektirir.

## 10. Başarı kriterleri

- `AUDIT-PROGRESS.md`'deki **tüm** üretim + test dosyaları `[x]`.
- Her bulgu §3 demir kurallarına uyar (kanıt + dosya:satır + alıntı).
- `needs-verification` bulgular ayrı işaretli, "bug" sayımına karışmamış.
- `AUDIT-INDEX.md` tüm bulguları şiddet/sınıf/durum ile listeler.
- Hiç uydurma kod/satır referansı yok (rastgele örnekleme ile öz-denetlenebilir).

## 11. Riskler ve kısıtlar

- **Token/oturum maliyeti:** ~110k satır + 603 test okumak büyük; ledger ile
  bölünür, her oturum kaldığı yerden devam eder.
- **Yanlış pozitif:** statik okuma runtime davranışını her zaman kesinleştiremez →
  `needs-verification` mekanizması bunu yönetir.
- **Kod kayması:** kampanya uzun sürer; bir dosya denetlendikten sonra değişirse
  ledger'da yeniden `[ ]` yapılır (git diff ile tespit).
- **Lokal DB-test kısıtı:** mevcut bilinen gotcha (native PG / Py sürümü) Faz 1'i
  etkilemez (okuma denetimi), yalnız Faz 2 doğrulamasında dikkate alınır.

## 12. Kapsam dışı (YAGNI)

- Faz 1'de **hiçbir kod değişikliği yapılmaz** (düzeltme Faz 2).
- Performans profilleme / yük testi (ayrı iş).
- Bağımlılık CVE taraması (CI `pip-audit`/`npm audit` zaten yapıyor; bulgu çıkarsa
  kayda alınır ama ayrı tarama koşulmaz).
- Yeni özellik / refactor uygulaması (yalnız tespit + öneri).
