from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, get_current_active_user
from app.database.models import Kullanici
from app.schemas.api_responses import (
    AiChatResponse,
    AiProgressResponse,
    AiStatusResponse,
)
from v2.modules.ai_assistant.application.orchestrate_ai_response import get_ai_service

router = APIRouter()


class AiQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    category: str = Field("general", max_length=40)


async def _fuel_trend_chart(db) -> Optional[dict]:
    """yakit_alimlari aylık toplam tutar → line chart spec (deterministik)."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT to_char(date_trunc('month', tarih), 'YYYY-MM') AS ay, "
                    "COALESCE(SUM(toplam_tutar), 0) AS tutar "
                    "FROM yakit_alimlari "
                    "WHERE tarih >= now() - make_interval(months => 12) "
                    "GROUP BY 1 ORDER BY 1"
                )
            )
        )
        .mappings()
        .all()
    )
    data = [{"ay": r["ay"], "tutar": float(r["tutar"])} for r in rows]
    if not data:
        return None
    return {
        "type": "line",
        "title": "Aylık Yakıt Maliyeti (TL)",
        "x_key": "ay",
        "series": [{"key": "tutar", "label": "Toplam Tutar"}],
        "data": data,
    }


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        json_schema_extra={"example": "Filo durumu nedir?"},
    )
    history: Optional[List[dict]] = Field(
        default_factory=list,
        json_schema_extra={"example": [{"role": "user", "content": "Selam"}]},
    )


@router.get("/progress", response_model=AiProgressResponse)
async def get_ai_model_progress(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """AI Model durumunu döndürür."""
    return get_ai_service().get_progress()


@router.get("/status", response_model=AiStatusResponse)
async def get_ai_status(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """AI sisteminin genel durumunu döner."""
    progress = get_ai_service().get_progress()
    return {"is_ready": progress["status"] == "ready", "progress": progress}


@router.post("/chat", response_model=AiChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    AIService üzerinden RAG destekli sohbet et.
    """
    ai_service = get_ai_service()

    # Generate response via AIService (which handles context/RAG and history)
    response = await ai_service.generate_response(user_input=request.message)

    return {"response": response, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.post("/query")
async def ai_query(
    request: AiQueryRequest,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> dict:
    """Faz 9 — kategori-farkında AI sorgu: fuel_trend → grafik+aksiyon, general → LLM.

    Grafik gerçek DB verisinden deterministik üretilir; LLM yalnız anlatı için
    (best-effort: Groq kesintisi grafiği/aksiyonu/200'ü bloklamaz).
    """
    chart = None
    actions: list[dict] = []
    if request.category == "fuel_trend":
        chart = await _fuel_trend_chart(db)
        actions = [{"label": "Yakıt sayfası", "url": "/fuel"}]

    try:
        prompt = request.message
        if request.category == "fuel_trend" and chart:
            prompt = (
                f"{request.message}\n\nAylık yakıt maliyeti verisi: "
                f"{chart['data'][-6:]}. Kısa Türkçe yorumla."
            )
        answer = await get_ai_service().generate_response(user_input=prompt)
    except Exception:  # noqa: BLE001 — LLM kesintisi grafiği/aksiyonu bloklamaz
        answer = (
            "Yapay zeka yorumu şu an üretilemedi; grafik ve veriler aşağıda."
            if chart
            else "Yapay zeka şu an yanıt veremiyor."
        )

    return {
        "category": request.category,
        "answer": answer,
        "chart": chart,
        "actions": actions,
    }
