import hashlib
import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


class TestLicenseService:
    def test_service_exists(self):
        from app.core.services.license_service import LicenseEngine

        assert LicenseEngine is not None

    def test_basic_initialization(self):
        from app.core.services.license_service import LicenseEngine

        engine = LicenseEngine()
        assert engine.tier == "FREE"
        assert engine.license_key is None

    def test_validate_license_key_empty_returns_free(self):
        from app.core.services.license_service import LicenseEngine

        engine = LicenseEngine()
        assert engine._validate_license_key("") == "FREE"

    def test_validate_license_key_unknown_returns_free(self):
        from app.core.services.license_service import LicenseEngine

        engine = LicenseEngine()
        assert engine._validate_license_key("random-unknown-key-xyz") == "FREE"

    def test_validate_license_key_pro_via_env(self):
        from app.core.services.license_service import LicenseEngine

        pro_key = "super-secret-pro-key-2024"
        pro_hash = hashlib.sha256(pro_key.encode()).hexdigest()

        with patch.dict(os.environ, {"LICENSE_PRO_HASH": pro_hash}):
            engine = LicenseEngine()

        result = engine._validate_license_key(pro_key)
        assert result == "PRO"

    def test_validate_license_key_enterprise_via_env(self):
        from app.core.services.license_service import LicenseEngine

        ent_key = "enterprise-license-key-2024"
        ent_hash = hashlib.sha256(ent_key.encode()).hexdigest()

        with patch.dict(os.environ, {"LICENSE_ENTERPRISE_HASH": ent_hash}):
            engine = LicenseEngine()

        result = engine._validate_license_key(ent_key)
        assert result == "ENTERPRISE"

    def test_limits_structure(self):
        from app.core.services.license_service import LicenseEngine

        assert "FREE" in LicenseEngine.LIMITS
        assert "PRO" in LicenseEngine.LIMITS
        assert "ENTERPRISE" in LicenseEngine.LIMITS
        assert (
            LicenseEngine.LIMITS["FREE"]["max_cars"]
            < LicenseEngine.LIMITS["PRO"]["max_cars"]
        )

    def test_edge_case_none_key_defaults_to_free(self):
        from app.core.services.license_service import LicenseEngine

        engine = LicenseEngine()
        # None treated as empty string → FREE
        result = engine._validate_license_key(None or "")
        assert result == "FREE"

    async def test_get_current_tier_no_key_in_db_returns_free(self, db_session):
        from app.core.services.license_service import LicenseEngine

        tier = await LicenseEngine().get_current_tier()  # no LICENSE_KEY row → FREE
        assert tier == "FREE"

    async def test_get_current_tier_pro_key_in_db(self, db_session):
        from app.core.services.license_service import LicenseEngine
        from app.tests._helpers.seed import seed_sistem_konfig

        pro_key = "pro-db-key-test"
        pro_hash = hashlib.sha256(pro_key.encode()).hexdigest()
        await seed_sistem_konfig(db_session, anahtar="LICENSE_KEY", deger=pro_key)
        await db_session.commit()
        with patch.dict(os.environ, {"LICENSE_PRO_HASH": pro_hash}):
            engine = LicenseEngine()  # picks up env hash at __init__
            tier = await engine.get_current_tier()
        assert tier == "PRO"

    async def test_check_car_limit_free_tier_under_limit(self, db_session):
        from app.core.services.license_service import LicenseEngine
        from app.tests._helpers.seed import seed_arac

        for i in range(3):
            await seed_arac(db_session, plaka=f"34CAR{i:03d}")
        await db_session.commit()
        assert await LicenseEngine().check_car_limit() is True  # 3 < 5 → True

    async def test_check_car_limit_free_tier_at_limit(self, db_session):
        from app.core.services.license_service import LicenseEngine
        from app.tests._helpers.seed import seed_arac

        for i in range(5):
            await seed_arac(db_session, plaka=f"34LIM{i:03d}")
        await db_session.commit()
        assert await LicenseEngine().check_car_limit() is False  # 5 >= 5 → False
