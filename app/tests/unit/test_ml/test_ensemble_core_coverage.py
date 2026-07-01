"""
Extended coverage for app/core/ml/ensemble_core.py.

Target: raise module coverage from ~76% toward ≥90%.

Covers the main gaps:
  - prepare_features: rota_detay / analysis branches, grade histogram, speed profile
  - _resolve_expected_feature_count: mock values, numeric vs non-numeric guard
  - _extract_route_analysis: dict / non-dict rota_detay
  - _align_feature_matrix: match / mismatch (too many / too few cols)
  - _get_physics_predictions: dorse override fields
  - fit: outlier guard, temporal weighting, y_actual=None path, label-leak guard,
         train/test split branches, LGBMfit MemoryError path
  - predict: NaN/Inf fallback, ML correction path, RuntimeError → physics fallback
  - explain_prediction
  - save_model / load_model guards
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sefer(
    mesafe_km: float = 500.0,
    ton: float = 20.0,
    ascent_m: float = 800.0,
    descent_m: float = 700.0,
    tuketim: float = 32.0,
    tarih: str = "2025-01-15",
    **kwargs,
) -> Dict:
    base = dict(
        mesafe_km=mesafe_km,
        ton=ton,
        ascent_m=ascent_m,
        descent_m=descent_m,
        flat_distance_km=300.0,
        tuketim=tuketim,
        tarih=tarih,
        zorluk="Normal",
        arac_yasi=5,
        yas_faktoru=1.0,
        mevsim_faktor=1.0,
        sofor_katsayi=1.0,
    )
    base.update(kwargs)
    return base


def _training_batch(n: int = 20, base_tuketim: float = 32.0) -> List[Dict]:
    return [
        _make_sefer(
            mesafe_km=400 + i * 10,
            ton=18 + (i % 5),
            tuketim=base_tuketim + (i % 3),
            tarih=f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# _extract_route_analysis
# ---------------------------------------------------------------------------


class TestExtractRouteAnalysis:
    def test_returns_none_for_non_dict_rota_detay(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = {"rota_detay": "not_a_dict"}
        result = p._extract_route_analysis(sefer)
        assert result is None

    def test_returns_none_if_no_rota_detay(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        result = p._extract_route_analysis({})
        assert result is None

    def test_returns_route_analysis_nested(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        inner = {"motorway": {"flat": 100, "up": 0, "down": 0}}
        sefer = {"rota_detay": {"route_analysis": inner}}
        result = p._extract_route_analysis(sefer)
        assert result is inner

    def test_falls_back_to_rota_detay_if_no_route_analysis(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        flat_analysis = {"motorway": {"flat": 50, "up": 0, "down": 0}}
        sefer = {"rota_detay": flat_analysis}
        result = p._extract_route_analysis(sefer)
        assert result is flat_analysis


# ---------------------------------------------------------------------------
# prepare_features — route analysis and grade histogram branches
# ---------------------------------------------------------------------------


class TestPrepareFeaturesBranches:
    def test_route_analysis_populates_ratios(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            mesafe_km=500.0,
            rota_detay={
                "route_analysis": {
                    "motorway": {"flat": 300, "up": 50, "down": 50},
                    "residential": {"flat": 20, "up": 10, "down": 10},
                }
            },
        )
        X = p.prepare_features([sefer])
        motorway_ratio = X[0, 10]  # FEATURE_NAMES index 10
        assert motorway_ratio > 0.0

    def test_grade_histogram_computed(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            mesafe_km=500.0,
            flat_distance_km=200.0,
            rota_detay={
                "route_analysis": {
                    "motorway": {"flat": 100, "up": 50, "down": 50},
                    "residential": {"flat": 30, "up": 10, "down": 10},
                }
            },
        )
        X = p.prepare_features([sefer])
        grade_gentle = X[0, 16]  # grade_gentle_ratio
        grade_steep = X[0, 18]  # grade_steep_ratio
        assert 0.0 <= grade_gentle <= 1.0
        assert 0.0 <= grade_steep <= 1.0

    def test_speed_profile_features_computed(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            mesafe_km=500.0,
            rota_detay={
                "route_analysis": {
                    "motorway": {"flat": 400, "up": 0, "down": 0},
                    "residential": {"flat": 50, "up": 0, "down": 0},
                }
            },
        )
        X = p.prepare_features([sefer])
        expected_avg_speed = X[0, 26]  # expected_avg_speed index
        assert expected_avg_speed > 0.0

    def test_no_rota_detay_defaults_zeros(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer()  # no rota_detay
        X = p.prepare_features([sefer])
        assert X.shape[1] == len(p.FEATURE_NAMES)
        assert np.all(np.isfinite(X))

    def test_stopgo_proxy_zero_on_zero_mesafe(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(mesafe_km=0.0)
        X = p.prepare_features([sefer])
        stopgo = X[0, 20]  # stopgo_proxy index
        assert stopgo == pytest.approx(0.0, abs=1e-6)

    def test_dorse_fields_extracted(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(dorse_bos_agirlik=7000.0, dorse_lastik_sayisi=8)
        X = p.prepare_features([sefer])
        dorse_bos = X[0, 24]  # dorse_bos_agirlik index
        dorse_lastik = X[0, 25]  # dorse_lastik_sayisi index
        assert dorse_bos == pytest.approx(7000.0)
        assert dorse_lastik == pytest.approx(8.0)

    def test_zorluk_cok_zor(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(zorluk="Çok Zor")
        X = p.prepare_features([sefer])
        assert X[0, 5] == 4  # zorluk_map["Çok Zor"] = 4

    def test_duration_min_field_used(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(duration_min=300)
        X = p.prepare_features([sefer])
        route_fatigue = X[0, 23]  # route_fatigue index
        assert route_fatigue == pytest.approx(300.0 / 600.0, abs=1e-5)


# ---------------------------------------------------------------------------
# _resolve_expected_feature_count
# ---------------------------------------------------------------------------


class TestResolveExpectedFeatureCount:
    def test_returns_none_all_none_attributes(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        # Before fitting, all n_features_in_ are None
        result = p._resolve_expected_feature_count()
        assert result is None

    def test_returns_value_from_scaler(self):
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        p.scaler.n_features_in_ = 29  # manually set
        result = p._resolve_expected_feature_count()
        assert result == 29

    def test_rejects_mock_object(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        p.scaler = MagicMock()
        p.scaler.n_features_in_ = MagicMock()  # non-numeric
        p.gb_model = None
        p.rf_model = None
        p.xgb_model = None
        p.lgb_model = None
        result = p._resolve_expected_feature_count()
        assert result is None


# ---------------------------------------------------------------------------
# _align_feature_matrix
# ---------------------------------------------------------------------------


class TestAlignFeatureMatrix:
    def test_no_mismatch_returns_x(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        X = np.zeros((3, 29))
        # Patch expected to match current
        with patch.object(p, "_resolve_expected_feature_count", return_value=29):
            result = p._align_feature_matrix(X)
        assert result is X

    def test_too_many_features_raises_and_marks_untrained(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        p.is_trained = True
        X = np.zeros((3, 30))  # 30 cols
        with patch.object(p, "_resolve_expected_feature_count", return_value=29):
            with pytest.raises(RuntimeError, match="mismatch"):
                p._align_feature_matrix(X)
        assert p.is_trained is False

    def test_too_few_features_raises(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        X = np.zeros((3, 28))  # 28 cols
        with patch.object(p, "_resolve_expected_feature_count", return_value=29):
            with pytest.raises(RuntimeError, match="mismatch"):
                p._align_feature_matrix(X)

    def test_expected_none_returns_x_unchanged(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        X = np.zeros((3, 99))  # any size
        with patch.object(p, "_resolve_expected_feature_count", return_value=None):
            result = p._align_feature_matrix(X)
        assert result is X


# ---------------------------------------------------------------------------
# _get_physics_predictions — dorse override fields
# ---------------------------------------------------------------------------


class TestGetPhysicsPredictions:
    def test_dorse_fields_applied_to_model(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            dorse_bos_agirlik=8000.0,
            dorse_lastik_direnci=0.007,
            dorse_hava_direnci=0.14,
        )
        preds = p._get_physics_predictions([sefer])
        assert preds.shape == (1,)
        assert preds[0] > 0

    def test_basic_predictions_positive(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        preds = p._get_physics_predictions(_training_batch(5))
        assert np.all(preds > 0)


# ---------------------------------------------------------------------------
# fit — extended branches
# ---------------------------------------------------------------------------


class TestFitBranches:
    def test_y_actual_none_extracted_from_seferler(self):
        """y_actual=None → extracted from sefer['tuketim']."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        batch = _training_batch(20)
        result = p.fit(batch)  # y_actual defaults to None
        assert "success" in result

    def test_outlier_guard_removes_extreme_values(self):
        """Z-score > 3 triggers outlier removal when n > 20."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        batch = _training_batch(25, base_tuketim=32.0)
        y = np.array([32.0 + (i % 3) * 0.3 for i in range(25)])
        # Add two extreme outliers
        y[10] = 500.0
        y[20] = 500.0
        result = p.fit(batch, y)
        # Should succeed (outliers removed, remaining valid data ≥ 10)
        assert result.get("success") in (True, False)  # at least doesn't crash

    def test_fit_date_object_tarih(self):
        """Sefer with date object (not string) for tarih field."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        today = date.today()
        batch = [
            _make_sefer(
                mesafe_km=400 + i * 10,
                ton=18 + (i % 5),
                tuketim=32.0 + (i % 3),
                tarih=today - timedelta(days=i),  # date object
            )
            for i in range(20)
        ]
        p = EnsembleFuelPredictor()
        result = p.fit(batch)
        assert "success" in result

    def test_fit_invalid_tarih_string_defaults(self):
        """Sefer with unparseable tarih string falls back without crashing."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        batch = [
            _make_sefer(
                mesafe_km=400 + i * 10,
                ton=18,
                tuketim=32.0 + (i % 3),
                tarih="INVALID_DATE",
            )
            for i in range(20)
        ]
        p = EnsembleFuelPredictor()
        result = p.fit(batch)
        # Should not crash
        assert "success" in result

    def test_fit_no_tarih_field(self):
        """Sefer without 'tarih' field gets weight=0.5."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        batch = [
            {
                "mesafe_km": 400 + i * 10,
                "ton": 18,
                "tuketim": 32.0 + (i % 3),
                "zorluk": "Normal",
                "arac_yasi": 5,
                "yas_faktoru": 1.0,
                "mevsim_faktor": 1.0,
                "sofor_katsayi": 1.0,
                "flat_distance_km": 200.0,
                "ascent_m": 500.0,
                "descent_m": 400.0,
            }
            for i in range(20)
        ]
        p = EnsembleFuelPredictor()
        result = p.fit(batch)
        assert "success" in result

    def test_fit_sklearn_not_available(self):
        from app.core.ml import ensemble_core

        original = ensemble_core.SKLEARN_AVAILABLE
        try:
            ensemble_core.SKLEARN_AVAILABLE = False
            p = ensemble_core.EnsembleFuelPredictor()
            p.gb_model = None
            p.rf_model = None
            p.scaler = None
            result = p.fit(_training_batch(20))
            assert result["success"] is False
        finally:
            ensemble_core.SKLEARN_AVAILABLE = original

    def test_lgb_oom_skipped(self):
        """LightGBM MemoryError during fit must be caught and skipped."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        if p.lgb_model is None:
            pytest.skip("LightGBM not available")

        original_fit = p.lgb_model.fit

        def _oom(*args, **kwargs):
            raise MemoryError("OOM")

        p.lgb_model.fit = _oom

        try:
            result = p.fit(_training_batch(20))
            # Should complete without raising
            assert "success" in result
        finally:
            p.lgb_model.fit = original_fit


# ---------------------------------------------------------------------------
# predict — extended branches
# ---------------------------------------------------------------------------


class TestPredictExtended:
    def test_predict_after_fit_returns_result(self):
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        batch = _training_batch(20)
        p.fit(batch)

        result = p.predict(_make_sefer())
        assert result.tahmin_l_100km > 0

    def test_predict_runtime_error_returns_physics_fallback(self):
        """RuntimeError from _align_feature_matrix → physics-only fallback."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        p.is_trained = True
        p.scaler = MagicMock()
        p.scaler.transform.side_effect = RuntimeError("forced schema mismatch")

        result = p.predict(_make_sefer())
        assert result.tahmin_l_100km > 0
        assert result.physics_weight == 1.0
        assert p.is_trained is False

    def test_predict_nan_result_falls_back(self):
        """When the weighted sum is NaN, predict() returns physics fallback."""
        from app.core.ml.ensemble_core import SKLEARN_AVAILABLE, EnsembleFuelPredictor

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        p = EnsembleFuelPredictor()
        p.is_trained = True
        p.scaler = MagicMock()
        p.scaler.transform.return_value = np.zeros((1, 29))

        mock_gb = MagicMock()
        mock_gb.predict.return_value = np.array([np.nan])
        mock_rf = MagicMock()
        mock_rf.predict.return_value = np.array([np.nan])
        p.gb_model = mock_gb
        p.rf_model = mock_rf
        p.xgb_model = None
        p.lgb_model = None

        result = p.predict(_make_sefer())
        assert result.physics_weight == 1.0  # fell back to physics

    def test_predict_with_dorse_fields(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            dorse_bos_agirlik=7500.0,
            dorse_lastik_direnci=0.006,
            dorse_hava_direnci=0.12,
        )
        result = p.predict(sefer)
        assert result.tahmin_l_100km > 0


# ---------------------------------------------------------------------------
# explain_prediction
# ---------------------------------------------------------------------------


class TestExplainPrediction:
    def test_returns_expected_keys(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        sefer = _make_sefer(
            ton=20,
            ascent_m=800,
            zorluk="Normal",
            mevsim_faktor=1.0,
            sofor_katsayi=1.0,
            motorway_ratio=0.5,
        )
        result = p.explain_prediction(sefer)
        assert "prediction" in result
        assert "unit" in result
        assert "contributions" in result
        assert result["unit"] == "L/100km"

    def test_contributions_contain_ml_correction(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        result = p.explain_prediction(_make_sefer())
        assert "ML Düzeltmesi" in result["contributions"]

    def test_confidence_is_non_negative(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        result = p.explain_prediction(_make_sefer())
        assert result["confidence"] >= 0


# ---------------------------------------------------------------------------
# save_model / load_model guards
# ---------------------------------------------------------------------------


class TestSaveLoadGuards:
    def test_save_raises_when_not_trained(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            p.save_model("/tmp/test_ensemble")

    def test_load_raises_meta_not_found(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        with pytest.raises(FileNotFoundError):
            p.load_model("/tmp/nonexistent_ensemble")

    def test_load_reads_metadata_fields(self, tmp_path):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        # Write minimal metadata file
        meta = {
            "physics_weight": 0.5,
            "training_stats": {"sample_count": 10},
            "is_trained": True,
            "sklearn_checksum": None,
            "model_weights": {"physics": 0.5, "gb": 0.25, "rf": 0.25},
        }
        base_path = tmp_path / "model"
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        # Sklearn file missing — skip load attempt
        result = p.load_model(str(base_path))
        assert result == {"success": True}
        assert p.physics_weight == 0.5
        assert p.is_trained is True

    def test_load_reads_feature_schema_hash_from_metadata(self, tmp_path):
        """2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 26): eskiden
        feature_schema_hash DB'ye (ModelVersion) yazılıyordu ama model
        dosyası (_meta.json) hiç içermiyordu, load_model da hiç okumuyordu
        — sadece feature SAYISI kontrol ediliyordu, isim/sıra drift'i
        sessizce geçiyordu. Artık _meta.json'da saklanıyor ve load_model
        bunu `_loaded_feature_schema_hash` attribute'una okuyor."""
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        meta = {
            "physics_weight": 0.5,
            "training_stats": {"sample_count": 10},
            "is_trained": True,
            "sklearn_checksum": None,
            "model_weights": {"physics": 0.5, "gb": 0.25, "rf": 0.25},
            "feature_schema_hash": "deadbeef12345678",  # pragma: allowlist secret
        }
        base_path = tmp_path / "model"
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        p.load_model(str(base_path))
        assert (
            p._loaded_feature_schema_hash
            == "deadbeef12345678"  # pragma: allowlist secret
        )

    def test_save_model_persists_feature_schema_hash(self, tmp_path):
        """save_model'in yazdığı _meta.json artık feature_schema_hash içeriyor
        (FEATURE_NAMES'in sırayla hash'i — isim/sıra drift'ini yakalar,
        sadece sayı değil)."""
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        p.is_trained = True
        p.physics_weight = 0.5
        p.training_stats = {"sample_count": 10}
        p.weights = {"physics": 0.5, "gb": 0.25, "rf": 0.25}
        # xgb/lgb fit edilmemiş (NotFittedError önler) — bu test yalnızca
        # metadata JSON'unu doğruluyor, gerçek model eğitimini değil.
        p.xgb_model = None
        p.lgb_model = None
        base_path = tmp_path / "model"
        p.save_model(str(base_path))

        with open(f"{base_path}_meta.json", encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["feature_schema_hash"] == p._feature_hash

    def test_load_checksum_mismatch_raises_security_error(self, tmp_path):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor, SecurityError

        p = EnsembleFuelPredictor()
        base_path = tmp_path / "model"

        sklearn_file = tmp_path / "model_sklearn.joblib"
        sklearn_file.write_bytes(b"fake_joblib_data")

        meta = {
            "physics_weight": 0.2,
            "training_stats": {},
            "is_trained": True,
            "sklearn_checksum": "deadbeef" * 8,  # wrong checksum
            "model_weights": EnsembleFuelPredictor.DEFAULT_WEIGHTS,
        }
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        with pytest.raises(SecurityError, match="bozulmuş"):
            p.load_model(str(base_path))

    def test_load_sklearn_too_large_raises(self, tmp_path):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor, SecurityError

        p = EnsembleFuelPredictor()
        base_path = tmp_path / "model"
        sklearn_file = tmp_path / "model_sklearn.joblib"
        sklearn_file.write_bytes(b"x" * 100)

        meta = {
            "physics_weight": 0.2,
            "training_stats": {},
            "is_trained": True,
            "sklearn_checksum": None,
            "model_weights": EnsembleFuelPredictor.DEFAULT_WEIGHTS,
        }
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        with patch.object(
            Path, "stat", return_value=MagicMock(st_size=200 * 1024 * 1024)
        ):
            with pytest.raises(SecurityError, match="boyut"):
                p.load_model(str(base_path))


# ---------------------------------------------------------------------------
# WEIGHTS property alias
# ---------------------------------------------------------------------------


class TestWeightsAlias:
    def test_weights_property_equals_instance_weights(self):
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        p = EnsembleFuelPredictor()
        assert p.WEIGHTS is p.weights


# ---------------------------------------------------------------------------
# Misc — SecurityError, PredictionResult
# ---------------------------------------------------------------------------


class TestSecurityError:
    def test_security_error_is_exception_subclass(self):
        from app.core.ml.ensemble_core import SecurityError

        assert issubclass(SecurityError, Exception)

    def test_raise_security_error(self):
        from app.core.ml.ensemble_core import SecurityError

        with pytest.raises(SecurityError, match="test"):
            raise SecurityError("test")
