# Debugging Playbook — Hata kovalama süresini 5x azaltacak iş akışı

Bu doküman bir hatayı **dedektif gibi kovalamak yerine**, sistematik
adımlarla 5-10 dakikada çözmenin yolunu gösterir. LojiNext'in mevcut
observability stack'ini etkili kullanmak için.

## TL;DR — Üç Soru

Bir hata gördüğünde sırayla sor:

1. **`trace_id` ne?** — Frontend toast'da, response'ta, log'da görünür
2. **Hangi katman?** — API / Service / DB / ML / External / Security
3. **Aynı `fingerprint` daha önce çıktı mı?** — error_events tablosunda dedup'lanır

Bu 3 sorunun cevabı %80 hata için yeterli — dakikalar içinde sebebi bul.

## Adım 1: Hata yakaladığında ilk 30 saniye

### Frontend hatası
1. **Tarayıcı toast'unda** `Trace ID: 4e1df02e-...` görünür → kopyala
2. Browser console'unda **network tab → response → trace_id**
3. Veya: backend log'larında zaman damgasıyla bul

### Backend exception
Stack trace zaten loglandı. Önemli bilgiler:
```
2026-05-28 ... | ERROR | app.api.v1.endpoints.trips | create_sefer | ...
trace_id=4e1df02e-31f5-4e03-829b-e8f02437823a
```

## Adım 2: Trace ID ile tüm event zinciri

```bash
make trace TRACE=4e1df02e-31f5-4e03-829b-e8f02437823a
```

Bu komut **3 container'ın** (backend, worker, celery-beat) son 24 saatlik
log'larını trace_id'ye göre filtreler. Tek satırda tüm zincir görünür:
- Request received
- Service çağrısı
- DB sorgusu
- ML predict
- Event publish
- Response

## Adım 3: `error_events` tablosunda yapılandırılmış arama

PostgreSQL'de tüm hatalar otomatik kaydedilir:

```bash
make psql
```

```sql
-- Son 24 saatte tekrar eden hatalar (count > 1)
SELECT fingerprint, layer, category, severity, count,
       LEFT(message, 80) as msg, last_seen
FROM error_events
WHERE resolved_at IS NULL
  AND last_seen > NOW() - INTERVAL '24 hours'
ORDER BY count DESC, last_seen DESC;

-- Belirli bir trace_id'ye ait kayıtlar
SELECT layer, category, severity, message, stack_trace
FROM error_events
WHERE trace_id = '4e1df02e-31f5-4e03-829b-e8f02437823a';

-- Katmana göre dağılım
SELECT layer, severity, COUNT(*) FROM error_events
WHERE resolved_at IS NULL
GROUP BY layer, severity ORDER BY layer, severity;
```

Veya UI: `/monitoring` → "Hata Olayları" sekmesi. Filtre + resolve aksiyonu var.

## Adım 4: Hatanın tipini tanı

| Kategori | Sebep | İlk adım |
|---|---|---|
| `db_error` | SQL syntax, FK ihlali, deadlock | psql ile sorguyu manuel çalıştır |
| `api_error / http_5xx` | Endpoint exception | Stack trace + ilgili service test'i |
| `service / domain_error` | İş kuralı ihlali (DomainError) | Sebep enum + ilgili Pydantic schema |
| `ml_error / Feature schema mismatch` | Model eski feature ile eğitilmiş | `make clean-models` + retrain |
| `external / 5xx` | ORS/Groq/OPET timeout | Provider healthcheck, .env kontrol |
| `security / jwt_anomaly` | Token süresi dolmuş | Beklenen, INFO seviyesi |
| `security / brute_force` | 10+ failed login | IP whitelist veya gerçek saldırı |

## Adım 5: Sentry ile retrospektif

Sentry DSN ayarlıysa (`SENTRY_DSN` env):
- Group view: aynı tipdeki tüm exception'lar bir araya gelir
- Issue detail: tam stack + breadcrumb + user context
- Performance: yavaş endpoint'ler

## Adım 6: Reproduction & fix

1. **Test koşa**: `make test-fast` (unit test'ler, 30 sn)
2. **İlgili modülün test'ini bul**: `app/tests/unit/test_<modül>.py`
3. **Reproducer ekle**: error_events'teki message/metadata'yı kullanarak yeni bir test yaz
4. **Fix yaz**, test'i tekrar koş, yeşil olunca commit
5. **Pre-commit otomatik çalışır**: ruff + format + ESLint

## Hızlı komut listesi

```bash
# Operasyon
make up                          # docker compose up -d
make rebuild                     # backend+frontend rebuild + recreate
make health                      # /api/v1/health JSON
make smoke                       # 4 servisin HTTP code'unu göster

# Debug
make logs-be                     # canlı backend log
make logs-worker                 # celery worker log
make trace TRACE=xxx             # trace_id ile filtre
make psql                        # PostgreSQL CLI
make redis                       # Redis CLI

# Kalite
make lint                        # ruff + frontend ESLint
make fmt                         # ruff format + prettier
make test-fast                   # unit tests (30 sn)
make test                        # tüm non-integration suite (6 dk)
make precommit                   # tüm dosyalarda pre-commit

# ML
make clean-models                # eski model dosyalarını arşivle (schema mismatch)
```

## Pre-commit hook nasıl çalışır?

Her `git commit` öncesi otomatik çalışır:

- ✅ Ruff (lint + autofix E,F,W,I)
- ✅ Ruff format
- ✅ Trailing whitespace, EOF newline
- ✅ YAML/TOML syntax check
- ✅ Merge conflict marker check
- ✅ 500 KB'tan büyük dosya engelle
- ✅ detect-secrets (API key/password leak yakalar)
- ✅ Frontend prettier + ESLint (sadece değişen dosyalar)
- ⚠️ mypy local'de çalışmaz (CI'da var) — manuel `make mypy`

Hook bypass etmek (acil durum):
```bash
git commit --no-verify -m "..."
```
> ⚠️ `--no-verify` sadece gerçek aciliyetlerde. Hook'lar kaliteyi korur.

## Bu playbook'u güncel tut

Yeni bir hata pattern'i yakaladığında, çözüm yolunu **Adım 4 tablosuna**
ekle. Bu sayede gelecekteki sen / takım arkadaşların aynı hatayı 5
dakikada çözer.
