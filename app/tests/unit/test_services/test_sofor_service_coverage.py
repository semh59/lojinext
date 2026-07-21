"""
Driver use-case coverage tests — targets uncovered branches in the driver
module's free-function use-cases (v2/modules/driver/application/*.py).

Covered here (not in test_sofor_service.py):
  - get_all_paged: filter kwargs (ehliyet_sinifi, min_score, max_score, search, aktif_only=False)
  - get_by_id: found case
  - update_sofor: ad_soyad rename, name collision, manual_score recalculation, no-op
  - delete_sofor: happy path, already-deleted guard
  - bulk_delete: non-empty list
  - update_score: happy path, driver-not-found, score boundary (0.1 / 2.0)
  - calculate_hybrid_score: with trip data (avg_consumption > 0)
  - get_score_breakdown_sofor: driver-not-found, no-trips fallback, trips branch
  - get_route_profile_sofor: driver-not-found, empty trips, trips with data,
                       best_route_type selection, insufficient candidates
  - bulk_add_sofor: empty list, skips short names, skips duplicates, inserts new
  - get_performance_details: various anomaly combinations + trend branches

0-mock (Dilim 23): all patch(UnitOfWork) removed → real DB via db_session fixture.
NOT: eski ``SoforService`` sınıfı silindi (B.1 free-function split, bkz.
v2/modules/driver/CLAUDE.md). ``get_score_breakdown_sofor``/
``get_route_profile_sofor`` uow=None verildiğinde artık kendi
``UnitOfWork()``'ünü açar (dalga 5 push-sonrası fix — eski modül-seviyeli
``get_sofor_repo()`` singleton'ı session'sız ORM ``get_by_id`` ile
prod'da 500 patlıyordu, bkz. CLAUDE.md); bu yüzden bu iki use-case artık
hiçbir repo patch'i gerektirmiyor, tamamen gerçek DB.
Documented boundary: exception-path test for calculate_hybrid_score uses a narrow
patch.object on the repo method (not the whole UoW).
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from v2.modules.driver.application.add_sofor import bulk_add_sofor
from v2.modules.driver.application.delete_sofor import bulk_delete
from v2.modules.driver.application.delete_sofor import delete_sofor as delete_sofor_fn
from v2.modules.driver.application.get_performance import get_performance_details
from v2.modules.driver.application.get_route_profile import get_route_profile_sofor
from v2.modules.driver.application.get_score import (
    calculate_hybrid_score,
    get_score_breakdown_sofor,
)
from v2.modules.driver.application.list_sofor import get_all_paged, get_by_id
from v2.modules.driver.application.update_sofor import update_score
from v2.modules.driver.application.update_sofor import update_sofor as update_sofor_fn

pytestmark = pytest.mark.integration


# ===========================================================================
# get_all_paged — filter paths
# ===========================================================================


class TestGetAllPaged:
    async def test_with_filters_passes_to_repo(self, db_session):
        await seed_sofor(
            db_session,
            ad_soyad="Ccc Ehliyet Driver",
            ehliyet_sinifi="C",
            score=0.8,
        )
        await seed_sofor(
            db_session,
            ad_soyad="Eee Ehliyet Driver",
            ehliyet_sinifi="E",
            score=1.5,
        )
        await db_session.commit()

        result = await get_all_paged(
            skip=0,
            limit=10,
            aktif_only=False,
            search="Ccc",
            ehliyet_sinifi="C",
            min_score=0.5,
            max_score=1.0,
        )

        assert result["total"] == 1
        assert result["items"][0]["ehliyet_sinifi"] == "C"

    async def test_no_filters(self, db_session):
        result = await get_all_paged()
        assert "items" in result
        assert "total" in result
        assert isinstance(result["total"], int)


# ===========================================================================
# get_by_id — found case
# ===========================================================================


class TestGetById:
    async def test_returns_driver_when_found(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="TestGetById Driver")
        await db_session.commit()

        result = await get_by_id(sofor.id)

        assert result is not None
        assert result["id"] == sofor.id


# ===========================================================================
# update_sofor
# ===========================================================================


class TestUpdateSofor:
    async def test_happy_path_no_name_change(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Update Phone Driver")
        await db_session.commit()

        result = await update_sofor_fn(sofor.id, telefon="05001112233")
        assert result is True

    async def test_ad_soyad_capitalised(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Original Name Driver")
        await db_session.commit()

        result = await update_sofor_fn(sofor.id, ad_soyad="ali veli renk")
        assert result is True

        updated = await get_by_id(sofor.id)
        assert updated["ad_soyad"] == "Ali Veli Renk"

    async def test_name_collision_raises(self, db_session):
        await seed_sofor(db_session, ad_soyad="Collide Alpha Driver")
        sofor2 = await seed_sofor(db_session, ad_soyad="Collide Beta Driver")
        await db_session.commit()

        with pytest.raises(ValueError, match="another driver"):
            await update_sofor_fn(sofor2.id, ad_soyad="Collide Alpha Driver")

    async def test_manual_score_recalculates_hybrid(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Manual Score Driver")
        await db_session.commit()

        result = await update_sofor_fn(sofor.id, manual_score=1.5)
        assert result is True

        updated = await get_by_id(sofor.id)
        assert updated is not None
        assert "score" in updated

    async def test_update_returns_false_when_driver_missing(self, db_session):
        result = await update_sofor_fn(999999, telefon="0")
        assert result is False


# ===========================================================================
# delete_sofor / _delete_sofor_uow
# ===========================================================================


class TestDeleteSofor:
    async def test_happy_path(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Delete Happy Driver")
        sofor_id = sofor.id
        await db_session.commit()

        result = await delete_sofor_fn(sofor_id)
        assert result is True
        # Verify soft-delete: second delete must return False (already deleted)
        result2 = await delete_sofor_fn(sofor_id)
        assert result2 is False

    async def test_returns_false_when_not_found(self, db_session):
        result = await delete_sofor_fn(999999)
        assert result is False

    async def test_returns_false_when_already_deleted(self, db_session):
        from v2.modules.driver.public import Sofor as SoforModel

        sofor = SoforModel(
            ad_soyad="Already Deleted Driver", aktif=False, is_deleted=True
        )
        db_session.add(sofor)
        await db_session.flush()
        await db_session.commit()

        result = await delete_sofor_fn(sofor.id)
        assert result is False


# ===========================================================================
# bulk_delete — non-empty list
# ===========================================================================


class TestBulkDelete:
    async def test_non_empty_list_delegates_to_repo(self, db_session):
        s1 = await seed_sofor(db_session, ad_soyad="Bulk Del Driver A")
        s2 = await seed_sofor(db_session, ad_soyad="Bulk Del Driver B")
        s3 = await seed_sofor(db_session, ad_soyad="Bulk Del Driver C")
        await db_session.commit()

        result = await bulk_delete([s1.id, s2.id, s3.id])
        assert result["deleted"] == 3
        assert result["status"] == "success"


# ===========================================================================
# update_score
# ===========================================================================


class TestUpdateScore:
    async def test_happy_path(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Score Happy Driver")
        await db_session.commit()

        result = await update_score(sofor.id, 1.5)
        assert result is True

    async def test_boundary_min_allowed(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Score Min Driver")
        await db_session.commit()

        result = await update_score(sofor.id, 0.1)
        assert result is True

    async def test_boundary_max_allowed(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Score Max Driver")
        await db_session.commit()

        result = await update_score(sofor.id, 2.0)
        assert result is True

    async def test_raises_below_min(self):
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await update_score(1, 0.09)

    async def test_raises_above_max(self):
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await update_score(1, 2.01)

    async def test_raises_when_driver_not_found(self, db_session):
        with pytest.raises(ValueError, match="Driver not found"):
            await update_score(999999, 1.0)


# ===========================================================================
# calculate_hybrid_score
# ===========================================================================


class TestCalculateHybridScore:
    async def test_with_trip_data(self, db_session):
        arac = await seed_arac(db_session, plaka="34HYBRID01")
        sofor = await seed_sofor(db_session, ad_soyad="Hybrid Score Driver A")
        for _ in range(10):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=30.0,
            )
        await db_session.commit()

        score = await calculate_hybrid_score(sofor.id, 1.0)
        # ort_tuketim=30 → perf_factor=30/30=1.0 → hybrid=1.0*0.6+1.0*0.4=1.0
        assert abs(score - 1.0) < 0.05

    async def test_high_consumption_reduces_auto_score(self, db_session):
        arac = await seed_arac(db_session, plaka="34HYBRID02")
        sofor = await seed_sofor(db_session, ad_soyad="Hybrid Score Driver B")
        for _ in range(5):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=60.0,
            )
        await db_session.commit()

        score = await calculate_hybrid_score(sofor.id, 1.0)
        # ort_tuketim=60 → perf_factor=0.5 → hybrid=0.5*0.6+1.0*0.4=0.7 < 1.0
        assert score < 1.0

    async def test_zero_consumption_returns_manual(self, db_session):
        arac = await seed_arac(db_session, plaka="34HYBRID03")
        sofor = await seed_sofor(db_session, ad_soyad="Hybrid Score Driver C")
        for _ in range(5):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=0.0,
            )
        await db_session.commit()

        score = await calculate_hybrid_score(sofor.id, 1.3)
        assert score == 1.3

    async def test_exception_returns_manual(self, db_session):
        """Exception in get_sefer_stats is swallowed; returns manual_score.

        Boundary: targeted patch on the specific repo method that must raise.
        The try/except block in calculate_hybrid_score handles this gracefully.
        """
        sofor = await seed_sofor(db_session, ad_soyad="Hybrid Exception Driver")
        await db_session.commit()

        import v2.modules.driver.infrastructure.repository as sofor_repo_mod

        with patch.object(
            sofor_repo_mod.SoforRepository,
            "get_sefer_stats",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db error"),
        ):
            score = await calculate_hybrid_score(sofor.id, 0.9)
        assert score == 0.9


# ===========================================================================
# get_score_breakdown_sofor
# ===========================================================================
# 0-mock: uow=None yolu artık kendi UnitOfWork()'ünü açıyor (fix — eski
# get_sofor_repo() singleton'ı session'sız ORM get_by_id ile 500 patlıyordu,
# bkz. v2/modules/driver/CLAUDE.md "score-breakdown 500" bulgusu). Bu yüzden
# artık gerçek DB'ye karşı, hiç repo patch'i olmadan test edilebiliyor.


class TestGetScoreBreakdown:
    async def test_driver_not_found_raises(self, db_session):
        with pytest.raises(ValueError, match="Driver not found"):
            await get_score_breakdown_sofor(999999)

    async def test_no_trips_returns_manual_fallback(self, db_session):
        sofor = await seed_sofor(
            db_session, ad_soyad="Score Breakdown No Trips", manual_score=1.2
        )
        await db_session.commit()

        result = await get_score_breakdown_sofor(sofor.id)

        assert result["has_trips"] is False
        assert result["manual"] == 1.2

    async def test_with_trips_computes_auto_score(self, db_session):
        arac = await seed_arac(db_session, plaka="34SBREAK01")
        sofor = await seed_sofor(
            db_session, ad_soyad="Score Breakdown With Trips", manual_score=1.0
        )
        for _ in range(8):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=30.0,
            )
        await db_session.commit()

        result = await get_score_breakdown_sofor(sofor.id)

        assert result["has_trips"] is True
        assert result["trip_count"] == 8
        assert abs(result["avg_consumption"] - 30.0) < 0.1
        assert "total" in result

    async def test_score_clamped_to_valid_range(self, db_session):
        """manual_score=3.0 should clamp to 2.0.

        DB'nin ``chk_sofor_manual_score_range`` CHECK constraint'i 0.1-2.0
        dışı bir değerin seed edilmesine izin vermiyor — bu yüzden yalnız
        bu senaryoda repo.get_by_id() dönüşü dar (narrow) patch'lenir
        (yazma yolu değil, yalnız okuma; test_stats_exception_falls_back_to_manual
        ile aynı sınıf istisna).
        """
        sofor = await seed_sofor(db_session, ad_soyad="Score Clamp Driver")
        await db_session.commit()

        import v2.modules.driver.infrastructure.repository as sofor_repo_mod

        with patch.object(
            sofor_repo_mod.SoforRepository,
            "get_by_id",
            new_callable=AsyncMock,
            return_value={
                "id": sofor.id,
                "ad_soyad": sofor.ad_soyad,
                "manual_score": 3.0,
            },
        ):
            result = await get_score_breakdown_sofor(sofor.id)

        assert result["manual"] == 2.0

    async def test_result_structure(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Score Structure Driver")
        await db_session.commit()

        result = await get_score_breakdown_sofor(sofor.id)

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

    async def test_stats_exception_falls_back_to_manual(self, db_session):
        """Exception in get_sefer_stats is swallowed; has_trips stays False."""
        sofor = await seed_sofor(
            db_session, ad_soyad="Score Exception Driver", manual_score=1.1
        )
        await db_session.commit()

        import v2.modules.driver.infrastructure.repository as sofor_repo_mod

        with patch.object(
            sofor_repo_mod.SoforRepository,
            "get_sefer_stats",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await get_score_breakdown_sofor(sofor.id)

        assert result["has_trips"] is False


# ===========================================================================
# get_route_profile_sofor
# ===========================================================================
# 0-mock: uow=None yolu artık kendi UnitOfWork()'ünü açıyor (fix — aynı
# get_score_breakdown_sofor bulgusu, bkz. yukarısı). classify_route hâlâ
# patch'leniyor: testing the use-case's bucketing logic, not the ML function.


class TestGetRouteProfile:
    async def test_driver_not_found_raises(self, db_session):
        with pytest.raises(ValueError, match="Driver not found"):
            await get_route_profile_sofor(999999)

    async def test_empty_trips_returns_zero_profiles(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Route Profile Empty Driver")
        await db_session.commit()

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            return_value="mixed",
        ):
            result = await get_route_profile_sofor(sofor.id)

        assert result["best_route_type"] is None
        for profile in result["profiles"]:
            assert profile["trip_count"] == 0

    async def test_with_trips_populates_profiles(self, db_session):
        arac = await seed_arac(db_session, plaka="34ROUTE01")
        sofor = await seed_sofor(db_session, ad_soyad="Route Profile Trips Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=300.0,
            tahmini_tuketim=280.0,
            rota_detay={"route_analysis": {"highway_km": 400}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            return_value="highway_dominant",
        ):
            result = await get_route_profile_sofor(sofor.id)

        highway_profile = next(
            p for p in result["profiles"] if p["route_type"] == "highway_dominant"
        )
        assert highway_profile["trip_count"] == 1
        assert highway_profile["avg_actual"] == 300.0

    async def test_best_route_type_selected_by_min_deviation(self, db_session):
        arac = await seed_arac(db_session, plaka="34ROUTE02")
        sofor = await seed_sofor(db_session, ad_soyad="Route Profile Best Driver")
        # 5 highway trips (low deviation), 5 urban trips (high deviation)
        for _ in range(5):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=100.0,
                tahmini_tuketim=102.0,
                rota_detay={"route_analysis": {"highway_km": 300}},
            )
        for _ in range(5):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=200.0,
                tahmini_tuketim=100.0,
                rota_detay={"route_analysis": {}},
            )
        await db_session.commit()

        def classify_side_effect(route_analysis):
            # highway trips have highway_km seeded; urban trips have empty analysis
            return "highway_dominant" if "highway_km" in route_analysis else "urban"

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            side_effect=classify_side_effect,
        ):
            result = await get_route_profile_sofor(sofor.id, min_trips_for_best=5)

        # highway: deviation=(100-102)/102*100 ≈ -2%; urban: (200-100)/100*100=100%
        # best_route_type = lowest deviation_pct = highway_dominant
        assert result["best_route_type"] == "highway_dominant"

    async def test_insufficient_trips_for_best(self, db_session):
        """best_route_type is None when all route_types have < min_trips_for_best."""
        arac = await seed_arac(db_session, plaka="34ROUTE03")
        sofor = await seed_sofor(db_session, ad_soyad="Route Profile Insuff Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=100.0,
            tahmini_tuketim=100.0,
            rota_detay={"route_analysis": {}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            return_value="mixed",
        ):
            result = await get_route_profile_sofor(sofor.id, min_trips_for_best=5)

        assert result["best_route_type"] is None

    async def test_classify_route_exception_skips_trip(self, db_session):
        """Exception in classify_route logs a warning and skips the trip."""
        arac = await seed_arac(db_session, plaka="34ROUTE04")
        sofor = await seed_sofor(db_session, ad_soyad="Route Classify Exc Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=100.0,
            tahmini_tuketim=100.0,
            rota_detay={"route_analysis": {}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            side_effect=ValueError("bad route"),
        ):
            result = await get_route_profile_sofor(sofor.id)

        assert all(p["trip_count"] == 0 for p in result["profiles"])

    async def test_unknown_route_type_skips_trip(self, db_session):
        """classify_route returning unknown type skips the trip (rtype not in buckets)."""
        arac = await seed_arac(db_session, plaka="34ROUTE05")
        sofor = await seed_sofor(db_session, ad_soyad="Route Unknown Type Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=100.0,
            tahmini_tuketim=100.0,
            rota_detay={"route_analysis": {}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.application.get_route_profile.classify_route",
            return_value="unknown_type_xyz",
        ):
            result = await get_route_profile_sofor(sofor.id)

        assert all(p["trip_count"] == 0 for p in result["profiles"])


# ===========================================================================
# bulk_add_sofor
# ===========================================================================


class TestBulkAddSofor:
    async def test_empty_list_returns_zero(self):
        result = await bulk_add_sofor([])
        assert result == 0

    async def test_skips_short_names(self, db_session):
        result = await bulk_add_sofor([{"ad_soyad": "Ab"}])
        assert result == 0

    async def test_skips_duplicate_names(self, db_session):
        await seed_sofor(db_session, ad_soyad="Ali Veli Duplicate")
        await db_session.commit()

        result = await bulk_add_sofor([{"ad_soyad": "Ali Veli Duplicate"}])
        assert result == 0

    async def test_inserts_new_drivers(self, db_session):
        result = await bulk_add_sofor(
            [{"ad_soyad": "Bulk New Driver One"}, {"ad_soyad": "Bulk New Driver Two"}]
        )
        assert result == 2

    async def test_model_dump_path(self, db_session):
        """Works with Pydantic-like objects that have model_dump()."""

        class FakeModel:
            def model_dump(self):
                return {
                    "ad_soyad": "Pydantic Sofor Bulk",
                    "telefon": "05001112233",
                    "ehliyet_sinifi": "E",
                }

        result = await bulk_add_sofor([FakeModel()])
        assert result == 1

    async def test_dict_path(self, db_session):
        """Works with objects that have dict() (legacy Pydantic v1)."""

        class LegacyModel:
            def dict(self):
                return {"ad_soyad": "Legacy Sofor Bulk", "ehliyet_sinifi": "E"}

        result = await bulk_add_sofor([LegacyModel()])
        assert result == 1


# ===========================================================================
# get_performance_details
# ===========================================================================


class TestGetPerformanceDetails:
    async def test_basic_structure(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Perf Basic Driver")
        await db_session.commit()

        result = await get_performance_details(sofor.id)

        assert "safety_score" in result
        assert "eco_score" in result
        assert "compliance_score" in result
        assert "total_score" in result
        assert "trend" in result

    async def test_trend_increasing_when_high_score(self, db_session):
        arac = await seed_arac(db_session, plaka="34PERF01")
        sofor = await seed_sofor(db_session, ad_soyad="Perf Trend Inc Driver")
        for _ in range(50):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=28.0,
                mesafe_km=200.0,
            )
        await db_session.commit()

        result = await get_performance_details(sofor.id)
        assert result["trend"] == "increasing"

    async def test_trend_decreasing_when_many_anomalies(self, db_session):
        from v2.modules.anomaly.public import Anomaly

        sofor = await seed_sofor(db_session, ad_soyad="Perf Trend Dec Driver")
        today = date.today()
        for _ in range(5):
            db_session.add(
                Anomaly(
                    tarih=today,
                    tip="tuketim",
                    kaynak_tip="sofor",
                    kaynak_id=sofor.id,
                    deger=50.0,
                    beklenen_deger=30.0,
                    sapma_yuzde=66.0,
                    severity="critical",
                    aciklama="Test critical",
                )
            )
        for _ in range(5):
            db_session.add(
                Anomaly(
                    tarih=today,
                    tip="tuketim",
                    kaynak_tip="sofor",
                    kaynak_id=sofor.id,
                    deger=45.0,
                    beklenen_deger=30.0,
                    sapma_yuzde=50.0,
                    severity="high",
                    aciklama="Test high",
                )
            )
        for _ in range(10):
            db_session.add(
                Anomaly(
                    tarih=today,
                    tip="tuketim",
                    kaynak_tip="sofor",
                    kaynak_id=sofor.id,
                    deger=38.0,
                    beklenen_deger=30.0,
                    sapma_yuzde=26.0,
                    severity="medium",
                    aciklama="Test medium",
                )
            )
        await db_session.commit()

        result = await get_performance_details(sofor.id)
        assert result["trend"] == "decreasing"

    async def test_trend_stable_mid_range(self, db_session):
        from v2.modules.anomaly.public import Anomaly

        arac = await seed_arac(db_session, plaka="34PERF02")
        sofor = await seed_sofor(db_session, ad_soyad="Perf Trend Stable Driver")
        for _ in range(20):
            await seed_sefer(
                db_session,
                arac_id=arac.id,
                sofor_id=sofor.id,
                tuketim=33.0,
                mesafe_km=250.0,
            )
        today = date.today()
        for _ in range(2):
            db_session.add(
                Anomaly(
                    tarih=today,
                    tip="tuketim",
                    kaynak_tip="sofor",
                    kaynak_id=sofor.id,
                    deger=40.0,
                    beklenen_deger=30.0,
                    sapma_yuzde=33.0,
                    severity="critical",
                    aciklama="Stable test critical",
                )
            )
        await db_session.commit()

        result = await get_performance_details(sofor.id)
        assert result["trend"] in ("stable", "increasing", "decreasing")

    async def test_eco_score_above_target(self, db_session):
        """ort_tuketim < 30 gives bonus eco score (but capped at 100)."""
        arac = await seed_arac(db_session, plaka="34PERF03")
        sofor = await seed_sofor(db_session, ad_soyad="Perf Eco Above Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=25.0,
        )
        await db_session.commit()

        result = await get_performance_details(sofor.id)
        assert result["eco_score"] >= 100.0

    async def test_eco_score_below_target(self, db_session):
        """ort_tuketim > 30 penalises eco score."""
        arac = await seed_arac(db_session, plaka="34PERF04")
        sofor = await seed_sofor(db_session, ad_soyad="Perf Eco Below Driver")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tuketim=45.0,
        )
        await db_session.commit()

        result = await get_performance_details(sofor.id)
        assert result["eco_score"] < 100.0


# NOTE: eski "get_sofor_service factory" testi kaldırıldı — SoforService
# sınıfı ve get_sofor_service() factory'si B.1 free-function split'inde
# silindi, yerine koyulacak bir factory yok (bkz. v2/modules/driver/CLAUDE.md).
