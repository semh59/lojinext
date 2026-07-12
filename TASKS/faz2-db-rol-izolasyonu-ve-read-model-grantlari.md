# FAZ2 — DB Rol İzolasyonu + Read-Model Grant'ları

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Amaç:** Her modüle kendi şemasında ALL, başkasında yalnız granted SELECT veren PG rolleri kurmak; 42 çapraz-şema FK'yı `fk_registry.yml` ile izlenebilir kılmak; raw-SQL sınır ihlalini FAZ1'in "yaklaşık" taramasından FAZ2'nin "kesin" runtime stop'una geçirmek.

**Giriş kriteri:** `faz2-schema-per-module-postgres.md` tamamlandı (13/14 şema kurulu).
**Çıkış kriteri:** rol ihlali hem testte hem prod'da `permission denied`; `fk_registry.yml` ↔ `information_schema` pytest diff'i CI'da aktif.

---

## Rol tanımları (15 iş modülü + platform)
```sql
CREATE ROLE m_trip;
GRANT ALL ON ALL TABLES IN SCHEMA trip TO m_trip;
GRANT USAGE ON SCHEMA trip TO m_trip;
-- ... 15 modül için tekrarlanır (isim deseni: m_<modul>)

CREATE ROLE m_analytics_executive;  -- read-model, kendi şeması yok
GRANT SELECT ON ALL TABLES IN SCHEMA trip, fleet, driver, fuel, anomaly, notification, reports TO m_analytics_executive;
CREATE ROLE m_anomaly_reader;       -- diğer read-model'ler benzer desenle
CREATE ROLE m_reports_reader;
CREATE ROLE m_ai_assistant_reader;
```
4 çok-kaynaklı okuyucu (anomaly, analytics_executive, reports, ai_assistant/context_builder — MEMORY §2.3) için SELECT-only grant matrisi:

| Okuyucu | SELECT grant aldığı şemalar |
|---|---|
| analytics_executive | trip, fleet, driver, fuel, anomaly, notification, reports |
| reports | trip, fleet, driver, fuel, import_excel |
| anomaly | trip, driver, fleet, fuel (theft_tasks'ın 5-modül erişimi) |
| ai_assistant | fleet, trip, fuel, reports (context_builder'ın 4-modül erişimi) |

## UoW implant noktası
`app/database/unit_of_work.py` — transaction başında modül context'ine göre rol set edilir:
```python
class UnitOfWork:
    def __init__(self, module_role: str | None = None):
        self._module_role = module_role or "m_platform"

    async def __aenter__(self):
        await self._session.execute(text(f"SET LOCAL ROLE {self._module_role}"))
        return self
```
Her modülün `public.py`'sindeki use-case'ler kendi `module_role`'ünü geçirir (ör. `UnitOfWork(module_role="m_trip")`). Transaction sonunda `SET LOCAL` otomatik reset olur (PostgreSQL garantisi — pool kirlenmez).

## fk_registry.yml (42 kenar, MEMORY §2.2'den)
```yaml
# arch/fk_registry.yml — her kenar açık onaylı
edges:
  - from: trip.seferler.guzergah_id
    to: location.lokasyonlar
  - from: trip.seferler.arac_id
    to: fleet.araclar
  - from: trip.seferler.sofor_id
    to: driver.soforler
  - from: trip.seferler.periyot_id
    to: fuel.yakit_periyotlari
  # ... 42 kenarın tamamı, MEMORY/PROGRESS.md §2.2'deki tam listeden
```
CI testi:
```python
def test_fk_registry_matches_live_schema():
    """information_schema'daki her çapraz-şema FK, registry'de kayıtlı olmalı."""
    live_edges = query_information_schema_foreign_keys()  # gerçek DB sorgusu
    registered = load_yaml("arch/fk_registry.yml")["edges"]
    assert set(live_edges) == set(registered)  # fazlası da eksiği de FAIL
```
Yeni çapraz-şema FK eklemek → bu dosyaya satır eklemek gerektirir → PR reviewer'ı görür → gerçek stop.

## Raw-SQL sınırının KESİN hale gelmesi
FAZ1'deki "yaklaşık" tablo-adı taraması (`faz1-import-linter-baseline-ve-gate.md`) burada gereksizleşir: bir modülün rolü, yabancı şemaya SELECT dışı erişim denerse (veya hiç grant'ı yoksa) PostgreSQL `permission denied` fırlatır — hem testte hem prod'da. `analiz_repo.py`'den taşınan `analytics_executive` read-model sorguları (`get_bulk_cost_stats`, `get_month_over_month_trends`) bu rolle çalışır; `anomaly`'nin FOR-UPDATE yazma yolu (`lock_investigation_for_update`) kendi şemasında ALL grant'ıyla sorunsuz.

## Kabul Kriterleri
- [ ] 15+4 rol tanımlı, her biri doğru grant setine sahip
- [ ] `UnitOfWork(module_role=...)` her modülün public.py'sinde kullanılıyor
- [ ] `fk_registry.yml` 42 kenarın tamamını içeriyor, CI testi yeşil
- [ ] Bilinçli rol ihlali testi (yanlış modülden yazma denemesi) `permission denied` üretiyor
- [ ] `m_ops` rolü (faz2-schema dosyasından) 16 script ile uyumlu çalışıyor
