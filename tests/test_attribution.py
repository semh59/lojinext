from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.anomaly.application.attribute_loss import override_attribution


@pytest.mark.asyncio
async def test_attribution_override_publishes_event():
    """Verify attribution override publishes event."""
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={"id": 123, "arac_id": 1, "sofor_id": 1}
    )
    uow.sefer_repo.update = AsyncMock(return_value=True)
    uow.commit = AsyncMock()

    with patch(
        "v2.modules.anomaly.application.attribute_loss.get_event_bus"
    ) as mock_get_eb:
        mock_eb = MagicMock()
        mock_eb.publish_async = AsyncMock()
        mock_get_eb.return_value = mock_eb

        success = await override_attribution(123, 2, 2, "Reason", uow=uow)

    assert success is True
    uow.sefer_repo.update.assert_awaited_once_with(
        123, is_corrected=True, correction_reason="Reason", arac_id=2, sofor_id=2
    )
    mock_eb.publish_async.assert_awaited_once()
