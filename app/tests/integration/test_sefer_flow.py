import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

# Add project root
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.core.entities.models import SeferCreate, YakitAlimiCreate
from app.core.services.sefer_service import get_sefer_service
from app.core.services.yakit_service import get_yakit_service
from app.database.repositories.sefer_repo import SeferRepository


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
        INSERT INTO soforler (ad_soyad, telefon, ise_baslama, aktif, ehliyet_sinifi, score, manual_score, hiz_disiplin_skoru, agresif_surus_faktoru, notlar)
        VALUES (:ad, :tel, :tarih, :aktif, :ehliyet, :score, :mscore, :hiz, :agresif, :notlar)
        RETURNING id
    """),  # noqa: E501
        {
            "ad": sofor_ad,
            "tel": "5551234567",
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
    yakit_service = get_yakit_service()
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

    yakit_id = await yakit_service.add_yakit(yakit_data)

    # Doğrula
    assert yakit_id is not None
    assert yakit_id > 0
