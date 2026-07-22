"""Application configuration loaded from environment.

Single source of truth: every `settings.X` reference in the codebase must
correspond to a field declared here. Validation is fail-fast: missing
required fields raise on startup.
"""

import json as _json
from typing import List, Literal, Optional

from pydantic import (
    SecretStr,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "test", "prod"]
JwtAlgorithm = Literal["HS256", "RS256"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core
    PROJECT_NAME: str = "LojiNext"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Environment = "dev"

    # Auth
    SECRET_KEY: SecretStr
    ALGORITHM: JwtAlgorithm = "HS256"
    JWT_PRIVATE_KEY: Optional[SecretStr] = None
    JWT_PUBLIC_KEY: Optional[SecretStr] = None
    JWT_AUDIENCE: str = "lojinext-api"
    JWT_REFRESH_AUDIENCE: str = "lojinext-refresh"
    JWT_ISSUER: str = "lojinext-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    SUPER_ADMIN_USERNAME: str = "admin"
    SUPER_ADMIN_PASSWORD: Optional[SecretStr] = None
    # Break-glass login'in brute-force bucket'ı (IP başına). Default prod
    # değeri kasıtlı olarak çok sıkı — DEĞİŞTİRME. CI/test ortamları, E2E ve
    # real-backend suit'lerinin meşru login yoğunluğu için env ile yükseltir
    # (2026-07-07: Playwright admin.spec test başına login yapınca 3/300s
    # bucket 4. testte doldu, 15 E2E testi 429 ile düştü).
    SUPER_ADMIN_LOGIN_RATE: float = 3.0
    SUPER_ADMIN_LOGIN_PERIOD: float = 300.0
    ADMIN_PASSWORD: Optional[SecretStr] = None
    DEFAULT_ADMIN_PASSWORD: Optional[SecretStr] = None

    # PII encryption-at-rest (Tier E madde 26) — Fernet key, also used as the
    # HMAC key for blind-index/trigram-index lookups. Generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    PII_ENCRYPTION_KEY: SecretStr

    # Database
    DATABASE_URL: str
    # Tier E madde 30 — when set, the ASYNC application engine (request/task
    # handling) connects through this URL (pgbouncer) instead of DATABASE_URL.
    # DATABASE_URL itself keeps pointing directly at Postgres and stays the
    # one Alembic/scripts use — DDL (e.g. CREATE INDEX CONCURRENTLY, used
    # elsewhere in alembic/versions/) and other session-level migration
    # behavior don't mix well with PgBouncer transaction pooling, so
    # migrations deliberately bypass it. None (default) = no pgbouncer, the
    # async engine also uses DATABASE_URL directly (dev/test default).
    DATABASE_URL_POOLED: Optional[str] = None
    # Connection pool sizing (ARCH-005). Tune relative to PostgreSQL
    # max_connections AND the number of app/worker replicas:
    #   total_conns ≈ replicas * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
    # Sync engine is now the async engine's internal wrapper — no separate pool.
    DB_POOL_SIZE: int = 40
    DB_MAX_OVERFLOW: int = 5
    # Per-statement timeout (seconds) for the async/asyncpg engine. A single
    # query (including lock waits) running longer than this is cancelled, so a
    # runaway or stuck statement cannot hold a pool connection indefinitely and
    # exhaust the pool (DoS). Per-STATEMENT, not per-transaction — long
    # multi-query operations are unaffected; the ~10 s MV refresh sits well
    # under the default and already degrades gracefully if cancelled. 0 = off.
    DB_COMMAND_TIMEOUT_S: float = 60.0
    # Tier E madde 30 — set True when DATABASE_URL points at the pgbouncer
    # service (transaction pooling) instead of Postgres directly. asyncpg
    # caches prepared statements per physical connection; under pgbouncer
    # transaction mode a given client "connection" can be routed to a
    # different backend server connection between statements, so a cached
    # prepared statement can silently reference the wrong backend and fail
    # with "prepared statement ... does not exist". Disabling asyncpg's
    # statement cache (statement_cache_size=0) is the documented fix — real
    # cost is losing prepared-statement reuse, not correctness risk. Direct
    # (non-pgbouncer) connections — e.g. TEST_DATABASE_URL in CI/tests —
    # leave this False and keep normal caching.
    DB_THROUGH_PGBOUNCER: bool = False

    # Cache / Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    REDIS_SSL_INSECURE: bool = False
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_EAGER: bool = False  # True in test env: tasks run inline, no broker needed

    # Tier E madde 31 — Redis is a SPOF (cache + Celery broker/backend +
    # rate-limit + event-dedup + idempotency + token-blacklist all share one
    # instance). Set True to discover the master via Sentinel instead of
    # connecting directly to REDIS_HOST/PORT — see
    # app/infrastructure/cache/redis_client_factory.py for the single place
    # this flag is consumed.
    REDIS_USE_SENTINEL: bool = False
    # Comma-separated "host:port" list, e.g.
    # "redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379".
    REDIS_SENTINEL_HOSTS: str = ""
    REDIS_SENTINEL_MASTER_NAME: str = "mymaster"

    # Resilience
    CB_FAIL_MAX: int = 5
    CB_RESET_TIMEOUT: float = 60.0

    # CORS — stored raw; exposed parsed via `cors_origins`. Accepts JSON
    # array, comma-separated list, or empty string from .env.
    CORS_ORIGINS: str = ""

    # Metrics endpoint protection — comma-separated allowed IPs/CIDRs.
    # Defaults to loopback + Docker internal range.
    METRICS_ALLOWED_IPS: str = "127.0.0.1,::1,172.16.0.0/12,10.0.0.0/8"

    # External APIs
    OPENROUTESERVICE_API_KEY: str = ""  # required in prod; "" disables ORS routing
    MAPBOX_API_KEY: Optional[SecretStr] = None
    WEATHER_API_KEY: Optional[SecretStr] = None

    # External API base URLs — real production defaults; overridable so
    # tests can point at a local deterministic stub server (0-mock epic,
    # Kategori B) instead of in-process httpx/client mocking.
    MAPBOX_API_BASE_URL: str = (
        "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"
    )
    OPENROUTE_API_BASE_URL: str = "https://api.openrouteservice.org/v2"
    OPEN_METEO_API_BASE_URL: str = "https://api.open-meteo.com/v1/elevation"
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"

    # AI / LLM
    GROQ_API_KEY: Optional[SecretStr] = None
    GROQ_API_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL_NAME: str = "llama-3.3-70b-versatile"
    COACHING_ENABLED: bool = True  # Feature A — şoför koçluk modülü feature flag
    THEFT_INVESTIGATION_ENABLED: bool = True  # Feature B — soruşturma akışı
    THEFT_ALARM_ENABLED: bool = True  # Feature B.5 — Telegram OPS alarm
    TRIP_PLANNER_ENABLED: bool = True  # Feature C — sefer planlama sihirbazı
    TRIP_PLANNER_CACHE_TTL_S: int = 300  # 5 dk — driver profile + arac shortlist
    MAINTENANCE_PREDICTOR_ENABLED: bool = True  # Feature D — bakım tahmin motoru
    MAINTENANCE_PREDICTOR_CACHE_TTL_S: int = 3600  # 1 saat
    MAINTENANCE_FACTOR_ENABLED: bool = True  # Feature D.4 — bakım→yakıt geri besleme
    # Phase 4.4/5.0 — SeferFuelEstimator opt-in production.
    # Pipeline: Mapbox per-segment + Open-Meteo elevation + weather (gerçek
    # sıcaklık/rüzgar/yağış) + adjustment factors + physics.
    # Default False: mevcut test suite mock'ları korunur. Production'da
    # docker-compose / .env üzerinden USE_SEFER_FUEL_ESTIMATOR=true ile aktif.
    # Aktivasyon sonrası sefer kaydedilirken yeni sistem çalışır → sefer.
    # tahmini_tuketim + route_simulation_id set edilir.
    USE_SEFER_FUEL_ESTIMATOR: bool = False
    # Bulk import için yakıt tahmin stratejisi:
    #  - "skip" (default): >threshold sefer ise tahmin atlanır (geçmiş veri
    #    import'unda gerçek tüketim zaten kayıtlı)
    #  - "share": aynı lokasyon group → tek simülasyon paylaşılır
    #  - "full": her sefer için ayrı simülasyon (pahalı)
    BULK_FUEL_ESTIMATE: str = "skip"
    BULK_FUEL_ESTIMATE_THRESHOLD: int = 20
    EXECUTIVE_ENABLED: bool = True  # Feature E — Strategic Cockpit
    EXECUTIVE_WHAT_IF_ENABLED: bool = True  # Feature E.2
    EXECUTIVE_CACHE_TTL_S: int = 1800  # 30 dk
    LITRE_DIESEL_TL: float = 50.0  # what-if + cashflow varsayımı
    AVG_BAKIM_COST_TL: float = 5000.0  # cashflow fallback
    REPORTS_V2_ENABLED: bool = True  # Reports v2 — yeni sayfalar
    REPORTS_V2_LLM_NARRATION_ENABLED: bool = False  # v1 OFF; v2.1 aktif
    REPORTS_V2_TRIAGE_LIMIT: int = 50  # Today sayfası max item
    # RV2.PWA — Web Push (VAPID self-hosted)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = ""  # mailto:admin@... format
    PUSH_NOTIFICATION_ENABLED: bool = False  # VAPID set olunca True yapılır

    # 3rd party provider entegrasyonları (kullanıcı seçince doldurulur)
    # AVL (araç takip): mobiliz, arvento, vodafone, ...
    AVL_PROVIDER: str = ""
    AVL_BASE_URL: str = ""
    AVL_API_KEY: str = ""
    AVL_ACCOUNT_ID: str = ""
    AVL_POLL_INTERVAL_SECONDS: int = 900  # 15 dk default

    # Akaryakıt kart: opet, shell, bp, po
    FUEL_PROVIDER: str = ""
    FUEL_BASE_URL: str = ""
    FUEL_API_KEY: str = ""
    FUEL_ACCOUNT_ID: str = ""
    FUEL_POLL_INTERVAL_SECONDS: int = 3600  # 1 saat default
    HF_TOKEN: Optional[SecretStr] = None
    AI_TEMPERATURE: float = 0.2
    AI_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    AI_EMBEDDING_DIM: int = 384
    # RAG engine character/threshold limits (rag_engine.py refactor)
    AI_RAG_MAX_CHARS: int = 4000
    AI_RAG_THRESHOLD: float = 0.35
    AI_RAG_MAX_DOC_CHARS: int = 10000
    AI_CONFIDENCE_THRESHOLD_RED: float = 0.40
    AI_CONFIDENCE_THRESHOLD_YELLOW: float = 0.60

    # ML
    VEHICLE_AGE_DEGRADATION_RATE: float = 0.015
    MAX_AGE_DEGRADATION: float = 0.15
    ANOMALY_Z_THRESHOLD: float = 2.5  # z-score cut-off for fuel anomaly detection

    # Faz 3 — kullanım analitiği: page_views retention (gün). Gece task'i bundan
    # eski satırları siler (kayıt hacmi kontrolü).
    ANALYTICS_RETENTION_DAYS: int = 90

    # Faz 8 — anomali kümeleri için Groq LLM insight metni (feature flag).
    # Kapalıyken pattern listesi yine döner; Groq kesintisi listeyi bloklamaz.
    ANOMALY_CLUSTER_LLM_ENABLED: bool = False

    # Faz 7 — çevresel faktör fiziksel üst sınırları (gerçek-veri validation
    # bulgusu; 5 referans rotadan bağımsız, overfit'siz). wind: ağır araç
    # highway aerodinamik drag tipik +%5-10. seasonal: bir FALLBACK; gerçek
    # soğuk weather_temperature (<=1.20) ile yakalanır → fallback fiziksel cap.
    WEATHER_WIND_FACTOR_MAX: float = 1.10
    SEASONAL_FACTOR_MAX: float = 1.03

    # Segment-tractive model (2026-06-14) — fiziksel-doğru per-segment yakıt.
    # Spec: docs/superpowers/specs/2026-06-14-segment-tractive-model-design.md
    PHYSICS_ENGINE_BSFC: float = 0.42  # Euro-6 dizel pik termal verim
    PHYSICS_DRIVELINE_EFF: float = 0.95  # şanzıman + aks verimi
    PHYSICS_PARASITIC_KW: float = (
        4.0  # soğutma+alternatör+klima+rölanti (zaman-bazlı base); 10-rota fit
    )
    PHYSICS_DRAG_CDA_M2: float = (
        6.80  # efektif Cd·A (m²); VECTO non-aero TIR, 10-rota fit
    )
    PHYSICS_GRADE_CLAMP_PCT: float = 9.0  # yol fiziksel max eğim (SRTM gürültü kesme)
    USE_SEGMENT_TRACTIVE_MODEL: bool = False  # rollout flag — validasyon sonrası true

    # Logistics / vehicle constants
    HGV_EMPTY_WEIGHT: float = 8000.0  # kg — default empty HGV truck weight
    DEFAULT_LOAD_TON: float = 10.0  # ton — default payload for fuel estimate
    DEFAULT_FILO_HEDEF_TUKETIM: float = 32.0  # L/100km — fleet fuel target
    ELITE_SCORE_TRIP_LIMIT: int = 50  # trip count for elite driver scoring

    # Weather thresholds (used in fuel-impact calculation)
    WEATHER_TEMP_HIGH_THRESHOLD: float = 35.0  # °C — hot weather penalty
    WEATHER_WIND_HIGH_THRESHOLD: float = 60.0  # km/h — high wind penalty
    WEATHER_IMPACT_MEDIUM: float = 1.05  # impact factor upper bound for "medium" band
    WEATHER_IMPACT_HIGH: float = 1.15  # impact factor upper bound for "high" band

    # Infra flags (used by test harnesses)
    ALEMBIC_READY: bool = False  # Set True by conftest after migration is confirmed

    # Rate limiting
    EXTERNAL_API_RATE_LIMIT: float = 10.0  # req/sec (generic external API limit)
    # Master switch — set False ONLY for capacity load tests (single-source bursts
    # otherwise trip per-IP limits and dominate the result). Prod must stay True.
    RATE_LIMIT_ENABLED: bool = True

    # Route validation delta thresholds (Mapbox vs ORS comparison)
    ROUTE_DIST_DELTA_WARN_PCT: float = 5.0  # warn when providers differ by >5%
    ROUTE_DIST_DELTA_FAIL_PCT: float = 15.0  # fail/fallback when >15%
    ROUTE_DUR_DELTA_WARN_PCT: float = 10.0
    ROUTE_DUR_DELTA_FAIL_PCT: float = 20.0

    # Observability
    SENTRY_DSN: Optional[str] = None
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    SQL_ECHO: bool = False

    # Backup / maintenance
    BACKUP_RETENTION_DAYS: int = 30

    # Email / SMTP (şifre sıfırlama + bildirimler)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "LojiNext"
    SMTP_USE_TLS: bool = True  # STARTTLS (port 587); False için SSL port 465 gerekir

    # Telegram bots
    TELEGRAM_OPS_BOT_TOKEN: str = ""
    TELEGRAM_OPS_CHAT_ID: str = ""
    TELEGRAM_DRIVER_BOT_TOKEN: str = ""
    # Minimum severity for immediate Telegram notification (warning|error|critical)
    NOTIFY_MIN_LEVEL: str = "error"

    # OCR service (internal Docker network)
    OCR_SERVICE_URL: str = "http://ocr-service:8001"
    OCR_SERVICE_API_KEY: str = ""  # Set to a random secret; empty = auth disabled (dev)
    BELGELER_UPLOAD_DIR: str = "/belgeler"

    # Read-only Docker Engine API proxy (see docker-compose.yml's
    # docker-socket-proxy: CONTAINERS+NETWORKS+EVENTS=1, POST=0) — used to
    # report the telegram bot containers' actual running/health state on the
    # admin Integrations page, since a DB-configured-key flag alone can't
    # tell an admin whether the bot (usually token-provisioned via .env, not
    # this panel) is actually up.
    DOCKER_SOCKET_PROXY_URL: str = "http://docker-socket-proxy:2375"

    # Internal API secret — shared between backend and telegram bot containers.
    # Requests to /api/v1/internal/* must carry: X-Internal-Token: <this value>
    INTERNAL_API_SECRET: str = ""

    # Global request body cap (DoS backstop). Rejects requests whose declared
    # Content-Length exceeds this, before the body is read into memory. Set well
    # above per-endpoint upload caps (10 MB Excel) so legitimate multipart
    # uploads pass; defends against absurd (multi-hundred-MB) bodies.
    MAX_REQUEST_BODY_BYTES: int = 25 * 1024 * 1024  # 25 MB

    # PII masking (consumed by v2.modules.platform_infra.logging.logger)
    LOG_PII_MASK_EMAIL: str = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    LOG_PII_MASK_PHONE: str = (
        r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,4}\)?[\s-]?)?\d{3}[\s-]?\d{2,4}[\s-]?\d{2,4}"
    )
    LOG_PII_MASK_TCKN: str = r"\b[1-9]\d{10}\b"
    LOG_PII_SENSITIVE_KEYS: str = (
        "password,passwd,pwd,token,api_key,apikey,secret,"
        "authorization,access_token,refresh_token"
    )

    # ── Parsed accessors ─────────────────────────────────────────────────
    @staticmethod
    def _parse_list(raw: str) -> List[str]:
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith("["):
            return list(_json.loads(raw))
        return [item.strip() for item in raw.split(",") if item.strip()]

    @computed_field
    @property
    def cors_origins(self) -> List[str]:
        return self._parse_list(self.CORS_ORIGINS)

    @computed_field
    @property
    def pii_sensitive_keys(self) -> List[str]:
        return self._parse_list(self.LOG_PII_SENSITIVE_KEYS)

    @model_validator(mode="after")
    def _validate(self):
        if self.ALGORITHM == "RS256" and not (
            self.JWT_PRIVATE_KEY and self.JWT_PUBLIC_KEY
        ):
            raise ValueError(
                "ALGORITHM=RS256 requires both JWT_PRIVATE_KEY and JWT_PUBLIC_KEY."
            )
        if self.ENVIRONMENT == "prod" and not self.ADMIN_PASSWORD:
            raise ValueError("ADMIN_PASSWORD is required in production.")
        if self.ENVIRONMENT == "prod" and not self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS must be set in production. "
                "Example: CORS_ORIGINS=https://app.example.com"
            )
        if self.ENVIRONMENT == "prod" and "*" in self.cors_origins:
            # The API is mounted with allow_credentials=True. With a wildcard,
            # Starlette reflects the request Origin and returns
            # Access-Control-Allow-Credentials: true — i.e. ANY site can make
            # authenticated cross-origin requests on a logged-in user's behalf.
            # Force an explicit allow-list in production.
            raise ValueError(
                "CORS_ORIGINS cannot be '*' in production: the API sends "
                "credentials, so a wildcard lets any origin make authenticated "
                "requests. List explicit origins, e.g. "
                "CORS_ORIGINS=https://app.example.com"
            )
        if self.ENVIRONMENT == "prod" and not self.OPENROUTESERVICE_API_KEY:
            raise ValueError(
                "OPENROUTESERVICE_API_KEY zorunlu — production'da route servisi için gereklidir."
            )
        if self.ENVIRONMENT == "prod" and not self.INTERNAL_API_SECRET:
            raise ValueError(
                "INTERNAL_API_SECRET is required in production. "
                "Set it to a cryptographically random string shared with the "
                "bot/OCR containers, otherwise internal endpoints fail at runtime."
            )
        return self


settings = Settings()
