"""Reports v2 RV2.5 — Reports Studio template list tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from v2.modules.reports.api.studio_routes import _TEMPLATES, list_templates
from v2.modules.reports.schemas import TemplateMeta


class _FakeUser:
    """get_current_active_user için minimum kullanıcı stub'ı."""

    id = 1
    username = "test"


@pytest.mark.asyncio
async def test_list_templates_returns_all_six(monkeypatch):
    """6 statik şablonun tamamı dönmeli (plan §5.1)."""
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "REPORTS_V2_ENABLED", True)

    result = await list_templates(current_user=_FakeUser())
    assert result.count == 6
    assert len(result.templates) == 6


@pytest.mark.asyncio
async def test_list_templates_unique_ids(monkeypatch):
    """Şablon id'leri benzersiz olmalı."""
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "REPORTS_V2_ENABLED", True)

    result = await list_templates(current_user=_FakeUser())
    ids = [t.id for t in result.templates]
    assert len(set(ids)) == len(ids)


@pytest.mark.asyncio
async def test_list_templates_disabled_returns_503(monkeypatch):
    """Flag kapalıysa 503."""
    from fastapi import HTTPException

    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "REPORTS_V2_ENABLED", False)

    with pytest.raises(HTTPException) as exc:
        await list_templates(current_user=_FakeUser())
    assert exc.value.status_code == 503


def test_static_templates_shape():
    """Statik liste içeriği — kategori dağılımı + format zorunluluğu."""
    # En az 1 executive + 1 fleet + 1 compliance olmalı (persona kapsamı)
    cats = {t.category for t in _TEMPLATES}
    assert "executive" in cats
    assert "fleet" in cats
    assert "compliance" in cats
    # Her şablonun en az 1 formatı olmalı
    for tmpl in _TEMPLATES:
        assert len(tmpl.formats) >= 1
        # endpoint_hint dolu
        assert tmpl.endpoint_hint.startswith("/")


def test_template_meta_pydantic_validation():
    """TemplateMeta schema'sı yanlış kategori reddetmeli."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TemplateMeta(  # type: ignore[call-arg]
            id="ceo_1pager",
            title="x",
            description="y",
            category="bogus",  # type: ignore[arg-type]
            formats=["pdf"],
            endpoint_hint="/x",
        )


@pytest.mark.integration
def test_list_templates_via_http(monkeypatch):
    """HTTP üzerinden çağrı (auth bypass + flag aç)."""
    from app.config import settings as app_settings
    from app.main import app
    from v2.modules.auth_rbac.public import get_current_active_user

    monkeypatch.setattr(app_settings, "REPORTS_V2_ENABLED", True)

    async def _fake_user():
        return _FakeUser()

    app.dependency_overrides[get_current_active_user] = _fake_user
    try:
        with TestClient(app) as client:
            r = client.get("/api/v1/reports/studio/templates")
            assert r.status_code == 200
            body = r.json()
            assert body["count"] == 6
            assert len(body["templates"]) == 6
            assert {"id", "title", "category", "formats"}.issubset(
                body["templates"][0].keys()
            )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
