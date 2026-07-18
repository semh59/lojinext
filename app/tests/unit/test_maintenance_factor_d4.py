"""D.4 — bakım→yakıt faktörünün estimator'a bağlanması (NO_HISTORY→1.0 nötr).

Kanıt (by-construction güvenlik): verisi olmayan araç için faktör TAM 1.0 =
D.4 öncesi davranışla birebir → p51/tahmin kayması yok. Sadece gerçek açık
ARIZA/ACIL + tamamlanmış PERIYODIK sinyali faktörü oynatır.
"""

from datetime import datetime, timezone

import pytest

from app.database.models import AracBakim, BakimTipi
from app.tests._helpers.seed import seed_arac
from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
    HealthInput,
    compute_maintenance_factor,
)
from v2.modules.trip.application.sefer_fuel_estimator import SeferFuelEstimator

pytestmark = pytest.mark.integration
# --- pure: neutralization logic -------------------------------------------


def test_no_history_neutralized_is_exactly_one():
    """no_history_factor=1.0 → verisiz araç tam 1.0 (D.4 öncesiyle birebir)."""
    res = compute_maintenance_factor(HealthInput(None, 0, 0), no_history_factor=1.0)
    assert res.factor == 1.0


def test_open_ariza_penalty_applies_without_history():
    """Geçmiş yok ama açık ARIZA var → penaltı devreye girer (1.05)."""
    res = compute_maintenance_factor(HealthInput(None, 1, 0), no_history_factor=1.0)
    assert res.factor == 1.05


def test_default_no_history_unchanged_for_other_callers():
    """Varsayılan (1.05) diğer çağıranlar için korunur — geriye dönük uyum."""
    res = compute_maintenance_factor(HealthInput(None, 0, 0))
    assert res.factor == 1.05


# --- real DB: estimator wiring --------------------------------------------


async def test_estimator_factor_neutral_when_no_data(db_session):
    arac = await seed_arac(db_session, plaka="34 MF 001")
    await db_session.commit()
    est = SeferFuelEstimator()
    factor = await est._fetch_maintenance_factor(db_session, arac.id)
    assert factor == 1.0  # veri yok → nötr


async def test_estimator_factor_reacts_to_open_ariza(db_session):
    arac = await seed_arac(db_session, plaka="34 MF 002")
    db_session.add(
        AracBakim(
            arac_id=arac.id,
            bakim_tipi=BakimTipi.ARIZA,
            km_bilgisi=1000,
            bakim_tarihi=datetime.now(timezone.utc),
            tamamlandi=False,
        )
    )
    await db_session.commit()
    est = SeferFuelEstimator()
    factor = await est._fetch_maintenance_factor(db_session, arac.id)
    assert factor > 1.0  # açık arıza → yakıt çarpanı artar
