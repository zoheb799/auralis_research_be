from datetime import date
from typing import Protocol

from app.integrations.market_data.schemas import (
    FundScheme,
    IPORecord,
    NavObservation,
    PriceObservation,
    StockInstrument,
)


class StockDataProvider(Protocol):
    provider_name: str

    def fetch_instruments(self, configured_symbols: set[str]) -> list[StockInstrument]: ...

    async def fetch_observations(
        self,
        instrument_keys: list[str],
    ) -> list[PriceObservation]: ...


class IPODataProvider(Protocol):
    provider_name: str
    minimum_poll_interval_seconds: int

    async def fetch_ipos(self) -> list[IPORecord]: ...


class MutualFundDataProvider(Protocol):
    provider_name: str

    async def discover_schemes(self, *, offset: int = 0) -> list[FundScheme]: ...

    async def fetch_latest_nav(
        self,
        scheme_code: str,
    ) -> tuple[FundScheme, NavObservation]: ...