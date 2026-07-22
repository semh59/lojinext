"""Per-request FastAPI dependency factory for the trip module (transitional).

2026-07-22 (Kalem 3 commit 1): auth-specific factories (``get_current_user``,
``get_current_active_user``, ``get_current_active_admin``,
``get_current_superadmin``, ``require_permissions``, ``TokenDep``) taşındı
``v2/modules/auth_rbac/application/authenticate.py``'ye — artık
``v2.modules.auth_rbac.public``'ten import edilirler.

2026-07-22 (Kalem 3 commit 2): jenerik DI alias'ları (``SessionDep``,
``UOWDep``) taşındı ``v2/modules/platform_infra/api_deps.py``'ye (artık
``v2.modules.platform_infra.public``'ten import edilirler) —
``container.py``'nin per-request ikizi olarak orada yaşıyorlar.
``get_background_job_manager`` bu taşımada tamamen SİLİNDİ — tüm
tüketiciler ``v2.modules.platform_infra.public.get_job_manager``'ı
doğrudan ``Depends()`` ile kullanacak şekilde güncellendi (ekstra bir
async wrapper'a gerek yoktu).

Yalnız ``get_sefer_service`` kaldı — request-scoped
(``SeferService(repo=uow.sefer_repo)``), ``trip.public``'in argümansız,
container-tabanlı ``get_sefer_service()``'inden TAMAMEN FARKLI bir şey
(bkz. aşağıdaki "iki katmanlı DI mimarisi" notu). Kalem 3'ün commit
3'ünde ``trip`` modülüne çakışmayan bir adla taşınacak, bu dosya (ve
``app/api/v1/api.py``) o commit'te tamamen silinecek.

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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v2.modules.trip.application.trip_service import SeferService

from v2.modules.platform_infra.public import UOWDep


async def get_sefer_service(uow: UOWDep) -> "SeferService":
    from v2.modules.trip.application.trip_service import SeferService

    return SeferService(repo=uow.sefer_repo)
