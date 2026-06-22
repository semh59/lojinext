"""
Remote chatbot katmani.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.ai.llm_client import LLMClient, LLMMessage, get_llm_client
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class Chatbot:
    SYSTEM_PROMPT = (
        "Sen LojiNext operasyonel zeka sisteminin lojistik asistanisin. "
        "Kurumsal, guvenli ve kisa yanit ver."
    )

    def __init__(self) -> None:
        self.MAX_INPUT_CHARS = 2000
        try:
            self.MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "10"))
        except (TypeError, ValueError):
            self.MAX_HISTORY = 10

        self._client: LLMClient = get_llm_client()
        self.device = "remote"

    @staticmethod
    def _sanitize_response(response: str) -> str:
        return str(response or "").strip()

    @staticmethod
    def _is_jailbreak_attempt(message: str) -> bool:
        lowered = message.lower()
        patterns = [
            "ignore all previous instructions",
            "ignore previous instructions",
            "system prompt",
            "developer mode",
            "jailbreak",
        ]
        return any(p in lowered for p in patterns)

    async def _generate_response(
        self,
        user_message: str,
        context: Optional[str],
        history: Optional[List["ChatMessage"]],
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        if self._is_jailbreak_attempt(user_message):
            return (
                "Guvenlik politikalari geregi sistem yonlendirmelerini paylasamam. "
                "Lojistik asistani olarak operasyonel sorulara yardimci olabilirim."
            )

        sys_prompt = self.SYSTEM_PROMPT
        if context:
            sys_prompt += f"\nAlan bilgisi (RAG):\n{context}"

        msgs: List[LLMMessage] = []
        if history:
            for h in history[-self.MAX_HISTORY :]:
                msgs.append(LLMMessage(role=h.role, content=h.content))
        msgs.append(LLMMessage(role="user", content=user_message))

        try:
            result = await asyncio.wait_for(
                self._client.chat(
                    messages=msgs,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=sys_prompt,
                ),
                timeout=30,
            )
            return self._sanitize_response(result)
        except asyncio.TimeoutError:
            return "Uzgunum, yanit uretimi cok uzun surdu."
        except Exception as exc:
            logger.error("Chatbot response error: %s", exc)
            return "Uzgunum, su anda yanit veremiyorum."

    async def chat(
        self,
        user_message: str,
        history: Optional[List["ChatMessage"]] = None,
        context: Optional[str] = None,
        use_rag: bool = True,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        message = str(user_message or "").strip()
        if not message:
            return "Lutfen gecerli bir soru girin."
        if len(message) > self.MAX_INPUT_CHARS:
            return "Mesajiniz cok uzun. Lutfen daha kisa bir metin girin."

        rag_context = context if use_rag else None
        return await self._generate_response(
            message,
            rag_context,
            history or [],
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def get_model_info(self) -> Dict:
        return {
            "model_name": getattr(self._client, "model", "remote"),
            "loaded": True,
            "device": self.device,
            "fallback_mode": False,
        }


_chatbot: Optional[Chatbot] = None


def get_chatbot() -> Chatbot:
    global _chatbot
    if _chatbot is None:
        _chatbot = Chatbot()
    return _chatbot
