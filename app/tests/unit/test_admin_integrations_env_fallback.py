"""_env_fallback_present() — mapbox/openroute/groq have a backend-visible
env fallback (settings.<X>_API_KEY, passed as env_fallback at each
get_integration_secret() call site), unlike the 2 bot services whose token
is only known to their own container. Same underlying "configured DB flag
!= actually working" issue as the bot containers, one level milder since
the backend can see this one itself — no docker-socket-proxy needed."""

from pydantic import SecretStr

from v2.modules.admin_platform.api.admin_integrations_routes import (
    _env_fallback_present,
)


def test_mapbox_present(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.MAPBOX_API_KEY",
        SecretStr("pk.fake"),  # pragma: allowlist secret
    )
    assert _env_fallback_present("mapbox") is True


def test_mapbox_absent_when_none(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.MAPBOX_API_KEY", None
    )
    assert _env_fallback_present("mapbox") is False


def test_mapbox_absent_when_empty_secret(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.MAPBOX_API_KEY",
        SecretStr(""),
    )
    assert _env_fallback_present("mapbox") is False


def test_openroute_present(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.OPENROUTESERVICE_API_KEY",
        "fake-key",  # pragma: allowlist secret
    )
    assert _env_fallback_present("openroute") is True


def test_openroute_absent_when_empty(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.OPENROUTESERVICE_API_KEY",
        "",
    )
    assert _env_fallback_present("openroute") is False


def test_groq_present(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.GROQ_API_KEY",
        SecretStr("gsk-fake"),  # pragma: allowlist secret
    )
    assert _env_fallback_present("groq") is True


def test_groq_absent_when_none(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.admin_platform.api.admin_integrations_routes.settings.GROQ_API_KEY", None
    )
    assert _env_fallback_present("groq") is False


def test_bot_services_return_none():
    """Bot tokens aren't backend-visible env fallbacks — handled entirely
    via container_health.get_container_status() instead."""
    assert _env_fallback_present("telegram_driver_bot") is None
    assert _env_fallback_present("telegram_ops_bot") is None
