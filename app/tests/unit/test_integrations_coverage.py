"""Coverage tests for:
- app/core/integrations/registry.py  (0% → ≥75%)
- app/core/integrations/avl/base.py  (0% → ≥75%)
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ===========================================================================
# AVL base dataclasses & Protocol
# ===========================================================================


class TestAVLTrip:
    def test_minimal_construction(self):
        from app.core.integrations.avl.base import AVLTrip

        t = AVLTrip(
            external_id="EXT-001",
            plaka="34ABC01",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            start_lat=41.0,
            start_lon=28.9,
            end_lat=39.9,
            end_lon=32.8,
            distance_km=450.0,
        )
        assert t.external_id == "EXT-001"
        assert t.plaka == "34ABC01"
        assert t.distance_km == 450.0
        assert t.ascent_m is None
        assert t.descent_m is None
        assert t.flat_distance_km is None
        assert t.driver_external_id is None
        assert t.raw_payload == {}

    def test_full_construction(self):
        from app.core.integrations.avl.base import AVLTrip

        now = datetime.now(timezone.utc)
        t = AVLTrip(
            external_id="EXT-002",
            plaka="06DEF02",
            start_time=now,
            end_time=now,
            start_lat=41.0,
            start_lon=28.9,
            end_lat=39.9,
            end_lon=32.8,
            distance_km=300.0,
            ascent_m=1200.5,
            descent_m=1150.0,
            flat_distance_km=290.0,
            driver_external_id="DRV-99",
            raw_payload={"source": "mobiliz"},
        )
        assert t.ascent_m == 1200.5
        assert t.descent_m == 1150.0
        assert t.flat_distance_km == 290.0
        assert t.driver_external_id == "DRV-99"
        assert t.raw_payload == {"source": "mobiliz"}

    def test_raw_payload_default_is_empty_dict(self):
        from app.core.integrations.avl.base import AVLTrip

        t = AVLTrip(
            external_id="x",
            plaka="P",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            start_lat=None,
            start_lon=None,
            end_lat=None,
            end_lon=None,
            distance_km=0.0,
        )
        # Each instance gets its own dict (not shared via default_factory)
        t2 = AVLTrip(
            external_id="y",
            plaka="Q",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            start_lat=None,
            start_lon=None,
            end_lat=None,
            end_lon=None,
            distance_km=0.0,
        )
        t.raw_payload["k"] = "v"
        assert "k" not in t2.raw_payload


class TestAVLPosition:
    def test_minimal_construction(self):
        from app.core.integrations.avl.base import AVLPosition

        now = datetime.now(timezone.utc)
        pos = AVLPosition(
            external_id="V-001",
            plaka="34ABC01",
            timestamp=now,
            lat=41.05,
            lon=28.93,
        )
        assert pos.external_id == "V-001"
        assert pos.lat == 41.05
        assert pos.speed_kmh is None
        assert pos.heading_deg is None
        assert pos.raw_payload == {}

    def test_full_construction(self):
        from app.core.integrations.avl.base import AVLPosition

        pos = AVLPosition(
            external_id="V-002",
            plaka="06DEF02",
            timestamp=datetime.now(timezone.utc),
            lat=39.92,
            lon=32.85,
            speed_kmh=85.5,
            heading_deg=270.0,
            raw_payload={"gps_quality": "good"},
        )
        assert pos.speed_kmh == 85.5
        assert pos.heading_deg == 270.0
        assert pos.raw_payload["gps_quality"] == "good"

    def test_raw_payload_independent_per_instance(self):
        from app.core.integrations.avl.base import AVLPosition

        p1 = AVLPosition("a", "P1", datetime.now(timezone.utc), 1.0, 2.0)
        p2 = AVLPosition("b", "P2", datetime.now(timezone.utc), 3.0, 4.0)
        p1.raw_payload["x"] = 1
        assert "x" not in p2.raw_payload


class TestAVLProviderProtocol:
    def test_protocol_is_importable(self):
        from app.core.integrations.avl.base import AVLProvider

        assert AVLProvider is not None

    def test_protocol_has_required_methods(self):
        from app.core.integrations.avl.base import AVLProvider

        # Protocol defines these abstract stubs
        assert hasattr(AVLProvider, "fetch_trips")
        assert hasattr(AVLProvider, "fetch_positions")
        assert hasattr(AVLProvider, "healthcheck")


# ===========================================================================
# Registry
# ===========================================================================


class TestGetAvlProviderNoKey:
    def test_returns_none_when_no_avl_provider_set(self):
        from app.core.integrations.registry import get_avl_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = ""
            result = get_avl_provider()

        assert result is None

    def test_returns_none_when_avl_provider_whitespace(self):
        from app.core.integrations.registry import get_avl_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = "   "
            result = get_avl_provider()

        assert result is None

    def test_returns_none_for_unknown_provider_key(self):
        from app.core.integrations.registry import get_avl_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = "unknown_xyz"
            result = get_avl_provider()

        assert result is None

    def test_returns_provider_for_mobiliz_key(self):
        from app.core.integrations.registry import get_avl_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = "mobiliz"
            mock_settings.AVL_BASE_URL = "https://api.mobiliz.com"
            mock_settings.AVL_API_KEY = "key123"  # pragma: allowlist secret
            mock_settings.AVL_ACCOUNT_ID = "acc456"
            result = get_avl_provider()

        # MobilizAVLProvider constructor requires all three params — so it returns an instance
        assert result is not None
        assert result.provider_key == "mobiliz"

    def test_returns_none_when_provider_init_raises(self):
        """If the provider class constructor raises, registry returns None."""
        from app.core.integrations.registry import get_avl_provider

        bad_cls = MagicMock(side_effect=ValueError("bad config"))

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = "mobiliz"
            with patch.dict(
                "app.core.integrations.registry.AVL_PROVIDERS", {"mobiliz": bad_cls}
            ):
                result = get_avl_provider()

        assert result is None

    def test_avl_provider_key_is_case_insensitive(self):
        from app.core.integrations.registry import get_avl_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.AVL_PROVIDER = "MOBILIZ"
            mock_settings.AVL_BASE_URL = "https://api.mobiliz.com"
            mock_settings.AVL_API_KEY = "key"  # pragma: allowlist secret
            mock_settings.AVL_ACCOUNT_ID = "acc"
            result = get_avl_provider()

        assert result is not None


class TestGetFuelProviderNoKey:
    def test_returns_none_when_no_fuel_provider_set(self):
        from app.core.integrations.registry import get_fuel_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.FUEL_PROVIDER = ""
            result = get_fuel_provider()

        assert result is None

    def test_returns_none_for_unknown_fuel_provider(self):
        from app.core.integrations.registry import get_fuel_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.FUEL_PROVIDER = "shell"  # not in FUEL_PROVIDERS yet
            result = get_fuel_provider()

        assert result is None

    def test_returns_provider_for_opet_key(self):
        from app.core.integrations.registry import get_fuel_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.FUEL_PROVIDER = "opet"
            mock_settings.FUEL_BASE_URL = "https://api.opet.com"
            mock_settings.FUEL_API_KEY = "key123"  # pragma: allowlist secret
            mock_settings.FUEL_ACCOUNT_ID = "acc789"
            result = get_fuel_provider()

        assert result is not None
        assert result.provider_key == "opet"

    def test_returns_none_when_fuel_provider_init_raises(self):
        from app.core.integrations.registry import get_fuel_provider

        bad_cls = MagicMock(side_effect=Exception("config error"))

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.FUEL_PROVIDER = "opet"
            with patch.dict(
                "app.core.integrations.registry.FUEL_PROVIDERS", {"opet": bad_cls}
            ):
                result = get_fuel_provider()

        assert result is None

    def test_fuel_provider_key_stripped(self):
        from app.core.integrations.registry import get_fuel_provider

        with patch("app.core.integrations.registry.settings") as mock_settings:
            mock_settings.FUEL_PROVIDER = "  opet  "
            mock_settings.FUEL_BASE_URL = "https://api.opet.com"
            mock_settings.FUEL_API_KEY = "k"  # pragma: allowlist secret
            mock_settings.FUEL_ACCOUNT_ID = "a"
            result = get_fuel_provider()

        assert result is not None


class TestProviderDicts:
    def test_avl_providers_dict_contains_mobiliz(self):
        from app.core.integrations.registry import AVL_PROVIDERS

        assert "mobiliz" in AVL_PROVIDERS

    def test_fuel_providers_dict_contains_opet(self):
        from app.core.integrations.registry import FUEL_PROVIDERS

        assert "opet" in FUEL_PROVIDERS

    def test_avl_providers_values_are_classes(self):
        from app.core.integrations.registry import AVL_PROVIDERS

        for name, cls in AVL_PROVIDERS.items():
            assert isinstance(cls, type), f"{name} value should be a class"

    def test_fuel_providers_values_are_classes(self):
        from app.core.integrations.registry import FUEL_PROVIDERS

        for name, cls in FUEL_PROVIDERS.items():
            assert isinstance(cls, type), f"{name} value should be a class"
