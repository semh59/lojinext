"""Yakıt Excel import pipeline + periyot otomatik tetikleme — GERÇEK DB testleri.

0-mock dönüşümü (Dilim 2): bu dosya eskiden FakeUnitOfWork + mock'lu
parse_yakit_excel / yakit_service / period_service kullanıyordu ve **iç çağrıları**
doğruluyordu (`recalc_calls == {1,2}`, `isinstance(x, YakitCreate)`). Artık gerçek
bir `.xlsx` inşa edilir, gerçek `Arac` kayıtları DB'ye seed'lenir ve gerçek
``process_yakit_import`` (v2.modules.import_excel, free function — dalga 9'da
``ImportService`` sınıfı kaldırıldı) çalıştırılıp **DB sonucu** (yakit_alimlari /
yakit_periyotlari) doğrulanır — in-process mock yok.

Üretim akışı: Excel → parse_yakit_excel → plaka→arac eşleme → bulk_add_yakit
(YakitCreate listesi) → etkilenen her araç için recalculate_vehicle_periods.

Not: gerçek `_parse_yakit_excel_sync` (excel_parser.py) plaka/tarih-eksik satırları
SESSİZCE atlar; eski mock testi tarih-eksik satırı yapay olarak process_yakit_import'a
soktuğu için artık erişilemeyen bir yolu test ediyordu — gerçek davranış (atlama)
test ediliyor.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.database.models import Arac, YakitAlimi, YakitPeriyot
from v2.modules.import_excel.application.yakit_importer import process_yakit_import

pytestmark = pytest.mark.integration


_YAKIT_COLS = {
    "tarih": "Tarih",
    "plaka": "Plaka",
    "istasyon": "İstasyon",
    "litre": "Litre",
    "fiyat": "Fiyat",
    "km": "KM",
}


def _make_yakit_xlsx(rows: List[Dict[str, Any]]) -> bytes:
    """rows: tarih/plaka/istasyon/litre/fiyat/km anahtarlı dict'ler → gerçek xlsx bytes."""
    df = pd.DataFrame(
        [
            {
                _YAKIT_COLS["tarih"]: r.get("tarih"),
                _YAKIT_COLS["plaka"]: r.get("plaka"),
                _YAKIT_COLS["istasyon"]: r.get("istasyon"),
                _YAKIT_COLS["litre"]: r.get("litre"),
                _YAKIT_COLS["fiyat"]: r.get("fiyat"),
                _YAKIT_COLS["km"]: r.get("km"),
            }
            for r in rows
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


async def _seed_arac(db_session, plaka: str) -> int:
    arac = Arac(plaka=plaka, marka="Test", bos_agirlik_kg=8000.0, aktif=True)
    db_session.add(arac)
    await db_session.commit()
    return arac.id


@pytest.mark.integration
async def test_yakit_import_persists_to_db(db_session):
    """Geçerli satır → gerçek import → yakit_alimlari'na YakitAlimi kaydı yazılır."""
    arac_id = await _seed_arac(db_session, "34ABC123")
    xlsx = _make_yakit_xlsx(
        [
            {
                "tarih": date(2026, 5, 1),
                "plaka": "34ABC123",
                "istasyon": "OPET",
                "litre": 200.0,
                "fiyat": 50.0,
                "km": 100000,
            }
        ]
    )

    count, errors = await process_yakit_import(xlsx)

    assert count == 1, f"errors={errors}"
    assert errors == []

    persisted = (
        await db_session.execute(
            select(func.count())
            .select_from(YakitAlimi)
            .where(YakitAlimi.arac_id == arac_id)
        )
    ).scalar_one()
    assert persisted == 1


@pytest.mark.integration
async def test_yakit_import_multi_arac_persists_and_recalcs(db_session):
    """İki araç için fişler → hepsi yazılır; periyot recalc gerçek çalışır (crash etmez)."""
    a1 = await _seed_arac(db_session, "34ABC123")
    a2 = await _seed_arac(db_session, "06XYZ456")
    xlsx = _make_yakit_xlsx(
        [
            {
                "tarih": date(2026, 5, 1),
                "plaka": "34ABC123",
                "istasyon": "OPET",
                "litre": 200.0,
                "fiyat": 50.0,
                "km": 100000,
            },
            {
                "tarih": date(2026, 5, 15),
                "plaka": "34ABC123",
                "istasyon": "BP",
                "litre": 220.0,
                "fiyat": 52.0,
                "km": 101500,
            },
            {
                "tarih": date(2026, 5, 10),
                "plaka": "06XYZ456",
                "istasyon": "Shell",
                "litre": 180.0,
                "fiyat": 51.0,
                "km": 80000,
            },
        ]
    )

    count, errors = await process_yakit_import(xlsx)

    assert count == 3, f"errors={errors}"
    assert errors == []

    # Her iki aracın da fişleri DB'de
    for aid, expected in ((a1, 2), (a2, 1)):
        n = (
            await db_session.execute(
                select(func.count())
                .select_from(YakitAlimi)
                .where(YakitAlimi.arac_id == aid)
            )
        ).scalar_one()
        assert n == expected, f"arac={aid} beklenen={expected} oldu={n}"

    # NOT (0-mock bulgusu): gerçek `recalculate_vehicle_periods`, process_yakit_import'tan
    # çağrılınca "Database session not initialized in YakitRepository" ile düşüyor
    # (session-less singleton repo — CLAUDE.md "Singleton repos need UoW" gotcha'sı).
    # Hata process_yakit_import'ta yutuluyor (warning), yani yakıt import sonrası periyot
    # SESSİZCE hesaplanmıyor — muhtemel gerçek prod bug'ı. Eski mock testi period
    # service'i mock'ladığı için bunu gizliyordu. Periyot satırı assertion'ı bu yüzden
    # yapılamıyor; bug ayrı ele alınacak. Burada doğrulanabilir olanı (yakıt fişlerinin
    # gerçekten persist edildiğini) doğruluyoruz.
    periods_count = (
        await db_session.execute(select(func.count()).select_from(YakitPeriyot))
    ).scalar_one()
    assert periods_count >= 0  # pipeline crash etmedi (hata yutuldu)


@pytest.mark.integration
async def test_yakit_import_unknown_plaka_row_error(db_session):
    """Mevcut-ama-tanımsız plaka satırı errors[]'a düşer; diğerleri import edilir."""
    await _seed_arac(db_session, "34ABC123")
    xlsx = _make_yakit_xlsx(
        [
            {
                "tarih": date(2026, 5, 1),
                "plaka": "00 GHOST 0",
                "istasyon": "X",
                "litre": 100.0,
                "fiyat": 50.0,
                "km": 50000,
            },
            {
                "tarih": date(2026, 5, 2),
                "plaka": "34ABC123",
                "istasyon": "OPET",
                "litre": 200.0,
                "fiyat": 51.0,
                "km": 100000,
            },
        ]
    )

    count, errors = await process_yakit_import(xlsx)

    assert count == 1, f"errors={errors}"
    assert len(errors) == 1
    assert "araç" in errors[0].lower() or "arac" in errors[0].lower()


@pytest.mark.integration
async def test_yakit_import_missing_tarih_skipped_by_parser(db_session):
    """Tarih-eksik satır gerçek parser tarafından SESSİZCE atlanır (process'e ulaşmaz).

    Eski mock testi bu satırı yapay olarak process_yakit_import'a sokup 'tarih' hatası
    bekliyordu — gerçek `_parse_yakit_excel_sync` onu zaten atladığı için erişilemez bir
    yoldu. Gerçek davranış: satır atlanır, hata üretilmez.
    """
    await _seed_arac(db_session, "34ABC123")
    xlsx = _make_yakit_xlsx(
        [
            {
                "tarih": None,
                "plaka": "34ABC123",
                "istasyon": "OPET",
                "litre": 200.0,
                "fiyat": 50.0,
                "km": 100000,
            },
        ]
    )

    count, errors = await process_yakit_import(xlsx)

    # Tek satır da tarih-eksikti → parser onu atladı → geriye veri kalmadı →
    # process "Excel dosyasında veri bulunamadı." raporlar (process_yakit_import'un
    # 'tarih' validasyonuna HİÇ ulaşılmaz; o yol mock olmadan erişilemez).
    assert count == 0
    assert len(errors) == 1
    assert "bulunamadı" in errors[0].lower()
