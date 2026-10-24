
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.ai.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
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
        logger.info(
            "Gemini provider initialized | model=%s | base_url=%s | timeout=%ss",
            self.model,
            self.base_url,
            self.timeout,
        )

    def build_payload(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "X-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }


    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        max_attempts = 3
        retryable_status_codes = {408, 429, 500, 502, 503, 504}
        url = f"{self.base_url}/models/{self.model}:generateContent"

        logger.info("Gemini request payload: %s", json.dumps(payload, ensure_ascii=False))
        logger.info("Gemini request URL: %s", url)

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    start = time.perf_counter()
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self._build_headers(),
                    )
                    elapsed = time.perf_counter() - start
                    logger.info(
                        "Gemini response status=%s elapsed=%.2fs",
                        response.status_code,
                        elapsed,
                    )
                    logger.info("Gemini raw response: %s", response.text)

                if not response.is_error:
                    return response.json()

                if response.status_code not in retryable_status_codes:
                    logger.error(
                        "Gemini request failed with non-retryable status %s: %s",
                        response.status_code,
                        response.text,
                    )
                    response.raise_for_status()

                logger.warning(
                    "Gemini temporary HTTP error status=%s attempt=%s/%s",
                    response.status_code,
                    attempt + 1,
                    max_attempts,
                )

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.exception(
                    "Gemini network/timeout error on attempt %s/%s: %s",
                    attempt + 1,
                    max_attempts,
                    type(exc).__name__,
                )

                if attempt == max_attempts - 1:
                    raise

            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Gemini request failed after all attempts")

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(
                "Gemini returned no candidates. "
                f"Response: {data}"
            )

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_parts = [
            part["text"]
            for part in parts
            if isinstance(part.get("text"), str)
        ]

        if not text_parts:
            raise ValueError(
                "Gemini returned no text content. "
                f"Response: {data}"
            )

        return "\n".join(text_parts)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        logger.info(
            "Gemini generate called | system_prompt=%s | user_prompt=%s",
            system_prompt,
            user_prompt,
        )
        payload = self.build_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        data = await self._post(payload)
        text = self._extract_text(data)
        logger.info("Gemini generated text: %s", text)
        return text

    @staticmethod
    def _to_gemini_schema(
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        definitions = schema.get("$defs", {})

        unsupported_keys = {
            "$defs",
            "$ref",
            "title",
            "default",
            "examples",
            "additionalProperties",
        }

        def convert(
            node: Any,
            resolving: frozenset[str] = frozenset(),
        ) -> Any:
            if isinstance(node, list):
                return [convert(item, resolving) for item in node]

            if not isinstance(node, dict):
                return node

            ref = node.get("$ref")

            if ref:
                definition_name = ref.rsplit("/", 1)[-1]

                if definition_name in resolving:
                    raise ValueError(
                        f"Circular schema reference: {ref}"
                    )

                if definition_name not in definitions:
                    raise ValueError(
                        f"Unknown schema reference: {ref}"
                    )

                resolved = convert(
                    definitions[definition_name],
                    resolving | {definition_name},
                )

                siblings = {
                    key: value
                    for key, value in node.items()
                    if key != "$ref"
                }

                if siblings:
                    resolved.update(convert(siblings, resolving))

                return resolved

            result: dict[str, Any] = {}

            if "anyOf" in node:
                variants = node["anyOf"]
                non_null = [
                    variant
                    for variant in variants
                    if variant.get("type") != "null"
                ]
                has_null = len(non_null) != len(variants)

                if len(non_null) != 1:
                    raise ValueError(
                        "Unsupported union in Gemini response schema."
                    )

                result.update(convert(non_null[0], resolving))

                if has_null:
                    result["nullable"] = True

            for key, value in node.items():
                if key in unsupported_keys or key == "anyOf":
                    continue

                result[key] = convert(value, resolving)

            return result

        return convert(schema)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
    ) -> str:
        payload = self.build_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": self._to_gemini_schema(response_schema),
        }

        data = await self._post(payload)
        return self._extract_text(data)