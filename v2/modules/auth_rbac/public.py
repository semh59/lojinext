"""Public surface of the auth_rbac module.

Other modules that need to call into auth_rbac must import from here, not
from ``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/auth-rbac.md and .importlinter's forbidden-imports contract).
2026-07-17 B.1 dedektif denetimi bulgusu: bu iddia daha önce doğru değildi
— hiçbir gerçek tüketici buradan geçmiyordu. 7 kardeş v2 modülü +
`app/core/services/sefer_read_service.py` + 5 admin endpoint + 3 script
artık gerçekten ``public`` üzerinden gidiyor (düzeltildi). ``app/api/
deps.py``/``v2/modules/platform_infra/container.py``/``app/database/repositories/
__init__.py``/``app/infrastructure/websocket/ws_auth.py``/``app/main.py``
hâlâ dokümante edilmiş composition-root/framework-wiring istisnası (bkz.
aşağı) — bu proje genelinde tutarlı bir karar, auth_rbac'a özgü değil.

There is no ``AuthService``/``UserService``/``PreferenceService`` class —
each use-case is a standalone function (same B.1 pattern as location/
notification/fleet/fuel/driver). ``SecurityService``/``Permission`` stay a
classmethod-only namespace (no constructor/state).
``TokenBlacklist`` stays a class — see CLAUDE.md for the exception
rationale (stateful singleton).

2026-07-22 dead-code denetimi: ``LicenseEngine`` (araç/sefer ticari limit
motoru) tamamen silindi — hash-tabanlı tier kontrolü gerçek/test-edilmişti
ama fleet'in araç-oluşturma/trip'in sefer-ekleme yollarından hiçbir zaman
çağrılmadı (kullanıcı kararıyla "abandoned" kabul edildi, wire etmek yerine
silindi). ``v2/modules/platform_infra/container.py``'nin
``license_service`` lazy-property'si ve ``v2.modules.fleet.public``'in
yalnız bu motor için var olan ``count_active_vehicles()`` sarmalayıcısı da
aynı geçişte kaldırıldı.

NOT (2026-07-22 güncellemesi): ``get_current_user``/``get_current_active_user``/
``get_current_active_admin``/``get_current_superadmin``/``require_permissions``/
``TokenDep`` artık BURADA (``application/authenticate.py``) — eskiden
``app/api/deps.py``'de kalmalarının tek sebebi ``permission_checker.py``'nin
(o zaman ``domain/``'da) bu dosyayı import etmesiyle oluşan döngüydü
(public.py zaten ``PermissionChecker``'ı import ediyordu). Dosyalar
v2/modules/ İÇİNE taşınınca (ve ``permission_checker.py`` da aynı turda
``application/``'a taşınınca, artık sibling import) döngü kendiliğinden
çözüldü. ``SessionDep``/``UOWDep``/``get_background_job_manager``/
``get_sefer_service`` (jenerik per-request DI alias'ları, auth_rbac'a ait
değil) hâlâ ``app/api/deps.py``'de — bunlar ayrı bir taşımanın konusu
(`platform_infra`/`trip`).
"""

from v2.modules.auth_rbac.application import auth_service, role_service
from v2.modules.auth_rbac.application.authenticate import (
    TokenDep,
    get_current_active_admin,
    get_current_active_user,
    get_current_superadmin,
    get_current_user,
    require_permissions,
)
from v2.modules.auth_rbac.application.permission_checker import (
    PermissionChecker,
    require_yetki,
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
from v2.modules.auth_rbac.domain.jwt_handler import get_decode_key
from v2.modules.auth_rbac.domain.security import get_jwks
from v2.modules.auth_rbac.domain.security import get_password_hash as hash_password
from v2.modules.auth_rbac.domain.security_service import Permission, SecurityService
from v2.modules.auth_rbac.infrastructure.kullanici_repository import (
    KullaniciRepository,
)
from v2.modules.auth_rbac.infrastructure.models import (
    Kullanici,
    KullaniciAyari,
    Rol,
)
from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
from v2.modules.auth_rbac.infrastructure.session_repository import SessionRepository
from v2.modules.auth_rbac.infrastructure.token_blacklist import (
    TokenBlacklist,
    blacklist,
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
    # roles (RBAC role CRUD — free functions, module import)
    "role_service",
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
    # FastAPI auth dependency factories (2026-07-22'de app/api/deps.py'den
    # taşındı — bkz. application/authenticate.py)
    "get_current_user",
    "get_current_active_user",
    "get_current_active_admin",
    "get_current_superadmin",
    "require_permissions",
    "TokenDep",
    # JWT / password hashing
    "jwt_handler",
    "get_decode_key",
    "hash_password",
    "get_jwks",
    # token blacklist
    "TokenBlacklist",
    "blacklist",
    # repositories
    "KullaniciRepository",
    "RolRepository",
    "SessionRepository",
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "Kullanici",
    "Rol",
    "KullaniciAyari",
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
