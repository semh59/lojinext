import hashlib
import os
from datetime import date
from typing import Dict, Optional

from sqlalchemy import func, select

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.fleet.public import count_active_vehicles

logger = get_logger(__name__)


class LicenseEngine:
    """
        LojiNext AI Ticari Kısıt ve Lisans Yönetim Sistemi.

        Güvenlik:
            - License key'ler kaynak kodda açık değil (hash-based validation)
            - Environment variable ile konfigüre edilebilir
            - Audit logging aktif

    TYPE: SINGLETON
    SCOPE: Application lifetime
    SINGLETON_REASON: Lisans doğrulama — konfigürasyon tabanlı, stateless
    olmayan (env'den bir kez yüklenen ``_LICENSE_HASHES`` mutable state'i
    var) — B.1 istisnası, driver/CLAUDE.md'deki DriverPerformanceML ile aynı
    gerekçe sınıfı (mutable, tekrar-hesaplanması pahalı/gereksiz durum).
    CREATED_BY: app/core/container.py (lazy property)
    """

    LIMITS = {
        "FREE": {"max_cars": 5, "max_trips_monthly": 100},
        "PRO": {"max_cars": 50, "max_trips_monthly": 2000},
        "ENTERPRISE": {"max_cars": 999999, "max_trips_monthly": 999999},
    }

    # License key hash'leri (SHA-256) - Environment variable'lardan okunur
    # Fallback: Geliştirme ortamı için test hash'leri
    _LICENSE_HASHES: Dict[str, str] = {}

    def __init__(self):
        self.license_key: Optional[str] = None
        self.tier: str = "FREE"
        # Instance-scoped kopya — aksi halde `self._LICENSE_HASHES[k] = v`
        # sınıf-seviyesi dict'i mutate eder ve her yeni LicenseEngine()
        # instance'ı öncekiyle state paylaşır/kirletir (üretimde container'ın
        # tek singleton'ıyla maskeleniyordu, 2026-07-16 dedektif denetiminde
        # bulundu — testte veya ikinci bir instantiation'da gerçek risk).
        self._LICENSE_HASHES = dict(type(self)._LICENSE_HASHES)
        self._init_license_hashes()

    def _init_license_hashes(self):
        """Environment variable'lardan license hash'lerini yükle"""
        # PRO tier hash (env: LICENSE_PRO_HASH veya LICENSE_PRO_KEY'in hash'i)
        pro_hash = os.getenv("LICENSE_PRO_HASH")
        if not pro_hash:
            pro_key = os.getenv("LICENSE_PRO_KEY", "")
            if pro_key:
                pro_hash = hashlib.sha256(pro_key.encode()).hexdigest()
        if pro_hash:
            self._LICENSE_HASHES[pro_hash] = "PRO"

        # ENTERPRISE tier hash
        ent_hash = os.getenv("LICENSE_ENTERPRISE_HASH")
        if not ent_hash:
            ent_key = os.getenv("LICENSE_ENTERPRISE_KEY", "")
            if ent_key:
                ent_hash = hashlib.sha256(ent_key.encode()).hexdigest()
        if ent_hash:
            self._LICENSE_HASHES[ent_hash] = "ENTERPRISE"

    def _validate_license_key(self, key: str) -> str:
        """License key'i hash ile doğrula ve tier döndür"""
        if not key:
            return "FREE"

        key_hash = hashlib.sha256(key.encode()).hexdigest()
        tier = self._LICENSE_HASHES.get(key_hash, "FREE")

        if tier != "FREE":
            logger.info(f"License doğrulandı: {tier} tier aktif")

        return tier

    async def get_current_tier(self) -> str:
        """Sistemin aktif lisans seviyesini getir (Hash-based validation).

        Lazy import zorunlu: ``auth_rbac.public`` → ``license_service`` →
        ``admin_platform.public`` → ``admin_audit_service`` →
        ``auth_rbac.public`` çemberini kırar (ampirik doğrulandı — dalga 16
        task #58'de ``SistemKonfig`` admin_platform'a taşınınca ortaya
        çıktı, ``check_monthly_trip_limit``'teki aynı desenle tutarlı).
        """
        from v2.modules.admin_platform.public import SistemKonfig as Ayarlar

        async with UnitOfWork() as uow:
            stmt = select(Ayarlar.deger).where(Ayarlar.anahtar == "LICENSE_KEY")
            result = await uow.session.execute(stmt)
            key = result.scalar_one_or_none()

            return self._validate_license_key(key or "")

    async def check_car_limit(self) -> bool:
        """Araç ekleme limiti kontrolü"""
        tier = await self.get_current_tier()
        limit = self.LIMITS[tier]["max_cars"]

        count = await count_active_vehicles()
        if count >= limit:
            logger.warning(
                f"Lisans Limiti: Araç sınırına ulaşıldı ({count}/{limit}). Seviye: {tier}"
            )
            return False
        return True

    async def check_monthly_trip_limit(self) -> bool:
        """Aylık sefer limiti kontrolü.

        ``Sefer`` (``trip.public.SeferORM``) doğrudan ORM erişimi (dalga 16,
        task #58'de ``trip.public`` üzerinden düzeltildi — ayrı bir
        use-case fonksiyonuna sarmak bu dalganın kapsamı dışı, mekanik
        import-path düzeltmesi). Lazy import zorunlu: ``auth_rbac.public``
        → ``license_service`` → ``trip.public`` → (list_trips.py vb.) →
        ``auth_rbac.public`` çemberini kırar (ampirik doğrulandı —
        top-level'da ``import app.main`` gerçekten patlıyordu).
        """
        from v2.modules.trip.public import SeferORM as Sefer

        tier = await self.get_current_tier()
        limit = self.LIMITS[tier]["max_trips_monthly"]

        today = date.today()
        first_day = today.replace(day=1)

        async with UnitOfWork() as uow:
            count = await uow.session.scalar(
                select(func.count(Sefer.id)).where(
                    Sefer.tarih >= first_day,
                    Sefer.is_deleted.is_(False),
                )
            )
            if count >= limit:
                logger.warning(
                    f"Lisans Limiti: Aylık sefer sınırına ulaşıldı ({count}/{limit}). Seviye: {tier}"
                )
                return False
        return True


def get_license_engine() -> LicenseEngine:
    from app.core.container import get_container

    return get_container().license_service
