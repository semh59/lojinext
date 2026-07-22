"""Per-request FastAPI dependency factories (generic DI plumbing).

2026-07-22 (Kalem 3 commit 1): auth-specific factories (``get_current_user``,
``get_current_active_user``, ``get_current_active_admin``,
``get_current_superadmin``, ``require_permissions``, ``TokenDep``) taşındı
``v2/modules/auth_rbac/application/authenticate.py``'ye — bunlar hiçbir
zaman gerçekten bu dosyaya ait değildi, yalnızca
``auth_rbac.domain.permission_checker``'ın bu dosyayı import etmesinden
doğan bir döngü onları burada tutuyordu (dosya v2/modules/ dışında
kaldığı için). Artık `v2.modules.auth_rbac.public`'ten import edilirler.

Kalan semboller (``SessionDep``/``UOWDep``/``get_background_job_manager``/
``get_sefer_service``) de jenerik/tekil-modül-dışı DI alias'ları — bunlar
da Kalem 3'ün sonraki commit'lerinde ``platform_infra``/``trip``'e
taşınacak (bkz. plan). Bu dosya o taşımalar tamamlanana kadar geçiş
durumunda.

─── DI Mimarisi — iki katmanlı ─────────────────────────────────────────────
1. ``app/api/deps.py`` (bu dosya)
   • UnitOfWork aracılığıyla transaction-scoped servis örnekleri oluşturur.
   • Her istek için yeni bir servis örneği üretilir; UoW commit/rollback
     garantisi request lifecycle'ına bağlıdır.
   • Kullanım alanı: domain CRUD endpoint'leri (araç, şoför, sefer, yakıt…)

2. ``v2/modules/platform_infra/container.py``
   • Uygulama ömrü boyunca yaşayan singleton servisler tutar
     (ML motoru, AI/RAG, anomali dedektörü, hava durumu vb.).
   • UoW gerektirmeyen, durumsuz (stateless) veya pahalı başlangıç
     maliyeti olan servisler buraya aittir.
   • Endpoint'lerin doğrudan bu container'a bağlanması GEREKMEYİP
     yalnızca ``container.py`` içindeki property'ler aracılığıyla erişilir.

Kural: Transactional domain servisleri için bu modülü kullan;
       ML/AI/infrastructure singleton'ları için container'ı kullan.
────────────────────────────────────────────────────────────────────────────
"""

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

if TYPE_CHECKING:
    from v2.modules.trip.application.trip_service import SeferService
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.platform_infra.background.job_manager import (
    BackgroundJobManager,
    get_job_manager,
)
from v2.modules.platform_infra.database.connection import get_db
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork, get_uow

SessionDep = Annotated[AsyncSession, Depends(get_db)]
UOWDep = Annotated[UnitOfWork, Depends(get_uow)]


async def get_background_job_manager() -> BackgroundJobManager:
    return get_job_manager()


async def get_sefer_service(uow: UOWDep) -> "SeferService":
    from v2.modules.trip.application.trip_service import SeferService

    return SeferService(repo=uow.sefer_repo)
