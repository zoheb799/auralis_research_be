
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.services.historical_analysis_service import (
    HistoricalAnalysisService,
)


def make_price(timestamp, price):
    return SimpleNamespace(
        asset_id=uuid4(),
        price_timestamp=timestamp,
        close=Decimal(str(price)),
        price=Decimal(str(price)),
    )


def make_db(records):
    db = AsyncMock()
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(
            all=lambda: records
        )
    )
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_no_price_records_returns_empty_analysis():
    service = HistoricalAnalysisService(make_db([]))

    result = await service.analyze(
        asset_id=uuid4(),
        lookback_days=365,
    )

    assert result.current_price is None
    assert result.period_return_percent is None
    assert result.volatility_percent is None
    assert result.observation_count == 0


@pytest.mark.asyncio
async def test_calculates_period_return_from_available_prices():
    now = datetime.now(timezone.utc)
    records = [
        make_price(now - timedelta(days=10), "100"),
        make_price(now - timedelta(days=5), "110"),
        make_price(now, "120"),
    ]

    service = HistoricalAnalysisService(make_db(records))

    result = await service.analyze(
        asset_id=uuid4(),
        lookback_days=365,
    )

    # (120 - 100) / 100 * 100 = 20%
    assert result.current_price == Decimal("120")
    assert result.period_return_percent == Decimal("20")
    assert result.highest_price == Decimal("120")
    assert result.lowest_price == Decimal("100")
    assert result.observation_count == 3


@pytest.mark.asyncio
async def test_rejects_non_positive_lookback_period():
    service = HistoricalAnalysisService(make_db([]))

    with pytest.raises(ValueError):
        await service.analyze(
            asset_id=uuid4(),
            lookback_days=0,
        )


@pytest.mark.asyncio
async def test_single_price_has_no_period_return_or_volatility():
    now = datetime.now(timezone.utc)
    records = [make_price(now, "100")]

    service = HistoricalAnalysisService(make_db(records))

    result = await service.analyze(
        asset_id=uuid4(),
        lookback_days=365,
    )

    assert result.current_price == Decimal("100")
    assert result.period_return_percent is None
    assert result.volatility_percent is None
    assert result.observation_count == 1
    
@pytest.mark.asyncio
async def test_aware_timestamps_are_normalized_to_utc():
    asset_id = uuid4()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # These two timestamps represent the same instant.
    records = [
        make_price(
            (now - timedelta(days=1)).astimezone(
                timezone(timedelta(hours=5, minutes=30))
            ),
            "100",
        ),
        make_price(now, "110"),
    ]

    for record in records:
        record.asset_id = asset_id

    service = HistoricalAnalysisService(make_db(records))

    result = await service.analyze(
        asset_id=asset_id,
        lookback_days=365,
    )

    assert result.observation_count == 2
    assert result.start_timestamp.utcoffset() == timedelta(0)
    assert result.end_timestamp.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_naive_timestamps_are_assumed_to_be_utc():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    naive_now = now.replace(tzinfo=None)

    record = make_price(naive_now, "100")
    service = HistoricalAnalysisService(make_db([record]))

    result = await service.analyze(
        asset_id=record.asset_id,
        lookback_days=365,
    )

    assert result.end_timestamp == now
    assert result.is_stale is False
    assert result.data_age_hours is not None
    assert result.data_age_hours < 1


@pytest.mark.asyncio
async def test_old_price_is_flagged_as_stale():
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=7)
    record = make_price(old_timestamp, "100")

    service = HistoricalAnalysisService(make_db([record]))

    result = await service.analyze(
        asset_id=record.asset_id,
        lookback_days=365,
    )

    assert result.current_price == Decimal("100")
    assert result.is_stale is True
    assert result.data_age_hours >= 24


@pytest.mark.asyncio
async def test_invalid_prices_are_excluded():
    now = datetime.now(timezone.utc)
    asset_id = uuid4()

    records = [
        make_price(now - timedelta(days=2), "100"),
        make_price(now - timedelta(days=1), "0"),
        make_price(now, "-10"),
    ]

    for record in records:
        record.asset_id = asset_id

    service = HistoricalAnalysisService(make_db(records))

    result = await service.analyze(
        asset_id=asset_id,
        lookback_days=365,
    )

    assert result.current_price == Decimal("100")
    assert result.observation_count == 1
    assert result.period_return_percent is None