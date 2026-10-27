import csv
import io
import re

import httpx

from app.integrations.market_data.errors import (
    ProviderRequestError,
    ProviderResponseError,
)
from app.integrations.market_data.schemas import StockInstrument


NSE_EQUITY_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


class NSEEquityCatalogProvider:
    provider_name = "nse"
    _SYMBOL_PATTERN = re.compile(r"[A-Z0-9&.-]+\Z")
    _REQUIRED_COLUMNS = {"SYMBOL", "NAME OF COMPANY", "SERIES"}

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http_client = http_client

    async def fetch_constituents(self) -> list[StockInstrument]:
        try:
            response = await self.http_client.get(
                NSE_EQUITY_CSV_URL,
                headers={
                    "Accept": "text/csv",
                    "User-Agent": "AuralisMarketDataSync/1.0",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                "Could not fetch the NSE equity master"
            ) from exc

        try:
            reader = csv.DictReader(
                io.StringIO(response.content.decode("utf-8-sig"), newline="")
            )
            if not reader.fieldnames or not self._REQUIRED_COLUMNS.issubset(
                {field.strip().upper() for field in reader.fieldnames}
            ):
                raise ProviderResponseError(
                    "NSE equity master is missing required columns"
                )

            instruments: list[StockInstrument] = []
            seen_symbols: set[str] = set()
            for row in reader:
                normalized_row = {
                    str(key).strip().upper(): value
                    for key, value in row.items()
                    if key is not None
                }
                if str(normalized_row.get("SERIES") or "").strip().upper() != "EQ":
                    continue
                symbol = str(normalized_row.get("SYMBOL") or "").strip().upper()
                name = str(normalized_row.get("NAME OF COMPANY") or "").strip()
                if (
                    not symbol
                    or not self._SYMBOL_PATTERN.fullmatch(symbol)
                    or len(symbol) > 50
                    or not name
                    or len(name) > 255
                    or symbol in seen_symbols
                ):
                    raise ProviderResponseError(
                        "NSE equity master contains an invalid or duplicate equity"
                    )
                seen_symbols.add(symbol)
                instruments.append(
                    StockInstrument(
                        instrument_key=f"NSE:{symbol}",
                        symbol=symbol,
                        name=name,
                        exchange="NSE",
                    )
                )
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ProviderResponseError(
                "NSE returned an unreadable equity master CSV"
            ) from exc

        if not instruments:
            raise ProviderResponseError(
                "NSE equity master did not contain any EQ-series securities"
            )
        return instruments
