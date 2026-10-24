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
from app.db.models.ipo import IPO
from app.integrations.market_data.errors import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from app.integrations.market_data.http import RetryingProviderClient
from app.integrations.market_data.providers.mfapi import MFAPIProvider
from app.integrations.market_data.providers.tejhq import TejHQProvider
from app.integrations.market_data.providers.xflot import XflotProvider
from app.integrations.market_data.registry import MarketDataProviderRegistry
from app.integrations.market_data.schemas import IPORecord, StockInstrument
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