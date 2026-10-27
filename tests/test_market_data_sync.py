from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.db.models.asset import Asset
from app.db.models.asset_identifier import AssetIdentifier
from app.db.models.asset_price import AssetPrice
from app.db.models.financial_metric import FinancialMetric
from app.db.models.ipo import IPO
from app.db.models.stock import Stock
from app.integrations.market_data.errors import (
    ProviderConfigurationError,
    ProviderInstrumentNotFoundError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from app.integrations.market_data.http import RetryingProviderClient
from app.integrations.market_data.providers.alpha_vantage import (
    AlphaVantageFundamentalsProvider,
)
from app.integrations.market_data.providers.bharatstock import (
    BharatStockFundamentalsProvider,
)
from app.integrations.market_data.providers.mfapi import MFAPIProvider
from app.integrations.market_data.providers.nse import (
    NSE_EQUITY_CSV_URL,
    NSEEquityCatalogProvider,
)
from app.integrations.market_data.providers.tejhq import TejHQProvider
from app.integrations.market_data.providers.xflot import XflotProvider
from app.integrations.market_data.registry import MarketDataProviderRegistry
from app.integrations.market_data.schemas import (
    FinancialPeriod,
    IPORecord,
    PriceObservation,
    StockCatalogSyncSummary,
    StockFundamentalData,
    StockInstrument,
)
from app.main import app
from app.services.market_data_sync import MarketDataSyncService


def build_settings(**overrides) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret_key="test-secret",
        **overrides,
    )


class FakeHTTPClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def get(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return self.responses.pop(0)


def response(status_code: int, *, json_data=None, headers=None):
    return httpx.Response(
        status_code,
        json=json_data,
        headers=headers,
        request=httpx.Request("GET", "https://provider.test"),
    )


@pytest.mark.asyncio
async def test_tejhq_observation_is_normalized_as_eod_not_live_quote():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "data": [{
                        "date": "2026-10-21",
                        "open": 120,
                        "high": 125,
                        "low": 119,
                        "close": 123.45,
                        "last": 123.50,
                        "prev_close": 122,
                        "volume": 42,
                        "turnover": 5000,
                        "trades": 10,
                    }],
                },
            )
        ]
    )
    provider = TejHQProvider(build_settings(), client)
    instruments = provider.fetch_instruments({"NSE:RELIANCE"})

    observations = await provider.fetch_observations(
        [instruments[0].instrument_key]
    )

    assert observations[0].price == Decimal("123.45")
    assert observations[0].observation_type == "eod"
    assert observations[0].interval == "1d"
    assert observations[0].price_timestamp.isoformat() == "2026-10-21T00:00:00+05:30"
    assert client.calls[0][0] == "https://api.tejhq.dev/v1/ohlcv/nse/RELIANCE"
    assert client.calls[0][2] is None


@pytest.mark.asyncio
async def test_stock_discovery_uses_bounded_database_catalog_not_env_symbols():
    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

        def scalars(self):
            return iter(self.rows)

    class FakeSession:
        def __init__(self, catalog, assets):
            self.catalog = catalog
            self.assets = assets
            self.call_count = 0

        async def execute(self, statement):
            self.call_count += 1
            if self.call_count == 1:
                return FakeResult(self.catalog)
            if self.call_count == 2:
                return FakeResult([])
            if self.call_count == 3:
                return FakeResult(self.assets)
            return FakeResult([])

        def add_all(self, items):
            self.added = items

        async def commit(self):
            pass

    class FakeStockProvider:
        provider_name = "tejhq"

        def fetch_instruments(self, configured_symbols):
            self.configured_symbols = configured_symbols
            return [
                StockInstrument(
                    instrument_key="NSE:RELIANCE",
                    symbol="RELIANCE",
                    exchange="NSE",
                ),
                StockInstrument(
                    instrument_key="NSE:TCS",
                    symbol="TCS",
                    exchange="NSE",
                ),
            ]

    class FakeRegistry:
        def __init__(self, provider):
            self.provider = provider

        def stocks(self):
            return self.provider

    assets = [
        Asset(
            id=uuid4(),
            name="Reliance Industries",
            symbol="RELIANCE",
            asset_type="stock",
            exchange="NSE",
            is_active=True,
        ),
        Asset(
            id=uuid4(),
            name="Tata Consultancy Services",
            symbol="TCS",
            asset_type="stock",
            exchange="NSE",
            is_active=True,
        ),
    ]
    provider = FakeStockProvider()
    config = build_settings(market_data_stock_symbols="NSE:WRONG")
    service = MarketDataSyncService(
        FakeSession(
            [("RELIANCE", "NSE"), ("TCS", "NSE")],
            assets,
        ),
        config,
        FakeRegistry(provider),
    )

    discovered = await service._discover_stocks(provider)

    assert discovered == 2
    assert provider.configured_symbols == {"NSE:RELIANCE", "NSE:TCS"}
    assert {
        item.external_id
        for item in service.db.added
        if isinstance(item, AssetIdentifier)
    } == {"RELIANCE", "TCS"}


@pytest.mark.asyncio
async def test_nse_catalog_parses_eq_equities_and_skips_other_series():
    csv_content = (
        "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING\n"
        "EXAMPLE,Example Limited,EQ,01-JAN-2020\n"
        "EXAMPLESME,Example SME Limited,BE,01-JAN-2020\n"
    )
    client = FakeHTTPClient(
        [
            httpx.Response(
                200,
                content=csv_content.encode(),
                request=httpx.Request("GET", NSE_EQUITY_CSV_URL),
            )
        ]
    )
    provider = NSEEquityCatalogProvider(client)

    instruments = await provider.fetch_constituents()

    assert len(instruments) == 1
    assert instruments[0].instrument_key == "NSE:EXAMPLE"
    assert instruments[0].name == "Example Limited"
    assert instruments[0].sector is None
    assert client.calls[0][0] == NSE_EQUITY_CSV_URL


@pytest.mark.asyncio
async def test_nse_catalog_rejects_duplicate_symbols():
    csv_content = (
        "SYMBOL,NAME OF COMPANY,SERIES\n"
        "EXAMPLE,Example Limited,EQ\n"
        "EXAMPLE,Duplicate Example,EQ\n"
    )
    client = FakeHTTPClient(
        [
            httpx.Response(
                200,
                content=csv_content.encode(),
                request=httpx.Request("GET", NSE_EQUITY_CSV_URL),
            )
        ]
    )
    provider = NSEEquityCatalogProvider(client)

    with pytest.raises(ProviderResponseError, match="invalid or duplicate equity"):
        await provider.fetch_constituents()


@pytest.mark.asyncio
async def test_stock_catalog_upsert_reactivates_existing_and_adds_missing_assets():
    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return iter(self.rows)

    class FakeSession:
        def __init__(self):
            self.execute_count = 0
            self.added = []

        async def execute(self, statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return FakeResult([existing_asset])
            if self.execute_count == 2:
                return FakeResult([])
            raise AssertionError("Unexpected database query")

        def add_all(self, rows):
            self.added.extend(rows)

        async def commit(self):
            pass

    existing_asset = Asset(
        id=uuid4(),
        name="Old Name",
        symbol="existing",
        asset_type="stock",
        exchange="nse",
        sector="Old Sector",
        is_active=False,
    )
    session = FakeSession()
    service = MarketDataSyncService(
        session,
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )

    inserted, updated, stock_rows = await service._upsert_stock_catalog(
        [
            StockInstrument(
                instrument_key="NSE:EXISTING",
                symbol="EXISTING",
                name="Updated Name",
                exchange="NSE",
                sector="Updated Sector",
            ),
            StockInstrument(
                instrument_key="NSE:NEWCO",
                symbol="NEWCO",
                name="New Company",
                exchange="NSE",
                sector="Industrials",
            ),
        ]
    )

    assert (inserted, updated, stock_rows) == (1, 1, 2)
    assert existing_asset.name == "Updated Name"
    assert existing_asset.symbol == "EXISTING"
    assert existing_asset.exchange == "NSE"
    assert existing_asset.sector == "Updated Sector"
    assert existing_asset.is_active is True
    new_assets = [item for item in session.added if isinstance(item, Asset)]
    new_stocks = [item for item in session.added if isinstance(item, Stock)]
    assert [(item.symbol, item.exchange) for item in new_assets] == [("NEWCO", "NSE")]
    assert len(new_stocks) == 2


@pytest.mark.asyncio
async def test_stock_discovery_imports_catalog_before_fetching_prices():
    asset_id = uuid4()

    class FakeResult:
        def all(self):
            return [(asset_id, "EXAMPLE", "NSE")]

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

        async def commit(self):
            pass

    class FakeStockProvider:
        provider_name = "tejhq"

        async def fetch_observations(self, instrument_keys):
            assert instrument_keys == ["NSE:EXAMPLE"]
            return [
                PriceObservation(
                    instrument_key="NSE:EXAMPLE",
                    price=Decimal("10"),
                    price_timestamp=datetime(2026, 10, 21, tzinfo=timezone.utc),
                )
            ]

    class FakeRegistry:
        def stocks(self):
            return FakeStockProvider()

    db = FakeSession()
    service = MarketDataSyncService(
        db,
        build_settings(),
        FakeRegistry(),
    )
    catalog_calls = 0

    async def sync_catalog():
        nonlocal catalog_calls
        catalog_calls += 1
        return StockCatalogSyncSummary(
            source="nse",
            fetched=100,
            assets_inserted=80,
            assets_updated=20,
            stock_records_inserted=100,
            identifiers_linked=1,
        )

    async def upsert_prices(rows):
        assert len(rows) == 1
        return 1, 0

    service.sync_stock_catalog = sync_catalog
    service._upsert_prices = upsert_prices

    summary = await service.sync_stocks(discover=True)

    assert catalog_calls == 1
    assert summary.discovered == 1
    assert summary.catalog_assets_inserted == 80
    assert summary.catalog_assets_updated == 20
    assert summary.catalog_stock_records_inserted == 100
    assert summary.inserted == 1


@pytest.mark.asyncio
async def test_stock_catalog_sync_links_all_in_bounded_batches():
    class FakeCatalogProvider:
        provider_name = "nse"

        async def fetch_constituents(self):
            return []

    class FakeStockProvider:
        provider_name = "tejhq"

    class FakeRegistry:
        def stock_catalog(self):
            return FakeCatalogProvider()

        def stocks(self):
            return FakeStockProvider()

    class FakeSession:
        pass

    service = MarketDataSyncService(
        FakeSession(),
        build_settings(),
        FakeRegistry(),
    )
    discovery_batches = iter([500, 500, 23, 0])
    discovery_calls = 0

    async def upsert_catalog(instruments):
        return 0, 0, 0

    async def discover_batch(provider):
        nonlocal discovery_calls
        discovery_calls += 1
        return next(discovery_batches)

    service._upsert_stock_catalog = upsert_catalog
    service._discover_stocks = discover_batch

    summary = await service.sync_stock_catalog()

    assert discovery_calls == 4
    assert summary.identifiers_linked == 1023


@pytest.mark.asyncio
async def test_alpha_vantage_fundamentals_normalize_annual_statements():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "Symbol": "EXAMPLE.BSE",
                    "MarketCapitalization": "1000000",
                    "PERatio": "18.5",
                    "EPS": "12.5",
                    "DividendYield": "0.02",
                    "BookValue": "40",
                    "ReturnOnEquityTTM": "0.15",
                },
            ),
            response(
                200,
                json_data={
                    "annualReports": [
                        {
                            "fiscalDateEnding": "2025-03-31",
                            "totalRevenue": "10000",
                            "operatingIncome": "1500",
                            "netIncome": "1000",
                            "reportedEPS": "12.5",
                        }
                    ]
                },
            ),
            response(
                200,
                json_data={
                    "annualReports": [
                        {
                            "fiscalDateEnding": "2025-03-31",
                            "totalDebt": "2000",
                            "totalShareholderEquity": "8000",
                            "cashAndCashEquivalentsAtCarryingValue": "500",
                        }
                    ]
                },
            ),
        ]
    )
    provider = AlphaVantageFundamentalsProvider(
        build_settings(alpha_vantage_api_key="test-key"),
        client,
    )

    data = await provider.fetch_fundamentals("EXAMPLE", "NSE")

    assert data.provider_symbol == "EXAMPLE.BSE"
    assert data.market_cap == Decimal("1000000")
    assert data.pe_ratio == Decimal("18.5")
    assert data.dividend_yield == Decimal("2.00")
    assert data.roe == Decimal("15.00")
    assert data.debt_to_equity == Decimal("0.25")
    assert data.periods[0].period_end == date(2025, 3, 31)
    assert data.periods[0].revenue == Decimal("10000")
    assert data.periods[0].roe == Decimal("12.500")
    assert data.periods[0].roce == Decimal(1500) / Decimal(9500) * 100
    assert provider.requests_made == 3
    assert [call[1]["function"] for call in client.calls] == [
        "OVERVIEW",
        "INCOME_STATEMENT",
        "BALANCE_SHEET",
    ]
    assert all(call[1]["apikey"] == "test-key" for call in client.calls)


@pytest.mark.asyncio
async def test_alpha_vantage_requires_key_and_surfaces_unsupported_symbols():
    no_key_provider = AlphaVantageFundamentalsProvider(
        build_settings(alpha_vantage_api_key=None),
        FakeHTTPClient([]),
    )
    with pytest.raises(ProviderConfigurationError, match="ALPHA_VANTAGE_API_KEY"):
        await no_key_provider.fetch_fundamentals("EXAMPLE", "NSE")

    unsupported_provider = AlphaVantageFundamentalsProvider(
        build_settings(alpha_vantage_api_key="test-key"),
        FakeHTTPClient(
            [
                response(
                    200,
                    json_data={"Error Message": "Invalid API call"},
                )
            ]
        ),
    )
    with pytest.raises(
        ProviderInstrumentNotFoundError,
        match="does not recognize",
    ):
        await unsupported_provider.fetch_fundamentals("EXAMPLE", "NSE")
    assert unsupported_provider.requests_made == 1


@pytest.mark.asyncio
async def test_alpha_vantage_rate_limit_is_not_treated_as_empty_fundamentals():
    provider = AlphaVantageFundamentalsProvider(
        build_settings(alpha_vantage_api_key="test-key"),
        FakeHTTPClient(
            [response(200, json_data={"Note": "API call frequency exceeded"})]
        ),
    )

    with pytest.raises(ProviderRateLimitError):
        await provider.fetch_fundamentals("EXAMPLE", "NSE")
    assert provider.requests_made == 1


@pytest.mark.asyncio
async def test_bharatstock_maps_verified_ratio_and_annual_statement_fields():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "symbol": "EXAMPLE",
                    "exchange": "NSE",
                    "metrics": {
                        "price": 200,
                        "shares_outstanding": 5_000_000,
                        "pe_ratio": 18.5,
                        "eps": 12.5,
                        "dividend_yield": 2,
                        "book_value_per_share": 40,
                        "debt_to_equity": 0.25,
                        "roe": 15,
                        "computed_at": "2026-10-28",
                    },
                    "latest_price": {"close": 199, "trade_date": "2026-10-27"},
                },
            ),
            response(
                200,
                json_data={
                    "items": [
                        {
                            "period_end_date": "2025-03-31",
                            "consolidation_type": "consolidated",
                            "revenue": 10000,
                            "operating_profit": 1500,
                            "net_profit": 1000,
                            "eps": 12.5,
                            "borrowings_current": 500,
                            "borrowings_non_current": 1500,
                            "total_equity": 8000,
                            "cash_and_cash_equivalents": 500,
                        }
                    ]
                },
            ),
        ]
    )
    provider = BharatStockFundamentalsProvider(
        build_settings(bharatstock_api_key="test-key"),
        client,
    )

    data = await provider.fetch_fundamentals("example", "NSE")

    assert data.provider_symbol == "EXAMPLE"
    assert data.source_provider == "bharatstock"
    assert data.source_as_of_date == date(2026, 10, 28)
    assert data.market_cap == Decimal("100")
    assert data.pe_ratio == Decimal("18.5")
    assert data.eps == Decimal("12.5")
    assert data.dividend_yield == Decimal("2")
    assert data.book_value == Decimal("40")
    assert data.debt_to_equity == Decimal("0.25")
    assert data.roe == Decimal("15")
    assert data.missing_fields == []
    assert data.periods[0].total_debt == Decimal("2000")
    assert data.periods[0].shareholder_equity == Decimal("8000")
    assert data.periods[0].consolidation_type == "consolidated"
    assert provider.requests_made == 2
    assert client.calls[0][2] == {"X-API-Key": "test-key"}
    assert client.calls[0][1] == {"exchange": "NSE"}
    assert client.calls[1][1]["period_type"] == "annual"


@pytest.mark.asyncio
async def test_bharatstock_keeps_ratio_data_when_annual_financials_are_missing():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "symbol": "EXAMPLE",
                    "exchange": "NSE",
                    "metrics": {"pe_ratio": 12, "computed_at": "2026-10-28"}
                },
            ),
            response(404, json_data={"detail": "No financials"}),
        ]
    )
    provider = BharatStockFundamentalsProvider(
        build_settings(bharatstock_api_key="test-key"),
        client,
    )

    data = await provider.fetch_fundamentals("EXAMPLE", "BSE")

    assert data.pe_ratio == Decimal("12")
    assert data.periods == []
    assert data.missing_fields == [
        "market_cap",
        "eps",
        "dividend_yield",
        "book_value",
        "debt_to_equity",
        "roe",
        "annual_financial_periods",
    ]
    assert provider.requests_made == 2


@pytest.mark.asyncio
async def test_bharatstock_requires_key_and_surfaces_quota_exhaustion():
    no_key_provider = BharatStockFundamentalsProvider(
        build_settings(bharatstock_api_key=None),
        FakeHTTPClient([]),
    )
    with pytest.raises(ProviderConfigurationError, match="BHARATSTOCK_API_KEY"):
        await no_key_provider.fetch_fundamentals("EXAMPLE", "NSE")

    rate_limited_provider = BharatStockFundamentalsProvider(
        build_settings(bharatstock_api_key="test-key"),
        FakeHTTPClient(
            [
                response(
                    429,
                    json_data={"detail": "quota reached"},
                    headers={"Retry-After": "86400"},
                )
            ]
        ),
    )
    with pytest.raises(
        ProviderRateLimitError,
        match="request quota",
    ):
        await rate_limited_provider.fetch_fundamentals("EXAMPLE", "NSE")


@pytest.mark.asyncio
async def test_fundamentals_dry_run_applies_symbol_filters_without_writing():
    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def all(self):
            return self.value

    class FakeSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            if len(self.statements) == 1:
                return FakeResult(0)
            return FakeResult([(uuid4(), "RELIANCE", "NSE")])

    class FakeProvider:
        provider_name = "bharatstock"
        requests_per_stock = 2
        requests_made = 0

    class FakeRegistry:
        def stock_fundamentals(self):
            return FakeProvider()

    db = FakeSession()
    service = MarketDataSyncService(
        db,
        build_settings(
            market_data_fundamentals_provider="bharatstock",
            bharatstock_api_key=None,
        ),
        FakeRegistry(),
    )

    summary = await service.sync_stock_fundamentals(
        dry_run=True,
        limit=1,
        symbol="reliance",
        exchange="nse",
    )

    assert summary.discovered == 1
    assert summary.requests_used == 0
    assert summary.request_budget_remaining == 60
    assert len(db.statements) == 2
    compiled_query = str(db.statements[1])
    assert "upper(assets.symbol)" in compiled_query
    assert "upper(assets.exchange)" in compiled_query


@pytest.mark.asyncio
async def test_fundamental_persistence_updates_stock_and_annual_history():
    asset_id = uuid4()
    stock = Stock(asset_id=asset_id, pe_ratio=Decimal("99"))

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

        def scalars(self):
            return iter(self.value)

    class FakeSession:
        def __init__(self):
            self.calls = 0
            self.added = []

        async def execute(self, statement):
            self.calls += 1
            if self.calls in (1, 3):
                return FakeResult(stock)
            return FakeResult([])

        def add(self, item):
            self.added.append(item)

        async def commit(self):
            pass

    db = FakeSession()
    service = MarketDataSyncService(
        db,
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )
    inserted, updated = await service._persist_stock_fundamentals(
        asset_id,
        StockFundamentalData(
            provider_symbol="EXAMPLE.BSE",
            source_provider="bharatstock",
            source_as_of_date=date(2026, 10, 28),
            market_cap=Decimal("1000000"),
            pe_ratio=Decimal("18.5"),
            eps=Decimal("12.5"),
            dividend_yield=Decimal("2"),
            book_value=Decimal("40"),
            debt_to_equity=Decimal("0.25"),
            roe=Decimal("15"),
            periods=[
                FinancialPeriod(
                    period_end=date(2025, 3, 31),
                    consolidation_type="consolidated",
                    revenue=Decimal("10000"),
                    operating_profit=Decimal("1500"),
                    net_profit=Decimal("1000"),
                    eps=Decimal("12.5"),
                    total_debt=Decimal("2000"),
                    cash=Decimal("500"),
                    roe=Decimal("12.5"),
                    roce=Decimal("15.79"),
                )
            ],
        ),
    )

    assert (inserted, updated) == (1, 0)
    assert stock.market_cap == Decimal("1000000")
    assert stock.pe_ratio == Decimal("18.5")
    assert stock.roe == Decimal("15")
    metrics = [item for item in db.added if isinstance(item, FinancialMetric)]
    assert len(metrics) == 1
    assert metrics[0].period_type == "annual"
    assert metrics[0].consolidation_type == "consolidated"
    assert metrics[0].source_provider == "bharatstock"
    assert metrics[0].source_as_of_date == date(2026, 10, 28)
    assert metrics[0].revenue == Decimal("10000")
    assert metrics[0].roce == Decimal("15.79")

    await service._persist_stock_fundamentals(
        asset_id,
        StockFundamentalData(provider_symbol="EXAMPLE.BSE"),
    )
    assert stock.pe_ratio == Decimal("18.5")
    assert stock.market_cap == Decimal("1000000")


@pytest.mark.asyncio
async def test_mfapi_keeps_direct_and_regular_schemes_distinct():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data=[
                    {"schemeCode": 1001, "schemeName": "Fund Direct Growth"},
                    {"schemeCode": 1002, "schemeName": "Fund Regular Growth"},
                ],
            )
        ]
    )
    provider = MFAPIProvider(build_settings(), client)

    schemes = await provider.discover_schemes()

    assert [scheme.scheme_code for scheme in schemes] == ["1001", "1002"]
    assert len({scheme.scheme_code for scheme in schemes}) == 2


@pytest.mark.asyncio
async def test_mfapi_latest_nav_parses_date_and_decimal():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "meta": {
                        "scheme_code": 125497,
                        "scheme_name": "Sample Direct Growth",
                        "fund_house": "Sample AMC",
                        "scheme_category": "Equity",
                        "isin_growth": "INF000000001",
                        "isin_div_reinvestment": None,
                    },
                    "data": [{"date": "21-10-2026", "nav": "12.34560"}],
                    "status": "SUCCESS",
                },
            )
        ]
    )
    provider = MFAPIProvider(build_settings(), client)

    scheme, nav = await provider.fetch_latest_nav("125497")

    assert scheme.isin_growth == "INF000000001"
    assert nav.nav_date == date(2026, 10, 21)
    assert nav.nav == Decimal("12.34560")


@pytest.mark.asyncio
async def test_http_client_retries_rate_limit_and_honors_retry_after():
    client = FakeHTTPClient(
        [
            response(429, headers={"Retry-After": "0"}),
            response(200, json_data={"status": "success"}),
        ]
    )
    provider = RetryingProviderClient(
        provider="test",
        client=client,
        max_retries=1,
    )

    result = await provider.get_json("https://provider.test/data")

    assert result == {"status": "success"}
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_xflot_maps_documented_ipo_fields_and_ignores_gmp():
    client = FakeHTTPClient(
        [
            response(
                200,
                json_data={
                    "ok": True,
                    "count": 1,
                    "ipos": [
                        {
                            "slug": "sample-ipo",
                            "name": "Sample IPO",
                            "status": "OPEN",
                            "priceMin": 100,
                            "priceMax": 110,
                            "issueSizeCr": 250,
                            "lotSize": 10,
                            "openDate": "2026-10-20T00:00:00.000Z",
                            "closeDate": "2026-10-24T00:00:00.000Z",
                            "lastGmp": 99,
                            "lastSubX": 88,
                        }
                    ],
                    "disclaimer": "Aggregated public information; verify independently.",
                },
            )
        ]
    )
    provider = XflotProvider(build_settings(), client)

    records = await provider.fetch_ipos()

    assert len(records) == 1
    assert records[0].ipo_id == "sample-ipo"
    assert records[0].status == "open"
    assert records[0].issue_price_low == Decimal("100")
    assert records[0].issue_size == Decimal("250")
    assert records[0].open_date == date(2026, 10, 20)
    assert records[0].source_attribution == "Xflot (https://www.xflot.com)"
    assert records[0].source_disclaimer.startswith("Aggregated public information")
    assert "gmp" not in IPORecord.model_fields
    assert provider.minimum_poll_interval_seconds == 60


@pytest.mark.asyncio
async def test_xflot_rejects_response_without_disclaimer():
    provider = XflotProvider(
        build_settings(),
        FakeHTTPClient([response(200, json_data={"ok": True, "ipos": []})]),
    )

    with pytest.raises(ProviderResponseError):
        await provider.fetch_ipos()


def test_identifier_and_price_constraints_are_provider_scoped():
    identifier_constraint = next(
        constraint
        for constraint in AssetIdentifier.__table__.constraints
        if constraint.name == "uq_asset_identifier_provider_type_external"
    )
    price_index = next(
        index
        for index in AssetPrice.__table__.indexes
        if index.name == "uq_asset_price_observation"
    )

    assert [column.name for column in identifier_constraint.columns] == [
        "provider",
        "identifier_type",
        "scope",
        "external_id",
    ]
    assert price_index.unique
    assert "provider <> 'legacy'" in str(
        price_index.dialect_options["postgresql"]["where"]
    )


@pytest.mark.asyncio
async def test_repeated_price_upsert_updates_existing_observation():
    from uuid import uuid4

    from sqlalchemy.dialects import postgresql

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeSession:
        def __init__(self, existing):
            self.existing = existing
            self.statement = None

        async def execute(self, statement):
            if statement.is_insert:
                self.statement = statement
                return None
            return FakeResult(self.existing)

        async def commit(self):
            pass

    asset_id = uuid4()
    timestamp = datetime(2026, 10, 22, 4, 30, tzinfo=timezone.utc)
    identity = (asset_id, "tejhq", "eod", "1d", timestamp)
    session = FakeSession([identity])
    service = MarketDataSyncService(
        session,
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )
    row = service._price_values(
        asset_id=asset_id,
        provider="tejhq",
        observation_type="eod",
        interval="1d",
        timestamp=timestamp,
        price=Decimal("125"),
    )

    inserted, updated = await service._upsert_prices([row])
    sql = str(session.statement.compile(dialect=postgresql.dialect()))

    assert (inserted, updated) == (0, 1)
    assert "ON CONFLICT" in sql
    assert "DO UPDATE" in sql


def test_provider_registry_rejects_incompatible_selection():
    config = build_settings(market_data_stock_provider="unknown")
    registry = MarketDataProviderRegistry(config, FakeHTTPClient([]))

    with pytest.raises(ProviderConfigurationError):
        registry.stocks()


def test_provider_registry_defaults_to_keyless_providers():
    registry = MarketDataProviderRegistry(build_settings(), FakeHTTPClient([]))

    assert registry.stocks().provider_name == "tejhq"
    assert registry.ipos().provider_name == "xflot"
    assert registry.mutual_funds().provider_name == "mfapi"


@pytest.mark.asyncio
async def test_ipo_status_updates_without_clearing_unavailable_fields():
    class FakeSession:
        async def execute(self, statement):
            class Result:
                def all(self):
                    return []

                def scalars(self):
                    return iter([])

            return Result()

        def add_all(self, values):
            self.values = values

        async def commit(self):
            pass

    service = MarketDataSyncService(
        FakeSession(),
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )
    record = IPORecord(
        ipo_id="sample-ipo",
        name="Sample IPO",
        status="listed",
        issue_price_low=Decimal("100"),
        issue_price_high=Decimal("110"),
        source_attribution="Xflot (https://www.xflot.com)",
        source_disclaimer="Aggregated public information; verify independently.",
    )

    inserted, updated, skipped = await service._persist_ipos(
        [record],
        provider_name="xflot",
    )

    ipo = next(item for item in service.db.values if item.__class__.__name__ == "IPO")
    assert (inserted, updated, skipped) == (1, 0, 0)
    assert ipo.ipo_status == "listed"
    assert ipo.issue_price_low == Decimal("100")
    assert ipo.listing_date is None
    assert ipo.source_attribution == "Xflot (https://www.xflot.com)"
    assert ipo.source_disclaimer.startswith("Aggregated public information")

    existing = IPO(
        asset_id=ipo.asset_id,
        ipo_status="open",
        issue_price_low=Decimal("95"),
        listing_date=date(2026, 10, 30),
    )
    service._update_ipo(existing, record)
    assert existing.ipo_status == "listed"
    assert existing.issue_price_low == Decimal("100")
    assert existing.listing_date == date(2026, 10, 30)
    assert existing.source_disclaimer == record.source_disclaimer


@pytest.mark.asyncio
async def test_ipo_persistence_merges_duplicate_provider_ids():
    class FakeSession:
        async def execute(self, statement):
            class Result:
                def scalars(self):
                    return iter([])

            return Result()

        def add_all(self, values):
            self.values = values

        async def commit(self):
            pass

    service = MarketDataSyncService(
        FakeSession(),
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )
    first = IPORecord(
        ipo_id="duplicate-ipo",
        name="Duplicate IPO",
        status="open",
        issue_price_low=Decimal("100"),
    )
    duplicate = IPORecord(
        ipo_id="duplicate-ipo",
        name="Duplicate IPO",
        status="listed",
        issue_price_high=Decimal("110"),
    )

    inserted, updated, skipped = await service._persist_ipos(
        [first, duplicate],
        provider_name="xflot",
    )

    new_identities = [
        item
        for item in service.db.values
        if isinstance(item, AssetIdentifier)
    ]
    new_ipos = [item for item in service.db.values if isinstance(item, IPO)]
    assert (inserted, updated, skipped) == (1, 0, 0)
    assert len(new_identities) == 1
    assert len(new_ipos) == 1
    assert new_ipos[0].ipo_status == "listed"
    assert new_ipos[0].issue_price_low == Decimal("100")
    assert new_ipos[0].issue_price_high == Decimal("110")


@pytest.mark.asyncio
async def test_xflot_sync_enforces_documented_minimum_poll_interval():
    class FakeResult:
        def scalar_one_or_none(self):
            return datetime.now(timezone.utc)

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

    service = MarketDataSyncService(
        FakeSession(),
        build_settings(),
        MarketDataProviderRegistry(build_settings(), FakeHTTPClient([])),
    )

    with pytest.raises(ProviderRateLimitError):
        await service.sync_ipos()


def test_internal_sync_requires_dedicated_cron_secret(monkeypatch):
    monkeypatch.setattr(settings, "market_data_cron_secret", "cron-test-secret")
    monkeypatch.setattr(settings, "market_data_sync_enabled", True)
    with TestClient(app) as client:
        response_without_secret = client.post(
            "/api/v1/internal/market-data/sync/stocks"
        )
        response_with_wrong_secret = client.post(
            "/api/v1/internal/market-data/sync/stocks",
            headers={"X-Cron-Secret": "wrong"},
        )

    assert response_without_secret.status_code == 401
    assert response_with_wrong_secret.status_code == 401


def test_combined_sync_discovers_catalogs_by_default():
    operation = app.openapi()["paths"][
        "/api/v1/internal/market-data/sync/all"
    ]["post"]
    discover_parameter = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "discover"
    )

    assert discover_parameter["schema"]["default"] is True


def test_combined_sync_returns_accepted_and_schedules_background_work(monkeypatch):
    import app.api.v1.market_data_sync as sync_api
    from app.api.v1.market_data_sync import get_sync_service

    recorded = []
    scheduled = []

    class FakeService:
        async def record_sync_state(self, summary, *, status, started_at):
            recorded.append((summary, status, started_at))

    async def fake_background_sync(**kwargs):
        scheduled.append(kwargs)

    monkeypatch.setattr(settings, "market_data_cron_secret", "cron-test-secret")
    monkeypatch.setattr(settings, "market_data_sync_enabled", True)
    monkeypatch.setattr(
        sync_api,
        "_run_all_sync_in_background",
        fake_background_sync,
    )
    app.dependency_overrides[get_sync_service] = lambda: FakeService()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/internal/market-data/sync/all?discover=true&discovery_offset=200",
                headers={"X-Cron-Secret": "cron-test-secret"},
            )
    finally:
        app.dependency_overrides.pop(get_sync_service, None)

    assert response.status_code == 202
    body = response.json()
    assert body["job"] == "all"
    assert body["status"] == "accepted"
    assert body["status_url"] == "/api/v1/internal/market-data/sync/status"
    assert len(recorded) == 1
    assert recorded[0][0].job_id == body["job_id"]
    assert recorded[0][1] == "running"
    assert len(scheduled) == 1
    assert scheduled[0]["discover"] is True
    assert scheduled[0]["discovery_offset"] == 200
    assert scheduled[0]["run_id"] == body["job_id"]