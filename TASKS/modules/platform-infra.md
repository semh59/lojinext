# Modül Görevi: platform-infra (dalga 17/17 — REGISTRY FİNALİ)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/platform/CLAUDE.md`'yi Read ile oku (yoksa oluştur).

**Doğa farkı:** shared_kernel gibi bu da iş modülü değil — gerçekten cross-cutting altyapı (cache/events/monitoring/resilience/middleware/DI/bootstrap). Bu dalga FAZ1'in SON adımı: `main.py`/`container.py`/`api.py`'nin kalıntısını registry desenine tam oturtur.

**Giriş kriteri:** shared-kernel dalgası (16) tamamlandı. **Çıkış kriteri:** `app/modules/registry.py` 15 modülün TAMAMINI içeriyor; `main.py` yalnız registry iterate ediyor, hard-code hook kalmadı.

---

## 1. Mevcut envanter (62 dosya, 9.654 LOC — değişmez, bu dalga TAŞIMIYOR, YENİDEN BAĞLIYOR)
Ana kalemler (tam liste MEMORY/PROGRESS.md kaynak taramasından): `main.py`, `config.py`, `api/deps.py`, `api/v1/api.py`, `core/container.py`, `database/{connection,db_session,init_db}.py`, `infrastructure/{audit,background,cache,context,database,events,logging,middleware,monitoring,resilience,security/pii_*}/*`, `services/external_service.py`, `workers/tasks/{dlq_tasks,outbox_tasks}.py`.

## 2. Bu dalganın gerçek işi: main.py/container.py/api.py'yi BOŞALTMAK
Faz1-registry-iskelet-ve-shim.md'de tanımlanan taşıma tablosu bu dalgada TAMAMLANIR:
- `api.py:53-153`'teki 47 `include_router` çağrısının HEPSİ artık `app/modules/registry.py` üzerinden geliyor olmalı — `api.py`'de yalnız `APIRouter()` toplama iskeleti kalır.
- `container.py`'nin 32 property'sinin HEPSİ modül `wire()` fonksiyonlarına taşınmış olmalı — `container.py`'de yalnız `event_bus` (satır 136-144, gerçek cross-cutting) ve registry-iterasyon mantığı kalır.
- `main.py` lifespan'ı (284-364) `for m in MODULES: ...` döngüsüne indirgenir; ML warm-up (300-338) `prediction_ml.startup`'a taşınmış olmalı (prediction-ml.md'de işaretlendi, burada doğrulanır).
- Sentry/Prometheus/OTEL/middleware/exception-handler'lar (206-282, 375-748) BURADA KALIR — gerçek platform-infra.

## 3. Doğrulama testi (bu dalganın çıkış kanıtı)
```python
# app/tests/architecture/test_registry_completeness.py
def test_all_15_modules_registered():
    from app.modules.registry import MODULES
    names = {m.name for m in MODULES}
    assert names == {
        "trip", "fleet", "driver", "fuel", "location", "route_simulation",
        "anomaly", "prediction_ml", "ai_assistant", "import_excel", "reports",
        "analytics_executive", "notification", "auth_rbac", "admin_platform",
    }

def test_api_py_has_no_hardcoded_include_router():
    import ast
    tree = ast.parse(open("app/api/v1/api.py", encoding="utf-8").read())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "include_router"]
    assert len(calls) == 0  # hepsi registry üzerinden
```

## 4. Kalan cross-cutting envanterin modül-içi izlenebilirliği
`cache_invalidation.py`'nin 15 subscriber'ı (MEMORY §3) burada kalır AMA hangi modülün event'ini dinlediği `events.py` DTO tipleriyle artık statik olarak izlenebilir (FAZ1 davranışsal testler bunu doğruluyor — `faz1-davranissal-mimari-testler.md` madde 3). `security_probe.py`'deki BruteForceDetector/RBACViolationTracker BURADA kalır, Redis-backed hale gelmesi FAZ2 işi (`faz2-guvenlik-state-redis.md`).

## 5. Kabul kriterleri
- [ ] `test_all_15_modules_registered` yeşil
- [ ] `test_api_py_has_no_hardcoded_include_router` yeşil
- [ ] `container.py` yalnız event_bus + registry-iterasyon içeriyor (32 property → 0)
- [ ] `main.py` lifespan'ı registry döngüsüne indirgendi
- [ ] **FAZ1'in genel çıkış kriteri burada test edilir:** import-linter gate 5 ardışık gün main'de yeşil (TASKS/README.md FAZ tablosu)
