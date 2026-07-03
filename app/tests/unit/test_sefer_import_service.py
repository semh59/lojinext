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

Master listeleri (arac/sofor/dorse/lokasyon) artık GERÇEK DB'den çekiliyor:
``process_excel_import`` kendi ``async with UnitOfWork()`` içinde
``uow.arac_repo.get_all(...)`` çağırır. Testler gerçek satır seed eder ve
gerçek repo sorgusunu + ORM-attribute lookup yolunu (üretimdeki ``getattr``
dalı, dict ``.get`` değil) çalıştırır. Sadece ``bulk_add_sefer`` (ayrı
SeferService sınırı) bir capture closure ile yakalanır — üretilen
SeferCreate listesi test edilen birimin çıktısıdır.

Excel parse (``parse_sefer_excel``) stub'lanır: xlsx ayrıştırma ayrı bir
birim (ExcelService) ve kendi testlerine sahip; buradaki birim parse
edilmiş satırlardan FK çözüp SeferCreate kuran mantıktır.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

from app.tests._helpers.seed import seed_arac, seed_lokasyon, seed_sofor

pytestmark = pytest.mark.integration


async def _make_service(db_session, *, seed_route=True):
    """Seed real master data and build SeferImportService with a bulk capture.

    Returns (service, captured). ``captured["calls"]`` collects each
    ``bulk_add_sefer`` argument list so tests can assert on the built
    SeferCreate objects.
    """
    from app.services.api.sefer_import_service import SeferImportService

    await seed_arac(db_session, plaka="34ABC123")
    await seed_sofor(db_session, ad_soyad="Ali Veli")
    if seed_route:
        await seed_lokasyon(db_session, cikis_yeri="İstanbul", varis_yeri="Ankara")
    await db_session.commit()

    captured: Dict[str, Any] = {"calls": []}

    async def _bulk(sefer_list):
        captured["calls"].append(sefer_list)
        return len(sefer_list)

    svc = SeferImportService(
        sefer_service=SimpleNamespace(bulk_add_sefer=_bulk),
        arac_repo=None,
        sofor_repo=None,
        dorse_repo=None,
        lokasyon_repo=None,
    )
    return svc, captured


def _stub_parse(monkeypatch, items: List[Dict[str, Any]]):
    monkeypatch.setattr(
        "app.core.services.excel_service.ExcelService.parse_sefer_excel",
        AsyncMock(return_value=items),
    )


# --- real DB master data ---------------------------------------------------


async def test_process_excel_import_produces_pydantic_objects(db_session, monkeypatch):
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
    svc, captured = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"fake-bytes", current_user_id=1)
    assert count == 1, f"İmport edilen sayı yanlış: {count}, errors={errors}"
    assert errors == [], f"Beklenmedik hata: {errors}"

    assert len(captured["calls"]) == 1
    forwarded = captured["calls"][0]
    assert len(forwarded) == 1
    assert isinstance(forwarded[0], SeferCreate), (
        "İmport service hâlâ dict döndürüyor — bulk_add_sefer attribute erişimi"
        " AttributeError verecek (1000-sefer'lik batch tamamen patlar)."
    )


async def test_excel_status_not_overwritten_by_hardcoded_planlandi(
    db_session, monkeypatch
):
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
    svc, captured = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    await svc.process_excel_import(b"x", current_user_id=1)
    sefer = captured["calls"][0][0]
    assert sefer.durum == "Completed", (
        f"Excel durum hardcoded ile eziliyor: {sefer.durum}"
    )


async def test_missing_tarih_raises_explicit_error(db_session, monkeypatch):
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
    svc, _ = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 0
    assert len(errors) == 1
    assert "tarih" in errors[0]["reason"].lower(), (
        f"Tarih hatası net belirtilmemiş: {errors}"
    )


async def test_route_not_found_does_not_block_import(db_session, monkeypatch):
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
    svc, captured = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 1, f"Güzergah eksikliği import'u bloklamamalı: errors={errors}"
    sefer = captured["calls"][0][0]
    # guzergah_id None olarak geçer — bulk_add_sefer kendisi yine arar
    assert sefer.guzergah_id is None


async def test_route_id_resolved_for_known_lokasyon(db_session, monkeypatch):
    """PR-3b: bilinen cikis/varis için guzergah_id gerçek lokasyon satırından çözülür."""
    lok = await seed_lokasyon(db_session, cikis_yeri="Mersin", varis_yeri="Gaziantep")
    await db_session.commit()
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Ali Veli",
            "cikis_yeri": "Mersin",
            "varis_yeri": "Gaziantep",
            "mesafe_km": 600.0,
            "net_kg": 10000.0,
        }
    ]
    # seed_arac/sofor only; route already seeded above.
    svc, captured = await _make_service(db_session, seed_route=False)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 1, f"errors={errors}"
    sefer = captured["calls"][0][0]
    assert sefer.guzergah_id == lok.id


async def test_gps_fields_propagated(db_session, monkeypatch):
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
    svc, captured = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    await svc.process_excel_import(b"x", current_user_id=1)
    sefer = captured["calls"][0][0]
    assert sefer.ascent_m == 320.0
    assert sefer.descent_m == 180.0
    assert sefer.sefer_no == "SEF-2026-001"


async def test_unknown_plaka_returns_row_error(db_session, monkeypatch):
    """Bulunamayan plaka satır error olarak listelenir, diğerleri import."""
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
    svc, captured = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 1
    assert len(errors) == 1
    assert (
        "araç" in errors[0]["reason"].lower() or "arac" in errors[0]["reason"].lower()
    )


async def test_unknown_sofor_returns_row_error(db_session, monkeypatch):
    """PR-3b: çözülemeyen şoför satırı 'Şoför bulunamadı' hatası verir, count 0."""
    items = [
        {
            "tarih": date(2026, 5, 1),
            "plaka": "34ABC123",
            "sofor_adi": "Hayalet Sürücü",  # sofor tablosunda YOK
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 100.0,
            "net_kg": 0,
        }
    ]
    svc, _ = await _make_service(db_session)
    _stub_parse(monkeypatch, items)

    count, errors = await svc.process_excel_import(b"x", current_user_id=1)
    assert count == 0
    assert len(errors) == 1
    assert "şoför" in errors[0]["reason"].lower()


# --- pure helper logic (no DB) ---------------------------------------------


def _bare_service():
    from app.services.api.sefer_import_service import SeferImportService

    return SeferImportService()


def test_resolve_master_id_unique_match():
    """Tek eşleşen kayıt → doğru ID döner."""
    drivers = [
        {"id": 1, "ad_soyad": "Ali Veli"},
        {"id": 2, "ad_soyad": "Mehmet Kaya"},
    ]
    assert _bare_service()._resolve_master_id("Ali Veli", drivers, "ad_soyad") == 1


def test_resolve_master_id_ambiguous_returns_none():
    """Aynı isimli iki kayıt → None (sessiz yanlış atama yerine import hatası)."""
    drivers = [
        {"id": 1, "ad_soyad": "Ahmet Yılmaz"},
        {"id": 2, "ad_soyad": "Ahmet Yılmaz"},
    ]
    assert (
        _bare_service()._resolve_master_id("Ahmet Yılmaz", drivers, "ad_soyad") is None
    )


def test_resolve_master_id_no_match_returns_none():
    """Eşleşme yoksa None döner."""
    drivers = [{"id": 1, "ad_soyad": "Ali Veli"}]
    assert _bare_service()._resolve_master_id("Yok Kişi", drivers, "ad_soyad") is None
