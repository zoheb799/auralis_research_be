from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.integrations.market_data.errors import (
    ProviderConfigurationError,
    ProviderInstrumentNotFoundError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
)
from app.integrations.market_data.schemas import (
    FinancialPeriod,
    StockFundamentalData,
)


class BharatStockFundamentalsProvider:
    provider_name = "bharatstock"
    requests_per_stock = 2

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client
        self.requests_made = 0

    async def fetch_fundamentals(
        self,
        symbol: str,
        exchange: str,
    ) -> StockFundamentalData:
        self.requests_made = 0
        api_key = self.settings.bharatstock_api_key
        if not api_key:
            raise ProviderConfigurationError(
                "BHARATSTOCK_API_KEY is required for stock fundamentals sync"
            )

        provider_symbol = symbol.upper()
        stock_payload = await self._request(
            f"/v1/stocks/{quote(provider_symbol, safe='')}",
            api_key,
            params={"exchange": exchange.upper()},
        )
        try:
            financial_payload = await self._request(
                f"/v1/stocks/{quote(provider_symbol, safe='')}/financials",
                api_key,
                params={
                    "exchange": exchange.upper(),
                    "period_type": "annual",
                    "page": 1,
                    "page_size": 100,
                },
            )
        except ProviderInstrumentNotFoundError:
            financial_payload = []

        stock = self._object_payload(stock_payload)
        returned_symbol = stock.get("symbol")
        returned_exchange = stock.get("exchange")
        if not isinstance(returned_symbol, str) or not isinstance(
            returned_exchange, str
        ):
            raise ProviderResponseError(
                "BharatStock stock detail omitted its symbol or exchange"
            )
        normalized_exchange = returned_exchange.upper()
        requested_exchange = exchange.upper()
        # BharatStock represents cross-listed names through the NSE pipeline.
        exchange_matches = normalized_exchange == requested_exchange or (
            requested_exchange == "BSE" and normalized_exchange == "NSE"
        )
        if returned_symbol.upper() != provider_symbol or not exchange_matches:
            raise ProviderResponseError(
                "BharatStock returned a different stock than requested"
            )
        metrics = self._object(stock.get("metrics"), "metrics")
        latest_price = self._object(stock.get("latest_price"), "latest_price")
        price = self._decimal(metrics.get("price"))
        if price is None:
            price = self._decimal(latest_price.get("close"))
        shares_outstanding = self._decimal(metrics.get("shares_outstanding"))
        market_cap = (
            price * shares_outstanding / Decimal(10_000_000)
            if price is not None and shares_outstanding is not None
            else None
        )
        source_date = self._date(metrics.get("computed_at"))
        if source_date is None:
            source_date = self._date(latest_price.get("trade_date"))

        periods = [
            self._period(row)
            for row in self._period_rows(financial_payload)
        ]
        values = {
            "market_cap": market_cap,
            "pe_ratio": self._decimal(metrics.get("pe_ratio")),
            "eps": self._decimal(metrics.get("eps")),
            "dividend_yield": self._decimal(metrics.get("dividend_yield")),
            "book_value": self._decimal(metrics.get("book_value_per_share")),
            "debt_to_equity": self._decimal(metrics.get("debt_to_equity")),
            "roe": self._decimal(metrics.get("roe")),
        }
        missing_fields = [name for name, value in values.items() if value is None]
        if not periods:
            missing_fields.append("annual_financial_periods")

        return StockFundamentalData(
            provider_symbol=provider_symbol,
            source_provider=self.provider_name,
            source_as_of_date=source_date,
            missing_fields=missing_fields,
            **values,
            periods=periods,
        )

    async def _request(
        self,
        path: str,
        api_key: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        url = f"{self.settings.bharatstock_base_url.rstrip('/')}{path}"
        try:
            self.requests_made += 1
            response = await self.http_client.get(
                url,
                params=params,
                headers={"X-API-Key": api_key},
            )
        except httpx.HTTPError as exc:
            raise ProviderRequestError("BharatStock request failed") from exc

        if response.status_code == 404:
            raise ProviderInstrumentNotFoundError(
                "BharatStock has no data for the requested stock"
            )
        if response.status_code == 429:
            try:
                retry_after = int(response.headers.get("Retry-After", "86400"))
            except ValueError:
                retry_after = 86400
            raise ProviderRateLimitError(
                "BharatStock request quota was reached",
                retry_after_seconds=retry_after,
            )
        if response.status_code in (401, 403):
            raise ProviderConfigurationError(
                "BharatStock rejected the API key or the key lacks endpoint access"
            )
        if response.is_error:
            raise ProviderRequestError(
                f"BharatStock returned HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                "BharatStock returned invalid JSON"
            ) from exc
        if not isinstance(payload, (dict, list)):
            raise ProviderResponseError(
                "BharatStock response was not an object or array"
            )
        return payload

    @staticmethod
    def _object_payload(
        payload: dict[str, Any] | list[Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "BharatStock stock detail response was not an object"
            )
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ProviderResponseError(
                "BharatStock stock detail data was not an object"
            )
        return data

    @staticmethod
    def _object(value: Any, field: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ProviderResponseError(
                f"BharatStock {field} field was not an object"
            )
        return value

    @staticmethod
    def _period_rows(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            rows = payload
        else:
            rows = payload.get("items", payload.get("data", []))
            if isinstance(rows, dict):
                rows = rows.get("items", [])
        if not isinstance(rows, list):
            raise ProviderResponseError(
                "BharatStock annual financials were not an array"
            )
        return [row for row in rows if isinstance(row, dict)]

    @classmethod
    def _period(cls, row: dict[str, Any]) -> FinancialPeriod:
        period_end = cls._date(row.get("period_end_date"))
        if period_end is None:
            raise ProviderResponseError(
                "BharatStock financial period has an invalid period-end date"
            )
        consolidation = row.get("consolidation_type")
        if consolidation is not None:
            consolidation = str(consolidation).strip().lower()
            if consolidation not in {"consolidated", "standalone"}:
                raise ProviderResponseError(
                    "BharatStock financial period has an unknown consolidation type"
                )

        current_debt = cls._decimal(row.get("borrowings_current"))
        noncurrent_debt = cls._decimal(row.get("borrowings_non_current"))
        total_debt = (
            current_debt + noncurrent_debt
            if current_debt is not None and noncurrent_debt is not None
            else None
        )
        return FinancialPeriod(
            period_end=period_end,
            consolidation_type=consolidation,
            revenue=cls._decimal(row.get("revenue")),
            operating_profit=cls._decimal(row.get("operating_profit")),
            net_profit=cls._first_decimal(
                row,
                "net_profit",
                "net_profit_attributable_to_owners",
            ),
            eps=cls._first_decimal(row, "eps", "diluted_eps"),
            total_debt=total_debt,
            shareholder_equity=cls._first_decimal(
                row,
                "total_equity",
                "equity_attributable_to_owners",
            ),
            cash=cls._decimal(row.get("cash_and_cash_equivalents")),
        )

    @classmethod
    def _first_decimal(
        cls,
        values: dict[str, Any],
        *keys: str,
    ) -> Decimal | None:
        for key in keys:
            value = cls._decimal(values.get(key))
            if value is not None:
                return value
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or str(value).strip().lower() in {"", "-", "n/a", "none"}:
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ProviderResponseError(
                "BharatStock returned an invalid numeric value"
            ) from exc
        if not result.is_finite():
            raise ProviderResponseError(
                "BharatStock returned a non-finite numeric value"
            )
        return result

    @staticmethod
    def _date(value: Any) -> date | None:
        if value is None:
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ProviderResponseError(
                "BharatStock returned an invalid date"
            ) from exc
