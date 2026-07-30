"""P5.1's 10 reference routes — single source of truth for physics
calibration (scripts/calibrate_physics.py and the weekly recalibration
Celery task both import this instead of each keeping their own copy).

lokasyon_id -> (name, load_tons, band_low, band_high). Bands are DAF/ICCT
literature consumption ranges (koşul-nötr, L/100km) for a loaded HGV on
each route type.
"""

from __future__ import annotations

REFERENCE_ROUTES: dict[int, tuple[str, int, float, float]] = {
    3: ("IST-ANK", 20, 30.0, 35.0),
    4: ("IST-IZM", 18, 29.0, 33.0),
    5: ("BUR-IST", 12, 28.0, 32.0),
    6: ("ANK-KON", 25, 31.0, 36.0),
    7: ("IST-BOL", 22, 34.0, 40.0),
    8: ("IZM-AYD", 14, 28.0, 33.0),
    9: ("ANK-ESK", 19, 30.0, 35.0),
    10: ("IST-TEK", 16, 29.0, 34.0),
    11: ("KON-AKS", 23, 32.0, 37.0),
    12: ("BUR-BAL", 17, 30.0, 35.0),
}

# Physical bounds (overfit guard) for the calibration grid search.
CDA_BAND: tuple[float, float] = (5.3, 7.5)
PAR_BAND: tuple[float, float] = (3.0, 12.0)
