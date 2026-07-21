import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

# Add project root
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.infrastructure.security.pii_encryption import blind_index, encrypt_pii
from v2.modules.fuel.application.add_yakit import add_yakit
from v2.modules.fuel.domain.entities import YakitAlimiCreate
from v2.modules.trip.application.trip_service import get_sefer_service
from v2.modules.trip.infrastructure.repository import SeferRepository
from v2.modules.trip.schemas import SeferCreate


@pytest.mark.asyncio
async def test_create_and_retrieve_sefer(db_session):
    """Sefer oluştur ve geri oku"""
    sefer_service = get_sefer_service()
    sefer_repo = SeferRepository(session=db_session)

    # Setup Data with unique labels to avoid IntegrityError
    unique_suffix = uuid.uuid4().hex[:8]
    plaka = f"99 TST {unique_suffix}"[-12:]  # Max 12 chars
    sofor_ad = f"Şoför {unique_suffix}"

    # Insert Vehicle
    arac_res = await db_session.execute(
        text("""
        INSERT INTO araclar (plaka, marka, model, yil, aktif)
        VALUES (:plaka, :marka, :model, :yil, :aktif)
        RETURNING id
    """),
        {
            "plaka": plaka,
            "marka": "TestMarka",
            "model": "TestModel",
            "yil": 2024,
            "aktif": True,
        },
    )
    arac_id = arac_res.scalar()

    # Insert Driver
    sofor_res = await db_session.execute(
        text("""
        INSERT INTO soforler (ad_soyad, ad_soyad_bidx, telefon, ise_baslama, aktif, ehliyet_sinifi, score, manual_score, hiz_disiplin_skoru, agresif_surus_faktoru, notlar)
        VALUES (:ad, :ad_bidx, :tel, :tarih, :aktif, :ehliyet, :score, :mscore, :hiz, :agresif, :notlar)
        RETURNING id
    """),  # noqa: E501
        {
            "ad": encrypt_pii(sofor_ad),
            "ad_bidx": blind_index(sofor_ad),
            "tel": encrypt_pii("5551234567"),
            "tarih": date(2024, 1, 1),
            "aktif": True,
            "ehliyet": "E",
            "score": 1.0,
            "mscore": 1.0,
            "hiz": 1.0,
            "agresif": 1.0,
            "notlar": "",
        },
    )
    sofor_id = sofor_res.scalar()

    # Insert Route (guzergah) - required by sefer create contract
    lokasyon_res = await db_session.execute(
        text(
            """
            INSERT INTO lokasyonlar (cikis_yeri, varis_yeri, mesafe_km, zorluk, aktif, ascent_m, descent_m, flat_distance_km, is_corrected)
            VALUES (:cikis, :varis, :mesafe, :zorluk, :aktif, :ascent, :descent, :flat_km, :is_corrected)
            RETURNING id
            """  # noqa: E501
        ),
        {
            "cikis": "Ankara",
            "varis": "İstanbul",
            "mesafe": 450.0,
            "zorluk": "Normal",
            "aktif": True,
            "ascent": 0.0,
            "descent": 0.0,
            "flat_km": 450.0,
            "is_corrected": False,
        },
    )
    guzergah_id = lokasyon_res.scalar()

    await db_session.commit()

    # Sefer oluştur
    sefer_data = SeferCreate(
        tarih=date.today(),
        guzergah_id=guzergah_id,
        arac_id=arac_id,
        sofor_id=sofor_id,
        cikis_yeri="Ankara",
        varis_yeri="İstanbul",
        mesafe_km=450,
        net_kg=20000,
    )

    sefer_id = await sefer_service.add_sefer(sefer_data)

    # Doğrula
    assert sefer_id is not None
    assert sefer_id > 0

    # Geri oku (Repo calls likely async now too)
    saved = await sefer_repo.get_by_id(sefer_id)
    assert saved is not None
    assert saved["cikis_yeri"] == "Ankara"
    assert saved["varis_yeri"] == "İstanbul"
    assert saved["mesafe_km"] == 450


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session):
    """Hata durumunda transaction rollback (Async test)"""
    # Service kullanılmıyor, sadece session.
    unique_suffix = uuid.uuid4().hex[:8]

    plaka = f"99 RLB {unique_suffix}"[-12:]

    res_initial = await db_session.execute(text("SELECT COUNT(*) FROM araclar"))
    initial = res_initial.scalar()

    try:
        # Nested transaction for async session
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO araclar (plaka, marka, aktif) VALUES (:plaka, :marka, :aktif)"
                ),
                {"plaka": plaka, "marka": "Test", "aktif": True},
            )

            # İkinci insert (Unique Violation)
            await db_session.execute(
                text(
                    "INSERT INTO araclar (plaka, marka, aktif) VALUES (:plaka, :marka, :aktif)"
                ),
                {"plaka": plaka, "marka": "Test", "aktif": True},
            )
    except Exception:
        pass

    res_final = await db_session.execute(text("SELECT COUNT(*) FROM araclar"))
    final = res_final.scalar()

    assert initial == final, "Rollback çalışmadı!"


@pytest.mark.asyncio
async def test_add_and_verify_fuel(db_session):
    """Yakıt ekle ve kontrol et"""
    unique_suffix = uuid.uuid4().hex[:8]
    plaka = f"99 FUL {unique_suffix}"[-12:]

    # Araç oluştur
    arac_id = None

    await db_session.execute(
        text("""
        INSERT INTO araclar (plaka, marka, model, yil, aktif)
        VALUES (:plaka, :marka, :model, :yil, :aktif)
    """),
        {
            "plaka": plaka,
            "marka": "TestMarka",
            "model": "TestModel",
            "yil": 2024,
            "aktif": True,
        },
    )

    arac_res = await db_session.execute(
        text("SELECT id FROM araclar WHERE plaka = :plaka"),
        {"plaka": plaka},
    )
    arac_id = arac_res.scalar()
    await db_session.commit()

    # Yakıt ekle
    yakit_data = YakitAlimiCreate(
        tarih=date.today(),
        arac_id=arac_id,
        istasyon="TestShell",
        litre=500,
        fiyat_tl=Decimal("45.0"),
        km_sayac=100000,
    )

    yakit_id = await add_yakit(yakit_data)

    # Doğrula
    assert yakit_id is not None
    assert yakit_id > 0
