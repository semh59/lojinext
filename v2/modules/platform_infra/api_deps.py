"""Per-request FastAPI dependency aliases (generic DI plumbing).

Sibling of ``container.py``: that file holds app-lifetime singleton
services (ML engine, AI/RAG, ...); this file holds the per-request
``AsyncSession``/``UnitOfWork`` dependency aliases that every module's own
request-scoped service factories build on top of.

2026-07-22 (Kalem 3 commit 2): taşındı ``app/api/deps.py``'den —
``SessionDep``/``UOWDep`` hiçbir zaman bir iş-modülüne ait değildi, yalnız
jenerik per-request DI alias'larıydı. ``get_background_job_manager``
(deps.py'nin bunları saran async wrapper'ı) bu taşımada SİLİNDİ — tüm
tüketiciler zaten yalnızca ``Depends(get_background_job_manager)`` sonra
``job_manager.submit(...)`` kalıbını izliyordu, bu da
``Depends(get_job_manager)`` (zaten ``public.py``'de export edilen senkron
fonksiyon) ile birebir aynı sonucu üretir — ekstra indirection'a gerek
yoktu.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.platform_infra.database.connection import get_db
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork, get_uow

SessionDep = Annotated[AsyncSession, Depends(get_db)]
UOWDep = Annotated[UnitOfWork, Depends(get_uow)]
