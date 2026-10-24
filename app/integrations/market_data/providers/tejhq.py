import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.market_data.errors import (
    ProviderConfigurationError,
    ProviderResponseError,
)
from app.integrations.market_data.http import RetryingProviderClient
from app.integrations.market_data.schemas import PriceObservation, StockInstrument


class TejHQProvider:
    provider_name = "tejhq"
    MARKET_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.base_url = settings.tejhq_api_base_url.rstrip("/")
        self.client = RetryingProviderClient(
            provider=self.provider_name,
            client=http_client,
            max_retries=settings.market_data_max_retries,
        )

    def fetch_instruments(self, configured_symbols: set[str]) -> list[StockInstrument]:
        instruments = []
        for value in sorted(configured_symbols):
            exchange, separator, symbol = value.partition(":")
            exchange = exchange.upper().strip()
            symbol = symbol.upper().strip()
            if not separator or exchange not in {"NSE", "BSE"} or not symbol:
                raise ProviderConfigurationError(
                    "MARKET_DATA_STOCK_SYMBOLS entries must use EXCHANGE:SYMBOL"
                )
            instruments.append(
                StockInstrument(
                    instrument_key=f"{exchange}:{symbol}",
                    symbol=symbol,
                    name=None,
                    exchange=exchange,
                )
            )
        if not instruments:
            raise ProviderConfigurationError(
                "Set MARKET_DATA_STOCK_SYMBOLS to a comma-separated exchange:symbol allowlist"
            )
        return instruments

    async def fetch_observations(
        self,
        instrument_keys: list[str],
    ) -> list[PriceObservation]:
        today = datetime.now(self.MARKET_TIMEZONE).date()
        lookback = min(30, max(1, self.settings.market_data_eod_lookback_days))
        start_date = today - timedelta(days=lookback)
        semaphore = asyncio.Semaphore(
            max(1, self.settings.market_data_max_concurrency)
        )

        async def fetch_one(instrument_key: str) -> list[PriceObservation]:
            exchange, separator, symbol = instrument_key.partition(":")
            if not separator or exchange not in {"NSE", "BSE"} or not symbol:
                raise ProviderConfigurationError("Invalid TejHQ exchange:symbol key")
            async with semaphore:
                payload = await self.client.get_json(
                    f"{self.base_url}/v1/ohlcv/{exchange.lower()}/{symbol}",
                    params={"from": start_date.isoformat(), "to": today.isoformat()},
                )
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ProviderResponseError("TejHQ OHLCV response was not a data array")
            result = []
            for row in payload["data"]:
                if not isinstance(row, dict):
                    continue
                try:
                    trading_date = date.fromisoformat(row["date"])
                    close = Decimal(str(row["close"]))
                    result.append(
                        PriceObservation(
                            instrument_key=instrument_key,
                            price=close,
                            price_timestamp=datetime.combine(
                                trading_date,
                                time.min,
                                tzinfo=self.MARKET_TIMEZONE,
                            ),
                            observation_type="eod",
                            interval="1d",
                            open=self._optional_decimal(row.get("open")),
                            high=self._optional_decimal(row.get("high")),
                            low=self._optional_decimal(row.get("low")),
                            close=close,
                            volume=(
                                int(row["volume"])
                                if row.get("volume") is not None
                                else None
                            ),
                        )
                    )
                except (KeyError, ValueError, TypeError, InvalidOperation, ValidationError) as exc:
                    raise ProviderResponseError(
                        "TejHQ EOD record failed validation"
                    ) from exc
            return result

        batches = await asyncio.gather(
            *(fetch_one(instrument_key) for instrument_key in instrument_keys)
        )
        return [observation for batch in batches for observation in batch]

    @staticmethod
    def _optional_decimal(value) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))