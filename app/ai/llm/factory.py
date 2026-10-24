from typing import Any

import httpx

from app.ai.llm.gemini import GeminiProvider
from app.ai.llm.provider import LLMProvider
from app.core.config import settings


class OpenAICompatibleProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not configured.")

    provider_name = (settings.ai_provider or "gemini").lower()

    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )

    if provider_name in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )

    raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")


__all__ = ["GeminiProvider", "OpenAICompatibleProvider", "get_llm_provider"]
