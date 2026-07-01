import pytest
from sqlalchemy import text

from app.database.base_repository import BaseRepository
from app.database.models import Arac

pytestmark = pytest.mark.integration


@pytest.fixture
def test_repo(db_session):
    """BaseRepository'den türeyen test repository'si"""

    class AracTestRepository(BaseRepository[Arac]):
        model = Arac

    return AracTestRepository(session=db_session)


@pytest.mark.asyncio
async def test_create_returns_id(test_repo):
    """create() yeni kayıt ID'si döner"""
    new_id = await test_repo.create(plaka="34 UT 01", marka="Test", model="X", yil=2020)
    assert new_id is not None
    assert new_id > 0


@pytest.mark.asyncio
async def test_get_by_id_existing(test_repo):
    """get_by_id() mevcut kayıt döner"""
    new_id = await test_repo.create(plaka="34 UT 02", marka="Test", model="X", yil=2020)
    result = await test_repo.get_by_id(new_id)
    assert result is not None
    assert result["plaka"] == "34 UT 02"


@pytest.mark.asyncio
async def test_update_modifies_data(test_repo):
    """update() veriyi günceller"""
    new_id = await test_repo.create(
        plaka="34 UT 03", marka="Original", model="X", yil=2020
    )
    success = await test_repo.update(new_id, marka="Updated")
    assert success is True

    result = await test_repo.get_by_id(new_id)
    assert result["marka"] == "Updated"


@pytest.mark.asyncio
async def test_soft_delete_logic(test_repo):
    """delete() aktif=False yapar (modellerde aktif varsa)"""
    new_id = await test_repo.create(plaka="34 UT 04", marka="Test", model="X", yil=2020)
    success = await test_repo.delete(new_id)
    assert success is True

    # Soft-deleted kayıt artık varsayılan get_by_id'de görünmez (bkz.
    # test_get_by_id_excludes_soft_deleted_by_default) — kaydın gerçekten
    # aktif=False olduğunu doğrulamak için include_inactive=True kullan.
    result = await test_repo.get_by_id(new_id, include_inactive=True)
    assert result["aktif"] is False


@pytest.mark.asyncio
async def test_get_by_id_excludes_soft_deleted_by_default(test_repo):
    """get_by_id() varsayılan olarak soft-deleted (aktif=False) kaydı döndürmez.

    2026-07-01 prod-grade denetiminde bulunan kök-neden bug: BaseRepository.get_by_id
    hiçbir soft-delete filtresi uygulamıyordu, bu yüzden silinmiş araç/şoför/dorse/
    lokasyon kayıtları var-mı kontrollerini sessizce geçebiliyordu (ör.
    maintenance_service.create_maintenance_record, arac_service._update_arac_impl).
    """
    new_id = await test_repo.create(plaka="34 UT 08", marka="Test", model="X", yil=2020)
    await test_repo.delete(new_id)

    result = await test_repo.get_by_id(new_id)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_for_update_excludes_soft_deleted_by_default(test_repo):
    """get_by_id(..., for_update=True) da aynı soft-delete filtresini uygulamalı."""
    new_id = await test_repo.create(plaka="34 UT 09", marka="Test", model="X", yil=2020)
    await test_repo.delete(new_id)

    result = await test_repo.get_by_id(new_id, for_update=True)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_include_inactive_bypasses_filter(test_repo):
    """include_inactive=True kasıtlı olarak pasif/silinmiş kaydı görmeyi sağlar
    (ör. smart-delete'in ikinci aşaması, hard-delete öncesi kontrol)."""
    new_id = await test_repo.create(plaka="34 UT 10", marka="Test", model="X", yil=2020)
    await test_repo.delete(new_id)

    result = await test_repo.get_by_id(new_id, include_inactive=True)
    assert result is not None
    assert result["aktif"] is False


@pytest.mark.asyncio
async def test_get_by_id_active_record_unaffected(test_repo):
    """Aktif bir kayıt için get_by_id davranışı değişmemeli."""
    new_id = await test_repo.create(plaka="34 UT 11", marka="Test", model="X", yil=2020)

    result = await test_repo.get_by_id(new_id)
    assert result is not None
    assert result["aktif"] is True


@pytest.mark.asyncio
async def test_get_all_filters_inactive(test_repo):
    """get_all() default olarak inaktifleri göstermez"""
    await test_repo.create(plaka="34 UT 05", aktif=True, marka="X", model="M", yil=2000)
    del_id = await test_repo.create(
        plaka="34 UT 06", aktif=True, marka="X", model="M", yil=2000
    )
    await test_repo.delete(del_id)

    results = await test_repo.get_all()
    plakalar = [r["plaka"] for r in results]
    assert "34 UT 05" in plakalar
    assert "34 UT 06" not in plakalar


@pytest.mark.asyncio
async def test_count(test_repo):
    """count() doğru sayıyı döner"""
    initial_count = await test_repo.count()
    await test_repo.create(plaka="34 UT 07", marka="X", model="M", yil=2000)
    new_count = await test_repo.count()
    assert new_count == initial_count + 1


@pytest.mark.asyncio
async def test_sql_injection_safe(test_repo, db_session):
    """SQL Injection koruması testi"""
    malicious_name = "' OR 1=1 --"
    # Parameterized query handles this safely
    new_id = await test_repo.create(
        plaka=malicious_name, marka="Test", model="X", yil=2020
    )

    result = await test_repo.get_by_id(new_id)
    assert result["plaka"] == malicious_name

    # Check table still exists
    res = await db_session.execute(text("SELECT to_regclass('public.araclar')"))
    table_ref = res.scalar()
    assert table_ref is not None
    assert "araclar" in str(table_ref)
