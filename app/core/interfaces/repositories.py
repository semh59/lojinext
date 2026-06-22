"""
TIR Yakıt Takip Sistemi - Repository Interfaces
Abstract base sınıflar - Dependency Inversion için
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):  # pragma: no cover
    """Generic base repository"""

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """ID ile getir"""
        pass

    @abstractmethod
    async def get_all(self, **filters) -> List[T]:
        """Tümünü getir (filtreli)"""
        pass

    @abstractmethod
    async def add(self, entity: T) -> int:
        """Ekle ve ID döndür"""
        pass

    @abstractmethod
    async def update(self, entity: T) -> bool:
        """Güncelle"""
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Sil"""
        pass


class IAracRepository(BaseRepository):  # pragma: no cover
    """Araç repository interface"""

    @abstractmethod
    async def get_by_plaka(self, plaka: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def get_aktif_araclar(self) -> List[Any]:
        pass


class ISoforRepository(BaseRepository):  # pragma: no cover
    """Şoför repository interface"""

    @abstractmethod
    async def get_aktif_soforler(self) -> List[Any]:
        pass


class IYakitRepository(BaseRepository):  # pragma: no cover
    """Yakıt alımları repository interface"""

    @abstractmethod
    async def get_by_arac(self, arac_id: int, limit: int = 100) -> List[Any]:
        pass

    @abstractmethod
    async def get_by_date_range(self, start: date, end: date) -> List[Any]:
        pass

    @abstractmethod
    async def get_son_km(self, arac_id: int) -> int:
        pass


class ISeferRepository(BaseRepository):  # pragma: no cover
    """Sefer repository interface"""

    @abstractmethod
    async def get_by_arac(self, arac_id: int, limit: int = 100) -> List[Any]:
        pass

    @abstractmethod
    async def get_by_tarih(self, tarih: date) -> List[Any]:
        pass

    @abstractmethod
    async def get_bugunun_seferleri(self) -> List[Any]:
        pass

    @abstractmethod
    async def get_by_periyot(self, periyot_id: int) -> List[Any]:
        pass


class ILokasyonRepository(BaseRepository):  # pragma: no cover
    """Lokasyon repository interface"""

    @abstractmethod
    async def get_mesafe(self, cikis: str, varis: str) -> int:
        pass

    @abstractmethod
    async def get_benzersiz_yerler(self) -> List[str]:
        pass


class IPeriyotRepository(BaseRepository):  # pragma: no cover
    """Yakıt periyotları repository interface"""

    @abstractmethod
    async def get_by_arac(self, arac_id: int) -> List[Any]:
        pass

    @abstractmethod
    async def get_aktif_periyotlar(self) -> List[Any]:
        pass
