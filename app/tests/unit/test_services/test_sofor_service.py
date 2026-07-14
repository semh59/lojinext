"""Driver use-case unit tests — real DB via db_session fixture.

NOT: eski ``SoforService`` sınıfı silindi (B.1 free-function split, bkz.
v2/modules/driver/CLAUDE.md). Testler artık ilgili free function'ları
doğrudan import edip çağırır.
"""

import pytest

from v2.modules.driver.application.add_sofor import add_sofor
from v2.modules.driver.application.delete_sofor import bulk_delete
from v2.modules.driver.application.get_score import calculate_hybrid_score
from v2.modules.driver.application.list_sofor import get_all_paged, get_by_id
from v2.modules.driver.application.update_sofor import update_score

pytestmark = pytest.mark.integration


class TestSoforService:
    async def test_happy_path_add_sofor(self, db_session):
        """add_sofor returns an integer ID when name is new (real DB)."""
        result = await add_sofor(ad_soyad="Sofor Dilim18 A")

        assert isinstance(result, int) and result > 0

    async def test_add_sofor_reactivates_passive_driver(self, db_session):
        """add_sofor re-activates an existing passive driver and returns its ID (real DB)."""
        from app.database.models import Sofor

        passive = Sofor(ad_soyad="Sofor Dilim18 B", aktif=False)
        db_session.add(passive)
        await db_session.flush()

        result = await add_sofor(ad_soyad="Sofor Dilim18 B")

        assert result == passive.id

    async def test_add_sofor_raises_on_duplicate_active(self, db_session):
        """add_sofor raises ValueError when an active driver with same name exists (real DB)."""
        from app.database.models import Sofor

        active = Sofor(ad_soyad="Sofor Dilim18 C", aktif=True)
        db_session.add(active)
        await db_session.flush()

        with pytest.raises(ValueError, match="already exists"):
            await add_sofor(ad_soyad="Sofor Dilim18 C")

    async def test_add_sofor_raises_on_short_name(self, db_session):
        """add_sofor raises ValueError when ad_soyad is too short."""
        with pytest.raises(ValueError, match="en az 3"):
            await add_sofor(ad_soyad="Ab")

    async def test_get_all_paged_returns_dict(self, db_session):
        """get_all_paged returns dict with 'items' and 'total' keys (real DB)."""
        result = await get_all_paged()

        assert "items" in result
        assert "total" in result

    async def test_get_by_id_returns_none_for_missing(self, db_session):
        """get_by_id returns None when driver does not exist (real DB)."""
        result = await get_by_id(999999)

        assert result is None

    async def test_update_score_raises_on_out_of_range(self):
        """update_score raises ValueError for score outside 0.1-2.0."""
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await update_score(1, 3.5)

    async def test_calculate_hybrid_score_no_trips(self, db_session):
        """calculate_hybrid_score returns manual_score when no trips found (real DB)."""
        from app.database.models import Sofor

        sofor = Sofor(ad_soyad="Sofor Dilim18 D", aktif=True)
        db_session.add(sofor)
        await db_session.flush()

        result = await calculate_hybrid_score(sofor_id=sofor.id, manual_score=1.2)

        assert result == 1.2

    async def test_bulk_delete_empty_list(self):
        """bulk_delete returns zeros when given an empty list."""
        result = await bulk_delete([])
        assert result["deleted"] == 0
        assert result["errors"] == []

    async def test_edge_case_none_ad_soyad_raises(self, db_session):
        """add_sofor raises ValueError when ad_soyad is empty string."""
        with pytest.raises(ValueError):
            await add_sofor(ad_soyad="")
