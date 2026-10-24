from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.market_data.errors import ProviderResponseError
from app.integrations.market_data.http import RetryingProviderClient
from app.integrations.market_data.schemas import IPORecord


class XflotProvider:
    provider_name = "xflot"
    minimum_poll_interval_seconds = 60
    attribution = "Xflot (https://www.xflot.com)"

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.base_url = settings.xflot_api_base_url.rstrip("/")
        self.max_records = min(200, max(1, settings.market_data_ipo_max_records))
        self.client = RetryingProviderClient(
            provider=self.provider_name,
            client=http_client,
            max_retries=settings.market_data_max_retries,
        )

    async def fetch_ipos(self) -> list[IPORecord]:
        payload = await self.client.get_json(
            f"{self.base_url}/api/public/market/ipos",
            params={"limit": self.max_records},
        )
        if (
            not isinstance(payload, dict)
            or payload.get("ok") is not True
            or not isinstance(payload.get("ipos"), list)
        ):
            raise ProviderResponseError("Xflot IPO response was unsuccessful or malformed")
        disclaimer = payload.get("disclaimer")
        if not isinstance(disclaimer, str) or not disclaimer.strip():
            raise ProviderResponseError("Xflot IPO response omitted its required disclaimer")

        records = []
        for item in payload["ipos"]:
            if not isinstance(item, dict):
                continue
            try:
                records.append(
                    IPORecord(
                        ipo_id=item["slug"],
                        name=item["name"],
                        status=self._status(item["status"]),
                        issue_size=self._optional_decimal(item.get("issueSizeCr")),
                        issue_price_low=self._optional_decimal(item.get("priceMin")),
                        issue_price_high=self._optional_decimal(item.get("priceMax")),
                        lot_size=(
                            int(item["lotSize"])
                            if item.get("lotSize") is not None
                            else None
                        ),
                        open_date=self._optional_date(item.get("openDate")),
                        close_date=self._optional_date(item.get("closeDate")),
                        source_attribution=self.attribution,
                        source_disclaimer=disclaimer.strip(),
                    )
                )
            except (KeyError, ValueError, TypeError, InvalidOperation, ValidationError) as exc:
                raise ProviderResponseError("Xflot IPO record failed validation") from exc
        return records

    @staticmethod
    def _status(value: Any) -> str:
        normalized = str(value).lower()
        if normalized not in {"upcoming", "open", "closed", "listed"}:
            raise ValueError("unsupported Xflot IPO status")
        return normalized

    @staticmethod
    def _optional_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _optional_date(value: Any) -> date | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise ValueError("invalid Xflot date") from exc