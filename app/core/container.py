"""
TIR Yakıt Takip Sistemi - Uygulama Ömürlü DI Container.

Bu container yalnızca **uygulama ömrü boyunca yaşayan singleton** servisleri
barındırır: ML/AI motorları, anomali dedektörü, hava durumu servisi vb.

─── Ne BURAYA girer ────────────────────────────────────────────────────────
• Pahalı başlangıç maliyeti olan servisler (model yükleme, vektör indeks)
• UoW/transaction gerektirmeyen, durumsuz (stateless) servisler
• Altyapı singletonu'ları (event bus, external service vb.)

─── Ne BURAYA girmez ───────────────────────────────────────────────────────
• Transaction-scoped domain servisleri (AracService, SeferService, …)
  → Bunlar ``app/api/deps.py`` içindeki Depends() factory'leri aracılığıyla
    her request'te UnitOfWork ile birlikte oluşturulur.

DI mimarisinin tam açıklaması: ``app/api/deps.py`` modül docstring'ine bakın.
────────────────────────────────────────────────────────────────────────────
"""

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.core.services.health_service import HealthService
    from app.infrastructure.events.event_bus import EventBus
    from v2.modules.ai_assistant.application.knowledge_base import SmartAIService
    from v2.modules.analytics_executive.infrastructure.executive_read_models import (
        AnalizRepository,
    )
    from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector
    from v2.modules.auth_rbac.application.license_service import LicenseEngine
    from v2.modules.driver.infrastructure.repository import SoforRepository
    from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
    from v2.modules.fleet.infrastructure.vehicle_repository import AracRepository
    from v2.modules.fuel.infrastructure.repository import YakitRepository
    from v2.modules.location.infrastructure.repository import LokasyonRepository
    from v2.modules.prediction_ml.application.prediction_service import (
        PredictionService,
    )
    from v2.modules.prediction_ml.application.time_series_service import (
        TimeSeriesService,
    )
    from v2.modules.trip.application.trip_service import SeferService
    from v2.modules.trip.infrastructure.repository import SeferRepository


class Container:
    """
    Dependency Injection Container — Singleton, Thread-Safe, Lazy-Loaded.

    INITIALIZATION ORDER (dependency graph sırası):
    1. Infrastructure : event_bus
    2. Repositories   : arac, sefer, sofor, yakit, lokasyon, dorse, analiz
    3. Domain Services: arac, sofor, sefer, yakit, lokasyon, dorse, analiz
    4. ML/AI          : prediction, anomaly_detector, time_series (ağır)
    5. External/Infra : license, health, route, smart_ai, weather (ağ bağımlı)

    SINGLETON vs PER-REQUEST KURALI:
    - BURAYA GİRER (singleton): ML model yüklemesi, AI engine, external API client,
      pahalı başlangıç maliyeti, durumsuz / değiştirilemez servisler.
    - BURAYA GİRMEZ (per-request): Transaction-scoped domain CRUD servisleri.
      Bunlar app/api/deps.py'de Depends() + UoW ile oluşturulur.

    Circular import kuralı: Servisler container'a doğrudan modül seviyesinde
    referans vermemeli. Fonksiyon içi deferred import kullanılmalı.
    """

    def __init__(self):
        self._lock = (
            threading.RLock()
        )  # Re-entrant lock to prevent deadlocks when properties call each other

        # ── 1. Infrastructure ───────────────────────────────────────────────
        # event_bus: domain event yayını için; diğer tüm servisler kullanabilir
        self._event_bus: Optional["EventBus"] = None

        # ── 2. Repositories (sessionsuz blueprint; UoW session inject eder) ─
        # Bu repo'lar "şablon" olarak yaşıyor. Gerçek sorgular UoW.session
        # üzerinden yapılır. Container'daki örnek sadece DI wire-up içindir.
        self._arac_repo: Optional["AracRepository"] = None
        self._sefer_repo: Optional["SeferRepository"] = None
        self._sofor_repo: Optional["SoforRepository"] = None
        self._yakit_repo: Optional["YakitRepository"] = None
        self._lokasyon_repo: Optional["LokasyonRepository"] = None
        self._dorse_repo: Optional["DorseRepository"] = None
        self._analiz_repo: Optional["AnalizRepository"] = None

        # ── 3. Core Domain Services (singleton — stateless read-heavy) ──────
        # NOT: Transaction-scoped CRUD servisleri (AracService, SeferService vb.)
        # burada da tutuluyor; ancak gerçek endpoint kullanımı deps.py üzerinden
        # per-request UoW ile yapılır. Bu instance'lar yalnızca diğer singleton
        # servislerin ihtiyaç duyduğu durumlarda devreye girer.
        self._sefer_service: Optional["SeferService"] = None

        # ── 4. ML/AI Subsystem (singleton — ağır model yüklemesi) ───────────
        # Model dosyaları ilk erişimde bir kez yüklenir.
        # Sonraki request'lerde in-memory model kullanılır.
        # Bu servisler THREAD-SAFE olmak zorunda (paralel inference).
        self._prediction_service: Optional["PredictionService"] = None
        self._anomaly_detector: Optional["AnomalyDetector"] = None
        self._time_series_service: Optional["TimeSeriesService"] = None
        self._ai_service = None
        self._smart_ai_service: Optional["SmartAIService"] = None

        # ── 5. External / Infrastructure Services ───────────────────────────
        # Ağ bağımlı veya konfigürasyon tabanlı servisler.
        self._license_service: Optional["LicenseEngine"] = None
        self._health_service: Optional["HealthService"] = None
        self._external_service = None
        self._weather_service = None
        self._export_service = None
        self._internal_service = None

    @property
    def event_bus(self) -> "EventBus":
        if self._event_bus is None:
            with self._lock:
                if self._event_bus is None:
                    from app.infrastructure.events.event_bus import get_event_bus

                    self._event_bus = get_event_bus()
        return self._event_bus

    # --- Repositories ---

    @property
    def arac_repo(self) -> "AracRepository":
        if self._arac_repo is None:
            with self._lock:
                if self._arac_repo is None:
                    from v2.modules.fleet.infrastructure.vehicle_repository import (
                        AracRepository,
                    )

                    self._arac_repo = AracRepository()
        return self._arac_repo

    @property
    def sefer_repo(self) -> "SeferRepository":
        if self._sefer_repo is None:
            with self._lock:
                if self._sefer_repo is None:
                    from v2.modules.trip.infrastructure.repository import (
                        SeferRepository,
                    )

                    self._sefer_repo = SeferRepository()
        return self._sefer_repo

    @property
    def sofor_repo(self) -> "SoforRepository":
        if self._sofor_repo is None:
            with self._lock:
                if self._sofor_repo is None:
                    from v2.modules.driver.infrastructure.repository import (
                        SoforRepository,
                    )

                    self._sofor_repo = SoforRepository()
        return self._sofor_repo

    @property
    def yakit_repo(self) -> "YakitRepository":
        if self._yakit_repo is None:
            with self._lock:
                if self._yakit_repo is None:
                    from v2.modules.fuel.infrastructure.repository import (
                        YakitRepository,
                    )

                    self._yakit_repo = YakitRepository()
        return self._yakit_repo

    @property
    def lokasyon_repo(self) -> "LokasyonRepository":
        if self._lokasyon_repo is None:
            with self._lock:
                if self._lokasyon_repo is None:
                    from v2.modules.location.infrastructure.repository import (
                        LokasyonRepository,
                    )

                    self._lokasyon_repo = LokasyonRepository()
        return self._lokasyon_repo

    @property
    def dorse_repo(self) -> "DorseRepository":
        if self._dorse_repo is None:
            with self._lock:
                if self._dorse_repo is None:
                    from v2.modules.fleet.infrastructure.trailer_repository import (
                        DorseRepository,
                    )

                    self._dorse_repo = DorseRepository()
        return self._dorse_repo

    # --- Core Services ---

    @property
    def sefer_service(self) -> "SeferService":
        if self._sefer_service is None:
            with self._lock:
                if self._sefer_service is None:
                    from v2.modules.trip.application.trip_service import SeferService

                    self._sefer_service = SeferService(
                        repo=self.sefer_repo, event_bus=self.event_bus
                    )
        return self._sefer_service

    @property
    def analiz_repo(self) -> "AnalizRepository":
        if self._analiz_repo is None:
            with self._lock:
                if self._analiz_repo is None:
                    from v2.modules.analytics_executive.infrastructure.executive_read_models import (
                        AnalizRepository,
                    )

                    self._analiz_repo = AnalizRepository()
        return self._analiz_repo

    @property
    def prediction_service(self) -> "PredictionService":
        if self._prediction_service is None:
            with self._lock:
                if self._prediction_service is None:
                    from v2.modules.prediction_ml.application.prediction_service import (
                        PredictionService,
                    )

                    self._prediction_service = PredictionService()
        return self._prediction_service

    @property
    def anomaly_detector(self) -> "AnomalyDetector":
        if self._anomaly_detector is None:
            with self._lock:
                if self._anomaly_detector is None:
                    from v2.modules.anomaly.application.detect_anomaly import (
                        AnomalyDetector,
                    )

                    self._anomaly_detector = AnomalyDetector()
        return self._anomaly_detector

    @property
    def time_series_service(self) -> "TimeSeriesService":
        if self._time_series_service is None:
            with self._lock:
                if self._time_series_service is None:
                    from v2.modules.prediction_ml.application.time_series_service import (
                        TimeSeriesService,
                    )

                    self._time_series_service = TimeSeriesService()
        return self._time_series_service

    @property
    def license_service(self) -> "LicenseEngine":
        if self._license_service is None:
            with self._lock:
                if self._license_service is None:
                    from v2.modules.auth_rbac.application.license_service import (
                        LicenseEngine,
                    )

                    self._license_service = LicenseEngine()
        return self._license_service

    @property
    def health_service(self) -> "HealthService":
        if self._health_service is None:
            with self._lock:
                if self._health_service is None:
                    from app.core.services.health_service import HealthService

                    self._health_service = HealthService()
        return self._health_service

    @property
    def ai_service(self):
        if self._ai_service is None:
            with self._lock:
                if self._ai_service is None:
                    from v2.modules.ai_assistant.application.orchestrate_ai_response import (
                        AIService,
                    )

                    self._ai_service = AIService()
        return self._ai_service

    @property
    def smart_ai_service(self) -> "SmartAIService":
        if self._smart_ai_service is None:
            with self._lock:
                if self._smart_ai_service is None:
                    from v2.modules.ai_assistant.application.knowledge_base import (
                        SmartAIService,
                    )

                    self._smart_ai_service = SmartAIService()
        return self._smart_ai_service

    @property
    def external_service(self):
        if self._external_service is None:
            with self._lock:
                if self._external_service is None:
                    from app.services.external_service import get_external_service

                    self._external_service = get_external_service()
        return self._external_service

    @property
    def export_service(self):
        if self._export_service is None:
            with self._lock:
                if self._export_service is None:
                    from v2.modules.import_excel.public import ExportService

                    self._export_service = ExportService()
        return self._export_service

    @property
    def internal_service(self):
        if self._internal_service is None:
            with self._lock:
                if self._internal_service is None:
                    from app.core.services.internal_service import InternalService

                    self._internal_service = InternalService()
        return self._internal_service

    @property
    def weather_service(self):
        if self._weather_service is None:
            with self._lock:
                if self._weather_service is None:
                    from app.core.services.weather_service import get_weather_service

                    self._weather_service = get_weather_service()
        return self._weather_service

    def shutdown(self) -> None:
        """
        Tüm servisleri ve kaynakları temizle.
        Garbage collection'a yardımcı olur ve bağlantıları keser.
        """
        with self._lock:
            # Servisleri sıfırla (Dependency sırasının tersine)
            self._smart_ai_service = None
            self._ai_service = None
            self._health_service = None
            self._license_service = None
            self._time_series_service = None
            self._anomaly_detector = None
            self._prediction_service = None
            self._sefer_service = None

            # External / infra singletons
            self._weather_service = None
            self._external_service = None

            # Repositories
            self._yakit_repo = None
            self._lokasyon_repo = None
            self._sefer_repo = None
            self._sofor_repo = None
            self._arac_repo = None
            self._dorse_repo = None

            # Infrastructure
            self._event_bus = None


# Global Instance
_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """Container singleton instance'ını getir (Thread-safe)."""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container


def reset_container() -> None:
    """
    Container singleton'ını sıfırla (Thread-safe).

    ⚠️ SADECE TEST İÇİN KULLANIN!
    """
    global _container
    with _container_lock:
        if _container:
            _container.shutdown()
        _container = None
