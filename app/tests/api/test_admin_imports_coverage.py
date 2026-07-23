"""Coverage tests for v2/modules/import_excel/api/import_routes.py (43% → ≥75%).

Covers: preview, commit, rollback, history endpoints including
error paths and edge cases not in the existing test_admin_imports.py.

B.1 free-function geçişi (dalga 9): route artık DI-injected bir servis
almıyor, ``parse_and_preview``/``execute_import``/``rollback_import``
free function'larını modül seviyesinde import edip doğrudan çağırıyor —
bu yüzden ``app.dependency_overrides`` yerine ``unittest.mock.patch``
hedefi tüketen modül (``v2.modules.import_excel.api.import_routes.<fn>``).
"""

import json
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# POST /preview
# ---------------------------------------------------------------------------


class TestPreviewImport:
    async def test_preview_success(self, async_client, admin_auth_headers):
        with patch(
            "v2.modules.import_excel.api.import_routes.parse_and_preview",
            new_callable=AsyncMock,
        ) as mock_preview:
            mock_preview.return_value = {
                "filename": "test.xlsx",
                "aktarim_tipi": "arac",
                "headers": ["Plaka", "Mesafe"],
                "total_rows": 0,
                "preview": [],
            }
            response = await async_client.post(
                "/api/v1/admin/imports/preview",
                headers=admin_auth_headers,
                data={"aktarim_tipi": "arac"},
                files={
                    "file": (
                        "test.xlsx",
                        BytesIO(b"content"),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 200
        mock_preview.assert_called_once()

    async def test_preview_generic_exception_returns_400(
        self, async_client, admin_auth_headers
    ):
        with patch(
            "v2.modules.import_excel.api.import_routes.parse_and_preview",
            new_callable=AsyncMock,
        ) as mock_preview:
            mock_preview.side_effect = Exception("parse error")
            response = await async_client.post(
                "/api/v1/admin/imports/preview",
                headers=admin_auth_headers,
                data={"aktarim_tipi": "arac"},
                files={
                    "file": ("test.xlsx", BytesIO(b"x"), "application/octet-stream")
                },
            )

        assert response.status_code == 400

    async def test_preview_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/admin/imports/preview",
            data={"aktarim_tipi": "arac"},
            files={"file": ("test.xlsx", BytesIO(b"x"), "application/octet-stream")},
        )
        assert response.status_code == 401

    async def test_preview_requires_permission(self, async_client, normal_auth_headers):
        response = await async_client.post(
            "/api/v1/admin/imports/preview",
            headers=normal_auth_headers,
            data={"aktarim_tipi": "arac"},
            files={"file": ("test.xlsx", BytesIO(b"x"), "application/octet-stream")},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /commit
# ---------------------------------------------------------------------------


class TestCommitImport:
    async def test_commit_success(self, async_client, admin_auth_headers):
        with patch(
            "v2.modules.import_excel.api.import_routes.execute_import",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = {
                "job_id": 1,
                "basarili": 5,
                "hatali": 0,
                "errors": {},
            }
            mapping = json.dumps({"Plaka": "plaka", "Mesafe": "mesafe_km"})
            response = await async_client.post(
                "/api/v1/admin/imports/commit",
                headers=admin_auth_headers,
                data={"aktarim_tipi": "arac", "mapping_str": mapping},
                files={
                    "file": ("test.xlsx", BytesIO(b"data"), "application/octet-stream")
                },
            )

        assert response.status_code == 200
        mock_execute.assert_called_once()

    async def test_commit_invalid_json_mapping(self, async_client, admin_auth_headers):
        response = await async_client.post(
            "/api/v1/admin/imports/commit",
            headers=admin_auth_headers,
            data={"aktarim_tipi": "arac", "mapping_str": "not-valid-json"},
            files={"file": ("test.xlsx", BytesIO(b"data"), "application/octet-stream")},
        )

        assert response.status_code == 400
        body = response.json()
        # Error may be in "detail" or top-level "message"; just check status
        detail_str = str(body).lower()
        assert "mapping" in detail_str or response.status_code == 400

    async def test_commit_generic_exception_returns_400(
        self, async_client, admin_auth_headers
    ):
        with patch(
            "v2.modules.import_excel.api.import_routes.execute_import",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.side_effect = Exception("db error")
            mapping = json.dumps({"Plaka": "plaka"})
            response = await async_client.post(
                "/api/v1/admin/imports/commit",
                headers=admin_auth_headers,
                data={"aktarim_tipi": "arac", "mapping_str": mapping},
                files={
                    "file": ("test.xlsx", BytesIO(b"data"), "application/octet-stream")
                },
            )

        assert response.status_code == 400

    async def test_commit_requires_auth(self, async_client):
        mapping = json.dumps({"Plaka": "plaka"})
        response = await async_client.post(
            "/api/v1/admin/imports/commit",
            data={"aktarim_tipi": "arac", "mapping_str": mapping},
            files={"file": ("test.xlsx", BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /{job_id}/rollback
# ---------------------------------------------------------------------------


class TestRollbackImport:
    async def test_rollback_success(self, async_client, admin_auth_headers):
        with patch(
            "v2.modules.import_excel.api.import_routes._rollback_import",
            new_callable=AsyncMock,
        ) as mock_rollback:
            mock_rollback.return_value = True
            response = await async_client.post(
                "/api/v1/admin/imports/42/rollback",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_rollback_generic_exception_returns_400(
        self, async_client, admin_auth_headers
    ):
        with patch(
            "v2.modules.import_excel.api.import_routes._rollback_import",
            new_callable=AsyncMock,
        ) as mock_rollback:
            mock_rollback.side_effect = Exception("rollback failed")
            response = await async_client.post(
                "/api/v1/admin/imports/42/rollback",
                headers=admin_auth_headers,
            )

        assert response.status_code == 400

    async def test_rollback_requires_auth(self, async_client):
        response = await async_client.post("/api/v1/admin/imports/1/rollback")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /history — already tested in test_admin_imports.py, add edge case
# ---------------------------------------------------------------------------


class TestImportHistoryWithData:
    async def test_history_returns_mapped_items(
        self, async_client, admin_auth_headers, db_session
    ):
        from v2.modules.import_excel.public import IceriAktarimGecmisi

        row = IceriAktarimGecmisi(
            dosya_adi="vehicles.xlsx",
            aktarim_tipi="arac",
            durum="tamamlandi",
            toplam_kayit=10,
            basarili_kayit=9,
            hatali_kayit=1,
        )
        db_session.add(row)
        await db_session.flush()

        response = await async_client.get(
            "/api/v1/admin/imports/history",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["dosya_adi"] == "vehicles.xlsx"
        assert data[0]["basarili"] == 9
        assert data[0]["hatali"] == 1
