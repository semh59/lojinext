"""Admin CRUD use-case'leri: `bildirim_kurallari` tablosu.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/notification_routes.py``'nin rule CRUD
handler'ları (``list_rules``/``create_rule``/``update_rule``/
``delete_rule``) daha önce ``application/`` katmanını atlayıp doğrudan
``uow.notification_repo``'yu çağırıyordu — modülün geri kalanı (get/mark/
mark_all) tutarlı biçimde ``application/``'a delege ederken bu 4 handler
etmiyordu. Mekanik taşıma, davranış değişikliği yok (repo çağrıları ve
commit sırası birebir korundu).
"""

from typing import Any, Dict, List, Optional

from app.database.models import BildirimKurali
from app.database.unit_of_work import UnitOfWork


async def list_rules() -> List[BildirimKurali]:
    """Admin: list every notification rule."""
    async with UnitOfWork() as uow:
        return await uow.notification_repo.get_all_rules()


async def create_rule(data: Dict[str, Any]) -> BildirimKurali:
    """Admin: create a new notification rule."""
    async with UnitOfWork() as uow:
        rule = await uow.notification_repo.create_rule(data)
        await uow.commit()
        return rule


async def update_rule(
    rule_id: int, changes: Dict[str, Any]
) -> Optional[BildirimKurali]:
    """Admin: partially update a notification rule (e.g. toggle aktif)."""
    async with UnitOfWork() as uow:
        rule = await uow.notification_repo.update_rule(rule_id, changes)
        if rule is not None:
            await uow.commit()
        return rule


async def delete_rule(rule_id: int) -> bool:
    """Admin: delete a notification rule."""
    async with UnitOfWork() as uow:
        deleted = await uow.notification_repo.delete_rule(rule_id)
        if deleted:
            await uow.commit()
        return deleted
