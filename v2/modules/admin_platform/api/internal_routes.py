"""Internal endpoints — only reachable within the Docker network.

These endpoints are called by telegram_bot containers. Every request must
carry the X-Internal-Token header matching settings.INTERNAL_API_SECRET.
Routes are NOT exposed through the public reverse-proxy.
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from app.config import settings
from v2.modules.admin_platform.application.integration_secrets import (
    BOT_TOKEN_SERVICES,
    get_integration_secret,
)
from v2.modules.admin_platform.application.telegram_bridge import (
    get_coaching_snapshot,
    get_seferler,
    get_sofor_by_telegram_id,
    kaydet_belge,
    olustur_pdf,
    report_driver_breakdown,
)
from v2.modules.admin_platform.schemas import (
    CoachingSnapshotResponse,
    DriverBreakdownRequest,
    SeferBelgeResponse,
    SoforTelegramInfo,
)
from v2.modules.platform_infra.metrics import telegram_belge_upload_total
from v2.modules.shared_kernel.schemas.api_responses import PDF_RESPONSES


async def _require_internal_token(
    x_internal_token: Annotated[Optional[str], Header()] = None,
) -> None:
    """Reject requests that do not carry the correct shared secret."""
    secret = settings.INTERNAL_API_SECRET
    if not secret:
        if settings.ENVIRONMENT == "prod":
            raise HTTPException(
                status_code=503, detail="Internal API secret not configured"
            )
        return
    if x_internal_token != secret:
        raise HTTPException(status_code=401, detail="Invalid internal token")


router = APIRouter(dependencies=[Depends(_require_internal_token)])

_ALLOWED_BELGE_TIPLERI = frozenset({"yakit_fisi", "sefer_fisi", "tir_ekran"})
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _looks_like_allowed_image(data: bytes) -> bool:
    """Verify the bytes actually start with a JPEG/PNG/WEBP signature.

    The Content-Type header is client-supplied and can be spoofed, so the MIME
    allow-list alone does not guarantee the payload is an image. Sniffing the
    magic bytes stops arbitrary content from being stored and queued for OCR.
    """
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":  # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WEBP
        return True
    return False


# ── Bot token bootstrap (admin-configurable Telegram tokens) ────────────────
# The telegram-driver-bot/telegram-ops-bot containers call this ONCE at
# startup to resolve their token: DB override (set via the admin UI) else
# their own .env fallback. This is the only place a plaintext value from
# entegrasyon_ayarlari ever leaves this backend process — deliberately
# restricted to BOT_TOKEN_SERVICES (NOT all of KNOWN_SERVICES), so a bug
# here can never leak the mapbox/openroute/groq keys.


@router.get("/bot-token/{servis_adi}")
async def bot_token(servis_adi: str) -> dict:
    if servis_adi not in BOT_TOKEN_SERVICES:
        raise HTTPException(status_code=404, detail="Bilinmeyen bot servisi")
    token = await get_integration_secret(servis_adi, env_fallback=None)
    if not token:
        raise HTTPException(status_code=404, detail="Yapılandırılmamış")
    return {"token": token}


# ── Şoför kimlik doğrulaması ─────────────────────────────────────────────────


@router.get("/sofor-by-telegram/{telegram_id}", response_model=SoforTelegramInfo)
async def sofor_by_telegram(telegram_id: str) -> SoforTelegramInfo:
    sofor = await get_sofor_by_telegram_id(telegram_id)
    if sofor is None:
        raise HTTPException(
            status_code=404, detail="Telegram ID kayıtlı şoför bulunamadı"
        )
    return SoforTelegramInfo(
        sofor_id=sofor["id"],
        ad_soyad=sofor["ad_soyad"],
        aktif=sofor["aktif"],
    )


# ── Feature A.4 — koçluk snapshot (bot /score komutu için) ───────────────


@router.get("/sofor-coaching/{telegram_id}", response_model=CoachingSnapshotResponse)
async def sofor_coaching_snapshot(telegram_id: str):
    """Bot için özetlenmiş koçluk verisi. Sofor bulunamazsa 404."""
    snapshot = await get_coaching_snapshot(telegram_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Telegram ID kayıtlı şoför bulunamadı",
        )
    return snapshot


# ── Belge yükleme ────────────────────────────────────────────────────────────


@router.post("/sefer-belge", response_model=SeferBelgeResponse, status_code=200)
async def sefer_belge_yukle(
    telegram_id: str = Form(...),
    belge_tipi: str = Form(...),
    telegram_mesaj_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
) -> SeferBelgeResponse:
    if belge_tipi not in _ALLOWED_BELGE_TIPLERI:
        raise HTTPException(
            status_code=422, detail=f"Geçersiz belge_tipi: '{belge_tipi}'"
        )

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415, detail=f"Desteklenmeyen dosya türü: {content_type}"
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="Dosya boyutu 10 MB sınırını aşıyor"
        )
    if not _looks_like_allowed_image(content):
        # Content-Type said image/* but the bytes are not a real JPEG/PNG/WEBP.
        raise HTTPException(
            status_code=415,
            detail="Dosya içeriği desteklenen bir görsel (JPEG/PNG/WEBP) değil.",
        )

    try:
        mesaj_id = int(telegram_mesaj_id) if telegram_mesaj_id else None
    except (ValueError, TypeError):
        mesaj_id = None

    try:
        result = await kaydet_belge(
            telegram_id=telegram_id,
            belge_tipi=belge_tipi,
            image_bytes=content,
            content_type=content_type,
            telegram_mesaj_id=mesaj_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    from v2.modules.import_excel.public import process_belge_ocr

    process_belge_ocr.delay(result["belge_id"])
    telegram_belge_upload_total.labels(belge_tipi=belge_tipi).inc()

    return SeferBelgeResponse(
        id=result["belge_id"],
        sofor_id=result["sofor_id"],
        sefer_id=None,
        belge_tipi=belge_tipi,
        ocr_durumu="bekliyor",
        ocr_veri=None,
        olusturulma=None,
    )


# ── Sefer listesi (şofora özel) ──────────────────────────────────────────────


@router.get("/sofor-seferler/{telegram_id}")
async def sofor_seferler(
    telegram_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> list:
    seferler = await get_seferler(telegram_id, limit=limit)
    if seferler is None:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    return [
        {
            "id": s.get("id"),
            "tarih": str(s.get("tarih", "")),
            "cikis_yeri": s.get("cikis_yeri"),
            "varis_yeri": s.get("varis_yeri"),
            "durum": s.get("durum"),
            "onay_durumu": s.get("onay_durumu"),
        }
        for s in seferler
    ]


# ── Arıza bildirimi (bot /ariza komutu) ──────────────────────────────────────


@router.post("/driver-breakdown", status_code=201)
async def driver_breakdown(payload: DriverBreakdownRequest) -> dict:
    """Sürücünün son seferindeki araç için açık arıza/acil kaydı oluşturur.

    Araç otomatik çözülür (sürücünün en yeni seferi). Çözülemezse 404.
    """
    try:
        return await report_driver_breakdown(
            payload.telegram_id, detaylar=payload.detaylar, acil=payload.acil
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── PDF indirme ──────────────────────────────────────────────────────────────


@router.get(
    "/sofor-pdf/{telegram_id}",
    responses=PDF_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def sofor_pdf(
    telegram_id: str,
    baslangic_tarihi: date = Query(...),
    bitis_tarihi: date = Query(...),
) -> StreamingResponse:
    pdf_bytes = await olustur_pdf(telegram_id, baslangic_tarihi, bitis_tarihi)

    if not pdf_bytes:
        raise HTTPException(
            status_code=404,
            detail="Belirtilen tarih aralığında onaylanmış sefer yok",
        )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=seferler_{baslangic_tarihi}_{bitis_tarihi}.pdf"
            )
        },
    )
