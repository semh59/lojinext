"""
Remote LLM istemcisi (Groq/OpenAI uyumlu) – lokal model yok.
Tüm LLM çağrıları tek yerden geçsin, timeout/retry ve PII temizliği sağlansın.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from pydantic import BaseModel

from app.config import settings
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.external_api_probe import get_monitored_client

logger = get_logger(__name__)


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMClient:
    """
    İnce HTTP tabanlı LLM istemcisi.
    Varsayılan sağlayıcı: Groq (OpenAI chat kompatibl endpoint).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or (
            settings.GROQ_API_KEY.get_secret_value()
            if getattr(settings, "GROQ_API_KEY", None)
            else None
        )
        self.model = model or getattr(settings, "GROQ_MODEL_NAME", "mixtral-8x7b-32768")
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        if not self.api_key:
            logger.warning("LLMClient: API key yok, istekler başarısız olacaktır.")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: List[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Basit blok yanıt üretir. Retry + timeout içerir.
        """
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        attempt = 0
        last_error = None
        while attempt <= self.max_retries:
            attempt += 1
            try:
                async with get_monitored_client(
                    timeout=self.timeout_seconds, base_url=self.base_url
                ) as client:
                    resp = await client.post(
                        "/chat/completions", headers=self._headers(), json=payload
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as exc:  # broad: httpx raises many types
                last_error = exc
                logger.warning(
                    "LLMClient chat attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                await asyncio.sleep(0.5 * attempt)

        return f"LLM hatası: {last_error}"

    @staticmethod
    def _mask_pii(text: str) -> str:
        """
        Basit PII maskesi: 10-11 haneli sayıları ve plaka benzeri desenleri maskeler.
        """
        import re

        text = re.sub(r"\b\d{10,11}\b", "[MASKED]", text)
        text = re.sub(
            r"\b\d{2}[A-Z]{1,3}\d{3,4}\b", "[PLAKA]", text, flags=re.IGNORECASE
        )
        return text

    def _build_messages(self, messages: List[LLMMessage], system_prompt: Optional[str]):
        result = []
        if system_prompt:
            result.append({"role": "system", "content": self._mask_pii(system_prompt)})
        for m in messages:
            result.append({"role": m.role, "content": self._mask_pii(m.content)})
        return result


# Singleton benzeri kullanım için yardımcı
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
