"""Activity-log wiring — core CRUD endpoints must invoke the audit helper.

The audit layer itself (log_audit_event -> _persist_audit_to_db -> admin_audit_log)
is unit-tested in test_audit_db_persist.py. Asserting the persisted row from the
test session is unreliable (the audit insert runs on its own session/transaction,
invisible to the request session's snapshot), so here we patch the helper as it is
imported into the endpoint module and assert the handler awaits it with the right
action/module — i.e. that the wiring exists end-to-end through the real request.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


async def test_vehicle_create_and_delete_invoke_activity_log(
    async_client, admin_auth_headers
):
    """POST + DELETE /vehicles must each await log_audit_event for module 'arac'."""
    payload = {
        "plaka": "34ACT99",
        "marka": "MAN",
        "model": "TGX",
        "yil": 2023,
        "tank_kapasitesi": 450,
        "hedef_tuketim": 30.0,
        "aktif": True,
    }

    with patch(
        "v2.modules.fleet.api.vehicle_routes.log_audit_event", new_callable=AsyncMock
    ) as mock_audit:
        resp = await async_client.post(
            "/api/v1/vehicles/", json=payload, headers=admin_auth_headers
        )
        assert resp.status_code == 201, resp.text
        arac_id = resp.json()["id"]

        del_resp = await async_client.delete(
            f"/api/v1/vehicles/{arac_id}", headers=admin_auth_headers
        )
        assert del_resp.status_code == 200, del_resp.text

    calls = mock_audit.await_args_list
    actions = [c.kwargs.get("action") for c in calls]
    modules = {c.kwargs.get("module") for c in calls}

    assert "create" in actions, f"create not audited; calls={actions}"
    assert "delete" in actions, f"delete not audited; calls={actions}"
    assert modules == {"arac"}, f"unexpected audit modules: {modules}"
