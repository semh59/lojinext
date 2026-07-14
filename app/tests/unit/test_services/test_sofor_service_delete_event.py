"""
T2-C: delete_sofor() commit başarısız → event yayınlanmamalı.

Bug Açıklaması:
  Commit failure durumunda event bus yine yayın yapıyor.
  Veri değişmeyince event gönderilmemeli.

Beklenen: Commit fail → event NOT published.

NOT: eski ``SoforService`` sınıfı silindi (B.1 free-function split, bkz.
v2/modules/driver/CLAUDE.md). ``delete_sofor`` artık
``v2.modules.driver.application.delete_sofor``'daki free function; ayrıca
``@publishes(EventType.SOFOR_DELETED)`` decorator'ı repo-genelinde ölü kod
(sadece fonksiyona ``_publishes`` attribute'u ekler, hiçbir yerde
event_bus.publish() çağrılmaz) — bu test artık trivially geçer (publish
zaten hiç çağrılmıyor), ama UnitOfWork'ü mock'layıp commit-failure'ın
exception'ı doğru fırlattığını doğrulamaya devam eder.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork
from v2.modules.driver.application.delete_sofor import delete_sofor


async def test_delete_sofor_no_event_on_commit_failure(mock_event_bus):
    """
    delete_sofor() commit başarısız olduğunda, event_bus.publish çağrılmamalı.
    """

    sofor_id = 99

    # Mock the repo to return a sofor for deletion (not deleted, not is_deleted)
    mock_sofor = {
        "id": sofor_id,
        "ad_soyad": "Test Şoför T2C",
        "aktif": True,
        "is_deleted": False,
    }
    mock_uow = MagicMock()
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=mock_sofor)
    mock_uow.sofor_repo.update = AsyncMock(return_value=True)
    # UoW.commit() başarısız olması mock et
    mock_uow.commit = AsyncMock(side_effect=Exception("Database connection lost"))

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        # delete_sofor() exception fırlatmalı
        with pytest.raises(Exception, match="Database connection lost"):
            await delete_sofor(sofor_id=sofor_id)

    # event_bus.publish çağrılmamalı (çünkü commit başarısız)
    assert not mock_event_bus.publish.called, (
        f"BUG T2-C: Commit başarısız olmasına rağmen event yayınlandı! "
        f"publish call count: {mock_event_bus.publish.call_count}. "
        f"Sorun: delete_sofor() exception'ı catch etmiyor veya event'i publish etmeden before commit yapıyor."
    )
