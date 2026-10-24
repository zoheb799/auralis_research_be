from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.market_data.errors import ProviderResponseError
from app.integrations.market_data.http import RetryingProviderClient
from app.integrations.market_data.schemas import FundScheme, NavObservation


class MFAPIProvider:
    provider_name = "mfapi"

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.base_url = settings.mfapi_base_url.rstrip("/")
        self.discovery_limit = max(1, settings.market_data_mf_discovery_limit)
        self.client = RetryingProviderClient(
            provider=self.provider_name,
            client=http_client,
            max_retries=settings.market_data_max_retries,
        )

    async def discover_schemes(self, *, offset: int = 0) -> list[FundScheme]:
        result: list[FundScheme] = []
        page_size = min(100, self.discovery_limit)
        page_offset = max(0, offset)
        while len(result) < self.discovery_limit:
            page = await self.client.get_json(
                f"{self.base_url}/mf",
                params={
                    "limit": min(page_size, self.discovery_limit - len(result)),
                    "offset": page_offset,
                },
            )
            if not isinstance(page, list):
                raise ProviderResponseError("MFAPI scheme list was not an array")
            for item in page:
                if not isinstance(item, dict):
                    continue
                try:
                    result.append(
                        FundScheme(
                            scheme_code=str(item["schemeCode"]),
                            name=item["schemeName"],
                            isin_growth=item.get("isinGrowth"),
                            isin_div_reinvestment=item.get("isinDivReinvestment"),
                        )
                    )
                except (KeyError, ValidationError) as exc:
                    raise ProviderResponseError(
                        "MFAPI scheme record failed validation"
                    ) from exc
            if len(page) < page_size:
                break
            page_offset += len(page)
        return result[: self.discovery_limit]

    async def fetch_latest_nav(self, scheme_code: str) -> tuple[FundScheme, NavObservation]:
        payload = await self.client.get_json(
            f"{self.base_url}/mf/{scheme_code}/latest"
        )
        if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
            raise ProviderResponseError("MFAPI returned an unsuccessful NAV response")
        metadata = payload.get("meta")
        data = payload.get("data")
        if not isinstance(metadata, dict) or not isinstance(data, list) or not data:
            raise ProviderResponseError("MFAPI latest NAV response was incomplete")
        row = data[0]
        if not isinstance(row, dict):
            raise ProviderResponseError("MFAPI NAV record was not an object")
        try:
            scheme = FundScheme(
                scheme_code=str(metadata["scheme_code"]),
                name=metadata["scheme_name"],
                fund_house=metadata.get("fund_house"),
                category=metadata.get("scheme_category"),
                isin_growth=metadata.get("isin_growth"),
                isin_div_reinvestment=metadata.get("isin_div_reinvestment"),
            )
            nav = NavObservation(
                scheme_code=scheme.scheme_code,
                nav_date=datetime.strptime(row["date"], "%d-%m-%Y").date(),
                nav=Decimal(str(row["nav"])),
            )
        except (KeyError, ValueError, InvalidOperation, ValidationError) as exc:
            raise ProviderResponseError("MFAPI NAV record failed validation") from exc
        return scheme, nav