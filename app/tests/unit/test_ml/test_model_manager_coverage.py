"""
Coverage tests for ModelManager (model_manager.py).
Focuses on NumpyEncoder, _row_to_model, ModelVersion dataclass,
ModelType enum, get_model_manager singleton, and mocked DB operations.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(**overrides):
    base = {
        "id": 1,
        "arac_id": 5,
        "version": 2,
        "model_type": "ensemble",
        "params_json": '{"r2": 0.85}',
        "r2_score": 0.85,
        "mae": 1.2,
        "sample_count": 100,
        "is_active": True,
        "created_at": datetime(2025, 1, 1, 12, 0, 0),
        "notes": "test notes",
        "feature_schema_hash": "abc123",
        "training_data_hash": "def456",
        "physics_version": "v1",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests: ModelType enum
# ---------------------------------------------------------------------------


class TestModelTypeEnum:
    def test_ensemble_value(self):
        from app.core.ml.model_manager import ModelType

        assert ModelType.ENSEMBLE.value == "ensemble"

    def test_kalman_value(self):
        from app.core.ml.model_manager import ModelType

        assert ModelType.KALMAN.value == "kalman"

    def test_physics_value(self):
        from app.core.ml.model_manager import ModelType

        assert ModelType.PHYSICS.value == "physics"

    def test_value_accessible_as_string(self):
        from app.core.ml.model_manager import ModelType

        # ModelType is a str-Enum; .value always returns the raw string
        assert ModelType.ENSEMBLE.value == "ensemble"


# ---------------------------------------------------------------------------
# Tests: NumpyEncoder
# ---------------------------------------------------------------------------


class TestNumpyEncoder:
    def test_encodes_numpy_int(self):
        from app.core.ml.model_manager import ModelManager

        enc = ModelManager.NumpyEncoder()
        val = np.int64(42)
        assert enc.default(val) == 42

    def test_encodes_numpy_float(self):
        from app.core.ml.model_manager import ModelManager

        enc = ModelManager.NumpyEncoder()
        val = np.float32(3.14)
        assert abs(enc.default(val) - 3.14) < 0.01

    def test_encodes_numpy_scalar_array(self):
        """Single-element arrays have .item() and are encoded as scalars."""
        from app.core.ml.model_manager import ModelManager

        enc = ModelManager.NumpyEncoder()
        val = np.array(42)  # 0-d array: has .item()
        assert enc.default(val) == 42

    def test_raises_for_unknown_type(self):
        from app.core.ml.model_manager import ModelManager

        enc = ModelManager.NumpyEncoder()
        with pytest.raises(TypeError):
            enc.default(object())

    def test_json_dumps_with_numpy_scalars(self):
        from app.core.ml.model_manager import ModelManager

        data = {"score": np.float64(0.95), "count": np.int64(5)}
        serialized = json.dumps(data, cls=ModelManager.NumpyEncoder)
        parsed = json.loads(serialized)
        assert parsed["score"] == pytest.approx(0.95)
        assert parsed["count"] == 5


# ---------------------------------------------------------------------------
# Tests: _row_to_model
# ---------------------------------------------------------------------------


class TestRowToModel:
    def test_basic_conversion(self):
        from app.core.ml.model_manager import ModelManager, ModelType, ModelVersion

        mgr = ModelManager()
        row = _make_row()
        mv = mgr._row_to_model(row)

        assert isinstance(mv, ModelVersion)
        assert mv.id == 1
        assert mv.arac_id == 5
        assert mv.version == 2
        assert mv.model_type == ModelType.ENSEMBLE
        assert mv.r2_score == 0.85
        assert mv.is_active is True

    def test_optional_fields_populated(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mv = mgr._row_to_model(_make_row())
        assert mv.notes == "test notes"
        assert mv.feature_schema_hash == "abc123"
        assert mv.training_data_hash == "def456"
        assert mv.physics_version == "v1"

    def test_none_sample_count_defaults_to_zero(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        row = _make_row(sample_count=None)
        mv = mgr._row_to_model(row)
        assert mv.sample_count == 0

    def test_is_active_false(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mv = mgr._row_to_model(_make_row(is_active=False))
        assert mv.is_active is False

    def test_optional_fields_missing_defaults_to_none(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        row = _make_row()
        # Remove optional keys
        row.pop("feature_schema_hash", None)
        row.pop("training_data_hash", None)
        row.pop("physics_version", None)
        row.pop("notes", None)
        mv = mgr._row_to_model(row)
        assert mv.feature_schema_hash is None
        assert mv.notes is None


# ---------------------------------------------------------------------------
# Tests: ModelVersion dataclass
# ---------------------------------------------------------------------------


class TestModelVersionDataclass:
    def test_instantiation(self):
        from app.core.ml.model_manager import ModelType, ModelVersion

        mv = ModelVersion(
            id=1,
            arac_id=2,
            version=1,
            model_type=ModelType.ENSEMBLE,
            params_json="{}",
            r2_score=0.9,
            mae=1.0,
            sample_count=50,
            is_active=True,
            created_at=datetime.now(),
        )
        assert mv.id == 1
        assert mv.model_type == ModelType.ENSEMBLE

    def test_optional_notes_defaults_to_none(self):
        from app.core.ml.model_manager import ModelType, ModelVersion

        mv = ModelVersion(
            id=1,
            arac_id=1,
            version=1,
            model_type=ModelType.KALMAN,
            params_json="{}",
            r2_score=None,
            mae=None,
            sample_count=0,
            is_active=False,
            created_at=datetime.now(),
        )
        assert mv.notes is None


# ---------------------------------------------------------------------------
# Tests: activate_version (mocked DB)
# ---------------------------------------------------------------------------


class TestActivateVersion:
    async def test_returns_false_when_version_not_found(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.activate_version(version_id=999)

        assert result is False

    async def test_returns_true_when_version_found(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (5, "ensemble")
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.activate_version(version_id=1)

        assert result is True


# ---------------------------------------------------------------------------
# Tests: delete_version (mocked DB)
# ---------------------------------------------------------------------------


class TestDeleteVersion:
    async def test_returns_false_when_not_found(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.delete_version(version_id=999)

        assert result is False

    async def test_returns_false_for_active_version(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)  # is_active = True
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.delete_version(version_id=1)

        assert result is False

    async def test_deletes_inactive_version(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        results = [MagicMock(), MagicMock()]
        results[0].fetchone.return_value = (False,)  # is_active = False
        call_count = 0

        async def side_effect(stmt, *args, **kwargs):
            nonlocal call_count
            r = results[min(call_count, 1)]
            call_count += 1
            return r

        mock_session.execute = side_effect
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.delete_version(version_id=2)

        assert result is True


# ---------------------------------------------------------------------------
# Tests: save_version (mocked DB)
# ---------------------------------------------------------------------------


class TestSaveVersion:
    async def test_save_version_returns_version_id(self):
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()

        # Set up a mock session with two execute calls:
        # 1st: SELECT MAX(version) → returns (0,)
        # 2nd: INSERT ... RETURNING id → returns (42,)
        # 3rd: UPDATE is_active (activate_in_session)
        # 4th: SELECT inactive versions (cleanup_in_session)
        call_results = []

        result0 = MagicMock()
        result0.fetchone.return_value = (0,)  # max version is 0

        result1 = MagicMock()
        result1.fetchone.return_value = (42,)  # new id

        result2 = MagicMock()  # activate update (no return needed)

        result3 = MagicMock()  # cleanup select
        result3.fetchall.return_value = []

        call_results.extend([result0, result1, result2, result3])
        call_index = [0]

        async def execute_side_effect(stmt, *args, **kwargs):
            idx = call_index[0]
            call_index[0] += 1
            if idx < len(call_results):
                return call_results[idx]
            return MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = execute_side_effect
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            version_id = await mgr.save_version(
                arac_id=1,
                model_type=ModelType.ENSEMBLE,
                params={"r2": 0.85},
                metrics={"r2_score": 0.85, "mae": 1.2, "sample_count": 100},
                notes="test save",
            )

        assert version_id == 42

    async def test_save_version_with_numpy_metrics(self):
        """Numpy values in metrics should be serialized without error."""
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()

        call_results = [
            MagicMock(fetchone=lambda: (1,)),  # max version
            MagicMock(fetchone=lambda: (99,)),  # insert id
            MagicMock(),  # activate
            MagicMock(fetchall=lambda: []),  # cleanup
        ]
        call_index = [0]

        async def execute_side_effect(stmt, *args, **kwargs):
            idx = call_index[0]
            call_index[0] += 1
            if idx < len(call_results):
                return call_results[idx]
            return MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = execute_side_effect
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        import numpy as np_test

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            version_id = await mgr.save_version(
                arac_id=5,
                model_type=ModelType.KALMAN,
                params={"r2": np_test.float64(0.9)},
                metrics={"r2_score": np_test.float64(0.9), "mae": np_test.float32(1.5)},
            )

        assert version_id == 99


# ---------------------------------------------------------------------------
# Tests: _cleanup_in_session / _cleanup_old_versions
# ---------------------------------------------------------------------------


class TestCleanupOldVersions:
    async def test_cleanup_deletes_excess_versions(self):
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()

        old_ids = [(10,), (11,)]
        select_result = MagicMock()
        select_result.fetchall.return_value = old_ids

        delete_results = [MagicMock(), MagicMock()]
        execute_calls = [select_result, *delete_results]
        call_idx = [0]

        async def execute_side(stmt, *args, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx < len(execute_calls):
                return execute_calls[idx]
            return MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = execute_side

        await mgr._cleanup_in_session(
            mock_session, arac_id=1, model_type=ModelType.ENSEMBLE
        )

        # Should have been called once for SELECT, twice for DELETE
        assert call_idx[0] == 3

    async def test_cleanup_old_versions_standalone(self):
        """_cleanup_old_versions opens its own session."""
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()

        mock_session = AsyncMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=select_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            await mgr._cleanup_old_versions(arac_id=1, model_type=ModelType.ENSEMBLE)

        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: activate_version error handling
# ---------------------------------------------------------------------------


class TestActivateVersionError:
    async def test_returns_false_on_exception(self):
        from app.core.ml.model_manager import ModelManager

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.activate_version(version_id=1)

        assert result is False


# ---------------------------------------------------------------------------
# Tests: get_active_version (mocked DB)
# ---------------------------------------------------------------------------


class TestGetActiveVersion:
    async def test_returns_none_when_no_active(self):
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.get_active_version(
                arac_id=1, model_type=ModelType.ENSEMBLE
            )

        assert result is None

    async def test_returns_model_version_when_found(self):
        from app.core.ml.model_manager import ModelManager, ModelType

        mgr = ModelManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        row_data = _make_row()
        # Simulate _mapping attribute on row
        mock_row = MagicMock()
        mock_row._mapping = row_data
        mock_result.fetchone.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.core.ml.model_manager.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await mgr.get_active_version(
                arac_id=5, model_type=ModelType.ENSEMBLE
            )

        assert result is not None
        assert result.arac_id == 5


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestModelManagerSingleton:
    def test_get_model_manager_returns_instance(self):
        from app.core.ml.model_manager import ModelManager, get_model_manager

        mgr = get_model_manager()
        assert isinstance(mgr, ModelManager)

    def test_get_model_manager_same_instance(self):
        from app.core.ml.model_manager import get_model_manager

        a = get_model_manager()
        b = get_model_manager()
        assert a is b
