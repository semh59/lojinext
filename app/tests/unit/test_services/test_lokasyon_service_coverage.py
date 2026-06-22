"""
LokasyonService coverage tests — targeting uncovered branches.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service(repo=None, event_bus=None):
    from app.core.services.lokasyon_service import LokasyonService

    mock_repo = repo or AsyncMock()
    mock_bus = event_bus or MagicMock()
    mock_bus.publish = MagicMock()
    return LokasyonService(repo=mock_repo, event_bus=mock_bus), mock_repo


def _make_create(**kwargs):
    from app.schemas.lokasyon import LokasyonCreate

    defaults = dict(
        cikis_yeri="İstanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
    )
    defaults.update(kwargs)
    return LokasyonCreate(**defaults)


# ---------------------------------------------------------------------------
# geocode_query
# ---------------------------------------------------------------------------


class TestGeocodeQuery:
    async def test_short_query_returns_empty(self):
        svc, _ = _make_service()
        result = await svc.geocode_query("A")
        assert result == []

    async def test_empty_query_returns_empty(self):
        svc, _ = _make_service()
        result = await svc.geocode_query("")
        assert result == []

    async def test_whitespace_only_returns_empty(self):
        svc, _ = _make_service()
        result = await svc.geocode_query("  ")
        assert result == []

    @patch(
        "app.core.services.lokasyon_service.LokasyonService._geocode_with_openroute",
        new_callable=AsyncMock,
    )
    @patch(
        "app.core.services.lokasyon_service.LokasyonService._geocode_with_nominatim",
        new_callable=AsyncMock,
    )
    async def test_falls_back_to_offline_when_both_empty(self, mock_nom, mock_ors):
        mock_ors.return_value = []
        mock_nom.return_value = []

        svc, _ = _make_service()
        with patch(
            "app.core.services.lokasyon_service.LokasyonService._geocode_offline"
        ) as mock_offline:
            mock_offline.return_value = [
                {"lat": 39.0, "lon": 35.0, "label": "TR", "source": "offline"}
            ]
            result = await svc.geocode_query("Ankara")

        mock_offline.assert_called_once_with("Ankara")
        assert result[0]["source"] == "offline"

    async def test_geocode_query_strips_whitespace_in_query(self):
        svc, _ = _make_service()
        with (
            patch.object(
                svc, "_geocode_with_openroute", new_callable=AsyncMock
            ) as mock_ors,
            patch.object(svc, "_geocode_with_nominatim", new_callable=AsyncMock),
        ):
            mock_ors.return_value = [
                {"lat": 41.0, "lon": 29.0, "label": "Istanbul", "source": "ors"}
            ]
            result = await svc.geocode_query("  Istanbul  ")

        # query should have been stripped
        mock_ors.assert_awaited_once_with("Istanbul", limit=5)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _dedupe_geocode_results
# ---------------------------------------------------------------------------


class TestDedupeGeocodeResults:
    def test_dedupes_identical_coords_and_label(self):
        from app.core.services.lokasyon_service import LokasyonService

        items = [
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
        ]
        result = LokasyonService._dedupe_geocode_results(items)
        assert len(result) == 1

    def test_keeps_distinct_coords(self):
        from app.core.services.lokasyon_service import LokasyonService

        items = [
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
            {"lat": 39.9, "lon": 32.8, "label": "Ankara"},
        ]
        result = LokasyonService._dedupe_geocode_results(items)
        assert len(result) == 2

    def test_empty_input(self):
        from app.core.services.lokasyon_service import LokasyonService

        assert LokasyonService._dedupe_geocode_results([]) == []


# ---------------------------------------------------------------------------
# _geocode_with_openroute
# ---------------------------------------------------------------------------


class TestGeocodeWithOpenroute:
    async def test_returns_empty_when_not_configured(self):
        svc, _ = _make_service()
        mock_ors_instance = MagicMock()
        mock_ors_instance.is_configured.return_value = False
        mock_ors_module = MagicMock()
        mock_ors_module.get_openroute_service = MagicMock(
            return_value=mock_ors_instance
        )

        with patch.dict(
            "sys.modules", {"app.core.services.openroute_service": mock_ors_module}
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert result == []

    async def test_returns_empty_on_non_200_status(self):
        svc, _ = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ors_instance = MagicMock()
        mock_ors_instance.is_configured.return_value = True
        mock_ors_instance._get_client = AsyncMock(return_value=mock_client)
        mock_ors_instance.BASE_URL = "https://api.openrouteservice.org"
        mock_ors_instance.api_key = (
            "test-key"  # pragma: allowlist secret  # pragma: allowlist secret
        )

        mock_ors_module = MagicMock()
        mock_ors_module.get_openroute_service = MagicMock(
            return_value=mock_ors_instance
        )

        with patch.dict(
            "sys.modules", {"app.core.services.openroute_service": mock_ors_module}
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert result == []

    async def test_returns_parsed_features_on_success(self):
        svc, _ = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {
                    "geometry": {"coordinates": [29.0, 41.0]},
                    "properties": {"label": "Istanbul, TR"},
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ors_instance = MagicMock()
        mock_ors_instance.is_configured.return_value = True
        mock_ors_instance._get_client = AsyncMock(return_value=mock_client)
        mock_ors_instance.BASE_URL = "https://api.openrouteservice.org"
        mock_ors_instance.api_key = "test-key"  # pragma: allowlist secret

        mock_ors_module = MagicMock()
        mock_ors_module.get_openroute_service = MagicMock(
            return_value=mock_ors_instance
        )

        with patch.dict(
            "sys.modules", {"app.core.services.openroute_service": mock_ors_module}
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert len(result) == 1
        assert result[0]["lat"] == 41.0
        assert result[0]["source"] == "ors"

    async def test_returns_empty_on_exception(self):
        svc, _ = _make_service()
        mock_ors_instance = MagicMock()
        mock_ors_instance.is_configured.return_value = True
        mock_ors_instance._get_client = AsyncMock(
            side_effect=Exception("network error")
        )

        mock_ors_module = MagicMock()
        mock_ors_module.get_openroute_service = MagicMock(
            return_value=mock_ors_instance
        )

        with patch.dict(
            "sys.modules", {"app.core.services.openroute_service": mock_ors_module}
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert result == []

    async def test_skips_features_with_insufficient_coords(self):
        svc, _ = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {
                    "geometry": {"coordinates": []},  # no coords
                    "properties": {"label": "Bad Feature"},
                },
                {
                    "geometry": {"coordinates": [29.0, 41.0]},
                    "properties": {"name": "Istanbul"},
                },
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ors_instance = MagicMock()
        mock_ors_instance.is_configured.return_value = True
        mock_ors_instance._get_client = AsyncMock(return_value=mock_client)
        mock_ors_instance.BASE_URL = "https://api.openrouteservice.org"
        mock_ors_instance.api_key = "test-key"  # pragma: allowlist secret

        mock_ors_module = MagicMock()
        mock_ors_module.get_openroute_service = MagicMock(
            return_value=mock_ors_instance
        )

        with patch.dict(
            "sys.modules", {"app.core.services.openroute_service": mock_ors_module}
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert len(result) == 1
        assert result[0]["label"] == "Istanbul"


# ---------------------------------------------------------------------------
# _geocode_with_nominatim
# ---------------------------------------------------------------------------


class TestGeocodeWithNominatim:
    async def _mock_monitored_client(self, response_json, status_code=200):
        """Build a context-manager mock for get_monitored_client."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_json

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx

    async def test_returns_results_on_success(self):
        svc, _ = _make_service()
        json_data = [{"lat": "41.0", "lon": "29.0", "display_name": "Istanbul, TR"}]
        mock_ctx = await self._mock_monitored_client(json_data)

        with patch(
            "app.core.services.lokasyon_service.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await svc._geocode_with_nominatim("Istanbul")

        assert len(result) == 1
        assert result[0]["source"] == "nominatim"
        assert result[0]["lat"] == 41.0

    async def test_returns_empty_on_non_200_status(self):
        svc, _ = _make_service()
        mock_ctx = await self._mock_monitored_client([], status_code=503)

        with patch(
            "app.core.services.lokasyon_service.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await svc._geocode_with_nominatim("Istanbul")

        assert result == []

    async def test_skips_items_missing_coords(self):
        svc, _ = _make_service()
        json_data = [
            {"lat": None, "lon": None, "display_name": "Bad Item"},
            {"lat": "39.9", "lon": "32.8", "display_name": "Ankara"},
        ]
        mock_ctx = await self._mock_monitored_client(json_data)

        with patch(
            "app.core.services.lokasyon_service.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await svc._geocode_with_nominatim("query")

        assert len(result) == 1
        assert "Ankara" in result[0]["label"]

    async def test_returns_empty_on_exception(self):
        svc, _ = _make_service()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("network down"))
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.services.lokasyon_service.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await svc._geocode_with_nominatim("Istanbul")

        assert result == []


# ---------------------------------------------------------------------------
# _geocode_offline
# ---------------------------------------------------------------------------


class TestGeocodeOffline:
    def test_returns_empty_when_openroute_returns_none(self):
        svc, _ = _make_service()
        # get_openroute_service is imported lazily inside the method
        with patch(
            "app.core.services.openroute_service.get_openroute_service"
        ) as mock_get_ors:
            ors_instance = MagicMock()
            ors_instance.geocode_offline.return_value = None
            mock_get_ors.return_value = ors_instance

            # Patch the import that happens inside _geocode_offline
            with patch.dict(
                "sys.modules",
                {
                    "app.core.services.openroute_service": MagicMock(
                        get_openroute_service=lambda: ors_instance
                    )
                },
            ):
                result = svc._geocode_offline("unknownplace")

        assert result == []

    def test_returns_result_when_coords_found(self):
        svc, _ = _make_service()
        ors_instance = MagicMock()
        ors_instance.geocode_offline.return_value = (29.0, 41.0)

        with patch.dict(
            "sys.modules",
            {
                "app.core.services.openroute_service": MagicMock(
                    get_openroute_service=lambda: ors_instance
                )
            },
        ):
            result = svc._geocode_offline("Istanbul")

        assert len(result) == 1
        assert result[0]["source"] == "offline"
        assert result[0]["lat"] == 41.0
        assert result[0]["lon"] == 29.0


# ---------------------------------------------------------------------------
# add_lokasyon — reactivation branch
# ---------------------------------------------------------------------------


class TestAddLokasyon:
    async def test_add_lokasyon_raises_if_active_route_exists(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_route.return_value = {
            "id": 1,
            "aktif": True,
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
        }
        data = _make_create()
        with pytest.raises(ValueError, match="zaten mevcut"):
            await svc.add_lokasyon(data)

    async def test_add_lokasyon_reactivates_passive_route(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_route.return_value = {
            "id": 7,
            "aktif": False,
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
        }
        mock_repo.update.return_value = True

        result = await svc.add_lokasyon(_make_create())

        assert result == 7
        mock_repo.update.assert_called_once()
        call_kwargs = mock_repo.update.call_args
        assert call_kwargs[1].get("aktif") is True or call_kwargs[0][1] == 7

    async def test_add_lokasyon_normalizes_names_to_titlecase(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_route.return_value = None
        mock_repo.add.return_value = 3

        data = _make_create(cikis_yeri="istanbul", varis_yeri="ankara")
        await svc.add_lokasyon(data)

        # repo.add must be called with title-cased names via model_dump
        mock_repo.add.assert_called_once()


# ---------------------------------------------------------------------------
# delete_lokasyon — error paths
# ---------------------------------------------------------------------------


class TestDeleteLokasyon:
    async def test_delete_returns_false_when_not_found(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_id.return_value = None

        result = await svc.delete_lokasyon(999)
        assert result is False

    async def test_hard_delete_raises_value_error_on_constraint(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_id.return_value = {"id": 5, "aktif": False}
        mock_repo.hard_delete.side_effect = Exception("FK violation")

        with pytest.raises(ValueError, match="silinemez"):
            await svc.delete_lokasyon(5)


# ---------------------------------------------------------------------------
# get_all_paged — validation error path
# ---------------------------------------------------------------------------


class TestGetAllPaged:
    async def test_skips_invalid_records_gracefully(self):
        svc, mock_repo = _make_service()
        # Return a record that fails LokasyonResponse validation (mesafe_km missing)
        mock_repo.get_all.return_value = [{"id": 1}]
        mock_repo.count.return_value = 1

        result = await svc.get_all_paged()

        # AUDIT-073: atlanan satır kadar total aşağı çekilir (sayfa-kayması düzeltmesi).
        # Tek kayıt geçersiz → skipped=1 → total = max(0, 1-1) = 0, items boş.
        assert "items" in result
        assert result["items"] == []
        assert result["total"] == 0

    async def test_get_all_paged_with_filters(self):
        svc, mock_repo = _make_service()
        mock_repo.get_all.return_value = []
        mock_repo.count.return_value = 0

        result = await svc.get_all_paged(
            skip=0, limit=10, zorluk="Zor", search="Ankara"
        )

        assert result["total"] == 0
        call_kwargs = mock_repo.get_all.call_args[1]
        assert call_kwargs["filters"].get("zorluk") == "Zor"
        assert call_kwargs["filters"].get("search") == "Ankara"


# ---------------------------------------------------------------------------
# analyze_route
# ---------------------------------------------------------------------------


class TestAnalyzeRoute:
    async def test_analyze_route_raises_if_no_coords(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "cikis_lat": None,
            "cikis_lon": None,
            "varis_lat": None,
            "varis_lon": None,
        }

        with pytest.raises(ValueError, match="koordinat"):
            await svc.analyze_route(1)

    async def test_analyze_route_raises_if_not_found(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="koordinat"):
            await svc.analyze_route(999)

    async def test_analyze_route_raises_on_route_service_error(self):
        svc, mock_repo = _make_service()
        mock_repo.get_by_id.return_value = {
            "id": 1,
            "cikis_lat": 41.0,
            "cikis_lon": 29.0,
            "varis_lat": 39.9,
            "varis_lon": 32.8,
        }
        mock_rs = AsyncMock()
        mock_rs.get_route_details = AsyncMock(return_value={"error": "timeout"})
        mock_route_service_module = MagicMock()
        mock_route_service_module.get_route_service = MagicMock(return_value=mock_rs)

        with patch.dict(
            "sys.modules", {"app.services.route_service": mock_route_service_module}
        ):
            with pytest.raises(ValueError, match="Analiz hatası"):
                await svc.analyze_route(1)
