# Faz 13 — Multi-Tenant (tenant_id + RLS) Tasarım (Spec)

**Tarih:** 2026-06-14
**Statü:** TASLAK — büyük epic; kendi plan/migration döngüsü gerektirir. Bu spec
mimari kararları + kapsamı sabitler; uygulama ayrı fazlara bölünür.
**Bağlam:** Sistem şu an **tek-tenant** (CLAUDE.md: `tenant_id` yok, RLS yok;
`SecurityService.apply_isolation` yalnız rol/permission filtreler). Roadmap Faz 13:
"Multi-tenant epic (`tenant_id` + RLS)".

---

## 1. Hedef & strateji kararı

**Hedef:** Birden çok müşteri/firma (tenant) aynı kurulumda **veri-izole** çalışsın;
bir tenant'ın verisi diğerine asla sızmasın — uygulama kodu unutsa bile.

**İzolasyon stratejisi (karar): Shared-DB + `tenant_id` kolonu + PostgreSQL
Row-Level Security (RLS).** Gerekçe (alternatifler elenerek):
- **Shared-DB + tenant_id + RLS (SEÇİLDİ):** tek şema, tek migration zinciri, tek
  connection pool; RLS DB seviyesinde zorlar → uygulama sorgu filtresini unutsa
  bile sızma olmaz (defense-in-depth). Tek-VPS docker-compose kurulumuna uygun.
- Schema-per-tenant: migration N× çoğalır, connection/şema yönetimi karmaşık.
- DB-per-tenant: izolasyon en güçlü ama tek-VPS'te operasyonel ağır; ertelendi.

**İlke:** RLS **birincil** zorlayıcı (DB); uygulama-katmanı filtresi (UoW/repo)
**ikincil** (performans + netlik). İkisi birden = belt-and-suspenders.

## 2. Kapsam — hangi tablolar

`app/database/models.py` → **40 iş tablosu**. Üç sınıf:
- **Tenant-scoped (çoğu):** araclar, soforler, dorseler, lokasyonlar, seferler,
  yakit_alimlari, anomalies, route_simulations, route_segments, bildirim_gecmisi,
  model_versiyonlar, admin_audit_log, page_views, … → **`tenant_id` kolonu + FK**.
- **Tenant-bağımsız (global):** alembic_version, (varsa) referans/lookup tablolar,
  sistem_konfig (tenant-başı mı global mi → §6 karar). → tenant_id YOK veya nullable.
- **Kullanıcılar:** `kullanicilar` → `tenant_id` FK (her kullanıcı bir tenant'a ait);
  **super_admin** istisna (tenant_id NULL = cross-tenant; §4).

Yeni tablo: **`tenants`** (id, ad, slug/subdomain, aktif, created_at, plan/limit
alanları sonra). Tüm tenant-scoped FK'ler buraya.

## 3. Şema değişikliği + mevcut veri migrasyonu

1. `tenants` tablosu oluştur + **bir "default" tenant** ekle (mevcut tek-tenant
   verisinin sahibi).
2. Her tenant-scoped tabloya `tenant_id BIGINT NOT NULL DEFAULT <default_tenant_id>
   REFERENCES tenants(id)` ekle (NOT NULL + default → mevcut satırlar default
   tenant'a atanır, sıfır-downtime backfill).
3. Backfill sonrası `DEFAULT` kaldır (yeni satırlar tenant'ı explicit set etmeli).
4. Her tenant-scoped tabloya **kompozit index** (`tenant_id`, sık-sorgulanan kolon)
   + mevcut UNIQUE constraint'leri **`(tenant_id, …)` kapsamına al** (örn.
   `soforler.ad_soyad` global unique → tenant-başı unique olmalı; aksi halde iki
   tenant aynı şoför adını giremez). **Bu, her UNIQUE'ın gözden geçirilmesi demek.**
5. **Alembic:** tek büyük migration riskli → tablo-grubu başına dilimlenmiş
   migration'lar (ARCH-004 mypy-slice deseni gibi). Her dilim `alembic check` temiz.

## 4. Auth / tenant bağlamı

- **JWT claim:** `create_access_token(data)` → `data["tenant_id"]` eklenir; login'de
  kullanıcının tenant'ından set edilir. Token doğrulamada `tenant_id` çıkarılır.
- **super_admin:** `tenant_id=NULL` → tüm tenant'lara erişim (cross-tenant ops).
  RLS policy super_admin için bypass (aşağıda).
- **Tenant tespiti:** birincil = JWT claim. (Subdomain/header opsiyonel, sonra.)
- **Request bağlamı:** `get_current_active_user` çözümünde tenant_id bir
  `ContextVar` / request.state'e yazılır.

## 5. RLS uygulaması (DB zorlaması)

- Her tenant-scoped tabloda RLS aç:
  `ALTER TABLE x ENABLE ROW LEVEL SECURITY;`
  Policy: `USING (tenant_id = current_setting('app.current_tenant')::bigint)`.
- super_admin bypass: ya `current_setting('app.current_tenant')='0'` özel değeri →
  policy `OR current_setting(...)='0'`, ya da ayrı DB rolü `BYPASSRLS`.
- **Session değişkeni:** `get_db()` (ve `session_scope`) her istek başında
  `SET LOCAL app.current_tenant = <tenant_id>` çalıştırır (transaction-scoped,
  connection-pool güvenli). tenant_id yoksa (auth-öncesi) policy hiçbir satır
  döndürmez (güvenli varsayılan).
- **asyncpg + pool:** `SET LOCAL` transaction içinde olmalı → UoW transaction
  açılışında set edilir. Pool'da connection paylaşımı sızdırmaz (LOCAL).

## 6. Uygulama katmanı (ikincil filtre + INSERT)

- **INSERT:** yeni kayıtlarda `tenant_id` set edilmeli. UoW/repo `create` yolları
  request tenant'ını otomatik enjekte eder (RLS INSERT policy de zorlar:
  `WITH CHECK (tenant_id = current_setting(...))`).
- **BaseRepository:** `tenant_id` filtresi RLS ile zaten zorlanıyor; repo katmanı
  açık filtre EKLEMEZ (RLS yeterli) ama `tenant_id`'yi create'te set eder.
- **sistem_konfig / global ayarlar:** karar — çoğu config tenant-başı olmalı
  (her firma kendi ayarı). Gerçekten global olanlar (feature flag'ler env'de zaten)
  tenant-bağımsız kalır.
- **Celery/worker:** task'lar tenant bağlamını **explicit argüman** olarak taşımalı
  (request ContextVar worker'da yok). Outbox/scheduled task'lar tenant döngüsü
  veya tenant_id parametresi ile çalışır. **Bu, her task'ın gözden geçirilmesi.**

## 7. Riskler

- **En büyük risk:** RLS `SET LOCAL` connection-pool'da sızarsa cross-tenant veri
  görünür → izolasyon çöker. Mitigasyon: transaction-scoped SET + pool reset testi
  + cross-tenant izolasyon entegrasyon testi (tenant A token ile tenant B verisi
  GÖRÜLMEMELİ — bu test SUITE'in çekirdeği).
- **UNIQUE constraint'ler:** tenant-kapsamına alınmazsa ya çakışma ya yanlış-izolasyon.
- **Celery/scheduled task'lar:** tenant bağlamı taşımazsa ya hep default tenant ya
  cross-tenant işlem.
- **Migration downtime:** 40 tabloya NOT NULL kolon + index → büyük tablolarda
  lock; dilimli + `CREATE INDEX CONCURRENTLY`.
- **Mevcut testler:** ~6400 test tek-tenant varsayıyor; tenant fixture'ı + RLS
  session set'i conftest'e girmeli (geniş ama mekanik).

## 8. Faz bölümleme (uygulama — ayrı plan döngüleri)

1. **MT-1:** `tenants` tablo + default tenant + `tenant_id` kolonları (backfill,
   NOT NULL, FK) — RLS YOK henüz, uygulama tek-tenant gibi çalışır (default).
2. **MT-2:** Auth tenant claim + `get_db` `SET LOCAL` + ContextVar.
3. **MT-3:** RLS policy'leri (tablo-grubu başına) + **cross-tenant izolasyon test
   suite'i** (kabul çekirdeği).
4. **MT-4:** UNIQUE constraint'lerin tenant-kapsamı + Celery task tenant bağlamı.
5. **MT-5:** Tenant lifecycle (oluştur/devre-dışı bırak) admin endpoint + UI.

## 9. Kabul kriteri

- Tenant A kullanıcısı, tenant B'nin hiçbir verisini (sefer/araç/şoför/anomali/…)
  API'den GÖREMEZ — RLS DB seviyesinde zorlar (uygulama filtresi kaldırılsa bile).
- super_admin cross-tenant görebilir.
- Mevcut tek-tenant veri "default" tenant altında kayıpsız çalışır.
- `alembic check` temiz; full suite + yeni izolasyon testleri yeşil.

## 10. Kapsam dışı (bu epic'te değil)

- DB-per-tenant / schema-per-tenant.
- Tenant-başı kaynak kotası/billing.
- Subdomain routing (JWT claim yeterli; sonra eklenebilir).
- Self-service tenant signup (admin-managed yeterli).
