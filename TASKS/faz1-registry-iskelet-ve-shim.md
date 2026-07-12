# FAZ1 (çatı) — Modül Registry, İskelet, Shim Stratejisi

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz. Uygulanmadan önce ilgili modül görev dosyaları (`TASKS/modules/*.md`) sırayla onaylanır.

**Amaç:** Bugünkü 3 kompozisyon-kökü god-dosyasını (`app/core/container.py` 569 satır/32 property, `app/api/v1/api.py` 46 modül/47 include_router, `app/main.py` lifespan 284-364) modül-başına `ModuleSpec` deseniyle değiştirmek; her taşıma dalgası boyunca eski import yollarını **tek-satır shim**'lerle canlı tutmak.

**Giriş kriteri:** FAZ0 çıkışı (baseline repo'da, main yeşil).
**Çıkış kriteri:** Bkz. `TASKS/README.md` FAZ1 satırı — 15 modül + 2 kova taşındı, import-linter gate 5 ardışık gün yeşil.

---

## Hedef dosya iskeleti (her modülde)

```
app/modules/<modul>/
  CLAUDE.md          # bkz. faz1-claude-md-per-module-template.md
  module.py          # ModuleSpec — aşağıda
  public.py          # TEK dışa açık yüzey
  events.py          # yayınlanan event tipleri + DTO'lar
  api/                # APIRouter'lar (ince)
  application/        # BİR dosya = BİR use-case
  domain/             # saf iş kuralları (I/O'suz)
  infrastructure/      # models.py, repository.py, dış istemciler
```

`module.py` içeriği — **ModuleSpec** (gerçek Python, hayali değil — mevcut FastAPI/container API'lerine bağlı):
```python
from dataclasses import dataclass, field
from fastapi import APIRouter

@dataclass
class ModuleSpec:
    name: str
    routers: list[tuple[APIRouter, str, list[str]]] = field(default_factory=list)  # (router, prefix, tags)
    wire: callable = None       # (container) -> None — servis/repo kaydı
    startup: callable = None    # async (app) -> None
    shutdown: callable = None   # async (app) -> None
```

`app/modules/registry.py`:
```python
from app.modules.location.module import spec as location_spec
from app.modules.notification.module import spec as notification_spec
# ... 15 modül import edilir (dalga sırasıyla eklenir, boş liste ile başlar)

MODULES = [location_spec, notification_spec, ...]
```

`main.py` lifespan bunu iterate eder (bugünkü hard-code satırlarının yerini alır):
```python
for m in MODULES:
    if m.wire:
        m.wire(container)
    if m.startup:
        await m.startup(app)
for m in MODULES:
    for router, prefix, tags in m.routers:
        app.include_router(router, prefix=settings.API_V1_STR + prefix, tags=tags)
```
Shutdown sırası TERS iterate eder (bağımlılık kabloları çözülme sırası).

## Taşınacak satırlar (ölçülmüş, 2. dalga composition-root ajanının tam okuma sonucu)

| Kaynak | Satır | Hedef |
|---|---|---|
| `api.py` router include'ları | 53-153 (47 çağrı) | her modülün `module.py`'sindeki `routers` listesi |
| `container.py` property'leri | 32 `@property` | her modülün `wire(container)` fonksiyonu |
| `container.py` event_bus (satır 136-144) | — | **platform-infra'da KALIR** (shared_kernel değil — infra) |
| `container.py` shutdown teardown | 501-541 | her modülün `shutdown(app)` hook'u |
| `main.py` ML warm-up | 300-338 | `prediction_ml.startup(app)` |
| `main.py` diğer start/stop (Sentry, Prometheus, OTEL, middleware, exception handler'lar) | 206-282, 375-748 | **platform-infra'da KALIR** — bunlar gerçekten cross-cutting |
| `deps.py` per-request fabrikalar | — | modülün `api/` katmanına (Depends zinciri modülle birlikte taşınır — RBAC dependency route'tan ASLA ayrılmaz) |

`app/database/repositories/__init__.py` re-export hunisi ve `app/core/entities/models.py` → `core/utils/sefer_status.py` ihlali bu FAZ'da kaldırılır (ikisi de MEMORY/PROGRESS.md §2.1'de tespit edilen gerçek katman ihlalleri).

## Shim stratejisi (kod kısalığı kuralına bağlı — kullanıcı talimatı)

Bir dosya `app/core/services/arac_service.py`'den `app/modules/fleet/application/...`'e taşındığında, eski yolda **TEK SATIR** shim bırakılır:
```python
# app/core/services/arac_service.py
from app.modules.fleet.application.arac_service import *  # shim — FAZ4'te silinir, TASKS/faz4-sikilastirma-ve-kapanis.md
```
Köprü sınıfı, adapter, "geçiş katmanı" YAZILMAZ — yalnız re-export. `arch/quality_baseline.json`'da shim dosyaları ayrı bir liste olarak izlenir; FAZ4'ün çıkış kriteri bu listenin boş olmasıdır.

## Dalga-içi PR disiplini
1. Bir modülün TÜM dosyaları tek PR'da taşınır (kısmi taşıma = kısmi shim = takip edilemez durum).
2. PR açıklamasında net-LOC değişimi raporlanır (kod kısalığı kuralı: beklenen ≈ 0, +50'yi aşan artış satır satır gerekçelendirilir).
3. Taşıma sonrası: `pytest -m "unit or not integration"` + değişen modülün entegrasyon testleri yeşil, `alembic check` boş-diff (modeller henüz taşınmadıysa bu adım no-op).
4. Dalga sırası `TASKS/README.md`'deki 17 kalemlik listeye uyar; sıra dışı taşıma yapılmaz (bağımlılık-az→çok sırası, geç taşınanlar erken taşınanları public.py üzerinden çağırır).

## Kabul Kriterleri
- [ ] `app/modules/registry.py` var, `MODULES` listesi dalga ilerledikçe büyüyor
- [ ] Her taşınan dosya için shim tek satır, köprü sınıfı yok
- [ ] `api.py`/`container.py`/`main.py` küçülüyor (platform-infra kovasına iniyor), büyümüyor
- [ ] Her dalga sonunda ilgili modülün entegrasyon testi + genel unit suite yeşil
