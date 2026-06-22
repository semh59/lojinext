# Observability — LojiNext

Bu belge LojiNext'in Sentry hata takibi ve OpenTelemetry dağıtık izleme
altyapısını yapılandırmak için gereken ortam değişkenlerini ve kurulum
adımlarını açıklar.

---

## Sentry

Sentry; çalışma zamanı hatalarını, işlenmeyen istisnaları ve yavaş işlemleri
yakalayarak bir Sentry projesine gönderir.

### Ortam Değişkenleri

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `SENTRY_DSN` | Hayır | `""` (devre dışı) | Sentry proje DSN'i. Boş bırakılırsa Sentry SDK başlatılmaz. |
| `ENVIRONMENT` | Evet | `"development"` | `production` / `staging` / `development` — Sentry'de environment etiketi olarak görünür. |
| `PROJECT_NAME` | Evet | `"LojiNext"` | Sentry'deki release/server_name değeri. |

### Örnek `.env`

```dotenv
SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project>
ENVIRONMENT=production
```

### Notlar

- DSN üretim ortamında **zorunlu** olarak ayarlanmalıdır; aksi takdirde
  runtime hataları görünmez olur.
- Sentry entegrasyonu `app/main.py` içinde `sentry_sdk.init()` ile
  başlatılmaktadır. `SENTRY_DSN` boşsa init çağrısı atlanır.
- Sentry'nin `traces_sample_rate` değeri düşük tutulmalıdır (önerilen: 0.05–0.1)
  yüksek trafik ortamlarında gereksiz veri gönderimini önlemek için.

---

## OpenTelemetry (OTel)

OpenTelemetry; isteklerin uçtan uca izini (trace), metrik dışa aktarımını
ve yapılandırılmış log bağlamını sağlar.

### Ortam Değişkenleri

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `OTEL_ENABLED` | Hayır | `False` | `True` olarak ayarlandığında OTel SDK başlatılır. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel açıksa Evet | `""` | OTLP gRPC/HTTP collector endpoint'i. Örn: `http://otel-collector:4317` |
| `OTEL_SERVICE_NAME` | Hayır | `"lojinext-backend"` | Trace'lerde görünen servis adı. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Hayır | `""` | `key=value,key2=value2` formatında ek HTTP başlıkları (API anahtarları vb.). |

### Örnek `.env`

```dotenv
OTEL_ENABLED=True
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=lojinext-backend
```

### Desteklenen Collector'lar

- **Grafana Alloy / Tempo** — doğrudan OTLP gRPC alır
- **OpenTelemetry Collector** — routing + sampling politikaları için
- **Jaeger** (`--collector.otlp.enabled`) — geliştirme ortamı için

### Docker Compose (Geliştirme)

`docker-compose.yml` dosyasında Jaeger servisi tanımlıdır:

```yaml
jaeger:
  image: jaegertracing/all-in-one:1.57
  ports:
    - "16686:16686"   # UI
    - "4317:4317"     # OTLP gRPC
```

OTel etkinleştirmek için backend servisine şu env'leri ekleyin:

```yaml
OTEL_ENABLED: "True"
OTEL_EXPORTER_OTLP_ENDPOINT: "http://jaeger:4317"
```

---

## Logging

Yapılandırılmış log çıktısı `app/infrastructure/logging/logger.py` tarafından
yönetilir.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LOG_LEVEL` | `"INFO"` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |

Production ortamında `LOG_LEVEL=WARNING` önerilir; gereksiz INFO satırları
log maliyetini artırır.

---

## Grafana & Prometheus

`docker-compose.prod.yml` içinde Grafana ve Prometheus tanımlıdır.

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | **Evet** | Grafana admin şifresi. Boş veya varsayılan bırakılamaz. |
| `PROMETHEUS_RETENTION_TIME` | Hayır | Varsayılan: `15d`. Metrik saklama süresi. |

> **Güvenlik:** `GF_SECURITY_ADMIN_PASSWORD` için zayıf/default değer
> kullanmayın. `docker-compose.prod.yml` bu değişkeni default olmadan
> zorunlu tutar; set edilmemişse compose config aşamasında hata verir.

---

## Checklist — Production Deploy

- [ ] `SENTRY_DSN` ortam değişkeni ayarlandı mı?
- [ ] `ENVIRONMENT=production` set edildi mi?
- [ ] `OTEL_ENABLED=True` ise collector endpoint erişilebilir mi?
- [ ] `GF_SECURITY_ADMIN_PASSWORD` strong bir değere sahip mi?
- [ ] `LOG_LEVEL=WARNING` prod için ayarlandı mı?
