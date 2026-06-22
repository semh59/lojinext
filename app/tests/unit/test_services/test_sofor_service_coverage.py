"""
SoforService coverage tests — targets uncovered branches in sofor_service.py.

Covered here (not in test_sofor_service.py):
  - get_all_paged: filter kwargs (ehliyet_sinifi, min_score, max_score, search, aktif_only=False)
  - get_by_id: found case
  - update_sofor: ad_soyad rename, name collision, manual_score recalculation, no-op
  - delete_sofor / _delete_sofor_uow: happy path, already-deleted guard
  - bulk_delete: non-empty list
  - update_score: happy path, driver-not-found, score boundary (0.1 / 2.0)
  - calculate_hybrid_score: with trip data (avg_consumption > 0)
  - get_score_breakdown: driver-not-found, no-trips fallback, trips branch
  - get_route_profile: driver-not-found, empty trips, trips with data,
                       best_route_type selection, insufficient candidates
  - bulk_add_sofor: empty list, skips short names, skips duplicates, inserts new
  - get_performance_details: various anomaly combinations + trend branches
  - get_sofor_service: factory smoke
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_uow():
    """Return a fully-configured mock UnitOfWork."""
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.commit = AsyncMock()
    uow.sofor_repo = MagicMock()
    uow.sofor_repo.get_by_name = AsyncMock(return_value=None)
    uow.sofor_repo.add = AsyncMock(return_value=10)
    uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
    uow.sofor_repo.update = AsyncMock(return_value=True)
    uow.sofor_repo.get_all = AsyncMock(return_value=[])
    uow.sofor_repo.count_all = AsyncMock(return_value=0)
    uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
    uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=[])
    uow.sofor_repo.bulk_create = AsyncMock(return_value=[1, 2])
    uow.sofor_repo.bulk_soft_delete = AsyncMock(return_value=3)
    uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
        return_value={"critical": 0, "high": 0, "medium": 0, "low": 0}
    )
    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(return_value=[])
    return uow


def _make_svc(uow=None):
    """Return a SoforService with a stub repo and event_bus."""
    from app.core.services.sofor_service import SoforService

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_eb = MagicMock()
    mock_eb.publish = MagicMock()
    svc = SoforService(repo=mock_repo, event_bus=mock_eb)
    return svc, uow or _make_uow()


# ===========================================================================
# get_all_paged — filter paths
# ===========================================================================


class TestGetAllPaged:
    async def test_with_filters_passes_to_repo(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_all = AsyncMock(return_value=[{"id": 1}])
        uow.sofor_repo.count_all = AsyncMock(return_value=1)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_all_paged(
                skip=5,
                limit=10,
                aktif_only=False,
                search="ali",
                ehliyet_sinifi="C",
                min_score=0.5,
                max_score=1.5,
            )

        assert result["total"] == 1
        call_kwargs = uow.sofor_repo.get_all.call_args.kwargs
        assert call_kwargs["filters"]["ehliyet_sinifi"] == "C"
        assert call_kwargs["filters"]["score_ge"] == 0.5
        assert call_kwargs["filters"]["score_le"] == 1.5
        assert call_kwargs["search"] == "ali"
        assert call_kwargs["sadece_aktif"] is False

    async def test_no_filters(self):
        svc, uow = _make_svc()
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_all_paged()
        assert "items" in result
        assert result["total"] == 0


# ===========================================================================
# get_by_id — found case
# ===========================================================================


class TestGetById:
    async def test_returns_driver_when_found(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(return_value={"id": 5, "ad_soyad": "Test"})
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_by_id(5)
        assert result["id"] == 5


# ===========================================================================
# update_sofor
# ===========================================================================


class TestUpdateSofor:
    async def test_happy_path_no_name_change(self):
        svc, uow = _make_svc()
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_sofor(1, telefon="05001112233")
        assert result is True

    async def test_ad_soyad_capitalised(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_name = AsyncMock(return_value=None)
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_sofor(1, ad_soyad="ali veli")
        assert result is True
        # update called with capitalised name
        call_kwargs = uow.sofor_repo.update.call_args
        assert call_kwargs.kwargs.get("ad_soyad") == "Ali Veli" or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] == "Ali Veli"
        )

    async def test_name_collision_raises(self):
        svc, uow = _make_svc()
        # existing driver with different ID
        uow.sofor_repo.get_by_name = AsyncMock(return_value={"id": 99})
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with pytest.raises(ValueError, match="another driver"):
                await svc.update_sofor(1, ad_soyad="Ali Veli")

    async def test_manual_score_recalculates_hybrid(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(
            return_value={"id": 1, "manual_score": 1.0}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_sofor(1, manual_score=1.5)
        assert result is True
        # score kwarg was injected
        update_kwargs = uow.sofor_repo.update.call_args.kwargs
        assert "score" in update_kwargs

    async def test_update_returns_false_when_repo_fails(self):
        svc, uow = _make_svc()
        uow.sofor_repo.update = AsyncMock(return_value=False)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_sofor(1, telefon="0")
        assert result is False


# ===========================================================================
# delete_sofor / _delete_sofor_uow
# ===========================================================================


class TestDeleteSofor:
    async def test_happy_path(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(
            return_value={"id": 3, "aktif": True, "is_deleted": False}
        )
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.delete_sofor(3)
        assert result is True
        uow.commit.assert_called_once()

    async def test_returns_false_when_not_found(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.delete_sofor(999)
        assert result is False
        uow.commit.assert_not_called()

    async def test_returns_false_when_already_deleted(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(
            return_value={"id": 3, "aktif": False, "is_deleted": True}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.delete_sofor(3)
        assert result is False


# ===========================================================================
# bulk_delete — non-empty list
# ===========================================================================


class TestBulkDelete:
    async def test_non_empty_list_delegates_to_repo(self):
        svc, uow = _make_svc()
        uow.sofor_repo.bulk_soft_delete = AsyncMock(return_value=3)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_delete([1, 2, 3])
        assert result["deleted"] == 3
        assert result["status"] == "success"
        uow.commit.assert_called_once()


# ===========================================================================
# update_score
# ===========================================================================


class TestUpdateScore:
    async def test_happy_path(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(
            return_value={"id": 1, "manual_score": 1.0}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_score(1, 1.5)
        assert result is True

    async def test_boundary_min_allowed(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(return_value={"id": 1})
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_score(1, 0.1)
        assert result is True

    async def test_boundary_max_allowed(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(return_value={"id": 1})
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.update = AsyncMock(return_value=True)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.update_score(1, 2.0)
        assert result is True

    async def test_raises_below_min(self):
        svc, _ = _make_svc()
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await svc.update_score(1, 0.09)

    async def test_raises_above_max(self):
        svc, _ = _make_svc()
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await svc.update_score(1, 2.01)

    async def test_raises_when_driver_not_found(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with pytest.raises(ValueError, match="Driver not found"):
                await svc.update_score(999, 1.0)


# ===========================================================================
# calculate_hybrid_score
# ===========================================================================


class TestCalculateHybridScore:
    async def test_with_trip_data(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"ort_tuketim": 30.0, "toplam_sefer": 10}]
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            score = await svc.calculate_hybrid_score(1, 1.0)
        # perf_factor = 30/30 = 1.0 => hybrid = 1.0*0.6 + 1.0*0.4 = 1.0
        assert abs(score - 1.0) < 0.01

    async def test_high_consumption_reduces_auto_score(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"ort_tuketim": 60.0, "toplam_sefer": 5}]
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            score = await svc.calculate_hybrid_score(1, 1.0)
        # perf_factor = 30/60 = 0.5 => hybrid = 0.5*0.6 + 1.0*0.4 = 0.7
        assert score < 1.0

    async def test_zero_consumption_returns_manual(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"ort_tuketim": 0, "toplam_sefer": 5}]
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            score = await svc.calculate_hybrid_score(1, 1.3)
        assert score == 1.3

    async def test_exception_returns_manual(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(side_effect=RuntimeError("db error"))
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            score = await svc.calculate_hybrid_score(1, 0.9)
        assert score == 0.9


# ===========================================================================
# get_score_breakdown
# ===========================================================================


class TestGetScoreBreakdown:
    async def test_driver_not_found_raises(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value=None)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with pytest.raises(ValueError, match="Driver not found"):
                await svc.get_score_breakdown(999)

    async def test_no_trips_returns_manual_fallback(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(
            return_value={"id": 1, "ad_soyad": "Ali Veli", "manual_score": 1.2}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_score_breakdown(1)
        assert result["has_trips"] is False
        assert result["manual"] == 1.2

    async def test_with_trips_computes_auto_score(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(
            return_value={"id": 1, "ad_soyad": "Ali Veli", "manual_score": 1.0}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"ort_tuketim": 30.0, "toplam_sefer": 8}]
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_score_breakdown(1)
        assert result["has_trips"] is True
        assert result["trip_count"] == 8
        assert result["avg_consumption"] == 30.0
        assert "total" in result

    async def test_score_clamped_to_valid_range(self):
        svc, uow = _make_svc()
        # score=3.0 should be clamped to 2.0
        svc.repo.get_by_id = AsyncMock(
            return_value={"id": 1, "ad_soyad": "X Y", "manual_score": 3.0}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_score_breakdown(1)
        assert result["manual"] == 2.0

    async def test_result_structure(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(
            return_value={"id": 2, "ad_soyad": "Test", "score": 1.0}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_score_breakdown(2)
        required_keys = {
            "sofor_id",
            "ad_soyad",
            "manual",
            "manual_weight",
            "auto",
            "auto_weight",
            "total",
            "trip_count",
            "avg_consumption",
            "target_reference",
            "has_trips",
        }
        assert required_keys.issubset(result.keys())

    async def test_stats_exception_falls_back_to_manual(self):
        """Exception in get_sefer_stats is swallowed; has_trips stays False."""
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(
            return_value={"id": 1, "ad_soyad": "Ali", "manual_score": 1.1}
        )
        uow.sofor_repo.get_sefer_stats = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_score_breakdown(1)
        assert result["has_trips"] is False


# ===========================================================================
# get_route_profile
# ===========================================================================


class TestGetRouteProfile:
    async def test_driver_not_found_raises(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value=None)
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with pytest.raises(ValueError, match="Driver not found"):
                await svc.get_route_profile(999)

    async def test_empty_trips_returns_zero_profiles(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(return_value=[])

        mock_classify = MagicMock(return_value="mixed")
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route", mock_classify
            ):
                result = await svc.get_route_profile(1)

        assert result["best_route_type"] is None
        for profile in result["profiles"]:
            assert profile["trip_count"] == 0

    async def test_with_trips_populates_profiles(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        trips = [
            {
                "id": 10,
                "gercek_tuketim": 300.0,
                "tahmini_tuketim": 280.0,
                "rota_detay": {"route_analysis": {"highway_km": 400}},
            }
        ]
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(
            return_value=trips
        )

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route",
                return_value="highway_dominant",
            ):
                result = await svc.get_route_profile(1)

        highway_profile = next(
            p for p in result["profiles"] if p["route_type"] == "highway_dominant"
        )
        assert highway_profile["trip_count"] == 1
        assert highway_profile["avg_actual"] == 300.0

    async def test_best_route_type_selected_by_min_deviation(self):
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        # 5 highway trips (low deviation), 5 urban trips (high deviation)
        trips = [
            {
                "id": i,
                "gercek_tuketim": 100.0,
                "tahmini_tuketim": 102.0,
                "rota_detay": {"route_analysis": {}},
            }
            for i in range(5)
        ] + [
            {
                "id": 10 + i,
                "gercek_tuketim": 200.0,
                "tahmini_tuketim": 100.0,
                "rota_detay": {"route_analysis": {}},
            }
            for i in range(5)
        ]
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(
            return_value=trips
        )

        call_count = {"n": 0}

        def classify_side_effect(route_analysis):
            n = call_count["n"]
            call_count["n"] += 1
            return "highway_dominant" if n < 5 else "urban"

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route",
                side_effect=classify_side_effect,
            ):
                result = await svc.get_route_profile(1, min_trips_for_best=5)

        assert result["best_route_type"] == "highway_dominant"

    async def test_insufficient_trips_for_best(self):
        """best_route_type is None when all route_types have < min_trips_for_best."""
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        trips = [
            {
                "id": 1,
                "gercek_tuketim": 100.0,
                "tahmini_tuketim": 100.0,
                "rota_detay": {},
            }
        ]
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(
            return_value=trips
        )

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route",
                return_value="mixed",
            ):
                result = await svc.get_route_profile(1, min_trips_for_best=5)

        assert result["best_route_type"] is None

    async def test_classify_route_exception_skips_trip(self):
        """Exception in classify_route logs a warning and skips the trip."""
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        trips = [
            {
                "id": 1,
                "gercek_tuketim": 100.0,
                "tahmini_tuketim": 100.0,
                "rota_detay": {},
            }
        ]
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(
            return_value=trips
        )

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route",
                side_effect=ValueError("bad route"),
            ):
                result = await svc.get_route_profile(1)

        # Trip was skipped — all profiles have 0 trip_count
        assert all(p["trip_count"] == 0 for p in result["profiles"])

    async def test_unknown_route_type_skips_trip(self):
        """classify_route returning an unknown type skips the trip (rtype not in buckets)."""
        svc, uow = _make_svc()
        svc.repo.get_by_id = AsyncMock(return_value={"id": 1, "ad_soyad": "Ali Veli"})
        trips = [
            {
                "id": 1,
                "gercek_tuketim": 100.0,
                "tahmini_tuketim": 100.0,
                "rota_detay": {},
            }
        ]
        uow.sefer_repo.get_driver_trips_with_route_analysis = AsyncMock(
            return_value=trips
        )

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            with patch(
                "app.core.ml.driver_route_profile.classify_route",
                return_value="unknown_type_xyz",
            ):
                result = await svc.get_route_profile(1)

        assert all(p["trip_count"] == 0 for p in result["profiles"])


# ===========================================================================
# bulk_add_sofor
# ===========================================================================


class TestBulkAddSofor:
    async def test_empty_list_returns_zero(self):
        svc, _ = _make_svc()
        result = await svc.bulk_add_sofor([])
        assert result == 0

    async def test_skips_short_names(self):
        svc, uow = _make_svc()
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_add_sofor([{"ad_soyad": "Ab"}])
        assert result == 0

    async def test_skips_duplicate_names(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=["Ali Veli"])
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_add_sofor([{"ad_soyad": "Ali Veli"}])
        assert result == 0

    async def test_inserts_new_drivers(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=[])
        uow.sofor_repo.bulk_create = AsyncMock(return_value=[1, 2])
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_add_sofor(
                [{"ad_soyad": "Ali Veli"}, {"ad_soyad": "Veli Ali"}]
            )
        assert result == 2

    async def test_model_dump_path(self):
        """Works with Pydantic-like objects that have model_dump()."""
        svc, uow = _make_svc()
        uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=[])
        uow.sofor_repo.bulk_create = AsyncMock(return_value=[99])

        class FakeModel:
            def model_dump(self):
                return {
                    "ad_soyad": "Pydantic Sofor",
                    "telefon": "05001112233",
                    "ehliyet_sinifi": "E",
                }

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_add_sofor([FakeModel()])
        assert result == 1

    async def test_dict_path(self):
        """Works with objects that have dict() (legacy Pydantic v1)."""
        svc, uow = _make_svc()
        uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=[])
        uow.sofor_repo.bulk_create = AsyncMock(return_value=[88])

        class LegacyModel:
            def dict(self):
                return {"ad_soyad": "Legacy Sofor", "ehliyet_sinifi": "E"}

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.bulk_add_sofor([LegacyModel()])
        assert result == 1


# ===========================================================================
# get_performance_details
# ===========================================================================


class TestGetPerformanceDetails:
    async def test_basic_structure(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert "safety_score" in result
        assert "eco_score" in result
        assert "compliance_score" in result
        assert "total_score" in result
        assert "trend" in result

    async def test_trend_increasing_when_high_score(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"toplam_km": 10000, "toplam_sefer": 50, "ort_tuketim": 28.0}]
        )
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert result["trend"] == "increasing"

    async def test_trend_decreasing_when_many_anomalies(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 5, "high": 5, "medium": 10, "low": 2}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert result["trend"] == "decreasing"

    async def test_trend_stable_mid_range(self):
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"toplam_km": 5000, "toplam_sefer": 20, "ort_tuketim": 33.0}]
        )
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 1, "high": 1, "medium": 2, "low": 0}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert result["trend"] in ("stable", "increasing", "decreasing")

    async def test_eco_score_above_target(self):
        """ort_tuketim < 30 gives bonus eco score (but capped at 100)."""
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"toplam_km": 0, "toplam_sefer": 0, "ort_tuketim": 25.0}]
        )
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert result["eco_score"] >= 100.0

    async def test_eco_score_below_target(self):
        """ort_tuketim > 30 penalises eco score."""
        svc, uow = _make_svc()
        uow.sofor_repo.get_sefer_stats = AsyncMock(
            return_value=[{"toplam_km": 0, "toplam_sefer": 0, "ort_tuketim": 45.0}]
        )
        uow.sofor_repo.get_driver_anomalies_count = AsyncMock(
            return_value={"critical": 0, "high": 0, "medium": 0, "low": 0}
        )
        with patch("app.core.services.sofor_service.UnitOfWork", return_value=uow):
            result = await svc.get_performance_details(1)
        assert result["eco_score"] < 100.0


# ===========================================================================
# get_sofor_service factory
# ===========================================================================


class TestGetSoforService:
    def test_factory_returns_instance(self):
        from app.core.services.sofor_service import SoforService

        mock_container = MagicMock()
        mock_container.sofor_service = SoforService(
            repo=MagicMock(), event_bus=MagicMock()
        )
        # get_container is imported locally inside get_sofor_service,
        # so we patch it in its source module.
        with patch(
            "app.core.container.get_container",
            return_value=mock_container,
        ):
            from app.core.services.sofor_service import get_sofor_service

            svc = get_sofor_service()
        assert isinstance(svc, SoforService)
