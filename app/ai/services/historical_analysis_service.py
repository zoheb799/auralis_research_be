
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from statistics import pstdev
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas.analysis import HistoricalAnalysis
from app.db.models.asset_price import AssetPrice


class HistoricalAnalysisService:
    MARKET_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
    UPDATE_GRACE_TIME = time(18, 0)
    STALE_AFTER_HOURS = 24.0

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @classmethod
    def _is_stale(
        cls,
        latest_timestamp: datetime,
        now: datetime,
        exchange: str | None,
    ) -> bool:
        exchange_name = (exchange or "").upper()

        # Use age-based freshness for unsupported exchanges.
        if exchange_name not in {"NSE", "BSE"}:
            age_hours = (
                now - latest_timestamp
            ).total_seconds() / 3600
            return age_hours > cls.STALE_AFTER_HOURS

        local_now = now.astimezone(cls.MARKET_TIMEZONE)
        local_timestamp = latest_timestamp.astimezone(
            cls.MARKET_TIMEZONE
        )

        # Daily closing data is expected after the market's
        # closing-data publication grace period.
        expected_date = local_now.date()

        if (
            local_now.weekday() >= 5
            or local_now.time() < cls.UPDATE_GRACE_TIME
        ):
            expected_date -= timedelta(days=1)

        # Skip weekends when finding the previous expected session.
        while expected_date.weekday() >= 5:
            expected_date -= timedelta(days=1)

        return local_timestamp.date() < expected_date

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        """Normalize timestamps to UTC; assume naive timestamps are UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    @staticmethod
    def _valid_price(value: Decimal | None) -> bool:
        return (
            value is not None
            and value.is_finite()
            and value > 0
        )

    @staticmethod
    def _empty_analysis(asset_id: UUID) -> HistoricalAnalysis:
        return HistoricalAnalysis(
            asset_id=asset_id,
            current_price=None,
            period_return_percent=None,
            highest_price=None,
            lowest_price=None,
            volatility_percent=None,
            observation_count=0,
            start_timestamp=None,
            end_timestamp=None,
            data_age_hours=None,
            is_stale=None,
        )

    async def analyze(
        self,
        *,
        asset_id: UUID,
        lookback_days: int,
        exchange: str | None = None,
    ) -> HistoricalAnalysis:
        if lookback_days <= 0:
            raise ValueError(
                "lookback_days must be greater than zero."
            )

        result = await self.db.execute(
            select(AssetPrice)
            .where(AssetPrice.asset_id == asset_id)
            .order_by(AssetPrice.price_timestamp.asc())
        )

        price_records = result.scalars().all()

        if not price_records:
            return self._empty_analysis(asset_id)

        normalized_records = [
            (
                record,
                self._normalize_timestamp(record.price_timestamp),
            )
            for record in price_records
        ]
        normalized_records.sort(key=lambda item: item[1])

        valid_records: list[tuple[object, datetime, Decimal]] = []

        for record, timestamp in normalized_records:
            price = (
                record.close
                if record.close is not None
                else record.price
            )

            if not self._valid_price(price):
                continue

            valid_records.append((record, timestamp, price))

        if not valid_records:
            return self._empty_analysis(asset_id)

        now = datetime.now(timezone.utc)
        _, latest_timestamp, _ = valid_records[-1]

        data_age_hours = max(
            0.0,
            (now - latest_timestamp).total_seconds() / 3600,
        )

        is_stale = self._is_stale(
            latest_timestamp=latest_timestamp,
            now=now,
            exchange=exchange,
        )

        # Calendar-day lookback anchored to the current time.
        start_cutoff = now - timedelta(days=lookback_days)

        records = [
            (record, timestamp, price)
            for record, timestamp, price in valid_records
            if start_cutoff <= timestamp <= now
        ]

        if not records:
            return self._empty_analysis(asset_id)

        prices = [price for _, _, price in records]

        current_price = prices[-1]
        highest_price = max(prices)
        lowest_price = min(prices)

        period_return_percent: Decimal | None = None

        if len(prices) >= 2 and prices[0] > 0:
            period_return_percent = (
                (current_price - prices[0]) / prices[0]
            ) * Decimal("100")

        returns: list[float] = []

        for previous, current in zip(prices, prices[1:]):
            if previous <= 0:
                continue

            percentage_return = (
                (current - previous) / previous
            ) * Decimal("100")

            returns.append(float(percentage_return))

        volatility_percent: Decimal | None = None

        if len(returns) >= 2:
            volatility_percent = Decimal(str(pstdev(returns)))

        return HistoricalAnalysis(
            asset_id=asset_id,
            current_price=current_price,
            period_return_percent=period_return_percent,
            highest_price=highest_price,
            lowest_price=lowest_price,
            volatility_percent=volatility_percent,
            observation_count=len(records),
            start_timestamp=records[0][1],
            end_timestamp=records[-1][1],
            data_age_hours=data_age_hours,
            is_stale=is_stale,
        )