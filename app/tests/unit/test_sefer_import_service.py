# PR-3b TODO (moved from test_dashboard_report_import_contracts.py during slice 3a):
#   Cover via real xlsx + real UoW master data (no mocks):
#   - import rejects a row whose sofor (driver) cannot be resolved -> error "Şoför bulunamadı", count 0
#   - import resolves guzergah_id for a valid row -> count 1, persisted sefer has guzergah_id set

"""SeferImportService — Excel toplu sefer import pipeline testleri.

Production hazırlığı (1000-10000 sefer):
- Excel'den parse edilmiş dict → SeferCreate Pydantic objesi (FK eşleşme +
  validation)
- bulk_add_sefer attribute erişimi yapıyor; dict göndermek runtime AttributeError
- Tarih eksikse default datetime.now() YERİNE explicit hata (geçmiş veri
  bugün damgalanmamalı)
- Excel'deki "durum" sütunu hardcoded "Planlandı" ile ezilmemeli
- GPS ascent/descent/sefer_no opsiyonel — varsa SeferCreate'e geçer
- Güzergah bulunamazsa hata değil; bulk_add_sefer fuzzy match yapacak
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest


def _make_service(items: List[Dict[str, Any]], monkeypatch):
    """SeferImportService factory + UoW master listeleri patch + parse stub.

    Master listeleri artık prod kodunda `async with UnitOfWork() as uow:`
    içinde çekiliyor; testlerin de UoW'u patch'lemesi gerek (helper kullanıyor).
    """
    from app.services.api.sefer_import_service import SeferImportService
    from app.tests._helpers.uow_mock import patch_unit_of_work

    svc = SeferImportService(
        sefer_service=AsyncMock(),
        arac_repo=AsyncMock(),
        sofor_repo=AsyncMock(),
        dorse_repo=AsyncMock(),
        lokasyon_repo=AsyncMock(),
    )
    patch_unit_of_work(
        monkeypatch,
        "app.services.api.sefer_import_service",
        arac_repo_get_all=[{"id": 1, "plaka": "34ABC123"}],
        sofor_repo_get_all=[{"id": 7, "ad_soyad": "Ali Veli"}],
        dorse_repo_get_all=[],
        lokasyon_repo_get_all=[
            {"id": 5, "cikis_yeri": "İstanbul", "varis_yeri": "Ankara"},
        ],
    )

    captured: Dict[str, Any] = {"calls": []}

    async def _bulk(sefer_list):
        captured["calls"].append(sefer_list)
        return len(sefer_list)

    svc.sefer_service.bulk_add_sefer = _bulk
    return svc, captured, items


@pytest.mark.asyncio
async def test_process_excel_import_produces_pydantic_objects(monkeypatch):
    """Eski bug: dict döndürülüyor → bulk_add_sefer AttributeError.
    Fix: SeferCreate objesi döner."""
    from app.schemas.sefer import SeferCreate

    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "net_kg": 12000.0,
            "durum": "Tamamlandı",
        },
    ]

    svc, captured, _ = _make_service(items, monkeypatch)

    async def _fake_parse(content):
        return items

    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        _fake_parse,
    )

    count, errors = await svc.process_excel_import(b"fake-bytes", current_user_id=1)
    assert count == 1, f"İmport edilen sayı yanlış: {count}, errors={errors}"
    assert errors == [], f"Beklenmedik hata: {errors}"

    # bulk_add_sefer'a giden SeferCreate listesi
    assert len(captured["calls"]) == 1
    forwarded = captured["calls"][0]
    assert len(forwarded) == 1
    assert isinstance(forwarded[0], SeferCreate), (
        "İmport service hâlâ dict döndürüyor — bulk_add_sefer attribute erişimi"
        " AttributeError verecek (1000-sefer'lik batch tamamen patlar)."
    )


@pytest.mark.asyncio
async def test_excel_status_not_overwritten_by_hardcoded_planlandi(monkeypatch):
    """Eski bug: hardcoded durum='Planlandı'. Excel'deki Tamamlandı yok sayılırdı."""
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 100.0,
            "net_kg": 5000.0,
            "durum": "Completed",
        }
    ]
    svc, captured, _ = _make_service(items, monkeypatch)
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )

    await svc.process_excel_import(b"x", current_user_id=1)
    sefer = captured["calls"][0][0]
    assert sefer.durum == "Completed", (
        f"Excel durum hardcoded ile eziliyor: {sefer.durum}"
    )


@pytest.mark.asyncio
async def test_missing_tarih_raises_explicit_error(monkeypatch):
    """Eski bug: tarih boşsa datetime.now() default → geçmiş veri bugün damgalı."""
    items = [
        {
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 100.0,
            "net_kg": 0,
        }
    ]
    svc, _, _ = _make_service(items, monkeypatch)
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 0
    assert len(errors) == 1
    assert "tarih" in errors[0]["reason"].lower(), (
        f"Tarih hatası net belirtilmemiş: {errors}"
    )


@pytest.mark.asyncio
async def test_route_not_found_does_not_block_import(monkeypatch):
    """Güzergah bulunamayan satırlar import edilebilmeli (bulk_add_sefer fuzzy
    match dener; yine yoksa guzergah_id=None ile kayıt).

    Eski davranış: route bulunamazsa hard fail → 1000 farklı şehir
    kombinasyonu varsa hiçbiri import edilmiyordu.
    """
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "Bursa",  # lokasyonlar tablosunda YOK
            "varis_yeri": "İzmir",
            "mesafe_km": 350.0,
            "net_kg": 8000.0,
        }
    ]
    svc, captured, _ = _make_service(items, monkeypatch)
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 1, f"Güzergah eksikliği import'u bloklamamalı: errors={errors}"
    sefer = captured["calls"][0][0]
    # guzergah_id None olarak geçer — bulk_add_sefer kendisi yine arar
    assert sefer.guzergah_id is None


@pytest.mark.asyncio
async def test_gps_fields_propagated(monkeypatch):
    """ascent_m/descent_m/sefer_no Excel'de varsa SeferCreate'e geçer."""
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "net_kg": 12000.0,
            "ascent_m": 320.0,
            "descent_m": 180.0,
            "sefer_no": "SEF-2026-001",
        }
    ]
    svc, captured, _ = _make_service(items, monkeypatch)
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )

    await svc.process_excel_import(b"x", current_user_id=1)
    sefer = captured["calls"][0][0]
    assert sefer.ascent_m == 320.0
    assert sefer.descent_m == 180.0
    assert sefer.sefer_no == "SEF-2026-001"


@pytest.mark.asyncio
async def test_unknown_plaka_or_driver_returns_row_error(monkeypatch):
    """Bulunamayan plaka/şoför satır error olarak listelenir, diğerleri import."""
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "00 GHOST 0",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 100.0,
            "net_kg": 0,
        },
        {
            "tarih": date(2026, 5, 2),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 200.0,
            "net_kg": 0,
        },
    ]
    svc, captured, _ = _make_service(items, monkeypatch)
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 1
    assert len(errors) == 1
    assert (
        "araç" in errors[0]["reason"].lower() or "arac" in errors[0]["reason"].lower()
    )


def test_resolve_master_id_unique_match():
    """Tek eşleşen kayıt → doğru ID döner."""
    from unittest.mock import AsyncMock

    from app.services.api.sefer_import_service import SeferImportService

    svc = SeferImportService(
        sefer_service=AsyncMock(),
        arac_repo=AsyncMock(),
        sofor_repo=AsyncMock(),
        dorse_repo=AsyncMock(),
        lokasyon_repo=AsyncMock(),
    )
    drivers = [
        {"id": 1, "ad_soyad": "Ali Veli"},
        {"id": 2, "ad_soyad": "Mehmet Kaya"},
    ]
    assert svc._resolve_master_id("Ali Veli", drivers, "ad_soyad") == 1


def test_resolve_master_id_ambiguous_returns_none():
    """Aynı isimli iki kayıt → None (sessiz yanlış atama yerine import hatası)."""
    from unittest.mock import AsyncMock

    from app.services.api.sefer_import_service import SeferImportService

    svc = SeferImportService(
        sefer_service=AsyncMock(),
        arac_repo=AsyncMock(),
        sofor_repo=AsyncMock(),
        dorse_repo=AsyncMock(),
        lokasyon_repo=AsyncMock(),
    )
    drivers = [
        {"id": 1, "ad_soyad": "Ahmet Yılmaz"},
        {"id": 2, "ad_soyad": "Ahmet Yılmaz"},
    ]
    result = svc._resolve_master_id("Ahmet Yılmaz", drivers, "ad_soyad")
    assert result is None


def test_resolve_master_id_no_match_returns_none():
    """Eşleşme yoksa None döner."""
    from unittest.mock import AsyncMock

    from app.services.api.sefer_import_service import SeferImportService

    svc = SeferImportService(
        sefer_service=AsyncMock(),
        arac_repo=AsyncMock(),
        sofor_repo=AsyncMock(),
        dorse_repo=AsyncMock(),
        lokasyon_repo=AsyncMock(),
    )
    drivers = [{"id": 1, "ad_soyad": "Ali Veli"}]
    assert svc._resolve_master_id("Bilinmiyor", drivers, "ad_soyad") is None
