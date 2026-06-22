"""Bulk-insert constraint enrichment testleri.

İki production-aykırı bug bu session'da yakaladık ve fix'ledik:

1. ``bulk_add_yakit`` dict key ``"fiyat"`` ↔ DB kolonu ``fiyat_tl`` mismatch +
   ``toplam_tutar = litre * fiyat_tl`` hesaplanmıyordu (NotNullViolation).

2. ``bulk_add_sefer`` ``ck_seferler_check_sefer_net_kg_calc`` constraint
   (``net_kg = dolu_agirlik_kg - bos_agirlik_kg``). Excel'den net_kg gelir,
   dolu/bos yok — ``bulk_add_sefer`` arac master'dan ``bos_agirlik_kg``
   pre-fetch + ``dolu = bos + net`` enrichment yapmalı.

Bu test'ler her iki fix'in geri gelmesini engeller.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.services.sefer_write_service as sefer_write_module
import app.core.services.yakit_service as yakit_module
from app.core.entities.models import SeferCreate
from app.core.services.sefer_write_service import SeferWriteService
from app.core.services.yakit_service import YakitService
from app.schemas.yakit import YakitCreate


class _BaseUoW:
    """Yakit + sefer bulk insert testleri için ortak fake UoW."""

    def __init__(self):
        self.session = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_bulk_add_yakit_emits_fiyat_tl_and_toplam_tutar(monkeypatch):
    """yakit_repo.bulk_create'a giden dict'te ``fiyat_tl`` (not ``fiyat``) ve
    ``toplam_tutar`` (litre*fiyat) olmalı; DB NotNullViolation'a düşmesin."""

    captured: list[list[dict]] = []

    class FakeUoW(_BaseUoW):
        def __init__(self):
            super().__init__()
            self.arac_repo = AsyncMock()
            self.arac_repo.get_all = AsyncMock(
                return_value=[{"id": 1, "plaka": "34ABC"}]
            )
            self.yakit_repo = AsyncMock()
            self.yakit_repo.get_son_km = AsyncMock(return_value=0)
            self.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

            async def _bulk_create(items):
                captured.append(items)

            self.yakit_repo.bulk_create = _bulk_create

    monkeypatch.setattr(yakit_module, "UnitOfWork", lambda: FakeUoW())

    service = YakitService(repo=AsyncMock(), event_bus=MagicMock())
    payload = [
        YakitCreate(
            arac_id=1,
            tarih=date(2026, 5, 1),
            istasyon="Shell",
            litre=50.0,
            fiyat_tl=42.5,
            km_sayac=100_500,
            depo_durumu="Doldu",
        )
    ]

    count = await service.bulk_add_yakit(payload)
    assert count == 1
    assert len(captured) == 1
    row = captured[0][0]

    # Bug 1: dict key fiyat_tl, NOT 'fiyat' (DB NotNullViolation engeli)
    assert "fiyat_tl" in row, f"fiyat_tl key eksik: {row}"
    assert row["fiyat_tl"] == 42.5
    assert "fiyat" not in row, (
        f"Eski 'fiyat' key DB kolonu fiyat_tl'i NULL bırakıyordu: {row}"
    )

    # Bug 2: toplam_tutar = litre * fiyat_tl (DB NotNullViolation engeli)
    assert "toplam_tutar" in row, f"toplam_tutar key eksik: {row}"
    assert row["toplam_tutar"] == 50.0 * 42.5


@pytest.mark.asyncio
async def test_bulk_add_sefer_enriches_bos_and_dolu_from_arac_master(
    monkeypatch,
):
    """``ck_seferler_check_sefer_net_kg_calc`` constraint:
    ``net_kg = dolu_agirlik_kg - bos_agirlik_kg``. SeferCreate sadece net_kg
    taşıyor → bulk_add_sefer arac master'dan bos_agirlik_kg pre-fetch
    yapıp dolu = bos + net hesaplamalı."""

    captured_items: list[list[dict]] = []

    class FakeUoW(_BaseUoW):
        def __init__(self):
            super().__init__()
            self.arac_repo = AsyncMock()
            self.arac_repo.get_all = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "plaka": "34ABC",
                        "bos_agirlik_kg": 8500,  # Master kayıt
                        "aktif": True,  # AUDIT-041: aktif olmazsa satır atlanır
                    }
                ]
            )
            self.arac_repo.get_by_ids = AsyncMock(return_value={})
            self.sofor_repo = AsyncMock()
            self.sofor_repo.get_by_ids = AsyncMock(return_value={})
            self.sofor_repo.get_all = AsyncMock(return_value=[{"id": 2, "aktif": True}])
            self.lokasyon_repo = AsyncMock()
            self.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(
                return_value=["Istanbul", "Ankara"]
            )
            self.lokasyon_repo.get_all = AsyncMock(return_value=[])
            self.lokasyon_repo.find_closest_match = AsyncMock(return_value=None)
            self.sefer_repo = AsyncMock()

            async def _bulk_create(items):
                captured_items.append(items)

            self.sefer_repo.bulk_create = _bulk_create

        async def _refresh_stats(self, *_):
            pass

    fake_uow = FakeUoW()
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: fake_uow)

    # ML prediction'ı atla — büyük batch davranışı (>200) gibi
    mock_pred_service = MagicMock()
    mock_pred_service.predict_consumption = AsyncMock(return_value=(30.0, {}))
    monkeypatch.setattr(
        "app.services.prediction_service.get_prediction_service",
        lambda: mock_pred_service,
    )

    service = SeferWriteService(repo=AsyncMock(), event_bus=MagicMock())
    # _refresh_stats'i no-op'a sahte at — UoW.refresh içermiyor
    monkeypatch.setattr(service, "_refresh_stats", AsyncMock())

    # Excel'den gelen SeferCreate — sadece net_kg dolu, bos/dolu YOK
    payload = [
        SeferCreate(
            tarih=date(2026, 5, 1),
            saat="09:00",
            arac_id=1,
            sofor_id=2,
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=450.0,
            net_kg=15000,
            durum="Tamamlandı",
            bos_sefer=False,
        )
    ]

    await service.bulk_add_sefer(payload)

    assert len(captured_items) == 1
    row = captured_items[0][0]

    # Constraint check: net = dolu - bos
    assert row["bos_agirlik_kg"] == 8500, (
        f"Arac master'dan bos_agirlik_kg gelmeli: {row}"
    )
    assert row["dolu_agirlik_kg"] == 8500 + 15000, (
        f"dolu = bos + net hesaplanmalı: {row}"
    )
    assert row["net_kg"] == row["dolu_agirlik_kg"] - row["bos_agirlik_kg"], (
        f"CK constraint violation: {row}"
    )


@pytest.mark.asyncio
async def test_bulk_add_sefer_fallback_when_arac_bos_unknown(monkeypatch):
    """Master kayıtta bos_agirlik_kg yoksa (legacy araç), bos=0 + dolu=net
    constraint hâlâ satisfy edilir: net = net - 0."""

    captured: list[list[dict]] = []

    class FakeUoW(_BaseUoW):
        def __init__(self):
            super().__init__()
            self.arac_repo = AsyncMock()
            # bos_agirlik_kg None/eksik; AUDIT-041: aktif olmazsa satır atlanır
            self.arac_repo.get_all = AsyncMock(
                return_value=[
                    {"id": 1, "plaka": "34ABC", "bos_agirlik_kg": None, "aktif": True}
                ]
            )
            self.arac_repo.get_by_ids = AsyncMock(return_value={})
            self.sofor_repo = AsyncMock()
            self.sofor_repo.get_by_ids = AsyncMock(return_value={})
            self.sofor_repo.get_all = AsyncMock(return_value=[{"id": 2, "aktif": True}])
            self.lokasyon_repo = AsyncMock()
            self.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
            self.lokasyon_repo.get_all = AsyncMock(return_value=[])
            self.lokasyon_repo.find_closest_match = AsyncMock(return_value=None)
            self.sefer_repo = AsyncMock()

            async def _bulk_create(items):
                captured.append(items)

            self.sefer_repo.bulk_create = _bulk_create

    fake_uow = FakeUoW()
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: fake_uow)
    monkeypatch.setattr(
        "app.services.prediction_service.get_prediction_service",
        lambda: AsyncMock(),
    )

    service = SeferWriteService(repo=AsyncMock(), event_bus=MagicMock())
    monkeypatch.setattr(service, "_refresh_stats", AsyncMock())

    await service.bulk_add_sefer(
        [
            SeferCreate(
                tarih=date(2026, 5, 1),
                saat="09:00",
                arac_id=1,
                sofor_id=2,
                cikis_yeri="Istanbul",
                varis_yeri="Ankara",
                mesafe_km=100.0,
                net_kg=5000,
                durum="Tamamlandı",
                bos_sefer=False,
            )
        ]
    )

    row = captured[0][0]
    assert row["bos_agirlik_kg"] == 0.0
    assert row["dolu_agirlik_kg"] == 5000.0
    assert row["net_kg"] == row["dolu_agirlik_kg"] - row["bos_agirlik_kg"]
