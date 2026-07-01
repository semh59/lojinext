import asyncio
import uuid

import pytest


@pytest.mark.asyncio
async def test_admin_config_update_value_serializes_concurrent_writes(async_db_engine):
    """
    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 12):
    `AdminConfigRepository.update_value` kilitsiz read-modify-write yapıyordu
    (`session.get` ile düz okuma, ardından mutate+flush). Eşzamanlı iki
    `PATCH /admin/config/{key}` isteğinde, ikinci (geç kalan) transaction ilk
    transaction commit etmeden ÖNCE okunan STALE bir değeri `eski_deger` olarak
    audit history'ye yazıyordu — flush anında satır kilidini beklese bile,
    okuma zaten kilitlenmeden önce olmuştu.

    Fix: `SELECT ... FOR UPDATE` satırı select anında kilitler; ikinci
    transaction ilkinin commit'ini bekler ve GÜNCEL (ilk transaction'ın
    yazdığı) değeri görür — audit history artık doğru.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database.models import SistemKonfig
    from app.database.repositories.admin_config_repo import AdminConfigRepository

    SessionLocal = async_sessionmaker(
        bind=async_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    key = f"test_concurrency_{uuid.uuid4().hex[:8]}"

    async with SessionLocal() as seed_session:
        seed_session.add(
            SistemKonfig(anahtar=key, deger="V0", tip="string", grup="test")
        )
        await seed_session.commit()

    lock_acquired = asyncio.Event()
    release_a = asyncio.Event()

    async def transaction_a():
        async with SessionLocal() as session:
            repo = AdminConfigRepository(session=session)
            result = await repo.update_value(key, "VA", reason="A")
            lock_acquired.set()
            await release_a.wait()
            await session.commit()
            return result

    async def transaction_b():
        await lock_acquired.wait()
        async with SessionLocal() as session:
            repo = AdminConfigRepository(session=session)
            # Fix'siz kodda bu SATIR bloklamaz (plain read committed SELECT),
            # stale "V0" hemen döner. Fix'li kodda A commit edene kadar
            # bloklar, sonra "VA" görür.
            result = await repo.update_value(key, "VB", reason="B")
            await session.commit()
            return result

    task_a = asyncio.create_task(transaction_a())
    task_b = asyncio.create_task(transaction_b())

    await asyncio.sleep(0.5)
    release_a.set()

    await asyncio.gather(task_a, task_b)

    async with SessionLocal() as check_session:
        check_repo = AdminConfigRepository(session=check_session)
        history = await check_repo.get_history(key, limit=10)

    b_entry = next(h for h in history if h["yeni_deger"] == "VB")
    assert b_entry["eski_deger"] == "VA", (
        "Beklenen eski_deger='VA' (kilit sonrası güncel değer), ama "
        f"'{b_entry['eski_deger']}' bulundu — kilitsiz read-modify-write "
        "race condition'ı hâlâ mevcut."
    )
