import asyncio
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.repositories.arac_repo import AracRepository
from app.database.repositories.sofor_repo import SoforRepository


@pytest.mark.asyncio
async def test_arac_repo_toctou_concurrency(async_db_engine):
    """
    Aynı plaka ile iki paralel 'add' isteği gönderildiğinde
    birinin başarılı olması, diğerinin ise ValueError veya IntegrityError (Unique constraint)
    fırlatması gerektiğini doğrular.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SessionLocal = async_sessionmaker(
        bind=async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Her test çalışmasında benzersiz bir plaka kullan (İzolasyon garantisi)
    unique_id = uuid.uuid4().hex[:6].upper()
    plaka = f"34CN{unique_id}"

    async def add_arac():
        async with SessionLocal() as session:
            repo = AracRepository(session=session)
            try:
                # AracRepository.add() artık harici session varsa 'flush' yapıyor.
                result = await repo.add(plaka=plaka, marka="Test", model="ThreadTest")
                await session.commit()
                return result
            except (ValueError, IntegrityError) as e:
                await session.rollback()
                return e
            except Exception as e:
                # Tanımlanmayan diğer hatalar (örn. Database is locked)
                await session.rollback()
                return e

    # asyncio.gather ile paralel çalıştırmayı simüle et
    # 2 paralel görev başlatıyoruz
    results = await asyncio.gather(add_arac(), add_arac(), return_exceptions=True)

    success_count = 0
    conflict_count = 0
    error_details = []

    for r in results:
        if isinstance(r, int):
            success_count += 1
        elif hasattr(r, "id") and isinstance(getattr(r, "id"), int):
            success_count += 1
        elif isinstance(r, (ValueError, IntegrityError)):
            conflict_count += 1
            error_details.append(str(r))
        else:
            error_details.append(f"Unexpected: {type(r).__name__}: {r!s}")

    print(
        f"\n[DEBUG ARAC] Results: count={len(results)}, success={success_count}, conflict={conflict_count}"
    )
    for i, err in enumerate(error_details):
        print(f"  Error {i}: {err[:100]}")

    # En az bir tanesi başarılı olmalı.
    # Eğer SQLite commit sırasında kilitlenirse ikincisi IntegrityError veya 'Database is locked' alabilir.
    assert success_count == 1, (
        f"Expected 1 success, got {success_count}. Errors: {error_details}"
    )
    assert conflict_count == 1, (
        f"Expected 1 conflict, got {conflict_count}. Errors: {error_details}"
    )


@pytest.mark.asyncio
async def test_sofor_repo_toctou_concurrency(async_db_engine):
    """
    Aynı isimle iki paralel 'add' isteği gönderildiğinde TOCTOU korumasını doğrular.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SessionLocal = async_sessionmaker(
        bind=async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    unique_name = f"Driver_{uuid.uuid4().hex[:6]}"

    async def add_sofor():
        async with SessionLocal() as session:
            repo = SoforRepository(session=session)
            try:
                result = await repo.add(ad_soyad=unique_name)
                await session.commit()
                return result
            except (ValueError, IntegrityError) as e:
                await session.rollback()
                return e
            except Exception as e:
                await session.rollback()
                return e

    results = await asyncio.gather(add_sofor(), add_sofor(), return_exceptions=True)

    success_count = 0
    conflict_count = 0
    error_details = []

    for r in results:
        if isinstance(r, int):
            success_count += 1
        elif isinstance(r, (ValueError, IntegrityError)):
            conflict_count += 1
            error_details.append(str(r))
        else:
            error_details.append(f"Unexpected: {type(r).__name__}: {r!s}")

    print(
        f"\n[DEBUG SOFOR] Results: success={success_count}, conflict={conflict_count}"
    )

    assert success_count == 1, (
        f"Expected 1 success, got {success_count}. Errors: {error_details}"
    )
    assert conflict_count == 1, (
        f"Expected 1 conflict, got {conflict_count}. Errors: {error_details}"
    )
