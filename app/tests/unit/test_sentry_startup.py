"""Tests for Sentry startup warning in _wire_observability."""

from unittest.mock import MagicMock, patch


def test_sentry_warns_when_dsn_missing_in_production():
    """Must call logger.warning when ENVIRONMENT=production and SENTRY_DSN is unset."""
    with (
        patch("app.config.settings.SENTRY_DSN", None),
        patch("app.config.settings.ENVIRONMENT", "production"),
        patch("app.main.logger") as mock_logger,
    ):
        from app.main import _wire_observability

        fake_app = MagicMock()
        _wire_observability(fake_app)

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("SENTRY_DSN not set" in c for c in warning_calls), (
        f"Expected logger.warning('SENTRY_DSN not set ...'). Calls: {warning_calls}"
    )


def test_sentry_no_warn_in_dev_without_dsn():
    """Must NOT call SENTRY_DSN warning in non-production environments."""
    with (
        patch("app.config.settings.SENTRY_DSN", None),
        patch("app.config.settings.ENVIRONMENT", "development"),
        patch("app.main.logger") as mock_logger,
    ):
        from app.main import _wire_observability

        fake_app = MagicMock()
        _wire_observability(fake_app)

    warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
    sentry_warnings = [c for c in warning_calls if "SENTRY_DSN not set" in c]
    assert len(sentry_warnings) == 0, (
        f"Should not warn about SENTRY_DSN in dev. Got: {sentry_warnings}"
    )
