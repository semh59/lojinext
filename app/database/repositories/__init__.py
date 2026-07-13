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
from app.database.repositories.analiz_repo import AnalizRepository
from app.database.repositories.arac_repo import AracRepository
from app.database.repositories.audit_repo import AuditRepository
from app.database.repositories.config_repo import ConfigRepository
from app.database.repositories.dorse_repo import DorseRepository, get_dorse_repo
from app.database.repositories.import_repo import ImportHistoryRepository
from app.database.repositories.kullanici_repo import KullaniciRepository
from app.database.repositories.maintenance_repository import MaintenanceRepository
from app.database.repositories.ml_training_repo import MLTrainingRepository
from app.database.repositories.model_versiyon_repo import ModelVersiyonRepository
from app.database.repositories.rol_repo import RolRepository
from app.database.repositories.sefer_repo import SeferRepository
from app.database.repositories.session_repo import SessionRepository
from app.database.repositories.setting_repository import SettingRepository
from app.database.repositories.sofor_repo import SoforRepository
from app.database.repositories.yakit_repo import YakitRepository
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.notification.infrastructure.repository import NotificationRepository
from v2.modules.route_simulation.infrastructure.repository import RouteRepository

__all__ = [
    "AdminConfigRepository",
    "AnalizRepository",
    "AracRepository",
    "AuditRepository",
    "ConfigRepository",
    "DorseRepository",
    "ImportHistoryRepository",
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
