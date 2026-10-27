from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

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


class AlphaVantageFundamentalsProvider:
    provider_name = "alphavantage"

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
        api_key = self.settings.alpha_vantage_api_key
        if not api_key:
            raise ProviderConfigurationError(
                "ALPHA_VANTAGE_API_KEY is required for stock fundamentals sync"
            )
        suffix = self.settings.alpha_vantage_exchange_suffix.strip()
        provider_symbol = (
            f"{symbol}{suffix}"
            if suffix
            else f"{symbol}.{exchange.upper()}"
        )
        overview = await self._request("OVERVIEW", provider_symbol, api_key)
        income = await self._request("INCOME_STATEMENT", provider_symbol, api_key)
        balance = await self._request("BALANCE_SHEET", provider_symbol, api_key)

        annual_income = self._reports(income, "annualReports")
        annual_balance = self._reports(balance, "annualReports")
        balance_by_date = {
            report.get("fiscalDateEnding"): report
            for report in annual_balance
            if report.get("fiscalDateEnding")
        }

        periods = [
            self._period(report, balance_by_date.get(report.get("fiscalDateEnding")))
            for report in annual_income[:5]
        ]
        latest_period = periods[0] if periods else None
        values = {
            "market_cap": self._decimal(overview.get("MarketCapitalization")),
            "pe_ratio": self._decimal(overview.get("PERatio")),
            "eps": self._decimal(overview.get("EPS"))
            or (latest_period.eps if latest_period else None),
            "dividend_yield": self._percentage(overview.get("DividendYield")),
            "book_value": self._decimal(overview.get("BookValue")),
            "debt_to_equity": (
                self._ratio(
                    latest_period.total_debt,
                    latest_period.shareholder_equity,
                )
                if latest_period
                else None
            ),
            "roe": (
                self._percentage(overview.get("ReturnOnEquityTTM"))
                or (latest_period.roe if latest_period else None)
            ),
        }
        missing_fields = [
            field for field, value in values.items() if value is None
        ]
        if not periods:
            missing_fields.append("annual_financial_periods")

        return StockFundamentalData(
            provider_symbol=provider_symbol,
            source_provider=self.provider_name,
            missing_fields=missing_fields,
            **values,
            periods=periods,
        )

    async def _request(
        self,
        function: str,
        symbol: str,
        api_key: str,
    ) -> dict[str, Any]:
        try:
            self.requests_made += 1
            response = await self.http_client.get(
                self.settings.alpha_vantage_base_url,
                params={
                    "function": function,
                    "symbol": symbol,
                    "apikey": api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                f"Alpha Vantage {function} request failed"
            ) from exc
        except ValueError as exc:
            raise ProviderResponseError(
                f"Alpha Vantage {function} returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderResponseError(
                f"Alpha Vantage {function} response was not an object"
            )
        if "Note" in payload or "Information" in payload:
            raise ProviderRateLimitError(
                "Alpha Vantage daily request limit was reached",
                retry_after_seconds=86400,
            )
        if "Error Message" in payload:
            raise ProviderInstrumentNotFoundError(
                f"Alpha Vantage does not recognize {symbol} for {function}"
            )
        if function == "OVERVIEW" and not payload.get("Symbol"):
            raise ProviderInstrumentNotFoundError(
                f"Alpha Vantage has no fundamentals for {symbol}"
            )
        return payload

    @staticmethod
    def _reports(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        reports = payload.get(key, [])
        if not isinstance(reports, list):
            raise ProviderResponseError(
                f"Alpha Vantage {key} was not an array"
            )
        return [report for report in reports if isinstance(report, dict)]

    @classmethod
    def _period(
        cls,
        income: dict[str, Any],
        balance: dict[str, Any] | None,
    ) -> FinancialPeriod:
        period_end_raw = income.get("fiscalDateEnding")
        try:
            period_end = date.fromisoformat(str(period_end_raw))
        except (TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Alpha Vantage statement has an invalid fiscal date"
            ) from exc

        total_debt = cls._first_decimal(
            balance,
            "shortLongTermDebtTotal",
            "longTermDebt",
            "currentDebt",
            "totalDebt",
        )
        equity = cls._first_decimal(
            balance,
            "totalShareholderEquity",
            "totalStockholdersEquity",
        )
        cash = cls._first_decimal(
            balance,
            "cashAndCashEquivalentsAtCarryingValue",
            "cashAndShortTermInvestments",
        )
        operating_profit = cls._decimal(income.get("operatingIncome"))
        net_profit = cls._decimal(income.get("netIncome"))
        roe = cls._percentage(cls._ratio(net_profit, equity))
        invested_capital = (
            equity + total_debt - (cash or Decimal(0))
            if equity is not None and total_debt is not None
            else None
        )
        roce = cls._percentage(cls._ratio(operating_profit, invested_capital))

        return FinancialPeriod(
            period_end=period_end,
            revenue=cls._decimal(income.get("totalRevenue")),
            operating_profit=operating_profit,
            net_profit=net_profit,
            eps=cls._decimal(income.get("reportedEPS"))
            or cls._decimal(income.get("dilutedEPS")),
            total_debt=total_debt,
            shareholder_equity=equity,
            cash=cash,
            roe=roe,
            roce=roce,
        )

    @classmethod
    def _first_decimal(
        cls,
        values: dict[str, Any] | None,
        *keys: str,
    ) -> Decimal | None:
        if values is None:
            return None
        for key in keys:
            value = cls._decimal(values.get(key))
            if value is not None:
                return value
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or str(value).strip().lower() in {"", "none", "-", "n/a"}:
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ProviderResponseError("Alpha Vantage returned an invalid number")
        if not result.is_finite():
            raise ProviderResponseError("Alpha Vantage returned a non-finite number")
        return result

    @classmethod
    def _percentage(cls, value: Any) -> Decimal | None:
        decimal_value = cls._decimal(value)
        if decimal_value is None:
            return None
        return decimal_value * 100 if abs(decimal_value) <= 1 else decimal_value

    @staticmethod
    def _ratio(
        numerator: Decimal | None,
        denominator: Decimal | None,
    ) -> Decimal | None:
        if numerator is None or denominator in (None, Decimal(0)):
            return None
        return numerator / denominator
