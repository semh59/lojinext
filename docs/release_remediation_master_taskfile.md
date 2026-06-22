# Release Remediation Taskfile

`Single Source of Truth`: `yes`
`Last Updated`: `2026-03-15`
`Current Phase`: `F1 - Migration Reset`
`Release Status`: `NO-GO`

## Kullanim

- `[x]` tamam
- `[ ]` acik veya blocked
- Evidence dosyalari `docs/release_remediation_impl/artifacts/` altinda kalir
- Bu dosya disinda ayri task/status dosyasi tutulmaz
- ID formati:
  - `F1-XX`: orijinal governance task ID'si
  - `L2-F1-XX`: execution sirasinda olusturulan Layer 2 alt gorev ID'si
  - `F1-EXX`: execution sirasinda ortaya cikan emergence is ID'si
  - `F1-VXX`: validation/verification task ID'si

## Program Kurallari

- `Feature Freeze`: Auth, migration, API contract, frontend API client alanlarina dokunan remediation disi merge kabul edilmez.
- `Merge Yasagi`: P0/P1 alanlarinda workaround veya temporary bypass merge edilmez.
- `Kanitsiz Kapanis Yasagi`: Kanit ve gate olmadan task `done` olamaz.

## Simdiki Durum

- [ ] Faz 0 passed
- [x] Faz 1 P0 recovery exception ile erken baslatildi
- [x] Legacy Alembic chain archive edildi ve active path izole edildi
- [x] Active path validation yapildi
- [x] Disposable runtime DB reset yapildi
- [x] `alembic heads` gecti
- [x] `alembic current` gecti
- [x] `alembic upgrade head` gecti
- [x] `alembic check` gecti
- [x] Frontend `test/build/lint` gecti
- [ ] Backend full suite gecti

## Tamamlananlar

- [x] `F1-01` Legacy migration inventory ve archive ayrimi uygulandi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-01_evidence.md`
- [x] `F1-02` Active vs archive ayrimi uygulandi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-01_evidence.md`
      (F1-01 ile ayni atomik operasyon — arsiv ve izolasyon tek adimda yapildi)
- [x] `F1-08/V01` Active Alembic visibility validation tamamlandi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-V01_evidence.md`
- [x] `F1-03 / L2-F1-02` Schema order artifact uretildi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/F1_schema_order.md`
- [x] `F1-04` Baseline scope lock karari alindi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/F1_schema_order.md`
- [x] `F1-05 / L2-F1-03` Hand-written baseline DDL migration yazildi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-03_evidence.md`
      Not:
      Orijinal planda F1-05 "gorevini tanimla" idi; execution'da plan asamasi atlanarak
      dogrudan hand-written baseline DDL yazildi. Constraint kaynagi: F1_schema_order.md
      tablo sirasi ve 28-tablo scope lock listesi.
- [x] `F1-05 / L2-F1-04` Baseline `downgrade()` guard eklendi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-V02_evidence.md`
- [x] `F1-06 / L2-F1-05` UPSERT tabanli seed/bootstrap migration yazildi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-05_evidence.md`
      Not:
      Orijinal planda "gorevini tanimla" idi; execution'da UPSERT semantigi ve idempotency
      kurali dogrudan migration dosyasina yazildi. Karar: super_admin + bootstrap admin
      minimum bootstrap seti.
- [x] `F1-07 / L2-F1-06` Disposable DB reset runbook'u yazildi ve dogrulandi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/F1_reset_runbook.md`
- [x] `F1-08 / L2-F1-V02` `downgrade()` expected-failure validation tamamlandi
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/L2-F1-V02_evidence.md`
- [x] `F1-09` CI migration jobs'u yeni baseline'a baglandi
      Evidence:
      `.github/workflows/ci.yml`
- [x] `F1-10` Release checklist baseline reset'e gore guncellendi
      Evidence:
      `docs/sefer_release_candidate_checklist.md`
- [x] `F1-E01` Full backend suite baseline+seed sonrasi tekrar kosuldu
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/F1_execution_snapshot_20260315_post_baseline.md`
- [x] `F1-E02` Test dependency gap kapatildi (`respx`)
      Evidence:
      `app/requirements-dev.txt`
- [x] `F1-E03` Test harness recovery ilk dalga tamamlandi
      Kapsam:
      `tests/conftest.py`, `app/infrastructure/events/event_bus.py`, `tests/test_auth_brute_force.py`, `app/tests/unit/test_trip_migration_chain_guards.py`
- [x] `F1-E04` Disposable `tir_yakit` schema reset ile stale revision referansi temizlendi
- [x] `F1-E05` P0 recovery sonrasi backend suite tekrar kosuldu
      Evidence:
      `docs/release_remediation_impl/artifacts/F1/F1_execution_snapshot_20260315.md`
      Raw:
      `docs/release_remediation_impl/artifacts/F1/full_pytest_after_p0.txt`

## Simdi Yapilacaklar

- [ ] `P1`
      Trip/API contract drift'i kapat
      Ilk hedef:
      `guzergah_id` kaynakli `422` cluster'i
      Faz kapsami:
      Bu is Faz 3 (API Kontratlari) kapsamindadir. P1 aciliyeti Faz sirasini
      atlamaz; Faz 2 canonical permission modeli olmadan trip contract
      degisikliginin blast radius'u kontrolsuz olur.
- [ ] `P1`
      Async DB session contention ve `MissingGreenlet` cluster'ini ayir
- [ ] `P1`
      Analytics/dashboard repo session initialization hatalarini kapat

## Blokajlar

- [ ] `Execution Debt`
      Faz 0 governance task'lari kapanmadi
      Durum:
      `CI baseline triage`, `Freeze governance`, `Staging env provision` acik
      Not:
      Faz 1 yalniz migration recovery'yi unblock etmek icin exception ile erken baslatildi
      Etki: 1. CI triage olmadan 49 failed testin pre-existing vs remediation-owned ayrimi yapilamadi 2. Freeze governance olmadan remediation disi merge korumasi yok 3. Staging env olmadan integration dogrulamasi production risk altinda 4. Risk register yoklugunda teknik surpriz riski acik
- [ ] `P1`
      Trip/API contract drift var
      Belirti:
      `guzergah_id` kaynakli `422` hatalari
- [ ] `P1`
      Async DB session contention var
      Belirti:
      `another operation is in progress`
      Triage ihtiyaci:
      Bu sorun (a) migration sonrasi test izolasyon kusuru veya (b) uygulama
      katmaninda bagimsiz bug olabilir. Ayrim yapmak icin: 1. Failing testleri tek tek calistirip session davranisini izole et 2. MissingGreenlet stack trace'lerini test mi uygulama mi kaynakli ayir 3. Sonuca gore Faz 1 backlog veya Faz 3 scope'a ata
- [ ] `P1`
      Domain regression cluster'lari acik
      Alanlar:
      analytics, websocket, RAG, export, route, mapbox

## Risk Register

| Risk                                          | Etki                       | Olasilik | Mitigasyon                          | Ilgili Faz |
| --------------------------------------------- | -------------------------- | -------- | ----------------------------------- | ---------- |
| RBAC namespace drift'i baseline sonrasi buyur | Yetkisiz erisim            | Orta     | Faz 2 canonical registry            | F2         |
| Migration reset prod veride veri kaybi        | Veri kaybi                 | Dusuk    | Data policy: disposable             | F1         |
| SSE auth token leak                           | Yetkisiz stream erisimi    | Orta     | TTL + one-time consume              | F3         |
| History rewrite sonrasi CI stale ref          | CI kirilmasi               | Yuksek   | Post-rewrite verification           | F5         |
| Placeholder endpoint guvenlik acigi           | Sahte success exploitation | Orta     | Faz 3 placeholder audit             | F3         |
| Async DB session contention                   | Runtime instability        | Belirsiz | Triage gerekli (Blokajlar'da detay) | —          |

## 49 Failed Cluster Ozeti

Su anki `49 failed` sonucu iki gruba ayrildi:

### Faz 1 sonrasi tekrar degerlendirilecekler

- `14` test
  `trip_contract_and_service`
  Not:
  `guzergah_id`, sefer yazma akisi, e2e trip flow, integration trip API
- `8` test
  `analytics_dashboard`
  Not:
  repo/session initialization ve dashboard response akisiyla bagli
- `1` test
  `export`
  Not:
  DB session initialization ile bagli

### Faz 1'den bagimsiz ama acik kalan cluster'lar

- `8` test
  `rag_ml_ai`
- `5` test
  `routing_mapbox`
- `6` test
  `infra_security_deep`
- `3` test
  `fuel_service`
- `1` test
  `websocket_realtime`
- `3` test
  `other`

Karar:

- Baseline DDL tamamlandi; bundan sonra `49 failed` cluster bazli temizlenecek
- Ancak bunlar ignore edilmiyor; Faz 1 parity kapandiktan sonra cluster bazli backlog'a alinacak

## Test Sonucu Ozeti

- [x] Targeted recovery tests:
      `15 passed`
- [x] Backend full suite latest:
      `583 passed`
- [ ] Backend full suite latest:
      `49 failed`
- [ ] Backend full suite latest:
      `2 skipped`
- [x] Frontend tests:
      `43 passed`
- [x] Frontend build:
      `pass`
- [x] Frontend lint:
      `pass`

## Faz Checklist

### Faz 0

- [ ] CI baseline triage
- [ ] Freeze governance
- [ ] Staging env provision
- [ ] Faz 0 passed

### Faz 1

- [x] Legacy chain archive
- [x] Active path isolation
- [x] Active path validation
- [x] Schema order artifact
- [x] Baseline scope lock
- [x] Baseline DDL
- [x] Downgrade guard
- [x] Seed/bootstrap migration
- [x] Reset runbook
- [x] Alembic parity full green
- [x] Downgrade expected-failure validation
- [x] CI migration update
- [x] Release checklist update

### Faz 2

- [ ] Canonical permission registry
- [ ] Auth guard consolidation
- [ ] `auth/me` additive payload
- [ ] Refresh deprecation protocol
- [ ] RBAC negative tests

### Faz 3

- [ ] Public contract lock
- [ ] `/vehicles/paginated`
- [ ] SSE token handshake
- [ ] `/users` honest facade
- [ ] `admin/health` honest operations

### Faz 4

- [ ] `legacy.ts` shim cleanup
- [ ] OpenAPI export
- [ ] TS type generation
- [ ] FE auth migration
- [ ] Vehicles UI migration
- [ ] Stream client migration

### Faz 5

- [ ] Mojibake cleanup
- [ ] Startup split
- [ ] Health payload modernization
- [ ] Tracked artifact cleanup
- [ ] History rewrite
- [ ] Final release sweep

## Kanit Dosyalari

- `docs/release_remediation_impl/artifacts/F1/L2-F1-01_evidence.md`
- `docs/release_remediation_impl/artifacts/F1/L2-F1-V01_evidence.md`
- `docs/release_remediation_impl/artifacts/F1/F1_schema_order.md`
- `docs/release_remediation_impl/artifacts/F1/L2-F1-03_evidence.md`
- `docs/release_remediation_impl/artifacts/F1/L2-F1-05_evidence.md`
- `docs/release_remediation_impl/artifacts/F1/F1_reset_runbook.md`
- `docs/release_remediation_impl/artifacts/F1/L2-F1-V02_evidence.md`
- `docs/release_remediation_impl/artifacts/F1/F1_execution_snapshot_20260315.md`
- `docs/release_remediation_impl/artifacts/F1/F1_execution_snapshot_20260315_post_baseline.md`
- `docs/release_remediation_impl/artifacts/F1/full_pytest_after_p0.txt`

## Sonraki Tek Is

- [ ] `P1-Trip-Contract`
      `guzergah_id` zorunlulugu nedeniyle `422` donen trip create cluster'ini kapat
