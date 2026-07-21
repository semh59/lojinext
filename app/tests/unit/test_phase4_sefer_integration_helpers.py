"""Phase 4.4 — sefer akışı entegrasyonu helper testleri.

DB'siz testler:
- SeferFuelEstimate.to_legacy_prediction_dict adapter shape doğru
- Feature flag default False (mevcut akış korunur)
- Sefer ORM model'inde route_simulation_id var, FK + ondelete=SET NULL
- sefer_repo allowed whitelist'e route_simulation_id + tahmini_tuketim eklendi

Integration testler (DB'li) Phase 4.4 sonrası CI'da koşacak — sefer create
→ feature flag açıkken seferler.route_simulation_id set ediliyor mu.
"""

from __future__ import annotations

from app.config import settings
from v2.modules.shared_kernel.infrastructure.base import Base
from v2.modules.trip.application.sefer_fuel_estimator import (
    FactorBreakdown,
    SeferFuelEstimate,
)


def test_legacy_prediction_dict_has_required_keys():
    """SeferFuelEstimate.to_legacy_prediction_dict — _extract_prediction_values
    helper'ı bu shape'i bekler."""
    est = SeferFuelEstimate(
        tahmini_tuketim=28.5,
        total_l=85.5,
        distance_km=300.0,
        duration_min=180.0,
        simulation_id=42,
        breakdown=FactorBreakdown(
            physics_baseline=24.0,
            driver=1.05,
            vehicle_age=1.02,
            maintenance=1.0,
            weather_temperature=1.18,
            weather_wind=1.05,
            weather_precipitation=1.03,
            seasonal=1.10,
            ml_correction_weight=0.0,
            final=28.5,
        ),
    )
    legacy = est.to_legacy_prediction_dict()

    # _extract_prediction_values bu alanları okur
    assert legacy["tahmini_tuketim"] == 28.5
    assert legacy["tahmin_l_100km"] == 28.5
    assert legacy["physics_only"] == 24.0
    assert legacy["ml_correction"] == 4.5  # 28.5 - 24.0
    assert legacy["physics_weight"] == 1.0  # cold start
    assert legacy["confidence_low"] == 25.7  # 28.5 × 0.9 = 25.65 round
    assert legacy["confidence_high"] == 31.4  # 28.5 × 1.1 = 31.35
    # Phase 4.4 ek alanlar
    assert legacy["simulation_id"] == 42
    assert legacy["distance_km"] == 300.0
    assert legacy["total_l"] == 85.5
    # factors_used breakdown'ı içerir
    fu = legacy["factors_used"]
    assert fu["physics_baseline"] == 24.0
    assert fu["driver"] == 1.05
    assert fu["weather_temperature"] == 1.18
    assert fu["seasonal"] == 1.10
    assert fu["source"] == "SeferFuelEstimator"


def test_use_sefer_fuel_estimator_opt_in_default_false():
    """Phase 5.0 — config default False; production'da .env üzerinden
    USE_SEFER_FUEL_ESTIMATOR=true ile aktif. Mevcut test suite mock'ları
    bozulmaz."""
    assert settings.USE_SEFER_FUEL_ESTIMATOR is False


def test_bulk_fuel_estimate_strategy_default_skip():
    """Default skip → mevcut bulk_add_sefer davranışı korunur."""
    assert settings.BULK_FUEL_ESTIMATE == "skip"
    assert settings.BULK_FUEL_ESTIMATE_THRESHOLD == 20


def test_sefer_has_route_simulation_id_fk():
    """ORM model Phase 4.4 FK doğru."""
    sefer_table = Base.metadata.tables["seferler"]
    cols = {c.name for c in sefer_table.columns}
    assert "route_simulation_id" in cols

    fk = next(
        (
            fk
            for fk in sefer_table.foreign_keys
            if "route_simulations" in str(fk.column)
        ),
        None,
    )
    assert fk is not None
    assert fk.ondelete == "SET NULL"


def test_sefer_repo_allowed_whitelist_phase44():
    """Phase 4.4: route_simulation_id + tahmini_tuketim allowed'da olmalı."""
    import re

    src = open(
        "v2/modules/trip/infrastructure/repository.py", encoding="utf-8"
    ).read()
    # allowed bloğunu bul
    m = re.search(r"allowed\s*=\s*\{([^}]+)\}", src)
    assert m is not None
    allowed_block = m.group(1)
    assert "route_simulation_id" in allowed_block
    assert "tahmini_tuketim" in allowed_block
    assert "tahmin_meta" in allowed_block
    assert "rota_detay" in allowed_block
