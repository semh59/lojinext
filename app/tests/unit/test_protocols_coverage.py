"""
Coverage tests for app/core/protocols.py
Tests runtime_checkable Protocol isinstance checks and method signatures.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pytest

from app.core.protocols import (
    IDriverService,
    IFuelService,
    IInternalService,
    ITripService,
    IVehicleService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Concrete stub implementations for protocol conformance checks
# ---------------------------------------------------------------------------


class StubTripService:
    async def get_sefer_by_id(
        self, sefer_id: int, current_user: Any = None
    ) -> Optional[Dict]:
        return {"id": sefer_id}

    async def get_all_paged(self, **kwargs) -> Dict[str, Any]:
        return {"items": [], "total": 0}

    async def create_sefer(self, data: Any) -> int:
        return 1

    async def update_sefer(self, sefer_id: int, data: Any) -> bool:
        return True

    async def delete_sefer(self, sefer_id: int) -> bool:
        return True

    async def set_onay_durumu(
        self,
        sefer_id: int,
        yeni_durum: str,
        onay_notu: Optional[str] = None,
        onaylayan_id: Optional[int] = None,
    ) -> Optional[Dict]:
        return {"sefer_id": sefer_id, "durum": yeni_durum}

    async def get_by_onay_durumu(
        self, onay_durumu: str, skip: int = 0, limit: int = 50
    ) -> List[Dict]:
        return []


class StubDriverService:
    async def get_sofor_by_id(self, sofor_id: int) -> Optional[Dict]:
        return {"id": sofor_id}

    async def get_all_paged(self, **kwargs) -> Dict[str, Any]:
        return {"items": []}

    async def add_sofor(self, data: Any) -> int:
        return 42

    async def update_sofor(self, sofor_id: int, data: Any) -> bool:
        return True

    async def delete_sofor(self, sofor_id: int) -> bool:
        return True


class StubVehicleService:
    async def get_arac_by_id(self, arac_id: int) -> Optional[Dict]:
        return {"id": arac_id}

    async def get_all_paged(self, **kwargs) -> Dict[str, Any]:
        return {"items": []}

    async def add_arac(self, data: Any) -> int:
        return 7

    async def update_arac(self, arac_id: int, data: Any) -> bool:
        return True

    async def delete_arac(self, arac_id: int) -> bool:
        return False


class StubFuelService:
    async def get_yakit_by_id(self, yakit_id: int) -> Optional[Dict]:
        return {"id": yakit_id}

    async def get_all_paged(self, **kwargs) -> Dict[str, Any]:
        return {"items": []}

    async def add_yakit(self, data: Any) -> int:
        return 99

    async def get_stats(self, **kwargs) -> Dict[str, Any]:
        return {"total_lt": 1000}


class StubInternalService:
    async def get_sofor_by_telegram_id(self, telegram_id: str) -> Optional[Dict]:
        return {"telegram_id": telegram_id}

    async def kaydet_belge(
        self,
        telegram_id: str,
        belge_tipi: str,
        image_bytes: bytes,
        content_type: str,
        telegram_mesaj_id: Optional[int] = None,
    ) -> Dict:
        return {"saved": True}

    async def get_seferler(
        self, telegram_id: str, limit: int = 10
    ) -> Optional[List[Dict]]:
        return []

    async def get_sofor_id(self, telegram_id: str) -> Optional[int]:
        return 5

    async def olustur_pdf(
        self, telegram_id: str, baslangic: date, bitis: date
    ) -> Optional[bytes]:
        return b"%PDF-1.4"


# ---------------------------------------------------------------------------
# Protocol isinstance tests (runtime_checkable)
# ---------------------------------------------------------------------------


def test_itrip_service_isinstance_with_stub():
    """Stub with all methods should satisfy isinstance check."""
    svc = StubTripService()
    assert isinstance(svc, ITripService)


def test_idriver_service_isinstance_with_stub():
    svc = StubDriverService()
    assert isinstance(svc, IDriverService)


def test_ivehicle_service_isinstance_with_stub():
    svc = StubVehicleService()
    assert isinstance(svc, IVehicleService)


def test_ifuel_service_isinstance_with_stub():
    svc = StubFuelService()
    assert isinstance(svc, IFuelService)


def test_iinternal_service_isinstance_with_stub():
    svc = StubInternalService()
    assert isinstance(svc, IInternalService)


def test_plain_object_not_itrip_service():
    """Object missing methods fails isinstance."""
    assert not isinstance(object(), ITripService)


def test_plain_object_not_idriver_service():
    assert not isinstance(object(), IDriverService)


def test_plain_object_not_ivehicle_service():
    assert not isinstance(object(), IVehicleService)


def test_plain_object_not_ifuel_service():
    assert not isinstance(object(), IFuelService)


def test_plain_object_not_iinternal_service():
    assert not isinstance(object(), IInternalService)


# ---------------------------------------------------------------------------
# Async method calls through the Protocol interface
# ---------------------------------------------------------------------------


async def test_itrip_create_and_get():
    svc: ITripService = StubTripService()
    trip_id = await svc.create_sefer({"plaka": "34ABC"})
    assert trip_id == 1
    result = await svc.get_sefer_by_id(trip_id)
    assert result["id"] == 1


async def test_itrip_update_and_delete():
    svc: ITripService = StubTripService()
    assert await svc.update_sefer(1, {}) is True
    assert await svc.delete_sefer(1) is True


async def test_itrip_set_onay_durumu_with_optional_args():
    svc: ITripService = StubTripService()
    result = await svc.set_onay_durumu(5, "onaylandi")
    assert result["durum"] == "onaylandi"
    # with optional kwargs
    result2 = await svc.set_onay_durumu(
        5, "reddedildi", onay_notu="sebep", onaylayan_id=2
    )
    assert result2 is not None


async def test_itrip_get_by_onay_durumu_defaults():
    svc: ITripService = StubTripService()
    items = await svc.get_by_onay_durumu("beklemede")
    assert isinstance(items, list)


async def test_itrip_get_all_paged_kwargs():
    svc: ITripService = StubTripService()
    page = await svc.get_all_paged(skip=0, limit=10, filtre="all")
    assert "items" in page


async def test_idriver_service_calls():
    svc: IDriverService = StubDriverService()
    new_id = await svc.add_sofor({"ad": "Ali"})
    assert new_id == 42
    found = await svc.get_sofor_by_id(new_id)
    assert found["id"] == 42
    assert await svc.update_sofor(42, {}) is True
    assert await svc.delete_sofor(42) is True
    page = await svc.get_all_paged(limit=5)
    assert "items" in page


async def test_ivehicle_service_calls():
    svc: IVehicleService = StubVehicleService()
    new_id = await svc.add_arac({"plaka": "06XYZ"})
    assert new_id == 7
    found = await svc.get_arac_by_id(new_id)
    assert found["id"] == 7
    assert await svc.update_arac(7, {}) is True
    assert await svc.delete_arac(7) is False  # stub returns False
    page = await svc.get_all_paged()
    assert "items" in page


async def test_ifuel_service_calls():
    svc: IFuelService = StubFuelService()
    new_id = await svc.add_yakit({"litre": 100})
    assert new_id == 99
    found = await svc.get_yakit_by_id(new_id)
    assert found["id"] == 99
    stats = await svc.get_stats(start="2025-01-01")
    assert "total_lt" in stats
    page = await svc.get_all_paged(limit=20)
    assert "items" in page


async def test_iinternal_service_calls():
    svc: IInternalService = StubInternalService()
    sofor = await svc.get_sofor_by_telegram_id("tg123")
    assert sofor["telegram_id"] == "tg123"
    sofor_id = await svc.get_sofor_id("tg123")
    assert sofor_id == 5
    seferler = await svc.get_seferler("tg123", limit=5)
    assert seferler == []
    pdf = await svc.olustur_pdf("tg123", date(2025, 1, 1), date(2025, 1, 31))
    assert pdf is not None


async def test_iinternal_kaydet_belge():
    svc: IInternalService = StubInternalService()
    result = await svc.kaydet_belge(
        "tg456", "cmr", b"\x89PNG", "image/png", telegram_mesaj_id=100
    )
    assert result["saved"] is True


async def test_iinternal_kaydet_belge_no_message_id():
    svc: IInternalService = StubInternalService()
    result = await svc.kaydet_belge("tg789", "fatura", b"data", "application/pdf")
    assert result["saved"] is True
