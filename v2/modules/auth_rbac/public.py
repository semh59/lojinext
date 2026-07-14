"""Public surface of the auth_rbac module.

Other modules that need to call into auth_rbac must import from here, not
from ``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/auth-rbac.md and .importlinter's forbidden-imports contract).

There is no ``AuthService``/``UserService``/``PreferenceService`` class —
each use-case is a standalone function (same B.1 pattern as location/
notification/fleet/fuel/driver). ``SecurityService``/``Permission`` stay a
classmethod-only namespace (no constructor/state — narrower exception than
the stateful-singleton class of ``LicenseEngine``, see CLAUDE.md).
``LicenseEngine``/``TokenBlacklist`` stay classes — see CLAUDE.md for the
exception rationale (stateful singleton).

NOT: ``get_current_user``/``get_current_active_user``/``get_current_active_admin``/
``require_permissions``/``UOWDep``/``TokenDep``/``SessionDep`` FastAPI
dependency wiring'i ``app/api/deps.py``'de KALIYOR (taşınmadı) — deps.py
FastAPI-wiring katmanı, modül kodu değil (driver/fleet dalgalarında da aynı
karar: `app/api/deps.py` hiçbir zaman v2/modules/*'e taşınmadı, yalnızca
import kaynakları güncellendi).
"""

from v2.modules.auth_rbac.application import auth_service
from v2.modules.auth_rbac.application.license_service import (
    LicenseEngine,
    get_license_engine,
)
from v2.modules.auth_rbac.application.preference_service import (
    delete_preference,
    get_preferences,
    save_preference,
    set_default,
)
from v2.modules.auth_rbac.application.user_service import (
    change_password,
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)
from v2.modules.auth_rbac.domain import jwt_handler
from v2.modules.auth_rbac.domain.permission_checker import (
    PermissionChecker,
    require_yetki,
)
from v2.modules.auth_rbac.domain.security import (
    create_access_token as create_access_token_core,
)
from v2.modules.auth_rbac.domain.security import get_jwks
from v2.modules.auth_rbac.domain.security import get_password_hash as hash_password
from v2.modules.auth_rbac.domain.security import verify_password as verify_password_core
from v2.modules.auth_rbac.domain.security_service import Permission, SecurityService
from v2.modules.auth_rbac.domain.token_blacklist import TokenBlacklist, blacklist
from v2.modules.auth_rbac.infrastructure.repository import (
    KullaniciRepository,
    RolRepository,
    SessionRepository,
)
from v2.modules.auth_rbac.schemas import (
    KullaniciCreate,
    KullaniciRead,
    KullaniciUpdate,
    PreferenceCreate,
    PreferenceItem,
    PreferenceListResponse,
    RolCreate,
    RolRead,
)

__all__ = [
    # auth (login/refresh/session/password-reset — free functions, module import)
    "auth_service",
    # user CRUD
    "list_users",
    "get_user",
    "create_user",
    "update_user",
    "delete_user",
    "change_password",
    # preferences
    "get_preferences",
    "save_preference",
    "delete_preference",
    "set_default",
    # RBAC
    "Permission",
    "SecurityService",
    "PermissionChecker",
    "require_yetki",
    # JWT / password hashing
    "jwt_handler",
    "hash_password",
    "verify_password_core",
    "create_access_token_core",
    "get_jwks",
    # token blacklist
    "TokenBlacklist",
    "blacklist",
    # license
    "LicenseEngine",
    "get_license_engine",
    # repositories
    "KullaniciRepository",
    "RolRepository",
    "SessionRepository",
    # schemas
    "KullaniciCreate",
    "KullaniciRead",
    "KullaniciUpdate",
    "RolCreate",
    "RolRead",
    "PreferenceCreate",
    "PreferenceItem",
    "PreferenceListResponse",
]
