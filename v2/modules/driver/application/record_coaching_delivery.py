"""Use-case: koçluk mesajı gönderim kaydı (A.5 — etki ölçümü).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/coaching_routes.py::send_coaching`` daha önce
route içinde inline ``UnitOfWork`` açıp ``CoachingDelivery`` INSERT'ini
doğrudan çalıştırıyordu — mekanik taşıma, davranış değişikliği yok
(exception yutma/log davranışı birebir korundu).
"""

from typing import Optional

from v2.modules.driver.application.get_score import get_score_breakdown_sofor
from v2.modules.driver.infrastructure.models import CoachingDelivery
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def record_coaching_delivery(
    sofor_id: int,
    *,
    channel: str,
    insight_category: Optional[str],
    message: str,
    sent_by_user_id: Optional[int],
) -> Optional[int]:
    """``CoachingDelivery`` satırını ekler; başarısızlıkta ``None`` döner
    (akışı bloklamaz — audit log her koşulda yazılır, çağıran sorumlu).
    """
    try:
        async with UnitOfWork() as uow:
            score_snapshot = await get_score_breakdown_sofor(sofor_id, uow=uow)
            # Virtual super-admin id<=0 → DB'de kayıt yok; FK ihlali yaşamamak
            # için yalnız gerçek user id'yi yaz.
            safe_sent_by = sent_by_user_id
            if safe_sent_by is not None and safe_sent_by <= 0:
                safe_sent_by = None
            delivery = CoachingDelivery(
                sofor_id=sofor_id,
                score_before=float(score_snapshot.get("total") or 1.0),
                channel=channel,
                insight_category=insight_category,
                message_excerpt=message[:500],
                sent_by_user_id=safe_sent_by,
            )
            uow.session.add(delivery)
            await uow.session.flush()
            await uow.session.refresh(delivery)
            delivery_id = int(delivery.id)
            await uow.commit()
            return delivery_id
    except Exception as exc:
        # Audit kalır ama etki ölçümü kaybedilir — kullanıcı akışı bozulmasın.
        logger.warning("CoachingDelivery INSERT failed: %s", exc)
        return None
