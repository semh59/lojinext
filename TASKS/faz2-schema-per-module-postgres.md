# FAZ2 — Şema-Başına-Modül (PostgreSQL)

> 🟡 **PİLOT TAMAMLANDI (2026-07-23)** — `import_excel`/`iceri_aktarim_gecmisi`
> ilk dalga olarak taşındı (`alembic/versions/0047_import_excel_schema_move.py`).
> Kalan 13 şema/42 tablo henüz başlamadı, her biri ayrı onaylı oturum
> gerektiriyor (session hijyeni). Pilot sırasında bu dosyanın orijinal
> planını düzelten/tamamlayan bulgular için aşağıdaki "Pilot sonrası
> bulgular" bölümüne bakın — özellikle **search_path tasarım kararı**
> (madde 32'nin altındaki "raw-SQL siteleri" sorununu bu dosyanın hiç
> öngörmediği bir yöntemle çözüyor) ve **index yeniden adlandırma**
> gerekliliği (gerçek `alembic check` koşumunda bulundu, aşağıda).

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Amaç:** 43 tabloyu 13 PostgreSQL şemasına dağıtmak (kod sınırından AYRI, Sert Kısıt 5). `SET SCHEMA` metadata-only ama kısa ACCESS EXCLUSIVE gerektirir.

**Giriş kriteri:** FAZ1 çıkışı — import-linter gate 5 ardışık gün yeşil, tüm 15 modül + shared_kernel/platform-infra taşınmış (models.py modül-başına bölünmüş, `TASKS/modules/shared-kernel.md`).
**Çıkış kriteri:** 43 tablo modül şemalarında; `e2e_pilot_smoke.py` + `p51_real_world_validation.py` PASS.

---

## Şema→tablo dağılımı (MEMORY/PROGRESS.md §2.2'den, toplam=43)

```
trip: seferler, seferler_log, sefer_belgeler
fleet: araclar, dorseler, arac_bakimlari, vehicle_event_log, vehicle_spec_timeline
driver: soforler, sofor_ad_soyad_trigram, sofor_adaptasyon, coaching_deliveries
fuel: yakit_alimlari, yakit_periyotlari, yakit_formul
location: lokasyonlar, lokasyon_segments
route_simulation: route_paths, route_simulations, route_segments, guzergah_kalibrasyonlari
anomaly: anomalies, fuel_investigations
prediction_ml: egitim_kuyrugu, model_versiyonlar, prediction_results
import_excel: iceri_aktarim_gecmisi
reports: page_views
notification: bildirim_kurallari, bildirim_gecmisi, push_subscriptions
auth_rbac: kullanicilar, roller, kullanici_oturumlari, kullanici_ayarlari
admin_platform: admin_audit_log, entegrasyon_ayarlari
platform: sistem_konfig, konfig_gecmis, outbox_events, error_events, error_occurrences (+ aylık partition'lar), idempotency_keys
```
(`ai_assistant` ve `analytics_executive` şema İÇERMEZ — sırasıyla FAISS dosya-tabanlı ve saf read-model.)

## Migration deseni (her tablo için)

```python
"""FAZ2: seferler tablosunu trip şemasına taşı.

Geri alınabilir: SET SCHEMA metadata-only, ACCESS EXCLUSIVE kısa süreli.
"""
def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS trip")
    op.execute("ALTER TABLE seferler SET SCHEMA trip")

def downgrade():
    op.execute("ALTER TABLE trip.seferler SET SCHEMA public")
```
Uygulama sırası: **tablo tablo, düşük trafik penceresinde** (görevin üretim-güvenliği kısıtı — Sert Kısıt 9d'nin veri-taşıma versiyonu). Her tablo için ayrı migration dosyası — toplu `SET SCHEMA` YOK (tek migration'da 43 tablo = tek uzun kilit penceresi, kabul edilemez).

## alembic/env.py değişikliği
```python
context.configure(
    ...,
    include_schemas=True,
    version_table_schema="platform",  # alembic_version tablosu platform şemasına taşınır
)
```
`naming_convention` (mevcut, korunur) şema-bağımsız çalışır — değişiklik gerekmez.

## MV/trigger/partition kararları
- `sefer_istatistik_mv` → `analytics_executive` şemasına (analytics_executive'in kendi tablosu yok ama bu MV'yi okuyor — MEMORY §2.2 notu).
- `error_hourly_stats` MV + `error_events_notify` trigger/fonksiyon + `error_occurrences_YYYY_MM` partition'ları → `platform` şemasında kalır.

## Dış yazar rolü (`m_ops`)
16 DB-script'i (MEMORY §5) için `m_ops` bakım rolü: tüm şemalara CREATE+ALL grant (superuser DEĞİL, ama geniş). `reset_business_data.py`'nin `SET session_replication_role=replica` ihtiyacı hâlâ superuser gerektirir — bu script'in çalıştırılması ayrı, elle onaylı bir operasyon olarak dokümante edilir (script değişmez, yalnız kim çalıştırabileceği netleşir). `alembic/env.py` geniş DDL grant'ını korur (migration yazarı zaten trusted).

## Geri alma
Her migration dosyası bağımsız `downgrade()` içerir (`SET SCHEMA public`). Bir tablo taşındıktan sonra sorun çıkarsa, o TEK tabloyu geri almak yeterli — toplu rollback gerekmez (tablo-tablo taşımanın avantajı).

## Kabul Kriterleri
- [x] 14 şemadan 1'i oluşturuldu (`import_excel` — pilot); 13'ü kalan dalgalarda
- [x] 43 tablodan 1'i dağıtıldı (`iceri_aktarim_gecmisi`), ayrı migration + ayrı downgrade — gerçek Postgres'te upgrade→downgrade→upgrade döngüsü doğrulandı
- [x] `include_schemas=True` aktif (pilotta eklendi); `version_table_schema="platform"` HENÜZ EKLENMEDİ (platform şeması henüz yok, o dalgaya ertelendi — bkz. aşağı)
- [ ] MV/trigger/partition'lar doğru şemada (pilotun kapsamı dışı, ilgili tablolar henüz taşınmadı)
- [ ] `e2e_pilot_smoke.py` + `p51_real_world_validation.py` her tablo taşımasından sonra PASS (bu pilotta gerçek Docker/Redis gerektiren tam smoke koşulmadı — bkz. "Doğrulama" notu)
- [ ] `m_ops` rolü tanımlı, 16 script'in erişimi doğrulandı (henüz başlanmadı)

## Pilot sonrası bulgular (2026-07-23) — sıradaki dalgalar için ZORUNLU okuma

**1. `MEMORY/PROGRESS.md`'nin raw-SQL sayısı BAYAT:** "32 site / analiz_repo.py'de
56 çağrı" ölçümü v2/ taşımasından ÖNCEKİ hale ait. İki araştırma ajanıyla
yapılan güncel tarama: `analytics_executive/infrastructure/
executive_read_models.py` = 17 çağrı (56 değil); ama toplamda
**~75 dosyada ~200 raw-SQL/`execute_query()` çağrı sitesi** var (32 değil) —
`BaseRepository.execute_query()` helper'ı (kendisi `text()` sarıyor) her
modüle yayıldığı için naif `text(` grep'i bunu kaçırıyor.

**2. Bu doküman "her siteyi şema-nitele" varsayıyordu — bunun yerine
`search_path` kullanıldı ve gerçek Postgres'te uçtan uca doğrulandı:**
Her taşınan şema, migration içinde `ALTER ROLE CURRENT_USER SET search_path
= public, <şema>, ...`'a eklenir. Bare sorgular (`FROM seferler`) hiç
değiştirilmeden çalışmaya devam eder. **Kritik gotcha (gerçek Postgres'te
bulundu, `alembic/env.py`'de düzeltildi):** rolün search_path'i genişleyince
Postgres'in `schema=None` ("varsayılan şema") tablo numaralandırması da
search_path'teki TÜM şemaları tarar — bu, alembic'in autogenerate/`check`
karşılaştırmasında taşınan tabloyu hem "varsayılan şema" hem "kendi şeması"
geçişinde bulup hayalet bir "kaldırılacak tablo" farkı üretiyordu. Çözüm:
`alembic/env.py`'nin KENDİ migration bağlantısı, migration'lar zaten açıkça
şema-nitelikli olduğu için (`CREATE SCHEMA`/`ALTER TABLE SET SCHEMA`/`ALTER
INDEX <şema>.<isim>`), search_path'i `public`'e sabitliyor — yalnız
alembic'in kendi reflection/check'i için, uygulamanın çalışma-zamanı
rolünün search_path'ini ETKİLEMEDEN. `connection.execute()`'un SQLAlchemy
2.0'da örtük transaction başlattığını ve `commit()` edilmezse `with`
bloğu çıkışında SESSİZCE rollback olduğunu (tüm migration'ı geri alarak,
hatasız görünüp) unutmayın — bu satırı hemen `connection.commit()` ile
kapatın.

**3. İndeks yeniden adlandırma gerekli (gerçek `alembic check` koşumunda
bulundu):** `alembic/env.py`'nin naming_convention'ı (`"ix":
"ix_%(column_0_label)s"`) `__table_args__`'a `schema=` eklenince
`column_0_label`'ı şema-önekli üretmeye başlıyor (`ix_<tablo>_<kolon>` →
`ix_<şema>_<tablo>_<kolon>`) — PK/FK isimleri (`%(table_name)s` tabanlı,
şema-bağımsız) ETKİLENMİYOR, yalnız index'ler. Her migration'ın `upgrade()`'i
DB'deki eski-isimli index'leri `ALTER INDEX <şema>.<eski> RENAME TO <yeni>`
ile yeniden adlandırmalı (metadata-only, yeniden inşa gerektirmez),
`downgrade()` tersini yapmalı — yoksa `alembic check` drift raporlar.

**4. `app/tests/conftest.py` + kök `tests/conftest.py` genelleştirildi
(bir daha dokunulmasına gerek yok):** her ikisi de artık `Base.metadata.
tables`'tan dinamik olarak toplanan şema kümesini kullanıyor (CREATE
SCHEMA + search_path/connect_args) — yeni bir şema taşındığında bu
dosyalara TEKRAR dokunmak gerekmiyor, model'e `schema=` eklemek yeterli.

**Doğrulama notu:** Bu pilot gerçek bir Postgres 16 kurulumuna karşı uçtan
uca doğrulandı (upgrade/downgrade/re-upgrade + `alembic check` + gerçek
`app/tests/` suite'inden 53+ test, import_excel'in execute_import/
rollback_import akışı dahil) — ama gerçek Docker/docker-compose (bu oturumun
sandbox'ında yok) + `e2e_pilot_smoke.py`/`p51_real_world_validation.py`
koşulmadı, CI'da doğrulanmalı.
