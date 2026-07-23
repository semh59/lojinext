"""
T1-E: dorse_repo.get_active_trailers() pasif dorse dahil — sorun yok (test olarak yazıldı).

Bug Açıklaması:
  Fonksiyon sadece is_deleted filtresi uyguluyordu.
  aktif = FALSE olan dorseler de dışlanmalıydı.

Beklenen: get_active_trailers() sadece aktif=TRUE ve is_deleted=FALSE dorseler dönmeli.
"""

import pytest
from sqlalchemy import insert

from v2.modules.fleet.public import Dorse

pytestmark = pytest.mark.integration


@pytest.mark.integration
async def test_get_active_trailers_excludes_deleted_and_inactive(
    db_session, dorse_repo
):
    """
    get_active_trailers() pasif ve silinmiş dorseler hariç tutmalı.
    aktif=FALSE veya is_deleted=TRUE olan dorseler dışlanmalı.
    """

    # Aktif ve silinmemiş dorse (DÖNMELİ)
    await db_session.execute(
        insert(Dorse).values(
            plaka="99 ACT 001",
            tipi="Standart",
            aktif=True,
            is_deleted=False,
            dorse_hava_direnci=0.2,
        )
    )

    # Aktif ama silinmiş dorse (DIŞLANMALI)
    await db_session.execute(
        insert(Dorse).values(
            plaka="99 DEL 001",
            tipi="Standart",
            aktif=True,
            is_deleted=True,
            dorse_hava_direnci=0.2,
        )
    )

    # Pasif ve silinmemiş dorse (DIŞLANMALI - BUG: bu da dönüyor)
    await db_session.execute(
        insert(Dorse).values(
            plaka="99 INA 001",
            tipi="Standart",
            aktif=False,
            is_deleted=False,
            dorse_hava_direnci=0.2,
        )
    )

    # Pasif ve silinmiş dorse (DIŞLANMALI)
    await db_session.execute(
        insert(Dorse).values(
            plaka="99 BRK 001",
            tipi="Standart",
            aktif=False,
            is_deleted=True,
            dorse_hava_direnci=0.2,
        )
    )

    await db_session.commit()

    # TEST: get_active_trailers
    trailers = await dorse_repo.get_active_trailers()

    assert len(trailers) == 1, (
        f"BUG T1-E: get_active_trailers() pasif dorseler dahil ediyor. "
        f"Beklenen: 1 (sadece aktif=TRUE ve is_deleted=FALSE), Aldık: {len(trailers)}. "
        f"Sorun: dorse_repo.py:23-27 - WHERE ~is_deleted yerine WHERE ~is_deleted AND aktif=TRUE olmalı."
    )

    assert trailers[0].plaka == "99 ACT 001", "Yalnızca aktif dorse döndü"
