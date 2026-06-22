"""UoW mocking helper.

Production tarafında `async with UnitOfWork() as uow:` ile master listeleri
çekiyoruz. Test'te bu UoW'u patch etmek için ortak bir async context manager:

    from app.tests._helpers.uow_mock import patch_unit_of_work

    def test_x(monkeypatch):
        fake = patch_unit_of_work(
            monkeypatch,
            "app.services.api.sefer_import_service",  # patch hedef modülü
            arac_repo_get_all=[{"id": 1, "plaka": "34ABC"}],
            sofor_repo_get_all=[{"id": 7, "ad_soyad": "Ali Veli"}],
            ...
        )

Tek dosya başına birden fazla modül patch'lenecekse `patch_unit_of_work`'ü
ardışık çağır; her biri kendi modülünün ``UnitOfWork`` referansını günceller.
"""

from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import AsyncMock


class FakeUnitOfWork:
    """Async context manager kılığında bir mock UoW.

    Repo attribute'larını dışarıdan inject edersin; `.commit()`, `.rollback()`
    ve `.session` no-op AsyncMock. Refactor sırasında repo eklenir/silinirse
    AsyncMock genel davranışı testleri yormaz, sadece beklenenler kontrol
    edilir.
    """

    def __init__(
        self,
        *,
        arac_repo: Optional[Any] = None,
        sofor_repo: Optional[Any] = None,
        dorse_repo: Optional[Any] = None,
        lokasyon_repo: Optional[Any] = None,
        yakit_repo: Optional[Any] = None,
        sefer_repo: Optional[Any] = None,
        import_repo: Optional[Any] = None,
        route_repo: Optional[Any] = None,
    ):
        self.arac_repo = arac_repo or AsyncMock()
        self.sofor_repo = sofor_repo or AsyncMock()
        self.dorse_repo = dorse_repo or AsyncMock()
        self.lokasyon_repo = lokasyon_repo or AsyncMock()
        self.yakit_repo = yakit_repo or AsyncMock()
        self.sefer_repo = sefer_repo or AsyncMock()
        self.import_repo = import_repo or AsyncMock()
        self.route_repo = route_repo or AsyncMock()
        self.session = AsyncMock()
        # Test'ler enter/exit/commit/rollback sayısına bakabilsin.
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _make_repo_mock(get_all: Optional[List[Any]] = None, **methods: Any) -> AsyncMock:
    """``return_value`` set'lenmiş AsyncMock üret — repo davranışlarını taklit."""
    repo = AsyncMock()
    if get_all is not None:
        repo.get_all = AsyncMock(return_value=get_all)
    for name, value in methods.items():
        if callable(value):
            setattr(repo, name, value)
        else:
            setattr(repo, name, AsyncMock(return_value=value))
    return repo


def patch_unit_of_work(
    monkeypatch,
    module_path: str,
    *,
    arac_repo_get_all: Optional[List[Any]] = None,
    sofor_repo_get_all: Optional[List[Any]] = None,
    dorse_repo_get_all: Optional[List[Any]] = None,
    lokasyon_repo_get_all: Optional[List[Any]] = None,
    yakit_repo_get_all: Optional[List[Any]] = None,
    arac_repo: Optional[Any] = None,
    sofor_repo: Optional[Any] = None,
    dorse_repo: Optional[Any] = None,
    lokasyon_repo: Optional[Any] = None,
    yakit_repo: Optional[Any] = None,
    sefer_repo: Optional[Any] = None,
) -> FakeUnitOfWork:
    """`module_path.UnitOfWork`'ü `FakeUnitOfWork` döndüren factory ile değiştir.

    ``*_repo_get_all`` parametreleri en sık ihtiyaç duyulan kısayol —
    direkt list verirsen repo.get_all return_value set'lenir. Daha kompleks
    setup gerekirse bütün ``*_repo`` AsyncMock'unu kendin geç.
    """
    fake = FakeUnitOfWork(
        arac_repo=arac_repo or _make_repo_mock(arac_repo_get_all),
        sofor_repo=sofor_repo or _make_repo_mock(sofor_repo_get_all),
        dorse_repo=dorse_repo or _make_repo_mock(dorse_repo_get_all),
        lokasyon_repo=lokasyon_repo or _make_repo_mock(lokasyon_repo_get_all),
        yakit_repo=yakit_repo or _make_repo_mock(yakit_repo_get_all),
        sefer_repo=sefer_repo,
    )
    monkeypatch.setattr(f"{module_path}.UnitOfWork", lambda: fake)
    return fake
