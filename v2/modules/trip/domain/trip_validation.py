"""Saf sefer validasyon/normalizasyon yardımcıları (I/O yok)."""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, cast

from v2.modules.shared_kernel.exceptions import RouteProcessingError
from v2.modules.trip.schemas import SeferCreate, TripStatus
from v2.modules.trip.sefer_status import (
    SEFER_STATUS_PLANLANDI,
    ensure_canonical_sefer_status,
)

# Yalnızca canonical durumlar (Planned/Completed/Cancelled) — DB CHECK ile
# birebir. ASSIGNED/IN_PROGRESS DB'de yok (ensure_canonical_sefer_status
# reddeder) ve eski geçiş tanımları ölü koddu (ARCH-003).
#
# NOT: `v2.modules.trip.trip_status.TRIP_STATUS_TRANSITIONS` ile
# KARIŞTIRILMAMALI — o daha kısıtlayıcı bir sözlük (Cancelled'dan hiçbir
# yere geçiş yok); bu sözlük Cancelled → Planned'e izin verir ("Allow
# re-planning after cancellation") ve yalnızca yazma yolunun (update_sefer)
# gerçek enforcement'ıdır.
ALLOWED_TRANSITIONS: Dict[TripStatus, List[TripStatus]] = {
    TripStatus.PLANNED: [
        TripStatus.COMPLETED,
        TripStatus.CANCELLED,
    ],
    TripStatus.COMPLETED: [],  # Terminal
    TripStatus.CANCELLED: [TripStatus.PLANNED],  # Allow re-planning after cancellation
}


def safe_durum(value: object) -> str:
    """Coerce a sefer durum to a canonical value (Planned/Completed/Cancelled).

    Folds Turkish/legacy values; for empty or unmappable input falls back to
    Planned instead of inserting a raw value that violates the DB durum-enum
    CHECK constraint (Sentry LOJINEXT-19G/19H on bulk Excel import).
    """
    try:
        return (
            ensure_canonical_sefer_status(cast(Optional[str], value), allow_none=False)
            or SEFER_STATUS_PLANLANDI
        )
    except ValueError:
        return SEFER_STATUS_PLANLANDI


def validate_sefer_create(data: "SeferCreate", trip_date: date) -> None:
    """Temel sefer oluşturma validasyonları."""
    if data.cikis_yeri == data.varis_yeri:
        raise RouteProcessingError(
            "Çıkış ve varış yeri aynı olamaz",
            field_name="cikis_yeri",
            reason="SAME_ORIGIN_DESTINATION",
        )
    if data.mesafe_km <= 0:
        raise RouteProcessingError(
            "Mesafe 0'dan büyük olmalıdır",
            field_name="mesafe_km",
            reason="INVALID_DISTANCE",
        )
    if trip_date > date.today() + timedelta(days=365):
        raise RouteProcessingError(
            "Sefer tarihi 1 yıldan daha ileri bir tarih olamaz",
            field_name="tarih",
            reason="DATE_TOO_FAR",
        )


def sync_weight_fields(data: "SeferCreate", arac: Dict[str, Any]) -> None:
    """bos/dolu/net ağırlık tutarlılığını in-place sağlar."""
    b_kg = data.bos_agirlik_kg or arac.get("bos_agirlik_kg", 0)
    n_kg = data.net_kg or 0
    d_kg = data.dolu_agirlik_kg or (b_kg + n_kg)
    if data.dolu_agirlik_kg:
        n_kg = d_kg - b_kg
    else:
        d_kg = b_kg + n_kg
    # Negatif net kargo fiziksel olarak imkânsız. Schema her alanı tek tek
    # ge=0 doğruluyor ama dolu<bos ilişkisini görmüyor; DB CHECK ise yalnız
    # ``net = dolu - bos`` aritmetiğini sağladığından negatif net'i kabul
    # eder (örn. net=-2000 = 3000-5000). Negatif ton tahmini de bozar —
    # burada erken ve dostça reddet (endpoint → 400).
    if n_kg < 0:
        raise ValueError(
            "Dolu ağırlık boş ağırlıktan küçük olamaz "
            f"(boş={b_kg} kg, dolu={d_kg} kg → net={n_kg} kg)."
        )
    data.bos_agirlik_kg = b_kg
    data.dolu_agirlik_kg = d_kg
    data.net_kg = n_kg
    data.ton = round(n_kg / 1000.0, 2)
