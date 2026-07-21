"""Test edilebilir saat/tarih sağlayıcı (clock injection).

date.today() ve datetime.now() doğrudan kullanımı test izolasyonunu
bozar (her test günü farklı sonuç, timezone bug'ı). Production kodu
bu helper üzerinden çağırırsa testlerde monkeypatch ile sabitlenebilir:

    monkeypatch.setattr(
        "v2.modules.shared_kernel.utils.clock.current_date",
        lambda: date(2026, 6, 15),
    )

Audit (AUDIT_REPORT_FINAL) "Fake items: date.today()" olarak işaretlediği
servisler (analytics_executive'in cost analizi, reports) bu helper'ı
kullanır.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def current_date() -> date:
    """Bugünün tarihi — production: date.today(), test: monkeypatched."""
    return date.today()


def current_datetime_utc() -> datetime:
    """Şu anki UTC datetime — production: datetime.now(tz=utc), test: monkeypatched."""
    return datetime.now(timezone.utc)
