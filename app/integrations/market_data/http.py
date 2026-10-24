import asyncio
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.integrations.market_data.errors import (
    ProviderRequestError,
    ProviderResponseError,
)


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class RetryingProviderClient:
    def __init__(
        self,
        *,
        provider: str,
        client: httpx.AsyncClient,
        max_retries: int,
    ) -> None:
        self.provider = provider
        self.client = client
        self.max_retries = max(0, max_retries)

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self._get_response(
            url,
            params=params,
            headers=headers,
        )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                f"{self.provider} returned invalid JSON"
            ) from exc

    async def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        response = await self._get_response(url, headers=headers)
        return response.content

    async def _get_response(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers=headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise ProviderRequestError(
                        f"{self.provider} request failed after retries"
                    ) from exc
                await asyncio.sleep(self._backoff(attempt))
                continue

            if response.status_code in RETRYABLE_STATUSES:
                if attempt >= self.max_retries:
                    raise ProviderRequestError(
                        f"{self.provider} returned HTTP {response.status_code}"
                    )
                retry_after = self._retry_after(response)
                await asyncio.sleep(
                    retry_after if retry_after is not None else self._backoff(attempt)
                )
                continue

            if response.status_code >= 400:
                raise ProviderRequestError(
                    f"{self.provider} returned HTTP {response.status_code}"
                )
            return response

        raise ProviderRequestError(f"{self.provider} request failed")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(8.0, 0.5 * (2**attempt)) + random.uniform(0.0, 0.25)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return min(30.0, max(0.0, float(value)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return min(
                    30.0,
                    max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds()),
                )
            except (TypeError, ValueError, OverflowError):
                return None