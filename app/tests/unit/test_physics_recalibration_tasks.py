"""Coverage for v2/modules/route_simulation/infrastructure/
physics_recalibration_tasks.py (Item C follow-up, 2026-07-30) -- was
added without any test, dragging the combined coverage gate below 92%.

Inline imports inside the module's own functions are patched at their
SOURCE module (this module's own convention, see
v2/modules/route_simulation/CLAUDE.md's "Test stratejisi" section).
UnitOfWork is mocked via the narrow __aenter__/__aexit__ patch pattern
already used by app/tests/unit/test_workers/test_coaching_tasks_more.py.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.route_simulation.infrastructure.physics_recalibration_tasks import (
    _append_snapshot,
    _build_snapshot,
    _refresh_all_reference_routes,
    _refresh_reference_route,
    _run_weekly_physics_recalibration,
    weekly_recalibration_snapshot,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def _uow_ctx(mock_uow):
    return (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    )


class _FakeFit:
    def __init__(self, green=8, sse=12.5, cda=6.1, parasitic_kw=5.0, in_band=True):
        self.green = green
        self.sse = sse
        self.cda = cda
        self.parasitic_kw = parasitic_kw
        self.in_physical_band = in_band


# ---------------------------------------------------------------------------
# _build_snapshot / _append_snapshot
# ---------------------------------------------------------------------------


def test_build_snapshot_shape():
    fit = _FakeFit()
    snap = _build_snapshot(fit, route_count=10, cda=6.8, par=4.0)

    assert snap["green"] == 8
    assert snap["total"] == 10
    assert snap["sse"] == 12.5
    assert snap["cda_fit"] == 6.1
    assert snap["parasitic_kw_fit"] == 5.0
    assert snap["in_physical_band"] is True
    assert snap["current_config_cda"] == 6.8
    assert snap["current_config_parasitic_kw"] == 4.0
    assert "date" in snap and "timestamp" in snap


def test_append_snapshot_writes_jsonl_line(tmp_path, monkeypatch):
    import v2.modules.route_simulation.infrastructure.physics_recalibration_tasks as mod

    log_path = tmp_path / "calibration" / "physics_recalibration_log.jsonl"
    monkeypatch.setattr(mod, "_LOG_PATH", log_path)

    _append_snapshot({"green": 9, "total": 10})
    _append_snapshot({"green": 8, "total": 10})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["green"] == 9
    assert json.loads(lines[1])["green"] == 8


# ---------------------------------------------------------------------------
# _refresh_reference_route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_reference_route_skips_when_no_coordinates():
    uow = MagicMock()
    result_row = None
    uow.session.execute = AsyncMock(
        return_value=MagicMock(first=MagicMock(return_value=result_row))
    )

    with patch(
        "v2.modules.route_simulation.application.create_route_simulation.create_route_simulation",
        new=AsyncMock(),
    ) as mock_create:
        await _refresh_reference_route(uow, lokasyon_id=3, arac_id=1, load_tons=20)

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_reference_route_calls_create_route_simulation():
    uow = MagicMock()
    coord_row = (40.7, 29.4, 39.9, 32.8)  # cikis_lat, cikis_lon, varis_lat, varis_lon
    uow.session.execute = AsyncMock(
        return_value=MagicMock(first=MagicMock(return_value=coord_row))
    )

    with (
        patch(
            "v2.modules.route_simulation.application.create_route_simulation.create_route_simulation",
            new=AsyncMock(),
        ) as mock_create,
        patch(
            "v2.modules.route_simulation.application.simulate_route.get_route_simulator",
            return_value="fake-simulator",
        ),
    ):
        await _refresh_reference_route(uow, lokasyon_id=3, arac_id=42, load_tons=20)

    mock_create.assert_called_once()
    _session_arg, simulator_arg = mock_create.call_args.args[:2]
    assert simulator_arg == "fake-simulator"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["lokasyon_id"] == 3
    assert kwargs["arac_id"] == 42
    assert kwargs["ton"] == 20.0
    assert kwargs["cikis_lat"] == 40.7
    assert kwargs["varis_lon"] == 32.8


# ---------------------------------------------------------------------------
# _refresh_all_reference_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_all_reference_routes_returns_none_when_vehicle_missing():
    uow = MagicMock()
    uow.arac_repo.get_by_plaka = AsyncMock(return_value=None)

    result = await _refresh_all_reference_routes(uow)

    assert result is None


@pytest.mark.asyncio
async def test_refresh_all_reference_routes_refreshes_every_route_and_commits():
    uow = MagicMock()
    uow.arac_repo.get_by_plaka = AsyncMock(return_value={"id": 7})
    uow.commit = AsyncMock()

    fake_routes = {3: ("IST-ANK", 20, 30.0, 35.0), 4: ("IST-IZM", 18, 29.0, 33.0)}

    with (
        patch(
            "v2.modules.route_simulation.domain.physics_reference_routes.REFERENCE_ROUTES",
            fake_routes,
        ),
        patch(
            "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._refresh_reference_route",
            new=AsyncMock(),
        ) as mock_refresh,
    ):
        result = await _refresh_all_reference_routes(uow)

    assert result == 7
    assert mock_refresh.call_count == 2
    uow.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# _run_weekly_physics_recalibration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_weekly_recalibration_skips_when_vehicle_missing():
    mock_uow = MagicMock()
    ctx1, ctx2 = _uow_ctx(mock_uow)

    with (
        ctx1,
        ctx2,
        patch(
            "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._refresh_all_reference_routes",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await _run_weekly_physics_recalibration()

    assert result == {"skipped": "reference_vehicle_missing"}


@pytest.mark.asyncio
async def test_run_weekly_recalibration_skips_when_no_routes_loaded():
    mock_uow = MagicMock()
    ctx1, ctx2 = _uow_ctx(mock_uow)

    with (
        ctx1,
        ctx2,
        patch(
            "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._refresh_all_reference_routes",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "v2.modules.route_simulation.application.physics_calibration.load_reference_route_segments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await _run_weekly_physics_recalibration()

    assert result == {"skipped": "no_routes_loaded"}


@pytest.mark.asyncio
async def test_run_weekly_recalibration_happy_path_appends_snapshot(
    tmp_path, monkeypatch
):
    import v2.modules.route_simulation.infrastructure.physics_recalibration_tasks as mod

    monkeypatch.setattr(mod, "_LOG_PATH", tmp_path / "physics_recalibration_log.jsonl")

    mock_uow = MagicMock()
    ctx1, ctx2 = _uow_ctx(mock_uow)
    fake_fit = _FakeFit(green=9, sse=5.0, cda=6.5, parasitic_kw=4.5, in_band=True)

    with (
        ctx1,
        ctx2,
        patch(
            "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._refresh_all_reference_routes",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "v2.modules.route_simulation.application.physics_calibration.load_reference_route_segments",
            new=AsyncMock(return_value=["route-a", "route-b"]),
        ),
        patch(
            "v2.modules.route_simulation.application.physics_calibration.grid_search_best_fit",
            return_value=fake_fit,
        ),
    ):
        result = await _run_weekly_physics_recalibration()

    assert result["green"] == 9
    assert result["total"] == 2
    assert mod._LOG_PATH.exists()
    logged = json.loads(mod._LOG_PATH.read_text(encoding="utf-8").strip())
    assert logged["green"] == 9


# ---------------------------------------------------------------------------
# weekly_recalibration_snapshot (Celery task)
# ---------------------------------------------------------------------------


def test_weekly_recalibration_snapshot_task_returns_runner_result():
    with patch(
        "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._run_weekly_physics_recalibration",
        new=AsyncMock(return_value={"green": 7, "total": 10}),
    ):
        result = weekly_recalibration_snapshot.apply().result

    assert result == {"green": 7, "total": 10}


def test_weekly_recalibration_snapshot_task_retries_on_connection_error():
    from celery.exceptions import Retry

    with patch(
        "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._run_weekly_physics_recalibration",
        new=AsyncMock(side_effect=ConnectionError("db down")),
    ):
        with pytest.raises(Retry):
            weekly_recalibration_snapshot.apply(throw=True)


def test_weekly_recalibration_snapshot_task_reraises_unexpected_errors():
    with patch(
        "v2.modules.route_simulation.infrastructure.physics_recalibration_tasks._run_weekly_physics_recalibration",
        new=AsyncMock(side_effect=ValueError("unexpected")),
    ):
        with pytest.raises(ValueError, match="unexpected"):
            weekly_recalibration_snapshot.apply(throw=True)
