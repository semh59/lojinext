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
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.security.pii_scrubber import scrub_pii
from v2.modules.shared_kernel.exceptions import LLMProviderError

_GROQ_TIMEOUT_S = 30.0

logger = get_logger(__name__)


def _sdk_base_url(configured: str) -> str:
    """AsyncGroq's own request builder already appends "/openai/v1"
    internally (its default base_url, when none is passed, is just
    "https://api.groq.com" — see groq.AsyncGroq.__init__). Passing our
    already-suffixed settings.GROQ_API_BASE_URL (correct as-is for
    llm_client.py's raw httpx client, which appends only "/chat/completions")
    straight to the SDK doubles the prefix to
    ".../openai/v1/openai/v1/chat/completions", 404ing on every call.
    Strip the suffix here so the SDK adds it exactly once."""
    return configured.removesuffix("/openai/v1")


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
                api_key=self.api_key, base_url=_sdk_base_url(settings.GROQ_API_BASE_URL)
            )
        elif self.api_key and AsyncGroq is None:
            logger.warning(
                "groq package is not installed. GroqService will be inactive."
            )
        else:
            logger.warning("GROQ_API_KEY is not set. GroqService will be inactive.")

    async def _get_client(self):
        """Resolve the active API key (admin-configured DB override takes
        priority over the .env fallback) and build a client for it.

        GroqService is a process-lifetime singleton (get_groq_service()),
        so unlike a per-request client this can't just bake the key in at
        __init__ — a key entered via the admin UI would never take effect
        without a full restart otherwise. AsyncGroq(...) construction is
        cheap (no network I/O), so resolving + rebuilding per call is fine.
        """
        if AsyncGroq is None:
            return None
        from v2.modules.admin_platform.public import (
            get_integration_secret,
        )

        api_key = await get_integration_secret("groq", self.api_key)
        if not api_key:
            return None
        return AsyncGroq(
            api_key=api_key, base_url=_sdk_base_url(settings.GROQ_API_BASE_URL)
        )

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
        client = await self._get_client()
        if not client:
            yield "Groq API anahtarı ayarlanmamış."
            return

        messages = self._prepare_messages(user_message, history, context, system_prompt)

        try:
            stream = await asyncio.wait_for(
                client.chat.completions.create(
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
        except asyncio.TimeoutError as e:
            logger.error("Groq streaming timeout after %ss", _GROQ_TIMEOUT_S)
            raise LLMProviderError("Yanıt zaman aşımına uğradı.") from e
        except Exception as e:
            logger.error(f"Groq Streaming Error: {e}")
            raise LLMProviderError(str(e)) from e

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
        client = await self._get_client()
        if not client:
            return "Groq API anahtarı ayarlanmamış."

        messages = self._prepare_messages(user_message, history, context, system_prompt)

        try:
            completion = await asyncio.wait_for(
                client.chat.completions.create(
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
        except asyncio.TimeoutError as e:
            logger.error("Groq chat timeout after %ss", _GROQ_TIMEOUT_S)
            raise LLMProviderError("Yanıt zaman aşımına uğradı.") from e
        except Exception as e:
            logger.error(f"Groq API Error: {e}")
            raise LLMProviderError(str(e)) from e

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
