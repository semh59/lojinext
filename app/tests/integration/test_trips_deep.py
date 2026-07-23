from datetime import date

import pytest


@pytest.fixture
async def sample_arac_sofor(arac_repo, sofor_repo):
    """Test için araç ve şoför hazırla"""
    from v2.modules.driver.schemas import SoforCreate
    from v2.modules.fleet.schemas import AracCreate

    arac_id = await arac_repo.create(
        **AracCreate(
            plaka="34 TEST 99", marka="Scania", model="R500", yil=2022, aktif=True
        ).model_dump()
    )

    sofor_id = await sofor_repo.create(
        **SoforCreate(ad_soyad="Test Şoför", telefon="5550001122").model_dump()
    )

    return {"arac_id": arac_id, "sofor_id": sofor_id}


@pytest.mark.asyncio
async def test_basic_sefer_repo_operations(sefer_repo, sample_arac_sofor):
    """Repo seviyesinde temel sefer işlemlerinin testi"""
    # Use raw dictionary to bypass Pydantic vs SQLAlchemy Enum/Validator friction in repository test
    data = {
        "tarih": date.today(),
        "arac_id": sample_arac_sofor["arac_id"],
        "sofor_id": sample_arac_sofor["sofor_id"],
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 450.0,
        "bos_agirlik_kg": 8000,
        "dolu_agirlik_kg": 28000,
        "net_kg": 20000,
        "durum": "Completed",
    }

    sefer_id = await sefer_repo.create(**data)
    assert sefer_id is not None

    record = await sefer_repo.get_by_id(sefer_id)
    assert record is not None
    assert record["cikis_yeri"] == "Istanbul"
    assert record["varis_yeri"] == "Ankara"


@pytest.mark.asyncio
async def test_sefer_mojibake_integrity(sefer_repo, sample_arac_sofor):
    """Türkçe karakterlerin veri tabanına doğru yazıldığının testi"""
    test_note = "Şoför yolda, yağışlı hava. İptal riski var."
    data = {
        "tarih": date.today(),
        "arac_id": sample_arac_sofor["arac_id"],
        "sofor_id": sample_arac_sofor["sofor_id"],
        "cikis_yeri": "Uşak",
        "varis_yeri": "Iğdır",
        "mesafe_km": 1200.0,
        "notlar": test_note,
        "durum": "Completed",
    }
    sid = await sefer_repo.create(**data)

    record = await sefer_repo.get_by_id(sid)
    assert record["notlar"] == test_note
    assert record["cikis_yeri"] == "Uşak"
    assert record["varis_yeri"] == "Iğdır"
