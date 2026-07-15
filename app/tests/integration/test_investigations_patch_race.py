import asyncio
from datetime import date, datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_concurrent_patch_does_not_lose_resolution_update(async_db_engine):
    """
    2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 18): `update_investigation`
    (`app/api/v1/endpoints/investigations.py`) `db.get(FuelInvestigation, inv_id)`
    ile kilitsiz okuma yapıyordu (TOCTOU). Eşzamanlı iki PATCH isteğinde:
      - İstek A: `resolution_type` set eder → status otomatik 'resolved'.
      - İstek B (aynı anda, hâlâ 'open' okuyarak): sadece `assigned_to_user_id`
        set eder → mevcut kod "status hâlâ open ise otomatik 'assigned'"
        mantığıyla, A'nın commit ettiği 'resolved' durumunu FARKINDA OLMADAN
        'assigned'e geri döndürür (lost update — çözümlenmiş bir soruşturma
        sessizce 'assigned'e düşer).

    Fix: `SELECT ... FOR UPDATE` ile satır kilitlenir; B, A'nın commit'ini
    bekler ve GÜNCEL ('resolved') durumu görüp otomatik 'assigned' geçişini
    tetiklemez.
    """
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database.models import Anomaly, FuelInvestigation
    from app.tests._helpers.seed import seed_kullanici

    SessionLocal = async_sessionmaker(
        bind=async_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with SessionLocal() as seed_session:
        user = await seed_kullanici(seed_session)
        assignee_id = user.id

        anomaly = Anomaly(
            tarih=date.today(),
            tip="tuketim",
            kaynak_tip="sefer",
            kaynak_id=1,
            deger=40.0,
            beklenen_deger=32.0,
            sapma_yuzde=25.0,
            severity="medium",
            aciklama="Race test anomaly",
            created_at=datetime.now(timezone.utc),
        )
        seed_session.add(anomaly)
        await seed_session.flush()

        inv = FuelInvestigation(anomaly_id=anomaly.id, status="open")
        seed_session.add(inv)
        await seed_session.flush()
        inv_id = inv.id
        await seed_session.commit()

    lock_acquired = asyncio.Event()
    release_a = asyncio.Event()

    async def patch_a_resolve():
        """Replicates update_investigation()'s resolution_type branch. Reads,
        decides, and issues (but does not yet commit) its UPDATE — the
        UPDATE statement itself takes the row lock even without an explicit
        FOR UPDATE, so this correctly blocks B's later UPDATE until A
        commits, regardless of which branch is under test."""
        from v2.modules.anomaly.infrastructure.investigation_repository import (
            get_investigation_repo,
        )

        async with SessionLocal() as session:
            repo = get_investigation_repo(session)
            current = await repo.lock_investigation_for_update(inv_id)
            assert current is not None
            values = {
                "resolution_type": "real_theft",
                "status": "resolved",
                "closed_at": datetime.now(timezone.utc),
            }
            await session.execute(
                update(FuelInvestigation)
                .where(FuelInvestigation.id == inv_id)
                .values(**values)
            )
            lock_acquired.set()
            await release_a.wait()
            await session.commit()

    async def patch_b_assign():
        """Replicates update_investigation()'s assigned_to_user_id branch.
        Fix'siz kodda bu SELECT hemen döner (A henüz commit etmedi, son
        commitlenmiş değer hâlâ 'open') — stale okuma. Fix'li kodda bu
        SELECT ... FOR UPDATE, A'nın (henüz commitlenmemiş) transaction'ının
        tuttuğu satır kilidi yüzünden bloklanır, A commit edene kadar bekler
        ve GÜNCEL durumu görür. B'nin kendi UPDATE'i her koşulda A'nın
        (uncommitted) UPDATE'i tarafından zaten kilitlenmiş satırda bekler,
        bu yüzden B'nin write'ı gerçek zamanda her zaman A'dan SONRA olur —
        asıl TOCTOU senaryosu budur."""
        from v2.modules.anomaly.infrastructure.investigation_repository import (
            get_investigation_repo,
        )

        await lock_acquired.wait()
        async with SessionLocal() as session:
            repo = get_investigation_repo(session)
            current = await repo.lock_investigation_for_update(inv_id)
            assert current is not None
            values = {"assigned_to_user_id": assignee_id}
            if current.status == "open" and "status" not in values:
                values["status"] = "assigned"
            await session.execute(
                update(FuelInvestigation)
                .where(FuelInvestigation.id == inv_id)
                .values(**values)
            )
            await session.commit()

    task_a = asyncio.create_task(patch_a_resolve())
    task_b = asyncio.create_task(patch_b_assign())

    # Sabit bir uyku yerine A'nın gerçekten update'i çalıştırdığını bekle
    # (task scheduling/bağlantı kurulumu gecikmesi mutlak zamanlamayı
    # güvenilmez kılıyordu) — sonra B'nin (fix'siz kodda hızlı dönen)
    # SELECT'inin tamamlanması için küçük bir tampon süre.
    await lock_acquired.wait()
    await asyncio.sleep(0.3)
    release_a.set()

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=10)

    async with SessionLocal() as check_session:
        final = await check_session.get(FuelInvestigation, inv_id)
        assert final.status == "resolved", (
            "Beklenen status='resolved' (B'nin gecikmiş 'assigned' geçişi "
            f"gerçek durumu görüp tetiklenmemeliydi), ama '{final.status}' "
            "bulundu — TOCTOU race condition'ı hâlâ mevcut."
        )
        assert final.resolution_type == "real_theft"
