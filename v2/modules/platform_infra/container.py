"""
TIR Yakıt Takip Sistemi - Uygulama Ömürlü DI Container.

`app/core/container.py`'den dalga 17 (platform_infra) denetiminde taşındı —
mekanik taşıma, davranış değişikliği yok (bkz. `TASKS/modules/
platform-infra.md`). TYPE_CHECKING/deferred-import deseni ve tüm lazy
singleton mekaniği birebir korundu.

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
    from v2.modules.ai_assistant.application.knowledge_base import SmartAIService
    from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector
    from v2.modules.platform_infra.events.event_bus import EventBus
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
    2. Repositories   : sefer (yalnız sefer_service'in DI wire-up'ı için —
                        diğer 6 repo property'si dalga 17 denetiminde sıfır-
                        çağıran bulunup kaldırıldı, bkz. platform-infra.md madde 0)
    3. Domain Services: sefer
    4. ML/AI          : prediction, anomaly_detector, time_series (ağır)
    5. External/Infra : smart_ai, ai, weather, export (ağ bağımlı)

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
        # Bu repo "şablon" olarak yaşıyor. Gerçek sorgular UoW.session
        # üzerinden yapılır. Container'daki örnek sadece `sefer_service`'in
        # DI wire-up'ı içindir — bu yüzden tek kalan repo bu (diğerleri
        # dalga 17 denetiminde sıfır-çağıran bulunup kaldırıldı, bkz.
        # platform-infra.md madde 0).
        self._sefer_repo: Optional["SeferRepository"] = None

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
        self._weather_service = None
        self._export_service = None

    @property
    def event_bus(self) -> "EventBus":
        if self._event_bus is None:
            with self._lock:
                if self._event_bus is None:
                    from v2.modules.platform_infra.events.event_bus import get_event_bus

                    self._event_bus = get_event_bus()
        return self._event_bus

    # --- Repositories ---

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
    def export_service(self):
        if self._export_service is None:
            with self._lock:
                if self._export_service is None:
                    from v2.modules.import_excel.public import ExportService

                    self._export_service = ExportService()
        return self._export_service

    @property
    def weather_service(self):
        if self._weather_service is None:
            with self._lock:
                if self._weather_service is None:
                    from v2.modules.route_simulation.application.weather_service import (
                        get_weather_service,
                    )

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
            self._time_series_service = None
            self._anomaly_detector = None
            self._prediction_service = None
            self._sefer_service = None

            # External / infra singletons
            self._weather_service = None

            # Repositories
            self._sefer_repo = None

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
