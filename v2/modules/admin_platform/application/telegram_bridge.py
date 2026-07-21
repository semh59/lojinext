"""Telegram bot ↔ backend köprüsü — iş mantığı.

Eski ``InternalService`` sınıfının B.1 gereği dissolve edilmiş hali: tek
alanı (``self._sofor_repo``) her çağrıda ``get_sofor_repo()`` ile trivially
yeniden kurulabiliyordu, gerçek mutable state yoktu.

All ORM/session management lives here; endpoints only handle HTTP concerns.
"""

import asyncio
import os
import uuid
from datetime import date
from typing import Dict, List, Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.driver.public import get_by_sofor_id, get_sofor_repo
from v2.modules.trip.public import SeferBelge

logger = get_logger(__name__)

_ALLOWED_BELGE_TIPLERI = frozenset({"yakit_fisi", "sefer_fisi", "tir_ekran"})
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


async def get_sofor_by_telegram_id(telegram_id: str) -> Optional[Dict]:
    """Telegram ID ile aktif şoför bilgisini döner, yoksa None."""
    repo = get_sofor_repo()
    return await repo.get_by_telegram_id(telegram_id)


async def kaydet_belge(
    telegram_id: str,
    belge_tipi: str,
    image_bytes: bytes,
    content_type: str,
    telegram_mesaj_id: Optional[int] = None,
) -> Dict:
    """
    Fotoğrafı diske yazar, DB kaydı oluşturur.
    Returns {belge_id, sofor_id}.
    Raises ValueError for unknown telegram_id.
    """
    repo = get_sofor_repo()
    sofor = await repo.get_by_telegram_id(telegram_id)
    if sofor is None:
        raise ValueError("Yetkisiz telegram_id")

    if belge_tipi not in _ALLOWED_BELGE_TIPLERI:
        raise ValueError(f"Geçersiz belge_tipi: {belge_tipi!r}")

    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Dosya {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor"
        )

    belgeler_dir = os.environ.get("BELGELER_UPLOAD_DIR", "/belgeler")
    os.makedirs(belgeler_dir, exist_ok=True)
    ext = ".jpg" if "jpeg" in content_type else ".png"
    filepath = os.path.join(belgeler_dir, f"{uuid.uuid4()}{ext}")

    def _write_file() -> None:
        with open(filepath, "wb") as fh:
            fh.write(image_bytes)

    await asyncio.to_thread(_write_file)

    try:
        async with UnitOfWork() as uow:
            belge = SeferBelge(
                sofor_id=sofor["id"],
                belge_tipi=belge_tipi,
                dosya_yolu=filepath,
                telegram_mesaj_id=telegram_mesaj_id,
                ocr_durumu="bekliyor",
            )
            uow.session.add(belge)
            await uow.flush()
            belge_id = int(belge.id)
            await uow.commit()
    except Exception:
        try:
            os.remove(filepath)
        except OSError:
            pass
        raise

    logger.info(
        "kaydet_belge: sofor_id=%s belge_tipi=%s belge_id=%s",
        sofor["id"],
        belge_tipi,
        belge_id,
    )
    return {"belge_id": belge_id, "sofor_id": sofor["id"]}


async def get_seferler(telegram_id: str, limit: int = 10) -> Optional[List[Dict]]:
    """Şofora ait son seferleri döner. Şoför bulunamazsa None."""
    repo = get_sofor_repo()
    sofor = await repo.get_by_telegram_id(telegram_id)
    if sofor is None:
        return None
    return await get_by_sofor_id(sofor["id"], limit=limit)


async def get_sofor_id(telegram_id: str) -> Optional[int]:
    """PDF oluşturma için sofor_id döner, bulunamazsa None."""
    repo = get_sofor_repo()
    sofor = await repo.get_by_telegram_id(telegram_id)
    return sofor["id"] if sofor else None


async def _arac_plaka(arac_id: int) -> Optional[str]:
    """Onay mesajı için aracın plakasını best-effort getirir (yoksa None)."""
    try:
        async with UnitOfWork() as uow:
            arac = await uow.arac_repo.get_by_id(arac_id)
    except Exception:
        return None
    if arac is None:
        return None
    if isinstance(arac, dict):
        return arac.get("plaka")
    return getattr(arac, "plaka", None)


async def report_driver_breakdown(
    telegram_id: str, *, detaylar: str = "", acil: bool = False
) -> Dict:
    """Sürücünün en son seferindeki araç için açık arıza/acil kaydı açar.

    Araç çözümü (ürün kararı A): en yeni sefer → arac_id. Sürücü plaka
    girmez. ValueError fırlatır: bilinmeyen telegram_id / sürücünün hiç
    seferi yok / son seferde araç tanımsız — endpoint bunları 404'e çevirir.
    """
    from app.database.models import BakimTipi
    from v2.modules.fleet.public import create_breakdown

    repo = get_sofor_repo()
    sofor = await repo.get_by_telegram_id(telegram_id)
    if sofor is None:
        raise ValueError("Telegram ID kayıtlı şoför bulunamadı")

    seferler = await get_by_sofor_id(sofor["id"], limit=1)
    if not seferler:
        raise ValueError("Şoföre ait sefer yok — araç otomatik çözülemiyor")
    arac_id = seferler[0].get("arac_id")
    if not arac_id:
        raise ValueError("Son seferde araç tanımlı değil — arıza bildirilemiyor")

    tip = BakimTipi.ACIL if acil else BakimTipi.ARIZA
    rec = await create_breakdown(bakim_tipi=tip, arac_id=int(arac_id), detaylar=detaylar)
    return {
        "bakim_id": rec.id,
        "arac_id": int(arac_id),
        "arac_plakasi": await _arac_plaka(int(arac_id)),
        "bakim_tipi": tip.value,
    }


async def olustur_pdf(
    telegram_id: str, baslangic: date, bitis: date
) -> Optional[bytes]:
    """Şofora ait onaylı seferleri PDF olarak üretir."""
    from v2.modules.driver.public import SoforSeferPDFService

    sofor_id = await get_sofor_id(telegram_id)
    if sofor_id is None:
        return None
    svc = SoforSeferPDFService()
    return await svc.olustur(sofor_id, baslangic, bitis)


async def get_coaching_snapshot(telegram_id: str) -> Optional[Dict]:
    """Telegram bot /score komutu için özetlenmiş koçluk snapshot'ı.

    Returns:
        None: telegram_id ile şoför bulunamadıysa.
        dict: {ad_soyad, skor, headline, top_suggestion, priority,
               insights_count, source}
    """
    repo = get_sofor_repo()
    sofor = await repo.get_by_telegram_id(telegram_id)
    if not sofor:
        return None

    from v2.modules.driver.public import get_driver_coaching_engine

    engine = get_driver_coaching_engine()
    try:
        insights = await engine.generate_coaching(int(sofor["id"]))
    except Exception as exc:
        logger.error("get_coaching_snapshot engine failed: %s", exc)
        return {
            "ad_soyad": sofor.get("ad_soyad", ""),
            "skor": float(sofor.get("score") or sofor.get("manual_score") or 1.0),
            "headline": "Koçluk önerisi şu an üretilemiyor",
            "top_suggestion": None,
            "priority": "low",
            "insights_count": 0,
            "source": "fallback",
        }

    top = insights.insights[0] if insights.insights else None
    return {
        "ad_soyad": insights.ad_soyad,
        "skor": float(sofor.get("score") or sofor.get("manual_score") or 1.0),
        "headline": insights.headline,
        "top_suggestion": top.suggestion if top else None,
        "priority": insights.priority,
        "insights_count": len(insights.insights),
        "source": insights.source,
    }
