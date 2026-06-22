"""Integration tests for POST /anomalies/{id}/acknowledge|/resolve."""

from datetime import date, datetime, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestAnomalyActions:
    async def _seed_anomaly(self, db_session) -> int:
        from app.database.models import Anomaly

        row = Anomaly(
            tarih=date.today(),
            tip="tuketim",
            kaynak_tip="sefer",
            kaynak_id=1,
            deger=45.0,
            beklenen_deger=32.0,
            sapma_yuzde=40.6,
            severity="high",
            aciklama="Test anomaly",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)
        return int(row.id)

    async def test_acknowledge_then_resolve_flow(
        self, async_client, admin_auth_headers, db_session
    ):
        anomaly_id = await self._seed_anomaly(db_session)

        ack = await async_client.post(
            f"/api/v1/anomalies/{anomaly_id}/acknowledge", headers=admin_auth_headers
        )
        assert ack.status_code == 200, ack.text
        ack_body = ack.json()
        assert ack_body["status"] == "acknowledged"
        assert ack_body["acknowledged_at"]

        resolve = await async_client.post(
            f"/api/v1/anomalies/{anomaly_id}/resolve",
            json={"notes": "Yakıt fişi eksikti, sahte alarm."},
            headers=admin_auth_headers,
        )
        assert resolve.status_code == 200, resolve.text
        resolve_body = resolve.json()
        assert resolve_body["status"] == "resolved"
        assert resolve_body["resolution_notes"] == "Yakıt fişi eksikti, sahte alarm."

    async def test_resolve_without_ack_auto_acks(
        self, async_client, admin_auth_headers, db_session
    ):
        """Direct resolve, otomatik acknowledge'lar (servis mantığı)."""
        anomaly_id = await self._seed_anomaly(db_session)

        resolve = await async_client.post(
            f"/api/v1/anomalies/{anomaly_id}/resolve",
            json={"notes": ""},
            headers=admin_auth_headers,
        )
        assert resolve.status_code == 200, resolve.text

        # status=resolved filter ile getirilmeli
        listed = await async_client.get(
            "/api/v1/anomalies/?status=resolved&days=2",
            headers=admin_auth_headers,
        )
        assert listed.status_code == 200, listed.text
        ids = [a["id"] for a in listed.json()["data"]["anomalies"]]
        assert anomaly_id in ids

    async def test_404_for_unknown_id(self, async_client, admin_auth_headers):
        resp = await async_client.post(
            "/api/v1/anomalies/999999/acknowledge", headers=admin_auth_headers
        )
        assert resp.status_code == 404

    async def test_status_filter_open(
        self, async_client, admin_auth_headers, db_session
    ):
        anomaly_id = await self._seed_anomaly(db_session)
        # Henüz acknowledge edilmedi → open
        resp = await async_client.get(
            "/api/v1/anomalies/?status=open&days=2", headers=admin_auth_headers
        )
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["data"]["anomalies"]]
        assert anomaly_id in ids
