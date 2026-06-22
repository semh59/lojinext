from pydantic import ValidationError

from app.config import Settings


def _set_required_env(monkeypatch, *, environment: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./routing-config-test.db")


def test_settings_allow_missing_openroute_key_in_dev(monkeypatch):
    _set_required_env(monkeypatch, environment="dev")
    monkeypatch.delenv("OPENROUTESERVICE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTE_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.OPENROUTESERVICE_API_KEY == ""


def test_settings_require_openroute_key_in_prod(monkeypatch):
    _set_required_env(monkeypatch, environment="prod")
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("GROQ_API_KEY", "prod-groq-key")
    monkeypatch.setenv("HF_TOKEN", "prod-hf-token")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    monkeypatch.delenv("OPENROUTESERVICE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTE_API_KEY", raising=False)

    try:
        Settings(_env_file=None)
    except ValidationError as exc:
        assert "OPENROUTESERVICE_API_KEY zorunlu" in str(exc)
    else:
        raise AssertionError("prod ortaminda routing key zorunlu olmaliydi")


def test_settings_reject_wildcard_cors_in_prod(monkeypatch):
    """Wildcard CORS + allow_credentials=True lets any origin make
    authenticated requests — must be rejected at startup in prod."""
    _set_required_env(monkeypatch, environment="prod")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("OPENROUTESERVICE_API_KEY", "prod-ors-key")
    monkeypatch.setenv("INTERNAL_API_SECRET", "prod-internal-secret")

    try:
        Settings(_env_file=None)
    except ValidationError as exc:
        assert "CORS_ORIGINS cannot be '*'" in str(exc)
    else:
        raise AssertionError("prod ortaminda wildcard CORS reddedilmeliydi")


def test_settings_allow_wildcard_cors_in_dev(monkeypatch):
    """Dev convenience: wildcard CORS is permitted outside production."""
    _set_required_env(monkeypatch, environment="dev")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["*"]
