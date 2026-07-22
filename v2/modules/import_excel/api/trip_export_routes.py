"""Sefer (trip) Excel export/şablon route'ları.

Dalga 14 — ``app/api/v1/endpoints/trips.py``'den taşındı (task dosyası
madde 2'nin kararı); mantık zaten bu modülün ``public.py``'sini
(``export_data``/``generate_template``) çağırıyordu, yalnız route
fonksiyonlarının fiziksel konumu değişti. ``api.py``'de hâlâ
``prefix="/trips"`` ile mount edilir — URL'ler DEĞİŞMEDİ.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import get_sefer_service
from v2.modules.auth_rbac.public import Kullanici, require_permissions
from v2.modules.import_excel.public import export_data, generate_template
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.shared_kernel.schemas.api_responses import EXCEL_XLSX_RESPONSES
from v2.modules.trip.public import SeferService

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/export",
    response_class=StreamingResponse,
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
)
async def export_seferler(
    background_tasks: BackgroundTasks,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Sefer listesini Excel olarak dışa aktar (Filtreli ve Limitli)."""
    try:
        MAX_EXPORT_LIMIT = 5000

        # Seferleri getir (MAX_EXPORT_LIMIT uygulanmis hali)
        seferler = await service.get_all_paged(
            current_user=current_user,
            skip=0,
            limit=MAX_EXPORT_LIMIT,
            aktif_only=False,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            durum=durum,
            search=search,
        )

        items = seferler.get("items", [])
        total = int((seferler.get("meta") or {}).get("total") or len(items))

        if total > MAX_EXPORT_LIMIT:
            raise ValueError(
                f"{MAX_EXPORT_LIMIT} satir limitini astiniz, tarih araligini daraltin."
            )

        data = []
        for s in items:
            d = s.model_dump() if hasattr(s, "model_dump") else s
            if getattr(s, "tarih", None):
                d["tarih"] = s.tarih.strftime("%Y-%m-%d")
            else:
                d["tarih"] = d.get("tarih", "")

            d["durum"] = getattr(s, "durum", d.get("durum"))
            d["plaka"] = getattr(s, "plaka", d.get("plaka", ""))
            d["sofor"] = getattr(s, "sofor_adi", d.get("sofor", ""))
            data.append(d)

        # Excel oluştur
        content = await export_data(data, type="sefer_listesi")
        filename = (
            f"sefer_listesi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
        )
        import urllib.parse

        encoded_filename = urllib.parse.quote(filename)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel export error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Excel dışa aktarım sırasında hata oluştu"
        )


@router.get(
    "/excel/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_excel_template(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
):
    """Sefer yükleme için örnek Excel şablonu indir."""
    try:
        content = await generate_template(type="sefer")
        filename = "sefer_yukleme_sablonu.xlsx"

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating trip template: {e}")
        raise HTTPException(status_code=500, detail="Şablon oluşturulamadı")
