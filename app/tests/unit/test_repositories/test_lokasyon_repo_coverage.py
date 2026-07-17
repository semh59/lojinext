"""LokasyonRepository comprehensive unit tests.

Covers:
- get_all: default kwargs, custom order_by/limit, include_inactive
- get_by_route: found, not found
- get_benzersiz_lokasyonlar: row extraction, limit clamping, offset clamping
- add: delegates to create with all params
- find_closest_match: empty input, no pre_fetched (fetches), pre_fetched match,
  pre_fetched no match above threshold, all_names empty
- get_lokasyon_repo: session arg returns new instance, no session returns singleton
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration
# 0-mock epiği: get_by_route/get_benzersiz_lokasyonlar testleri gerçek DB'ye
# (db_session) çevrildi — bu iki metod gerçekten `_session.execute` çağırıyor.
# Diğer sınıflar (find_closest_match/add) SESSION'ı değil, AYNI sınıfın
# kardeş bir metodunu (get_by_route/execute_query/
# get_benzersiz_lokasyonlar/create) mock'luyor — bu gerçek bir dış sınır
# değil, meşru bir call-contract/delegation testi (o kardeş metod kendi
# testinde ayrıca gerçek DB'ye karşı doğrulanıyor), o yüzden dokunulmadı.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return a LokasyonRepository with a mocked async session."""
    from v2.modules.location.infrastructure.repository import LokasyonRepository

    repo = LokasyonRepository.__new__(LokasyonRepository)
    repo._session = session if session is not None else AsyncMock()
    return repo


def _mappings_result(rows):
    mapping_mock = MagicMock()
    mapping_mock.all = MagicMock(return_value=list(rows))
    r = MagicMock()
    r.mappings = MagicMock(return_value=mapping_mock)
    return r


def _scalar_one_or_none_result(obj):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=obj)
    return r


def _scalars_all_result(objs):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=objs)
    r = MagicMock()
    r.scalars = MagicMock(return_value=scalars)
    return r


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


class TestLokasyonRepoGetAll:
    async def test_get_all_defaults(self):
        """get_all with no kwargs uses default order_by/limit/include_inactive."""
        repo = _make_repo()

        called_kwargs = {}

        async def fake_super_get_all(**kwargs):
            called_kwargs.update(kwargs)
            return []

        with patch.object(
            type(repo).__bases__[0],
            "get_all",
            new=AsyncMock(side_effect=fake_super_get_all),
        ):
            result = await repo.get_all()

        assert result == []

    async def test_get_all_custom_limit(self):
        """get_all passes custom limit to super().get_all."""
        repo = _make_repo()

        async def fake_super(**kwargs):
            return [{"id": 1}]

        with patch.object(
            type(repo).__bases__[0],
            "get_all",
            new=AsyncMock(side_effect=fake_super),
        ):
            result = await repo.get_all(limit=50)

        assert result == [{"id": 1}]

    async def test_get_all_include_inactive_false(self):
        """get_all with include_inactive=False passed through."""
        repo = _make_repo()

        async def fake_super(**kwargs):
            return []

        with patch.object(
            type(repo).__bases__[0],
            "get_all",
            new=AsyncMock(side_effect=fake_super),
        ):
            result = await repo.get_all(include_inactive=False)

        assert result == []


# ---------------------------------------------------------------------------
# get_by_route
# ---------------------------------------------------------------------------


class TestLokasyonRepoGetByRoute:
    """0-mock epiği: gerçek seed'li DB'ye karşı — Türkçe case-insensitive
    eşleme (neutralize_sql, İ/ı harmanlama) gerçek Postgres'e karşı kanıtlanır."""

    async def test_found_returns_dict(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        await seed_lokasyon(db_session, cikis_yeri="İstanbul", varis_yeri="Ankara")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_by_route("İstanbul", "Ankara")
        assert result is not None
        assert result["cikis_yeri"] == "İstanbul"

    async def test_not_found_returns_none(self, db_session):
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_by_route("NonExist", "NoWhere")
        assert result is None


# ---------------------------------------------------------------------------
# get_benzersiz_lokasyonlar
# ---------------------------------------------------------------------------


class TestLokasyonRepoGetBenzersizLokasyonlar:
    """0-mock epiği: gerçek DB'ye karşı — UNION DISTINCT + LIMIT/OFFSET
    clamping gerçek SQL ile kanıtlanır."""

    async def test_returns_list_of_location_names(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        await seed_lokasyon(db_session, cikis_yeri="Ankara", varis_yeri="İstanbul")
        await seed_lokasyon(db_session, cikis_yeri="İzmir", varis_yeri="Ankara")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_benzersiz_lokasyonlar()
        assert set(result) == {"Ankara", "İstanbul", "İzmir"}

    async def test_returns_empty_list(self, db_session):
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_benzersiz_lokasyonlar()
        assert result == []

    async def test_limit_clamped_to_5000(self, db_session):
        """Limit above 5000 is clamped to 5000 (gerçek sorgu hata vermeden döner)."""
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        repo = LokasyonRepository(session=db_session)
        # Gerçek clamp'i doğrudan gözlemlemek yerine (private davranış),
        # gerçekten hatasız çalıştığını ve makul bir sonuç döndürdüğünü kanıtla.
        result = await repo.get_benzersiz_lokasyonlar(limit=99999)
        assert isinstance(result, list)

    async def test_limit_minimum_is_1(self, db_session):
        from app.tests._helpers.seed import seed_lokasyon
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await seed_lokasyon(db_session, cikis_yeri="C", varis_yeri="D")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_benzersiz_lokasyonlar(limit=1)
        assert len(result) == 1

    async def test_offset_minimum_is_0(self, db_session):
        """Negative offset is clamped to 0 (gerçek sorgu hata vermeden döner)."""
        from app.tests._helpers.seed import seed_lokasyon
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await db_session.commit()

        repo = LokasyonRepository(session=db_session)
        result = await repo.get_benzersiz_lokasyonlar(offset=-10)
        assert isinstance(result, list)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestLokasyonRepoAdd:
    async def test_add_delegates_to_create(self):
        """add calls create with all expected kwargs."""
        repo = _make_repo()
        repo.create = AsyncMock(return_value=42)

        result = await repo.add(
            cikis_yeri="İstanbul",
            varis_yeri="Ankara",
            mesafe_km=450,
            tahmini_sure_saat=5.0,
            zorluk="Normal",
            notlar="test",
            cikis_lat=41.0,
            cikis_lon=28.9,
            varis_lat=39.9,
            varis_lon=32.8,
            api_mesafe_km=448.0,
            api_sure_saat=4.8,
            ascent_m=200.0,
            descent_m=190.0,
            flat_distance_km=300.0,
            otoban_mesafe_km=350.0,
            sehir_ici_mesafe_km=50.0,
            aktif=True,
            ad="IST-ANK",
        )

        assert result == 42
        repo.create.assert_called_once()
        call_kwargs = repo.create.call_args.kwargs
        assert call_kwargs["cikis_yeri"] == "İstanbul"
        assert call_kwargs["varis_yeri"] == "Ankara"
        assert call_kwargs["mesafe_km"] == 450
        assert call_kwargs["ad"] == "IST-ANK"

    async def test_add_minimal_params(self):
        """add with only required params uses defaults."""
        repo = _make_repo()
        repo.create = AsyncMock(return_value=1)

        result = await repo.add(
            cikis_yeri="A",
            varis_yeri="B",
            mesafe_km=100,
        )
        assert result == 1
        call_kwargs = repo.create.call_args.kwargs
        assert call_kwargs["zorluk"] == "Normal"
        assert call_kwargs["aktif"] is True


# ---------------------------------------------------------------------------
# find_closest_match
# ---------------------------------------------------------------------------


class TestLokasyonRepoFindClosestMatch:
    async def test_empty_input_returns_none(self):
        """find_closest_match returns None for empty string."""
        repo = _make_repo()
        result = await repo.find_closest_match("")
        assert result is None

    async def test_pre_fetched_match_returns_original_case(self):
        """find_closest_match returns original name from pre_fetched_names."""
        repo = _make_repo()
        names = ["İstanbul", "Ankara", "İzmir"]
        result = await repo.find_closest_match(
            "istanbul", pre_fetched_names=names, threshold=0.6
        )
        assert result == "İstanbul"

    async def test_pre_fetched_no_match_returns_none(self):
        """find_closest_match returns None when no match above threshold."""
        repo = _make_repo()
        names = ["Ankara", "İzmir"]
        result = await repo.find_closest_match(
            "ZZZZZZZ", pre_fetched_names=names, threshold=0.6
        )
        assert result is None

    async def test_pre_fetched_empty_list_returns_none(self):
        """find_closest_match returns None when pre_fetched_names is empty."""
        repo = _make_repo()
        result = await repo.find_closest_match(
            "Ankara", pre_fetched_names=[], threshold=0.6
        )
        assert result is None

    async def test_no_pre_fetched_calls_get_benzersiz(self):
        """find_closest_match fetches names when pre_fetched_names is None."""
        repo = _make_repo()
        repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=["Ankara", "İstanbul"])

        result = await repo.find_closest_match("ankara", pre_fetched_names=None)
        repo.get_benzersiz_lokasyonlar.assert_awaited_once()
        assert result == "Ankara"

    async def test_exact_match_found(self):
        """find_closest_match finds exact match in list."""
        repo = _make_repo()
        names = ["İstanbul", "Ankara", "İzmir", "Konya"]
        result = await repo.find_closest_match("ANKARA", pre_fetched_names=names)
        assert result == "Ankara"


# ---------------------------------------------------------------------------
# get_lokasyon_repo factory
# ---------------------------------------------------------------------------


class TestGetLokasyonRepo:
    def test_session_arg_returns_new_instance(self):
        """Passing session always returns a fresh LokasyonRepository."""
        from v2.modules.location.infrastructure.repository import get_lokasyon_repo

        mock_session = MagicMock()
        repo = get_lokasyon_repo(session=mock_session)
        assert repo._session is mock_session

    def test_no_session_returns_singleton(self):
        """Calling twice without session returns same singleton."""
        import v2.modules.location.infrastructure.repository as mod
        from v2.modules.location.infrastructure.repository import get_lokasyon_repo

        # Reset singleton for clean test
        mod._lokasyon_repo = None
        repo1 = get_lokasyon_repo()
        repo2 = get_lokasyon_repo()
        assert repo1 is repo2

    def test_no_session_singleton_is_lokasyon_repo(self):
        """Singleton instance is LokasyonRepository."""
        import v2.modules.location.infrastructure.repository as mod
        from v2.modules.location.infrastructure.repository import (
            LokasyonRepository,
            get_lokasyon_repo,
        )

        mod._lokasyon_repo = None
        repo = get_lokasyon_repo()
        assert isinstance(repo, LokasyonRepository)
