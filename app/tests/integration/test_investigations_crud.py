"""Feature B.2 — FuelInvestigation CRUD integration testleri."""

from datetime import date, datetime, timezone

import pytest


async def _seed_anomaly(
    db_session, *, sapma: float = 25.0, severity: str = "medium"
) -> int:
    from app.database.models import Anomaly

    row = Anomaly(
        tarih=date.today(),
        tip="tuketim",
        kaynak_tip="sefer",
        kaynak_id=1,
        deger=40.0,
        beklenen_deger=32.0,
        sapma_yuzde=sapma,
        severity=severity,
        aciklama="Test anomaly",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return int(row.id)


@pytest.mark.integration
@pytest.mark.asyncio
class TestInvestigationsCRUD:
    async def test_post_creates_investigation_with_classification(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session, sapma=30.0, severity="high")
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid, "initial_notes": "Şüpheli yakıt kaybı"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["anomaly_id"] == aid
        assert body["status"] == "open"
        assert body["suspicion_level"] in ("low", "medium", "high")
        assert body["suspicion_score"] is not None
        assert body["notes"] == "Şüpheli yakıt kaybı"
        assert body["evidence_files"] == []

    async def test_post_duplicate_anomaly_returns_409(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        resp1 = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        assert resp1.status_code == 201
        resp2 = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        assert resp2.status_code == 409

    async def test_post_unknown_anomaly_returns_404(
        self, async_client, admin_auth_headers
    ):
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": 999999},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404

    async def test_get_list_no_filter(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        resp = await async_client.get(
            "/api/v1/admin/investigations", headers=admin_auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert any(item["anomaly_id"] == aid for item in body)

    async def test_get_list_filter_status_open(
        self, async_client, admin_auth_headers, db_session
    ):
        a1 = await _seed_anomaly(db_session)
        await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": a1},
            headers=admin_auth_headers,
        )
        resp = await async_client.get(
            "/api/v1/admin/investigations?status=open",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        assert all(item["status"] == "open" for item in resp.json())

    async def test_get_single_join_fields(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        resp = await async_client.get(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == inv_id
        # JOIN field'ları mevcut (kaynak_tip='sefer' ama gerçek sefer yok → NULL)
        assert "plaka" in body
        assert "sofor_adi" in body
        assert body["sapma_yuzde"] is not None

    async def test_get_404_unknown_id(self, async_client, admin_auth_headers):
        resp = await async_client.get(
            "/api/v1/admin/investigations/99999", headers=admin_auth_headers
        )
        assert resp.status_code == 404

    async def test_patch_assigned_user_sets_status_assigned(
        self, async_client, admin_auth_headers, db_session
    ):
        """assigned_to_user_id verildiğinde status otomatik 'assigned' olur."""
        # FK için gerçek user seed et
        from sqlalchemy import select

        from app.database.models import Kullanici, Rol
        from v2.modules.auth_rbac.domain.security import get_password_hash

        rol = (
            await db_session.execute(select(Rol).where(Rol.ad == "izleyici"))
        ).scalar_one_or_none()
        if not rol:
            rol = Rol(ad="izleyici", yetkiler={"sefer:read": True})
            db_session.add(rol)
            await db_session.commit()
            await db_session.refresh(rol)
        u = Kullanici(
            email="theft-assignee@test.local",
            ad_soyad="Theft Assignee",
            rol_id=rol.id,
            sifre_hash=get_password_hash("x"),
            aktif=True,
        )
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        real_user_id = int(u.id)

        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        resp = await async_client.patch(
            f"/api/v1/admin/investigations/{inv_id}",
            json={"assigned_to_user_id": real_user_id},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["assigned_to_user_id"] == real_user_id
        assert body["status"] == "assigned"

    async def test_patch_resolution_type_auto_resolves(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        resp = await async_client.patch(
            f"/api/v1/admin/investigations/{inv_id}",
            json={
                "resolution_type": "real_theft",
                "notes": "Şoför itiraf etti",
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["resolution_type"] == "real_theft"
        assert body["status"] == "resolved"
        assert body["closed_at"] is not None

    async def test_patch_evidence_files_max_10(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        resp = await async_client.patch(
            f"/api/v1/admin/investigations/{inv_id}",
            json={"evidence_files": [f"/url/{i}.jpg" for i in range(11)]},
            headers=admin_auth_headers,
        )
        # Pydantic max_length=10 → 422
        assert resp.status_code == 422

    async def test_patch_after_closed_returns_409(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        # Önce kapat
        await async_client.delete(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        resp = await async_client.patch(
            f"/api/v1/admin/investigations/{inv_id}",
            json={"notes": "ek not"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 409

    async def test_delete_soft_closes(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        resp = await async_client.delete(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 204
        get_resp = await async_client.get(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        assert get_resp.json()["status"] == "closed"

    async def test_delete_idempotent_on_already_closed(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session)
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        await async_client.delete(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        # İkinci DELETE de 204
        resp = await async_client.delete(
            f"/api/v1/admin/investigations/{inv_id}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 204

    async def test_classify_endpoint_updates_suspicion(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_anomaly(db_session, sapma=10.0, severity="low")
        post_resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        inv_id = post_resp.json()["id"]
        initial_score = post_resp.json()["suspicion_score"]

        # Anomaly'nin severity'sini critical yap (DB direct)
        from sqlalchemy import update as _upd

        from app.database.models import Anomaly

        await db_session.execute(
            _upd(Anomaly)
            .where(Anomaly.id == aid)
            .values(severity="critical", sapma_yuzde=45.0)
        )
        await db_session.commit()

        resp = await async_client.post(
            f"/api/v1/admin/investigations/{inv_id}/classify",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        # Yeni suspicion eski'den büyük olmalı
        assert body["suspicion_score"] >= (initial_score or 0)

    async def test_503_when_feature_flag_off(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.THEFT_INVESTIGATION_ENABLED", False)
        resp = await async_client.get(
            "/api/v1/admin/investigations", headers=admin_auth_headers
        )
        assert resp.status_code == 503

    async def test_patterns_endpoint_returns_list(
        self, async_client, admin_auth_headers
    ):
        """Patterns endpoint çağrılır — boş bile olsa 200 + liste döner."""
        resp = await async_client.get(
            "/api/v1/admin/investigations/patterns?days=30&min_count=2",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
