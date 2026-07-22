"""
Layer 1 — DB Schema Integrity
Verifies that PostgreSQL-level constraints (FK, CHECK, UNIQUE, soft-delete, indexes, MV)
are actually enforced, not just assumed at the application layer.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from v2.modules.platform_infra.security.pii_encryption import blind_index, encrypt_pii

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_fk_arac_on_seferler_enforced(db_session):
    """Trip with non-existent arac_id must raise IntegrityError.

    asyncpg sends raw SQL immediately on execute(), so the FK violation
    is raised there — not on flush(). Both execute and flush are wrapped.
    seferler.is_deleted has no server_default so must be explicit.
    """
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO seferler "
                "(tarih, arac_id, sofor_id, cikis_yeri, varis_yeri, mesafe_km, "
                " bos_agirlik_kg, dolu_agirlik_kg, net_kg, durum, is_deleted) "
                "VALUES (:tarih, 999999, 999999, 'A', 'B', 100, 0, 0, 0, 'Planned', FALSE)"
            ),
            {"tarih": date.today()},
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_tank_kapasitesi_positive(db_session):
    """Vehicle with tank_kapasitesi <= 0 must raise IntegrityError (CHECK constraint)."""
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
                "VALUES (:plaka, 'Test', -1, 30.0)"
            ),
            {"plaka": f"99 ZZZ {uuid.uuid4().hex[:4].upper()}"},
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_sefer_mesafe_positive(db_session):
    """Trip with mesafe_km = 0 must raise IntegrityError (DB CHECK constraint).

    soforler columns score/manual_score/hiz_disiplin_skoru/agresif_surus_faktoru/aktif
    have only Python-side defaults (no server_default) so they must be explicit in raw SQL.
    """
    num = int(uuid.uuid4().hex[:4], 16) % 9000 + 1000  # 1000-9999
    plaka = f"88 AB {num}"
    name = f"Zero Sofor {num}"

    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'Test', 600, 32.0)"
        ),
        {"plaka": plaka},
    )
    await db_session.flush()
    result = await db_session.execute(
        text("SELECT id FROM araclar WHERE plaka = :p"), {"p": plaka}
    )
    arac_id = result.scalar_one()

    # Include all NOT NULL columns that lack server_default
    await db_session.execute(
        text(
            "INSERT INTO soforler "
            "(ad_soyad, ad_soyad_bidx, ehliyet_sinifi, score, manual_score, "
            " hiz_disiplin_skoru, agresif_surus_faktoru, aktif) "
            "VALUES (:name, :name_bidx, 'E', 1.0, 1.0, 1.0, 1.0, TRUE)"
        ),
        {"name": encrypt_pii(name), "name_bidx": blind_index(name)},
    )
    await db_session.flush()
    result = await db_session.execute(
        text("SELECT id FROM soforler WHERE ad_soyad_bidx = :n"),
        {"n": blind_index(name)},
    )
    sofor_id = result.scalar_one()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO seferler "
                "(tarih, arac_id, sofor_id, cikis_yeri, varis_yeri, mesafe_km, "
                " bos_agirlik_kg, dolu_agirlik_kg, net_kg, durum, is_deleted) "
                "VALUES (:tarih, :arac_id, :sofor_id, 'A', 'B', 0, 0, 0, 0, 'Planned', FALSE)"
            ),
            {"tarih": date.today(), "arac_id": arac_id, "sofor_id": sofor_id},
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_unique_plaka_enforced(db_session):
    """Two vehicles with the same plaka must raise IntegrityError (UNIQUE constraint)."""
    plaka = f"06 DUP {uuid.uuid4().hex[:4].upper()}"
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'TestA', 600, 32.0)"
        ),
        {"plaka": plaka},
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
                "VALUES (:plaka, 'TestB', 600, 32.0)"
            ),
            {"plaka": plaka},
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_yakit_litre_positive(db_session):
    """Fuel record with litre = 0 must raise IntegrityError (CHECK litre > 0)."""
    suffix = uuid.uuid4().hex[:4].upper()
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'Test', 600, 32.0)"
        ),
        {"plaka": f"07 YKT {suffix}"},
    )
    await db_session.flush()
    result = await db_session.execute(
        text("SELECT id FROM araclar WHERE plaka = :p"),
        {"p": f"07 YKT {suffix}"},
    )
    arac_id = result.scalar_one()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO yakit_alimlari "
                "(tarih, arac_id, litre, fiyat_tl, toplam_tutar, km_sayac, durum) "
                "VALUES (:tarih, :arac_id, 0, 10.0, 0, 100000, 'Bekliyor')"
            ),
            {"tarih": date.today(), "arac_id": arac_id},
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_soft_delete_filter_via_api(async_client, admin_auth_headers, db_session):
    """
    Create a vehicle via API, mark is_deleted=True directly in DB,
    then verify it disappears from the list endpoint.
    """
    num = int(uuid.uuid4().hex[:4], 16) % 9000 + 1000
    resp = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": f"35 AB {num}",
            "marka": "Volvo",
            "model": "FH",
            "yil": 2022,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 30.0,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, f"Vehicle create failed: {resp.text}"
    arac_id = resp.json()["id"]

    await db_session.execute(
        text("UPDATE araclar SET is_deleted = TRUE WHERE id = :id"),
        {"id": arac_id},
    )
    await db_session.commit()

    list_resp = await async_client.get("/api/v1/vehicles/", headers=admin_auth_headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    # GET /vehicles/ returns StandardResponse: {"data": [...], "meta": {...}}
    # Support both StandardResponse and plain list/paginated formats
    if isinstance(body, dict) and "data" in body:
        raw = body["data"]
    elif isinstance(body, dict) and "items" in body:
        raw = body["items"]
    elif isinstance(body, list):
        raw = body
    else:
        raw = []
    ids_in_list = [v["id"] for v in raw]
    assert arac_id not in ids_in_list, (
        f"Soft-deleted vehicle (id={arac_id}) still appears in list. "
        "is_deleted filter is not applied."
    )


@pytest.mark.asyncio
async def test_materialized_view_refresh(async_client, admin_auth_headers, db_session):
    """
    After creating a sefer via API, REFRESH MATERIALIZED VIEW must not fail
    and the view must contain a row for 'Planned'.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    num = int(uuid.uuid4().hex[:4], 16) % 9000 + 1000

    arac_resp = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": f"38 AB {num}",
            "marka": "MAN",
            "model": "TGX",
            "yil": 2023,
            "tank_kapasitesi": 700,
            "hedef_tuketim": 31.0,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert arac_resp.status_code == 201
    arac_id = arac_resp.json()["id"]

    sofor_resp = await async_client.post(
        "/api/v1/drivers/",
        json={
            "ad_soyad": f"MV Sofor {suffix}",
            "ehliyet_sinifi": "E",
            "ise_baslama": "2020-01-01",
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert sofor_resp.status_code == 201
    sofor_id = sofor_resp.json()["id"]

    lok_resp = await async_client.post(
        "/api/v1/locations/",
        json={
            "cikis_yeri": f"MV Sehir {suffix}",
            "varis_yeri": f"MV Hedef {suffix}",
            "mesafe_km": 300.0,
            "zorluk": "Normal",
        },
        headers=admin_auth_headers,
    )
    assert lok_resp.status_code == 201
    guzergah_id = lok_resp.json()["id"]

    sefer_resp = await async_client.post(
        "/api/v1/trips/",
        json={
            "tarih": date.today().isoformat(),
            "arac_id": arac_id,
            "sofor_id": sofor_id,
            "guzergah_id": guzergah_id,
            "cikis_yeri": f"MV Sehir {suffix}",
            "varis_yeri": f"MV Hedef {suffix}",
            "mesafe_km": 300.0,
            "net_kg": 0,
            "durum": "Planned",
        },
        headers=admin_auth_headers,
    )
    assert sefer_resp.status_code == 201

    await db_session.execute(text("REFRESH MATERIALIZED VIEW sefer_istatistik_mv"))
    await db_session.commit()

    result = await db_session.execute(
        text("SELECT toplam_sefer FROM sefer_istatistik_mv WHERE durum = 'Planned'")
    )
    row = result.fetchone()
    assert row is not None, (
        "sefer_istatistik_mv has no row for 'Planned' after refresh. "
        "MV definition may be broken."
    )
    assert row[0] >= 1, f"toplam_sefer should be >= 1, got {row[0]}"


@pytest.mark.asyncio
async def test_composite_indexes_exist(db_session):
    """
    Verify composite indexes from migration 0004_composite_indexes exist.
    Each absence is a named failure.
    """
    expected = [
        ("seferler", "ix_seferler_arac_id_tarih"),
        ("seferler", "ix_seferler_sofor_id_tarih"),
        ("seferler", "ix_seferler_arac_id_durum"),
        ("yakit_alimlari", "ix_yakit_alimlari_arac_id_tarih"),
    ]
    for table_name, index_name in expected:
        result = await db_session.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :table AND indexname = :idx"
            ),
            {"table": table_name, "idx": index_name},
        )
        assert result.fetchone() is not None, (
            f"Missing index '{index_name}' on table '{table_name}'. "
            f"Run `alembic upgrade head` and re-run tests."
        )
