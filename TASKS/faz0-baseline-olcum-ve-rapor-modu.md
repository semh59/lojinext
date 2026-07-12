# FAZ0 — Baseline Ölçüm ve Rapor Modu

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz.

**Amaç:** Hiçbir kodu değiştirmeden, mevcut ihlalleri sayıp dondurmak; CI'a yalnız RAPOR modunda (non-blocking) bir adım eklemek. Sert Kısıt 2 (baseline önce, gate sonra).

**Giriş kriteri:** Plan onayı (bu dosyanın kendisi).
**Çıkış kriteri:** Baseline dosyaları repo'da; rapor adımı CI'da yeşil; main dalı YEŞİL (kırmızı-CI disiplini — kırmızıysa önce onu düzelt, üstüne stacklenmez).

---

## Adım 1 — import-linter kurulumu (rapor modu, henüz gate değil) — ✅ TAMAMLANDI

`app/requirements-dev.txt`'e eklendi: `import-linter==2.13`.

Repo kökünde `.importlinter` (INI formatı — root `pyproject.toml` yok, ölçüldü, bu yüzden ayrı dosya). **Düzeltme (lokal test sırasında bulundu):** plandaki `app.api.v1.endpoints` gerçekte `__init__.py` içermeyen bir namespace-package — grimp (import-linter'ın AST motoru) bunu "modül yok" diye reddediyor. Gerçek paketlerle değiştirildi:
```ini
[importlinter]
root_package = app

[importlinter:contract:report-only]
name = Modular monolith boundary (report-only, FAZ0)
type = independence
modules =
    app.core.services
    app.services
```
Bu ilk kontrat kasıtlı olarak zayıf (gerçek bölme FAZ1'de). Lokal doğrulama: `lint-imports --config .importlinter` çalıştı, crash etmedi, beklenen ihlalleri raporladı (`app.core.services` → `app.services` — bilinen mevcut bağlaşıklık, MEMORY §2.1'deki container.py kablolamasıyla tutarlı). Amaç yalnız aracın çalıştığını kanıtlamaktı — BROKEN çıktısı normal ve beklenen (rapor-modu, gate değil).

CI'a (`.github/workflows/ci.yml`, "Backend lint (ruff)" adımından hemen sonra) non-blocking adım eklendi:
```yaml
      - name: Import boundary report (non-blocking, FAZ0)
        run: lint-imports --config .importlinter || true
        continue-on-error: true
```
`requirements-dev.txt` bu job'da zaten satır 139'da kuruluyor — ayrı bir pip install adımı gerekmedi.

## Adım 2 — Kalite baseline JSON'ları — ✅ TAMAMLANDI

```bash
radon cc app -j -i tests > docs/superpowers/audits/faz0-radon-baseline.json   # 2097 fonksiyon/metot bloğu
find app -name "*.py" -not -path "*/tests/*" -not -path "*__pycache__*" -not -path "*archive*" | \
  xargs wc -l | sort -rn > docs/superpowers/audits/faz0-loc-baseline.txt      # 327 dosya + toplam satırı
```
İki dosya da `docs/superpowers/audits/`'a yazıldı — **düzeltme:** repo kuralı bu dizinde yalnız `.md` commit eder (`.gitignore:140,143` geniş `*.txt`/`*.json` engeli var, mevcut audit klasörü emsali sadece markdown). Ham dump'lar yerel kaldı; bulgular `docs/superpowers/audits/faz0-baseline-sonuclari.md`'ye özetlenip commit'lendi. `arch/quality_baseline.json`'un ham girdisi olacak (FAZ1'de üretilir) — FAZ0'da yalnız ham ölçüm donduruldu.

## Adım 3 — model_versions ↔ model_versiyonlar doğrulaması — ✅ TAMAMLANDI

`app/core/ml/model_manager.py`'de 9 site (satır 85,102,159,174,199,214,226,237,253 — plandaki "7"den düzeltildi, `grep -c model_versions` ile yeniden sayıldı) raw SQL `model_versions` tablosuna erişiyor; ORM tablosu `model_versiyonlar` (models.py:1147). Canlı DB'de doğrulandı:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```
**Sonuç: `model_versiyonlar` MEVCUT (50 tablodan biri), `model_versions` YOK.** `model_manager.py`'deki 9 raw-SQL sitesi **kırık/ölü kod** — `relation "model_versions" does not exist` hatası verirler. Bu modüler-monolit planının kapsamı dışında ayrı bir bug — `TASKS/modules/prediction-ml.md` §3'e not düşüldü, bu FAZ'da kod DEĞİŞTİRİLMEDİ (yalnız tespit + dokümantasyon).

## Adım 4 — iceri_aktarim_gecmisi sahiplik kararı — ✅ TAMAMLANDI

`grep -rn iceri_aktarim_gecmisi app --include="*.py"` (tests/__pycache__ hariç) sonucu: tablonun repository'si (`app/database/repositories/import_repo.py::ImportHistoryRepository`) VE tek okuyucu endpoint'i (`app/api/v1/endpoints/admin_imports.py`) **zaten import_excel modülünün dosya envanterinde**; admin_platform'da hiçbir kullanım sitesi yok. **Karar: (B) sahiplik import_excel'e taşınır → 14 şema.** `MEMORY/PROGRESS.md` §4.3, `TASKS/modules/import-excel.md` §3 ve `TASKS/modules/admin-platform.md` §3'e işlendi.

## Adım 5 — main dalı yeşil teyidi — ✅ KÖK NEDEN BULUNDU + DÜZELTİLDİ (harici sorun, kullanıcı isteğiyle bu oturumda çözüldü)

```bash
git log --oneline -5
gh run list --branch main --limit 5
```
**Ölçüm (2026-07-12):** main run `29194122114` (commit `abd673b`) FAIL — ama yalnız "Frontend E2E tests" adımında, 25/257 test kırmızı; tüm önceki backend/unit/integration gate'leri ✓. `gh run view --log-failed` + Playwright rapor artifact'i (`error-context.md`'ler) indirilip incelendi. **5 ayrı kök neden, hepsi test-fixture/locator kaynaklı, üretim kodunda hiçbir bug yok:**

1. `alerts.spec.ts`+`dashboard.spec.ts` (15 test): mock'lar eski `reason: string` alanını kullanıyordu, gerçek Zod şeması (`MaintenanceVehicleSchema`) `reason_codes: {code,params}[]` istiyor → `AnomalyTable.tsx`/`AnomalyWidget.tsx` `undefined.map()` ile çöküyordu.
2. `analitik.spec.ts` (7 test): AdminLayout'un `<h2>` üst-başlığı ile sayfanın kendi `<h1>`'i AYNI metni ("Kullanım Analitiği") gösteriyor → `beforeEach`'teki belirsiz locator strict-mode ihlaliyle düşüyordu.
3. `maintenance.spec.ts` (1 test): `MOCK_PREDICTION`'da `bakim_tipi` alanı hiç yoktu → `getBakimTipiMeta(undefined).label` çöküyordu.
4. `veri-yonetim.spec.ts` (2 test): mock `durum: 'tamamlandi'/'geri_alindi'` (Türkçe) kullanıyordu, uygulama kodu (kendi yorumunda açıkça belirtilmiş) gerçek backend kontratı `"COMPLETED"/"ROLLED_BACK"` (İngilizce) bekliyor.

Hepsi `frontend/e2e/tests/` altında test-only düzeltmeler, ayrı commit'te (`fix(e2e): 5 stale test fixture/locator failures...`). `tsc --noEmit` temiz. Yerel authedPage koşumu, yerel dev DB'nin `.env.test` kimlik bilgileriyle eşleşen bir admin seed'i olmadığı için yapılamadı (CI kendi taze admin'ini seed ediyor) — kanıt kod-seviyesinde (gerçek Zod şeması + uygulamanın kendi açıklayıcı yorumları + tam eşleşen stack-trace satırları) çok güçlü olduğundan, doğrulama CI'nin bir sonraki koşusuna bırakıldı.

## Kabul Kriterleri
- [x] `.importlinter` dosyası var, `lint-imports --config .importlinter` lokal çalışıyor (hata vermeden, rapor basıyor)
- [x] CI'daki rapor adımı eklendi (`continue-on-error: true`) — push sonrası CI koşumunda gözlemle doğrulanacak
- [x] Baseline ölçüldü ve commit'lendi: `docs/superpowers/audits/faz0-baseline-sonuclari.md` (ham json/txt repo kuralı gereği lokal)
- [x] model_versions/model_versiyonlar sorusu cevaplanmış ve not düşülmüş
- [x] iceri_aktarim_gecmisi kararı verilmiş, 2 bağımlı görev dosyasına işlenmiş
- [x] main dalını kırmızı yapan harici sorun kök-neden bulunup düzeltildi; push sonrası CI'da yeşil teyidi bekleniyor
