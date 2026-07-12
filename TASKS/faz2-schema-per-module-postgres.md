# FAZ2 — Şema-Başına-Modül (PostgreSQL)

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
- [ ] 14 şema oluşturuldu (FAZ0 kararı: iceri_aktarim_gecmisi → import_excel)
- [ ] 43 tablo dağıtıldı, her biri ayrı migration, ayrı downgrade
- [ ] `include_schemas=True` + `version_table_schema` aktif
- [ ] MV/trigger/partition'lar doğru şemada
- [ ] `e2e_pilot_smoke.py` + `p51_real_world_validation.py` her tablo taşımasından sonra PASS
- [ ] `m_ops` rolü tanımlı, 16 script'in erişimi doğrulandı
