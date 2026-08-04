"""Internal endpoints -- only reachable within the Docker network.

Added 2026-08-04 for the prediction_ml_service extraction (see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md,
Task 5 Step 2b Option B). Same X-Internal-Token pattern as
admin_platform/api/internal_routes.py.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from v2.modules.ai_assistant.public import LLMMessage, get_llm_client, get_smart_ai


async def _require_internal_token(
    x_internal_token: Annotated[Optional[str], Header()] = None,
) -> None:
    secret = settings.INTERNAL_API_SECRET
    if not secret:
        if settings.ENVIRONMENT == "prod":
            raise HTTPException(
                status_code=503, detail="Internal API secret not configured"
            )
        return
    if x_internal_token != secret:
        raise HTTPException(status_code=401, detail="Invalid internal token")


router = APIRouter(
    prefix="/internal/ai",
    dependencies=[Depends(_require_internal_token)],
)


class TeachBody(BaseModel):
    msg: str
    category: str = "genel"


@router.post("/teach")
async def teach(body: TeachBody) -> dict:
    ok = await get_smart_ai().teach(body.msg, category=body.category)
    return {"ok": ok}


class ChatMessageBody(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: List[ChatMessageBody]
    system_prompt: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.3


@router.post("/chat")
async def chat(body: ChatBody) -> dict:
    llm = get_llm_client()
    answer = await llm.chat(
        messages=[LLMMessage(role=m.role, content=m.content) for m in body.messages],
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        system_prompt=body.system_prompt,
    )
    return {"answer": answer}
