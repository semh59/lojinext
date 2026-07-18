"""Repository module — domain-scoped persistence layer.

Every repository takes an `AsyncSession` in its constructor (see
`BaseRepository`). Wire them via `UnitOfWork` rather than calling factories
directly.
"""

from __future__ import annotations

from app.database.repositories.admin_config_repo import (
    AdminConfigRepository,
    get_admin_config_repo,
)
from app.database.repositories.audit_repo import AuditRepository
from app.database.repositories.config_repo import ConfigRepository
from app.database.repositories.setting_repository import SettingRepository
from v2.modules.analytics_executive.infrastructure.executive_read_models import (
    AnalizRepository,
)
from v2.modules.anomaly.infrastructure.anomaly_repository import AnomalyRepository
from v2.modules.anomaly.infrastructure.investigation_repository import (
    InvestigationRepository,
)
from v2.modules.auth_rbac.infrastructure.kullanici_repository import (
    KullaniciRepository,
)
from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
from v2.modules.auth_rbac.infrastructure.session_repository import SessionRepository
from v2.modules.driver.infrastructure.repository import SoforRepository
from v2.modules.fleet.infrastructure.maintenance_repository import (
    MaintenanceRepository,
)
from v2.modules.fleet.infrastructure.trailer_repository import (
    DorseRepository,
    get_dorse_repo,
)
from v2.modules.fleet.infrastructure.vehicle_repository import AracRepository
from v2.modules.fuel.infrastructure.repository import YakitRepository
from v2.modules.import_excel.infrastructure.repository import ImportHistoryRepository
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.notification.infrastructure.repository import NotificationRepository
from v2.modules.prediction_ml.infrastructure.ml_training_repo import (
    MLTrainingRepository,
)
from v2.modules.prediction_ml.infrastructure.model_versiyon_repo import (
    ModelVersiyonRepository,
)
from v2.modules.route_simulation.infrastructure.repository import RouteRepository
from v2.modules.trip.infrastructure.repository import SeferRepository

__all__ = [
    "AdminConfigRepository",
    "AnalizRepository",
    "AnomalyRepository",
    "AracRepository",
    "AuditRepository",
    "ConfigRepository",
    "DorseRepository",
    "ImportHistoryRepository",
    "InvestigationRepository",
    "KullaniciRepository",
    "LokasyonRepository",
    "MLTrainingRepository",
    "MaintenanceRepository",
    "ModelVersiyonRepository",
    "NotificationRepository",
    "RolRepository",
    "RouteRepository",
    "SeferRepository",
    "SessionRepository",
    "SettingRepository",
    "SoforRepository",
    "YakitRepository",
    "get_admin_config_repo",
    "get_dorse_repo",
]
