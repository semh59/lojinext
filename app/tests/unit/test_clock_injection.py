"""Clock injection regression — date.today() kullanımının
app.core.utils.clock üzerinden gittiğini doğrular.

Audit (AUDIT_REPORT_FINAL) "Fake items: date.today()" işaretlediği
servisler: analytics_executive'in cost analizi (analyze_costs.py),
report_service. Bu test monkeypatch ile sabit tarih enjekte
edilebildiğini garanti eder.
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


def test_cost_analyzer_uses_clock_helper():
    import v2.modules.analytics_executive.application.analyze_costs as mod

    assert hasattr(mod, "current_date")


def test_report_service_uses_clock_helper():
    import v2.modules.reports.application.generate_fleet_summary as mod

    assert hasattr(mod, "current_date")


def test_no_direct_date_today_in_three_services():
    """Production kodunda date.today() çağrısı bu modüllerde olmamalı.

    dalga 10'da report_service.py application/generate_fleet_summary.py +
    generate_vehicle_report.py + generate_monthly_trend.py'ye bölündü (B.1
    free-function refactor) — üçü de current_date() kullanıyor.
    """
    import v2.modules.analytics_executive.application.analyze_costs as cost_mod
    import v2.modules.reports.application.generate_fleet_summary as fleet_mod
    import v2.modules.reports.application.generate_monthly_trend as trend_mod
    import v2.modules.reports.application.generate_vehicle_report as vehicle_mod

    for mod in (cost_mod, fleet_mod, vehicle_mod, trend_mod):
        src = inspect.getsource(mod)
        assert "date.today()" not in src, (
            f"{mod.__name__} hala date.today() kullanıyor (clock injection bozuk)"
        )
