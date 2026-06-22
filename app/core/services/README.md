# Core Services Architecture

## Lifecycle Types

### PER-REQUEST Services
Her HTTP request'te `app/api/deps.py`'deki `Depends()` factory'leri tarafından
UnitOfWork ile birlikte oluşturulur. Transaction garantisi sağlar.

| Servis | Depends On | Endpoint Factory |
|--------|-----------|-----------------|
| AracService | UoW.arac_repo | deps.get_arac_service |
| SoforService | UoW.sofor_repo | deps.get_sofor_service |
| SeferService | UoW.sefer_repo | deps.get_sefer_service |
| YakitService | UoW.yakit_repo | deps.get_yakit_service |
| LokasyonService | UoW.lokasyon_repo | deps.get_lokasyon_service |
| DorseService | UoW.dorse_repo | deps.get_dorse_service |
| AuthService | UoW.session | deps.get_auth_service |

### SINGLETON Services (`app/core/container.py`)
Uygulama ömrü boyunca tek instance. Thread-safe olmalı.

| Servis | Reason | Init Cost |
|--------|--------|-----------|
| PredictionService | ML ensemble model loading | ~5-30s |
| AnomalyDetector | Isolation Forest + LGBM | ~2-10s |
| TimeSeriesService | ARIMA engine | ~1s |
| SmartAIService | FAISS + embedding model | ~5s |
| RouteService | HTTP client pool (ORS) | ~0.1s |
| LicenseService | Config validation | ~0s |
| HealthService | Connection ping | ~0s |
| ExportService | Excel/PDF generation | ~0s |
| ImportService | Excel parse + bulk insert | ~0s |
| ReportService | Read-only analytics | ~0s |
| AnalizService | Dashboard aggregates | ~0s |
| AIService | Groq LLM calls | ~0s |
| InternalService | Telegram bot bridge | ~0s |
| SoforAnalizService | Driver performance metrics | ~0s |

## Kurallar

1. **Domain CRUD servisleri PER-REQUEST olmalı** — UoW transaction garantisi
2. **ML/AI servisleri SINGLETON olmalı** — model yüklemesi pahalı
3. **Constructor injection kullan** — bir servis başkasına bağımlıysa parametre al
4. **Modül seviyesinde `from app.core.container import get_container` yasak** — fonksiyon içinde deferred import kullan
5. **Singleton servisler `async with UnitOfWork()` açabilir** — ancak endpoint UoW'una katılmaz

## Yeni Servis Ekleme

### PER-REQUEST ise:
1. `app/core/services/` altına ekle
2. `app/api/deps.py`'ye factory ekle: `async def get_x_service(uow: UOWDep): ...`
3. Module docstring'e `TYPE: PER-REQUEST` marker ekle

### SINGLETON ise:
1. `app/services/` veya `app/core/services/` altına ekle
2. `app/core/container.py`'ye lazy property ekle
3. Module docstring'e `TYPE: SINGLETON` marker ekle
4. Thread-safety garanti et (lock veya stateless tasarım)

## DI Akışı

```
HTTP Request
  ↓
app/api/v1/endpoints/*.py  (route handler)
  ↓ FastAPI Depends()
app/api/deps.py            (factory functions)
  ↓ UnitOfWork context
app/core/services/*.py     (PER-REQUEST services)
  ↓ uow.repo / uow.session
app/database/repositories/ (repositories)
  ↓
PostgreSQL

Parallel path (container):
app/core/container.py      (SINGLETON services)
  ↗ lazy-loaded on first access
```
