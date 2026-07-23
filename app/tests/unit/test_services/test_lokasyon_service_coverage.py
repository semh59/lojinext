"""
Location use-case coverage tests — targeting uncovered branches.

v2 rebuild: LokasyonService sınıfı yok, her use-case standalone fonksiyon
(bkz. v2/modules/location/public.py docstring'i).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.location.application.analyze_location_route import (
    analyze_location_route,
)
from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.geocode_location import geocode_location
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.infrastructure.geocode_providers import (
    dedupe_geocode_results,
    geocode_via_offline,
    geocode_via_openroute,
)
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonCreate

# 0-mock epiği CTO denetimi (bağımsız ajan) buldu: bu dosya c05e9a4'te
# TestAddLokasyon/TestDeleteLokasyon/TestGetAllPaged/TestAnalyzeRoute (9 test)
# gerçek db_session'a çevrildi ama modül marker'ı unit'te kalmıştı — sibling
# dosyalar (test_lokasyon_service.py, test_lokasyon_service_more.py) doğru
# şekilde integration işaretliydi, bu dosya atlanmıştı. `pytest -m unit`
# TEST_DATABASE_URL olmadan koşulunca 9 test RuntimeError ile patlıyordu.
pytestmark = pytest.mark.integration


def _make_create(**kwargs):
    defaults = dict(
        cikis_yeri="İstanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
    )
    defaults.update(kwargs)
    return LokasyonCreate(**defaults)


# ---------------------------------------------------------------------------
# geocode_location
# ---------------------------------------------------------------------------


class TestGeocodeLocation:
    async def test_short_query_returns_empty(self):
        result = await geocode_location("A")
        assert result == []

    async def test_empty_query_returns_empty(self):
        result = await geocode_location("")
        assert result == []

    async def test_whitespace_only_returns_empty(self):
        result = await geocode_location("  ")
        assert result == []

    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_openroute",
        new_callable=AsyncMock,
    )
    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_nominatim",
        new_callable=AsyncMock,
    )
    async def test_falls_back_to_offline_when_both_empty(self, mock_nom, mock_ors):
        mock_ors.return_value = []
        mock_nom.return_value = []

        with patch(
            "v2.modules.location.application.geocode_location.geocode_via_offline"
        ) as mock_offline:
            mock_offline.return_value = [
                {"lat": 39.0, "lon": 35.0, "label": "TR", "source": "offline"}
            ]
            result = await geocode_location("Ankara")

        mock_offline.assert_called_once_with("Ankara")
        assert result[0]["source"] == "offline"

    async def test_geocode_location_strips_whitespace_in_query(self):
        with (
            patch(
                "v2.modules.location.application.geocode_location.geocode_via_openroute",
                new_callable=AsyncMock,
            ) as mock_ors,
            patch(
                "v2.modules.location.application.geocode_location.geocode_via_nominatim",
                new_callable=AsyncMock,
            ),
        ):
            mock_ors.return_value = [
                {"lat": 41.0, "lon": 29.0, "label": "Istanbul", "source": "ors"}
            ]
            result = await geocode_location("  Istanbul  ")

        # query should have been stripped
        mock_ors.assert_awaited_once_with("Istanbul", limit=5)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# dedupe_geocode_results
# ---------------------------------------------------------------------------


class TestDedupeGeocodeResults:
    def test_dedupes_identical_coords_and_label(self):
        items = [
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
        ]
        result = dedupe_geocode_results(items)
        assert len(result) == 1

    def test_keeps_distinct_coords(self):
        items = [
            {"lat": 41.0, "lon": 29.0, "label": "Istanbul"},
            {"lat": 39.9, "lon": 32.8, "label": "Ankara"},
        ]
        result = dedupe_geocode_results(items)
        assert len(result) == 2

    def test_empty_input(self):
        assert dedupe_geocode_results([]) == []


# ---------------------------------------------------------------------------
# geocode_via_openroute
# ---------------------------------------------------------------------------


class TestGeocodeViaOpenroute:
    """0-mock epiği: gerçek OpenRouteService singleton'ı gerçek api_stub'a
    (Faz 0/1) işaret eder — sys.modules/httpx mock'u değil."""

    def _real_ors(self, configured: bool = True):
        from v2.modules.location.infrastructure.openroute_geocode_client import (
            OpenRouteService,
        )

        ors = OpenRouteService(api_key="test-key")
        ors.base_url = "http://localhost:9000/v2"
        if not configured:
            # __init__ falls back to settings.OPENROUTESERVICE_API_KEY when
            # api_key=None is passed — override directly to force "not
            # configured" regardless of the real env's key.
            ors.api_key = None
        return ors

    async def test_returns_empty_when_not_configured(self):
        ors = self._real_ors(configured=False)

        with patch(
            "v2.modules.location.infrastructure.openroute_geocode_client.get_openroute_service",
            return_value=ors,
        ):
            result = await geocode_via_openroute("Istanbul")

        assert result == []

    async def test_returns_empty_on_non_200_status(self):
        ors = self._real_ors()

        with patch(
            "v2.modules.location.infrastructure.openroute_geocode_client.get_openroute_service",
            return_value=ors,
        ):
            # __ERROR401__ sentinel (bkz. api_stub/main.py) gerçek 401 döner.
            result = await geocode_via_openroute("__ERROR401__")

        assert result == []

    async def test_returns_parsed_features_on_success(self):
        ors = self._real_ors()

        with patch(
            "v2.modules.location.infrastructure.openroute_geocode_client.get_openroute_service",
            return_value=ors,
        ):
            result = await geocode_via_openroute("Istanbul")

        assert len(result) == 1
        # api_stub'ın deterministik canned response'u.
        assert result[0]["lat"] == pytest.approx(39.93, abs=0.01)
        assert result[0]["source"] == "ors"

    async def test_returns_empty_on_exception(self):
        ors = self._real_ors()
        ors.base_url = "http://localhost:1/v2"  # gerçek bağlantı hatası

        with patch(
            "v2.modules.location.infrastructure.openroute_geocode_client.get_openroute_service",
            return_value=ors,
        ):
            result = await geocode_via_openroute("Istanbul")

        assert result == []

    async def test_skips_features_with_insufficient_coords(self):
        """__MULTI_ONE_BAD__ sentinel iki feature döner, biri koordinatsız —
        gerçek stub'a karşı, mock değil."""
        ors = self._real_ors()

        with patch(
            "v2.modules.location.infrastructure.openroute_geocode_client.get_openroute_service",
            return_value=ors,
        ):
            result = await geocode_via_openroute("__MULTI_ONE_BAD__")

        assert len(result) == 1
        assert result[0]["label"] == "Istanbul"


# ---------------------------------------------------------------------------
# geocode_via_nominatim
# ---------------------------------------------------------------------------


class TestGeocodeViaNominatim:
    """DOKÜMANTE BACKLOG: Nominatim (nominatim.openstreetmap.org) hardcoded,
    settings'ten override edilebilir değil (Faz 0 sadece Mapbox/OpenRoute/
    Open-Meteo/Telegram/Groq'u kapsadı) — bu üçüncü-parti sınır bu turun
    kapsamı dışında, mock'lu kalıyor. Gelecek bir dilimde stub'a eklenebilir."""

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
        from v2.modules.location.infrastructure.geocode_providers import (
            geocode_via_nominatim,
        )

        json_data = [{"lat": "41.0", "lon": "29.0", "display_name": "Istanbul, TR"}]
        mock_ctx = await self._mock_monitored_client(json_data)

        with patch(
            "v2.modules.location.infrastructure.geocode_providers.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await geocode_via_nominatim("Istanbul")

        assert len(result) == 1
        assert result[0]["source"] == "nominatim"
        assert result[0]["lat"] == 41.0

    async def test_returns_empty_on_non_200_status(self):
        from v2.modules.location.infrastructure.geocode_providers import (
            geocode_via_nominatim,
        )

        mock_ctx = await self._mock_monitored_client([], status_code=503)

        with patch(
            "v2.modules.location.infrastructure.geocode_providers.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await geocode_via_nominatim("Istanbul")

        assert result == []

    async def test_skips_items_missing_coords(self):
        from v2.modules.location.infrastructure.geocode_providers import (
            geocode_via_nominatim,
        )

        json_data = [
            {"lat": None, "lon": None, "display_name": "Bad Item"},
            {"lat": "39.9", "lon": "32.8", "display_name": "Ankara"},
        ]
        mock_ctx = await self._mock_monitored_client(json_data)

        with patch(
            "v2.modules.location.infrastructure.geocode_providers.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await geocode_via_nominatim("query")

        assert len(result) == 1
        assert "Ankara" in result[0]["label"]

    async def test_returns_empty_on_exception(self):
        from v2.modules.location.infrastructure.geocode_providers import (
            geocode_via_nominatim,
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("network down"))
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "v2.modules.location.infrastructure.geocode_providers.get_monitored_client",
            return_value=mock_ctx,
        ):
            result = await geocode_via_nominatim("Istanbul")

        assert result == []


# ---------------------------------------------------------------------------
# geocode_via_offline
# ---------------------------------------------------------------------------


class TestGeocodeViaOffline:
    """0-mock epiği: geocode_offline gerçek bir haversine/hardcoded-şehir
    lookup'u (ağ/DB yok) — gerçek OpenRouteService instance'ı kullanılır."""

    def test_returns_empty_when_openroute_returns_none(self):
        result = geocode_via_offline("unknownplace-xyz")
        assert result == []

    def test_returns_result_when_coords_found(self):
        result = geocode_via_offline("Istanbul")

        assert len(result) == 1
        assert result[0]["source"] == "offline"
        # Gerçek OpenRouteService.geocode_offline'ın hardcoded değeri.
        assert result[0]["lat"] == pytest.approx(41.0082, abs=0.01)
        assert result[0]["lon"] == pytest.approx(28.9784, abs=0.01)


# ---------------------------------------------------------------------------
# create_location — reactivation branch
# ---------------------------------------------------------------------------


class TestCreateLocation:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    async def test_create_location_raises_if_active_route_exists(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(
            db_session, cikis_yeri="İstanbul", varis_yeri="Ankara", aktif=True
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        data = _make_create()
        with pytest.raises(ValueError, match="zaten mevcut"):
            await create_location(repo, data)

    async def test_create_location_reactivates_passive_route(self, db_session):
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="İstanbul", varis_yeri="Ankara", aktif=False
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await create_location(repo, _make_create())

        assert result == lokasyon.id
        row = (
            await db_session.execute(
                text("SELECT aktif FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row.aktif is True

    async def test_create_location_normalizes_names_to_titlecase(self, db_session):
        from sqlalchemy import text

        repo = LokasyonRepository(session=db_session)
        data = _make_create(cikis_yeri="istanbul", varis_yeri="ankara")
        lokasyon_id = await create_location(repo, data)

        row = (
            await db_session.execute(
                text("SELECT cikis_yeri, varis_yeri FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon_id},
            )
        ).fetchone()
        # Türkçe-doğru title-case: baştaki 'i' -> dotted capital 'İ'.
        assert row.cikis_yeri == "İstanbul"
        assert row.varis_yeri == "Ankara"


# ---------------------------------------------------------------------------
# delete_location — error paths
# ---------------------------------------------------------------------------


class TestDeleteLocation:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    async def test_delete_returns_false_when_not_found(self, db_session):
        repo = LokasyonRepository(session=db_session)

        result = await delete_location(repo, 999999)
        assert result is False

    async def test_hard_delete_raises_value_error_on_constraint(self, db_session):
        """FK ihlali (başka bir tablo bu lokasyon'a referans veriyor) →
        gerçek DB IntegrityError'ı ValueError'a çevrilir."""
        from app.tests._helpers.seed import (
            seed_arac,
            seed_lokasyon,
            seed_sefer,
            seed_sofor,
        )

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="A", varis_yeri="B", aktif=False
        )
        arac = await seed_arac(db_session)
        sofor = await seed_sofor(db_session)
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            guzergah_id=lokasyon.id,
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)

        with pytest.raises(ValueError, match="silinemez"):
            await delete_location(repo, lokasyon.id)


# ---------------------------------------------------------------------------
# list_locations — validation error path
# ---------------------------------------------------------------------------


class TestListLocations:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    async def test_skips_invalid_records_gracefully(self, db_session):
        """AUDIT-073: LokasyonResponse validasyonunu geçemeyen bir satır
        atlanır, total buna göre düşer.

        Gerçek DB kolonu `mesafe_km` NOT NULL ama >0 CHECK constraint'i YOK
        (sadece Sefer.mesafe_km'de var, models.py:556) — Pydantic şeması ise
        `gt=0` zorunlu kılıyor (v2/modules/location/schemas.py). Bu, DB'nin
        izin verdiği ama response şemasının reddettiği GERÇEK bir
        tutarsızlık; mesafe_km=0 seed edilerek bire bir üretiliyor (mock
        değil)."""
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B", mesafe_km=0)
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await list_locations(repo)

        # AUDIT-073: atlanan satır kadar total aşağı çekilir (sayfa-kayması düzeltmesi).
        assert result["items"] == []
        assert result["total"] == 0

    async def test_list_locations_with_filters(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(
            db_session, cikis_yeri="Ankara", varis_yeri="Konya", zorluk="Zor"
        )
        await seed_lokasyon(
            db_session, cikis_yeri="Bursa", varis_yeri="Izmir", zorluk="Normal"
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await list_locations(
            repo, skip=0, limit=10, zorluk="Zor", search="Ankara"
        )

        assert result["total"] == 1


# ---------------------------------------------------------------------------
# analyze_location_route
# ---------------------------------------------------------------------------


class TestAnalyzeLocationRoute:
    """0-mock epiği: ilk iki test gerçek DB'ye (db_session) çevrildi."""

    async def test_analyze_raises_if_no_coords(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)

        with pytest.raises(ValueError, match="koordinat"):
            await analyze_location_route(repo, lokasyon.id)

    async def test_analyze_raises_if_not_found(self, db_session):
        repo = LokasyonRepository(session=db_session)

        with pytest.raises(ValueError, match="koordinat"):
            await analyze_location_route(repo, 999999)

    async def test_analyze_raises_on_route_service_error(self, db_session):
        """DOKÜMANTE İSTİSNA: route_service (route_simulation modülü) ayrı
        bir domain — o modülün kendi test dilimi ayrıca gerçek stub'a
        çevrilecek. Burada sadece bu servisin hata-yayma davranışı
        (analyze_location_route'un ValueError'a çevirmesi) test ediliyor."""
        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session,
            cikis_yeri="A",
            varis_yeri="B",
            cikis_lat=41.0,
            cikis_lon=29.0,
            varis_lat=39.9,
            varis_lon=32.8,
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)

        mock_route_service_module = MagicMock()
        mock_route_service_module.get_route_details = AsyncMock(
            return_value={"error": "timeout"}
        )

        with patch.dict(
            "sys.modules",
            {
                "v2.modules.route_simulation.application.get_route_details": (
                    mock_route_service_module
                )
            },
        ):
            with pytest.raises(ValueError, match="Analiz hatası"):
                await analyze_location_route(repo, lokasyon.id)
