import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, List

if TYPE_CHECKING:
    from groq import AsyncGroq
else:
    try:
        from groq import AsyncGroq
    except ImportError:
        AsyncGroq = None
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.pii_scrubber import scrub_pii

_GROQ_TIMEOUT_S = 30.0

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: datetime = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class GroqService:
    """
    Refined Groq API Service with Streaming, Reasoning, and RAG Support.
    """

    def __init__(self):
        self.api_key = (
            settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
        )
        self.model_name = settings.GROQ_MODEL_NAME
        self.client = None
        if self.api_key and AsyncGroq is not None:
            self.client = AsyncGroq(
                api_key=self.api_key, base_url=settings.GROQ_API_BASE_URL
            )
        elif self.api_key and AsyncGroq is None:
            logger.warning(
                "groq package is not installed. GroqService will be inactive."
            )
        else:
            logger.warning("GROQ_API_KEY is not set. GroqService will be inactive.")

    async def chat_stream(
        self,
        user_message: str,
        history: List[ChatMessage] = None,
        context: str = None,
        system_prompt: str = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Groq API üzerinden streaming yanıt üretir."""
        if not self.client:
            yield "Groq API anahtarı ayarlanmamış."
            return

        messages = self._prepare_messages(user_message, history, context, system_prompt)

        try:
            stream = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1,
                    stream=True,
                    stop=None,
                ),
                timeout=_GROQ_TIMEOUT_S,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except asyncio.TimeoutError:
            logger.error("Groq streaming timeout after %ss", _GROQ_TIMEOUT_S)
            yield "Hata: Yanıt zaman aşımına uğradı."
        except Exception as e:
            logger.error(f"Groq Streaming Error: {e}")
            yield f"Hata: {str(e)}"

    async def chat(
        self,
        user_message: str,
        history: List[ChatMessage] = None,
        context: str = None,
        system_prompt: str = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> str:
        """Groq API üzerinden blok (non-streaming) yanıt üretir."""
        if not self.client:
            return "Groq API anahtarı ayarlanmamış."

        messages = self._prepare_messages(user_message, history, context, system_prompt)

        try:
            completion = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1,
                    stream=False,
                    stop=None,
                ),
                timeout=_GROQ_TIMEOUT_S,
            )
            return completion.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error("Groq chat timeout after %ss", _GROQ_TIMEOUT_S)
            return "Hata: Yanıt zaman aşımına uğradı."
        except Exception as e:
            logger.error(f"Groq API Error: {e}")
            return f"Hata: {str(e)}"

    def _prepare_messages(
        self,
        user_message: str,
        history: List[ChatMessage],
        context: str,
        system_prompt: str,
    ) -> List[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"ÖNEMLİ - LojiNext Domain Bilgisi (RAG):\n{context}\nLütfen sadece bu verilere dayanarak yanıt ver.",  # noqa: E501
                }
            )

        if history:
            for msg in history[-5:]:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": scrub_pii(user_message)})
        return messages


# Singleton instance
_groq_service = None


def get_groq_service() -> GroqService:
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService()
    return _groq_service
