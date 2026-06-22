"""Clock injection regression — date.today() kullanımının
app.core.utils.clock üzerinden gittiğini doğrular.

Audit (AUDIT_REPORT_FINAL) "Fake items: date.today()" işaretlediği 3
servis: dashboard_service, cost_analyzer, report_service. Bu test
monkeypatch ile sabit tarih enjekte edilebildiğini garanti eder.
"""

from __future__ import annotations

import inspect
from datetime import date


def test_clock_helper_exposes_current_date():
    """clock.current_date() default olarak gerçek bugünü döner."""
    from app.core.utils.clock import current_date

    today = current_date()
    assert isinstance(today, date)


def test_clock_helper_monkeypatchable(monkeypatch):
    """monkeypatch ile sabit tarih döndürülebilmeli."""
    fixed = date(2026, 1, 1)
    monkeypatch.setattr(
        "app.core.utils.clock.current_date",
        lambda: fixed,
    )
    from app.core.utils.clock import current_date

    assert current_date() == fixed


def test_dashboard_service_uses_clock_helper():
    """dashboard_service.py modül seviyesinde clock import etmeli."""
    import app.core.services.dashboard_service as mod

    assert hasattr(mod, "current_date"), (
        "dashboard_service date.today() yerine current_date() kullanmalı"
    )


def test_cost_analyzer_uses_clock_helper():
    import app.core.services.cost_analyzer as mod

    assert hasattr(mod, "current_date")


def test_report_service_uses_clock_helper():
    import app.core.services.report_service as mod

    assert hasattr(mod, "current_date")


def test_no_direct_date_today_in_three_services():
    """Production kodunda date.today() çağrısı bu 3 modülde olmamalı."""
    import app.core.services.cost_analyzer as cost_mod
    import app.core.services.dashboard_service as dash_mod
    import app.core.services.report_service as rep_mod

    for mod in (dash_mod, cost_mod, rep_mod):
        src = inspect.getsource(mod)
        assert "date.today()" not in src, (
            f"{mod.__name__} hala date.today() kullanıyor (clock injection bozuk)"
        )
