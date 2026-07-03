"""
LokasyonService coverage tests — targeting uncovered branches.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 0-mock epiği CTO denetimi (bağımsız ajan) buldu: bu dosya c05e9a4'te
# TestAddLokasyon/TestDeleteLokasyon/TestGetAllPaged/TestAnalyzeRoute (9 test)
# gerçek db_session'a çevrildi ama modül marker'ı unit'te kalmıştı — sibling
# dosyalar (test_lokasyon_service.py, test_lokasyon_service_more.py) doğru
# şekilde integration işaretliydi, bu dosya atlanmıştı. `pytest -m unit`
# TEST_DATABASE_URL olmadan koşulunca 9 test RuntimeError ile patlıyordu.
pytestmark = pytest.mark.integration


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
    """0-mock epiği: gerçek OpenRouteService singleton'ı gerçek api_stub'a
    (Faz 0/1) işaret eder — sys.modules/httpx mock'u değil."""

    def _real_ors(self, configured: bool = True):
        from app.core.services.openroute_service import OpenRouteService

        ors = OpenRouteService(api_key="test-key")
        ors.base_url = "http://localhost:9000/v2"
        if not configured:
            # __init__ falls back to settings.OPENROUTESERVICE_API_KEY when
            # api_key=None is passed — override directly to force "not
            # configured" regardless of the real env's key.
            ors.api_key = None
        return ors

    async def test_returns_empty_when_not_configured(self):
        svc, _ = _make_service()
        ors = self._real_ors(configured=False)

        with patch(
            "app.core.services.openroute_service.get_openroute_service",
            return_value=ors,
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert result == []

    async def test_returns_empty_on_non_200_status(self):
        svc, _ = _make_service()
        ors = self._real_ors()

        with patch(
            "app.core.services.openroute_service.get_openroute_service",
            return_value=ors,
        ):
            # __ERROR401__ sentinel (bkz. api_stub/main.py) gerçek 401 döner.
            result = await svc._geocode_with_openroute("__ERROR401__")

        assert result == []

    async def test_returns_parsed_features_on_success(self):
        svc, _ = _make_service()
        ors = self._real_ors()

        with patch(
            "app.core.services.openroute_service.get_openroute_service",
            return_value=ors,
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert len(result) == 1
        # api_stub'ın deterministik canned response'u.
        assert result[0]["lat"] == pytest.approx(39.93, abs=0.01)
        assert result[0]["source"] == "ors"

    async def test_returns_empty_on_exception(self):
        svc, _ = _make_service()
        ors = self._real_ors()
        ors.base_url = "http://localhost:1/v2"  # gerçek bağlantı hatası

        with patch(
            "app.core.services.openroute_service.get_openroute_service",
            return_value=ors,
        ):
            result = await svc._geocode_with_openroute("Istanbul")

        assert result == []

    async def test_skips_features_with_insufficient_coords(self):
        """__MULTI_ONE_BAD__ sentinel iki feature döner, biri koordinatsız —
        gerçek stub'a karşı, mock değil."""
        svc, _ = _make_service()
        ors = self._real_ors()

        with patch(
            "app.core.services.openroute_service.get_openroute_service",
            return_value=ors,
        ):
            result = await svc._geocode_with_openroute("__MULTI_ONE_BAD__")

        assert len(result) == 1
        assert result[0]["label"] == "Istanbul"


# ---------------------------------------------------------------------------
# _geocode_with_nominatim
# ---------------------------------------------------------------------------


class TestGeocodeWithNominatim:
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
    """0-mock epiği: geocode_offline gerçek bir haversine/hardcoded-şehir
    lookup'u (ağ/DB yok) — gerçek OpenRouteService instance'ı kullanılır."""

    def test_returns_empty_when_openroute_returns_none(self):
        svc, _ = _make_service()
        result = svc._geocode_offline("unknownplace-xyz")
        assert result == []

    def test_returns_result_when_coords_found(self):
        svc, _ = _make_service()
        result = svc._geocode_offline("Istanbul")

        assert len(result) == 1
        assert result[0]["source"] == "offline"
        # Gerçek OpenRouteService.geocode_offline'ın hardcoded değeri.
        assert result[0]["lat"] == pytest.approx(41.0082, abs=0.01)
        assert result[0]["lon"] == pytest.approx(28.9784, abs=0.01)


# ---------------------------------------------------------------------------
# add_lokasyon — reactivation branch
# ---------------------------------------------------------------------------


class TestAddLokasyon:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    def _real_service(self, db_session):
        from app.database.repositories.lokasyon_repo import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        return _make_service(repo=repo)[0]

    async def test_add_lokasyon_raises_if_active_route_exists(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(
            db_session, cikis_yeri="İstanbul", varis_yeri="Ankara", aktif=True
        )
        await db_session.commit()

        svc = self._real_service(db_session)
        data = _make_create()
        with pytest.raises(ValueError, match="zaten mevcut"):
            await svc.add_lokasyon(data)

    async def test_add_lokasyon_reactivates_passive_route(self, db_session):
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="İstanbul", varis_yeri="Ankara", aktif=False
        )
        await db_session.commit()

        svc = self._real_service(db_session)
        result = await svc.add_lokasyon(_make_create())

        assert result == lokasyon.id
        row = (
            await db_session.execute(
                text("SELECT aktif FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row.aktif is True

    async def test_add_lokasyon_normalizes_names_to_titlecase(self, db_session):
        from sqlalchemy import text

        svc = self._real_service(db_session)
        data = _make_create(cikis_yeri="istanbul", varis_yeri="ankara")
        lokasyon_id = await svc.add_lokasyon(data)

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
# delete_lokasyon — error paths
# ---------------------------------------------------------------------------


class TestDeleteLokasyon:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    async def test_delete_returns_false_when_not_found(self, db_session):
        from app.database.repositories.lokasyon_repo import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        svc, _ = _make_service(repo=repo)

        result = await svc.delete_lokasyon(999999)
        assert result is False

    async def test_hard_delete_raises_value_error_on_constraint(self, db_session):
        """FK ihlali (başka bir tablo bu lokasyon'a referans veriyor) →
        gerçek DB IntegrityError'ı ValueError'a çevrilir."""
        from app.database.repositories.lokasyon_repo import LokasyonRepository
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
        svc, _ = _make_service(repo=repo)

        with pytest.raises(ValueError, match="silinemez"):
            await svc.delete_lokasyon(lokasyon.id)


# ---------------------------------------------------------------------------
# get_all_paged — validation error path
# ---------------------------------------------------------------------------


class TestGetAllPaged:
    """0-mock epiği: gerçek LokasyonRepository + gerçek DB (db_session)."""

    async def test_skips_invalid_records_gracefully(self, db_session):
        """AUDIT-073: LokasyonResponse validasyonunu geçemeyen bir satır
        atlanır, total buna göre düşer.

        Gerçek DB kolonu `mesafe_km` NOT NULL ama >0 CHECK constraint'i YOK
        (sadece Sefer.mesafe_km'de var, models.py:556) — Pydantic şeması ise
        `gt=0` zorunlu kılıyor (schemas/lokasyon.py:15). Bu, DB'nin izin
        verdiği ama response şemasının reddettiği GERÇEK bir tutarsızlık;
        mesafe_km=0 seed edilerek bire bir üretiliyor (mock değil)."""
        from app.database.repositories.lokasyon_repo import LokasyonRepository
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B", mesafe_km=0)
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        svc, _ = _make_service(repo=repo)
        result = await svc.get_all_paged()

        # AUDIT-073: atlanan satır kadar total aşağı çekilir (sayfa-kayması düzeltmesi).
        assert result["items"] == []
        assert result["total"] == 0

    async def test_get_all_paged_with_filters(self, db_session):
        from app.database.repositories.lokasyon_repo import LokasyonRepository
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(
            db_session, cikis_yeri="Ankara", varis_yeri="Konya", zorluk="Zor"
        )
        await seed_lokasyon(
            db_session, cikis_yeri="Bursa", varis_yeri="Izmir", zorluk="Normal"
        )
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        svc, _ = _make_service(repo=repo)
        result = await svc.get_all_paged(
            skip=0, limit=10, zorluk="Zor", search="Ankara"
        )

        assert result["total"] == 1


# ---------------------------------------------------------------------------
# analyze_route
# ---------------------------------------------------------------------------


class TestAnalyzeRoute:
    """0-mock epiği: ilk iki test gerçek DB'ye (db_session) çevrildi."""

    async def test_analyze_route_raises_if_no_coords(self, db_session):
        from app.database.repositories.lokasyon_repo import LokasyonRepository
        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        svc, _ = _make_service(repo=repo)

        with pytest.raises(ValueError, match="koordinat"):
            await svc.analyze_route(lokasyon.id)

    async def test_analyze_route_raises_if_not_found(self, db_session):
        from app.database.repositories.lokasyon_repo import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        svc, _ = _make_service(repo=repo)

        with pytest.raises(ValueError, match="koordinat"):
            await svc.analyze_route(999999)

    async def test_analyze_route_raises_on_route_service_error(self):
        """DOKÜMANTE İSTİSNA: route_service (app.services.route_service) ayrı
        bir domain — Faz 1'in ilerideki 'route_service*' diliminde ayrıca
        gerçek stub'a çevrilecek. Burada sadece bu servisin hata-yayma
        davranışı (analyze_route'un ValueError'a çevirmesi) test ediliyor."""
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
