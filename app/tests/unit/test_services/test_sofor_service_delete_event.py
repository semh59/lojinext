"""
T2-C: sofor_service.delete_sofor() commit başarısız → event yayınlanmamalı.

Bug Açıklaması:
  Commit failure durumunda event bus yine yayın yapıyor.
  Veri değişmeyince event gönderilmemeli.

Beklenen: Commit fail → event NOT published.
"""

import pytest


async def test_delete_sofor_no_event_on_commit_failure(
    sofor_service_with_mock_event_bus, mock_event_bus, mock_sofor_service_uow
):
    """
    sofor_service.delete_sofor() commit başarısız olduğunda,
    event_bus.publish çağrılmamalı.
    """

    sofor_id = 99

    # Mock the repo to return a sofor for deletion (not deleted, not is_deleted)
    mock_sofor = {
        "id": sofor_id,
        "ad_soyad": "Test Şoför T2C",
        "aktif": True,
        "is_deleted": False,
    }
    mock_sofor_service_uow.sofor_repo.get_by_id.return_value = mock_sofor

    # Mock the update to return success
    mock_sofor_service_uow.sofor_repo.update.return_value = True

    # UoW.commit() başarısız olması mock et
    mock_sofor_service_uow.commit.side_effect = Exception("Database connection lost")

    # delete_sofor() exception fırlatmalı
    with pytest.raises(Exception, match="Database connection lost"):
        await sofor_service_with_mock_event_bus.delete_sofor(sofor_id=sofor_id)

    # event_bus.publish çağrılmamalı (çünkü commit başarısız)
    assert not mock_event_bus.publish.called, (
        f"BUG T2-C: Commit başarısız olmasına rağmen event yayınlandı! "
        f"publish call count: {mock_event_bus.publish.call_count}. "
        f"Sorun: delete_sofor() exception'ı catch etmiyor veya event'i publish etmeden before commit yapıyor."
    )
