import asyncio
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, text, tuple_
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.asset import Asset
from app.db.models.asset_identifier import AssetIdentifier
from app.db.models.asset_fundamental_sync_state import AssetFundamentalSyncState
from app.db.models.asset_price import AssetPrice
from app.db.models.financial_metric import FinancialMetric
from app.db.models.ipo import IPO
from app.db.models.market_data_sync_state import MarketDataSyncState
from app.db.models.market_data_api_usage import MarketDataAPIUsage
from app.db.models.mutual_fund import MutualFund
from app.db.models.stock import Stock
from app.integrations.market_data.errors import (
    MarketDataError,
    ProviderInstrumentNotFoundError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
)
from app.integrations.market_data.registry import MarketDataProviderRegistry
from app.integrations.market_data.schemas import (
    FundScheme,
    FinancialPeriod,
    IPORecord,
    NavObservation,
    PriceObservation,
    StockCatalogSyncSummary,
    StockFundamentalData,
    StockInstrument,
    SyncSummary,
)


class SyncAlreadyRunning(MarketDataError):
    pass


class MarketDataSyncService:
    MARKET_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
    ALPHA_VANTAGE_REQUESTS_PER_STOCK = 3

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        providers: MarketDataProviderRegistry,
    ) -> None:
        self.db = db
        self.settings = settings
        self.providers = providers

    async def record_sync_state(
        self,
        summary: SyncSummary,
        *,
        status: str,
        started_at: datetime,
        error_category: str | None = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        state = MarketDataSyncState.__table__
        statement = pg_insert(MarketDataSyncState).values(
            id=uuid4(),
            job=summary.job,
            provider=summary.provider,
            status=status,
            last_run_id=UUID(summary.job_id),
            last_started_at=started_at,
            last_finished_at=finished_at,
            last_success_at=finished_at if status == "success" else None,
            duration_seconds=Decimal(str(summary.duration_seconds)),
            discovered=summary.discovered,
            inserted=summary.inserted,
            updated=summary.updated,
            skipped=summary.skipped,
            failed=summary.failed,
            error_category=error_category,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["job", "provider"],
            set_={
                "status": statement.excluded.status,
                "last_run_id": statement.excluded.last_run_id,
                "last_started_at": statement.excluded.last_started_at,
                "last_finished_at": statement.excluded.last_finished_at,
                "last_success_at": func.coalesce(
                    statement.excluded.last_success_at,
                    state.c.last_success_at,
                ),
                "duration_seconds": statement.excluded.duration_seconds,
                "discovered": statement.excluded.discovered,
                "inserted": statement.excluded.inserted,
                "updated": statement.excluded.updated,
                "skipped": statement.excluded.skipped,
                "failed": statement.excluded.failed,
                "error_category": statement.excluded.error_category,
                "updated_at": func.now(),
            },
        )
        await self.db.execute(statement)
        await self.db.commit()

    async def sync_stocks(self, *, discover: bool = False) -> SyncSummary:
        provider = self.providers.stocks()
        discovered = 0
        catalog_assets_inserted = 0
        catalog_assets_updated = 0
        catalog_stock_records_inserted = 0
        if discover:
            catalog_summary = await self.sync_stock_catalog()
            discovered = catalog_summary.identifiers_linked
            catalog_assets_inserted = catalog_summary.assets_inserted
            catalog_assets_updated = catalog_summary.assets_updated
            catalog_stock_records_inserted = (
                catalog_summary.stock_records_inserted
            )

        identifiers = await self.db.execute(
            select(
                AssetIdentifier.asset_id,
                AssetIdentifier.external_id,
                AssetIdentifier.scope,
            )
            .join(Asset, Asset.id == AssetIdentifier.asset_id)
            .where(
                AssetIdentifier.provider == provider.provider_name,
                AssetIdentifier.identifier_type == "stock_symbol",
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
            )
            .order_by(AssetIdentifier.scope, AssetIdentifier.external_id)
            .limit(max(1, self.settings.market_data_stock_sync_limit))
        )
        rows = identifiers.all()
        if not rows:
            raise ProviderConfigurationError(
                "No linked stocks; run the stock catalog sync or stock discovery"
            )

        asset_by_key = {
            f"{scope}:{external_id}": asset_id
            for asset_id, external_id, scope in rows
        }
        await self.db.commit()
        observations = await provider.fetch_observations(list(asset_by_key))
        if not observations:
            raise ProviderResponseError(
                f"{provider.provider_name} returned no price observations"
            )

        price_rows = []
        for observation in observations:
            asset_id = asset_by_key.get(observation.instrument_key)
            if asset_id is None:
                continue
            price_rows.append(
                self._price_values(
                    asset_id=asset_id,
                    provider=provider.provider_name,
                    observation_type=observation.observation_type,
                    interval=observation.interval,
                    timestamp=observation.price_timestamp,
                    price=observation.price,
                    open_price=observation.open,
                    high=observation.high,
                    low=observation.low,
                    close=observation.close,
                    volume=observation.volume,
                )
            )
        inserted, updated = await self._upsert_prices(price_rows)
        return SyncSummary(
            job="stocks",
            provider=provider.provider_name,
            discovered=discovered,
            catalog_assets_inserted=catalog_assets_inserted,
            catalog_assets_updated=catalog_assets_updated,
            catalog_stock_records_inserted=catalog_stock_records_inserted,
            inserted=inserted,
            updated=updated,
            skipped=len(observations) - len(price_rows),
        )

    async def sync_stock_catalog(self) -> StockCatalogSyncSummary:
        catalog_provider = self.providers.stock_catalog()
        instruments = await catalog_provider.fetch_constituents()
        assets_inserted, assets_updated, stock_records_inserted = (
            await self._upsert_stock_catalog(instruments)
        )
        identifiers_linked = 0
        stock_provider = self.providers.stocks()
        while True:
            batch_linked = await self._discover_stocks(stock_provider)
            identifiers_linked += batch_linked
            if batch_linked == 0:
                break
        return StockCatalogSyncSummary(
            source=catalog_provider.provider_name,
            fetched=len(instruments),
            assets_inserted=assets_inserted,
            assets_updated=assets_updated,
            stock_records_inserted=stock_records_inserted,
            identifiers_linked=identifiers_linked,
        )

    async def sync_stock_fundamentals(
        self,
        *,
        dry_run: bool = False,
        limit: int | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        retry_failed: bool = False,
        force_refresh: bool = False,
    ) -> SyncSummary:
        provider = self.providers.stock_fundamentals()
        if not dry_run:
            required_key = (
                self.settings.bharatstock_api_key
                if provider.provider_name == "bharatstock"
                else self.settings.alpha_vantage_api_key
            )
            if not required_key:
                key_name = (
                    "BHARATSTOCK_API_KEY"
                    if provider.provider_name == "bharatstock"
                    else "ALPHA_VANTAGE_API_KEY"
                )
                raise ProviderConfigurationError(
                    f"{key_name} is required for stock fundamentals sync"
                )

        requests_per_stock = getattr(
            provider,
            "requests_per_stock",
            self.ALPHA_VANTAGE_REQUESTS_PER_STOCK,
        )
        today = datetime.now(timezone.utc).date()
        usage_result = await self.db.execute(
            select(MarketDataAPIUsage.requests_used).where(
                MarketDataAPIUsage.provider == provider.provider_name,
                MarketDataAPIUsage.usage_date == today,
            )
        )
        requests_used = usage_result.scalar_one_or_none() or 0
        daily_limit = max(
            0,
            (
                self.settings.bharatstock_daily_request_limit
                if provider.provider_name == "bharatstock"
                else self.settings.alpha_vantage_daily_request_limit
            ),
        )
        remaining_budget = max(0, daily_limit - requests_used)
        batch_limit = min(
            max(1, self.settings.market_data_stock_sync_limit),
            remaining_budget // requests_per_stock,
        )
        if limit is not None:
            batch_limit = min(batch_limit, max(0, limit))
        if batch_limit == 0:
            return SyncSummary(
                job="fundamentals",
                provider=provider.provider_name,
                request_budget_remaining=remaining_budget,
            )

        now = datetime.now(timezone.utc)
        today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
        refresh_before = now - timedelta(days=1)
        unsupported_retry_before = now - timedelta(days=90)
        eligibility = (
            True
            if force_refresh
            else (
                AssetFundamentalSyncState.asset_id.is_(None)
                | (
                    (AssetFundamentalSyncState.status == "success")
                    & (
                        AssetFundamentalSyncState.last_attempted_at
                        < refresh_before
                    )
                )
                | (
                    (AssetFundamentalSyncState.status == "unsupported")
                    & (
                        AssetFundamentalSyncState.last_attempted_at
                        < unsupported_retry_before
                    )
                )
                | (
                    (AssetFundamentalSyncState.status == "failed")
                    & (
                        or_(
                            retry_failed,
                            AssetFundamentalSyncState.last_attempted_at
                            < today_start,
                        )
                    )
                )
            )
        )
        candidate_query = (
            select(Asset.id, Asset.symbol, Asset.exchange)
            .join(Stock, Stock.asset_id == Asset.id)
            .outerjoin(
                AssetFundamentalSyncState,
                AssetFundamentalSyncState.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
                Asset.symbol.is_not(None),
                func.upper(Asset.exchange).in_(("NSE", "BSE")),
                eligibility,
            )
            .order_by(
                AssetFundamentalSyncState.last_attempted_at.asc().nullsfirst(),
                Asset.symbol,
            )
        )
        if symbol:
            candidate_query = candidate_query.where(
                func.upper(Asset.symbol) == symbol.strip().upper()
            )
        if exchange:
            candidate_query = candidate_query.where(
                func.upper(Asset.exchange) == exchange.strip().upper()
            )
        candidates_result = await self.db.execute(
            candidate_query.limit(batch_limit)
        )
        candidates = candidates_result.all()
        if dry_run:
            return SyncSummary(
                job="fundamentals",
                provider=provider.provider_name,
                discovered=len(candidates),
                request_budget_remaining=remaining_budget,
            )
        inserted = updated = skipped = failed = processed = 0

        for asset_id, symbol, exchange in candidates:
            reserved = await self._reserve_api_requests(
                provider=provider.provider_name,
                usage_date=today,
                requests=requests_per_stock,
                daily_limit=daily_limit,
            )
            if not reserved:
                break
            try:
                fundamentals = await provider.fetch_fundamentals(symbol, exchange)
                added, changed = await self._persist_stock_fundamentals(
                    asset_id,
                    fundamentals,
                )
                inserted += added
                updated += changed
                await self._record_asset_fundamentals_sync(
                    asset_id,
                    status="success",
                    error_category=None,
                    provider=provider.provider_name,
                    data=fundamentals,
                )
            except ProviderInstrumentNotFoundError as exc:
                skipped += 1
                await self._record_asset_fundamentals_sync(
                    asset_id,
                    status="unsupported",
                    error_category=type(exc).__name__,
                    provider=provider.provider_name,
                )
            except ProviderRateLimitError as exc:
                await self._record_asset_fundamentals_sync(
                    asset_id,
                    status="failed",
                    error_category=type(exc).__name__,
                    provider=provider.provider_name,
                )
                raise
            except ProviderRequestError as exc:
                failed += 1
                await self._record_asset_fundamentals_sync(
                    asset_id,
                    status="failed",
                    error_category=type(exc).__name__,
                    provider=provider.provider_name,
                )
            except ProviderResponseError as exc:
                failed += 1
                await self._record_asset_fundamentals_sync(
                    asset_id,
                    status="failed",
                    error_category=type(exc).__name__,
                    provider=provider.provider_name,
                )
            finally:
                requests_made = provider.requests_made
                processed += requests_made
                unused_reservation = (
                    requests_per_stock - requests_made
                )
                if unused_reservation > 0:
                    await self._release_api_requests(
                        provider=provider.provider_name,
                        usage_date=today,
                        requests=unused_reservation,
                    )

        return SyncSummary(
            job="fundamentals",
            provider=provider.provider_name,
            discovered=len(candidates),
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            failed=failed,
            requests_used=processed,
            request_budget_remaining=max(0, remaining_budget - processed),
        )

    async def _reserve_api_requests(
        self,
        *,
        provider: str,
        usage_date: date,
        requests: int,
        daily_limit: int,
    ) -> bool:
        statement = pg_insert(MarketDataAPIUsage).values(
            provider=provider,
            usage_date=usage_date,
            requests_used=requests,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["provider", "usage_date"],
            set_={
                "requests_used": MarketDataAPIUsage.requests_used + requests,
            },
            where=MarketDataAPIUsage.requests_used + requests <= daily_limit,
        ).returning(MarketDataAPIUsage.requests_used)
        result = await self.db.execute(statement)
        reserved = result.scalar_one_or_none() is not None
        await self.db.commit()
        return reserved

    async def _release_api_requests(
        self,
        *,
        provider: str,
        usage_date: date,
        requests: int,
    ) -> None:
        await self.db.execute(
            MarketDataAPIUsage.__table__.update()
            .where(
                MarketDataAPIUsage.provider == provider,
                MarketDataAPIUsage.usage_date == usage_date,
            )
            .values(
                requests_used=func.greatest(
                    0,
                    MarketDataAPIUsage.requests_used - requests,
                )
            )
        )
        await self.db.commit()

    async def _persist_stock_fundamentals(
        self,
        asset_id: UUID,
        data: StockFundamentalData,
    ) -> tuple[int, int]:
        stock_result = await self.db.execute(
            select(Stock).where(Stock.asset_id == asset_id)
        )
        stock = stock_result.scalar_one()
        for field in (
            "market_cap",
            "pe_ratio",
            "eps",
            "dividend_yield",
            "book_value",
            "debt_to_equity",
            "roe",
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(stock, field, value)

        period_dates = [period.period_end for period in data.periods]
        existing_result = await self.db.execute(
            select(FinancialMetric).where(
                FinancialMetric.asset_id == asset_id,
                FinancialMetric.period_type == "annual",
                FinancialMetric.period_end.in_(period_dates),
            )
        ) if period_dates else None
        existing = (
            {
                (metric.period_end, metric.consolidation_type): metric
                for metric in existing_result.scalars()
            }
            if existing_result is not None
            else {}
        )

        inserted = updated = 0
        used_metric_ids = set()
        for period in data.periods:
            metric = existing.get(
                (period.period_end, period.consolidation_type)
            )
            if (
                metric is None
                and period.consolidation_type is not None
            ):
                legacy_metric = existing.get((period.period_end, None))
                if (
                    legacy_metric is not None
                    and legacy_metric.id not in used_metric_ids
                ):
                    metric = legacy_metric
            is_new = metric is None
            if metric is None:
                metric = FinancialMetric(
                    asset_id=asset_id,
                    period_type="annual",
                    period_end=period.period_end,
                )
            if metric.id is not None:
                used_metric_ids.add(metric.id)
            existing[(period.period_end, period.consolidation_type)] = metric
            metric.consolidation_type = period.consolidation_type
            metric.source_provider = (
                data.source_provider
                or self.settings.market_data_fundamentals_provider
            )
            metric.source_as_of_date = data.source_as_of_date
            self._apply_financial_period(metric, period)
            if is_new:
                self.db.add(metric)
                inserted += 1
            else:
                updated += 1
        await self.db.commit()
        return inserted, updated

    @staticmethod
    def _apply_financial_period(
        metric: FinancialMetric,
        period: FinancialPeriod,
    ) -> None:
        for field in (
            "revenue",
            "operating_profit",
            "net_profit",
            "eps",
            "total_debt",
            "shareholder_equity",
            "cash",
            "roe",
            "roce",
        ):
            value = getattr(period, field)
            if value is not None:
                setattr(metric, field, value)

    async def _record_asset_fundamentals_sync(
        self,
        asset_id: UUID,
        *,
        status: str,
        error_category: str | None,
        provider: str,
        data: StockFundamentalData | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        statement = pg_insert(AssetFundamentalSyncState).values(
            asset_id=asset_id,
            status=status,
            provider=provider,
            last_attempted_at=now,
            last_success_at=now if status == "success" else None,
            source_as_of_date=data.source_as_of_date if data else None,
            missing_fields=(
                json.dumps(data.missing_fields)
                if data and data.missing_fields
                else None
            ),
            error_category=error_category,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["asset_id"],
            set_={
                "status": statement.excluded.status,
                "provider": statement.excluded.provider,
                "last_attempted_at": statement.excluded.last_attempted_at,
                "last_success_at": func.coalesce(
                    statement.excluded.last_success_at,
                    AssetFundamentalSyncState.last_success_at,
                ),
                "source_as_of_date": statement.excluded.source_as_of_date,
                "missing_fields": statement.excluded.missing_fields,
                "error_category": statement.excluded.error_category,
            },
        )
        await self.db.execute(statement)
        await self.db.commit()

    async def _upsert_stock_catalog(
        self,
        instruments: list[StockInstrument],
    ) -> tuple[int, int, int]:
        catalog_keys = {
            (instrument.exchange.upper(), instrument.symbol.upper())
            for instrument in instruments
        }
        existing_result = await self.db.execute(
            select(Asset).where(
                Asset.asset_type == "stock",
                tuple_(
                    func.upper(Asset.exchange),
                    func.upper(Asset.symbol),
                ).in_(catalog_keys),
            )
        )
        existing_assets: dict[tuple[str, str], Asset] = {}
        for asset in existing_result.scalars():
            key = ((asset.exchange or "").upper(), (asset.symbol or "").upper())
            if key in existing_assets:
                raise ProviderResponseError(
                    f"Multiple stock assets exist for {key[0]}:{key[1]}"
                )
            existing_assets[key] = asset

        new_assets: list[Asset] = []
        stock_asset_ids: list[UUID] = []
        assets_inserted = assets_updated = 0
        for instrument in instruments:
            key = (instrument.exchange.upper(), instrument.symbol.upper())
            asset = existing_assets.get(key)
            if asset is None:
                asset = Asset(
                    id=uuid4(),
                    name=instrument.name or instrument.symbol,
                    symbol=instrument.symbol,
                    asset_type="stock",
                    exchange=instrument.exchange,
                    sector=instrument.sector,
                    is_active=True,
                )
                new_assets.append(asset)
                existing_assets[key] = asset
                assets_inserted += 1
                continue

            if (
                asset.name != instrument.name
                or asset.symbol != instrument.symbol
                or asset.exchange != instrument.exchange
                or (
                    instrument.sector is not None
                    and asset.sector != instrument.sector
                )
                or not asset.is_active
            ):
                asset.name = instrument.name or instrument.symbol
                asset.symbol = instrument.symbol
                asset.exchange = instrument.exchange
                if instrument.sector is not None:
                    asset.sector = instrument.sector
                asset.is_active = True
                assets_updated += 1
            stock_asset_ids.append(asset.id)

        stock_ids: set[UUID] = set()
        if stock_asset_ids:
            stock_result = await self.db.execute(
                select(Stock.asset_id).where(Stock.asset_id.in_(stock_asset_ids))
            )
            stock_ids = set(stock_result.scalars())

        new_stocks = [
            Stock(asset_id=asset_id)
            for asset_id in stock_asset_ids
            if asset_id not in stock_ids
        ]
        stock_records_inserted = len(new_stocks) + len(new_assets)
        new_stocks.extend(Stock(asset_id=asset.id) for asset in new_assets)
        self.db.add_all([*new_assets, *new_stocks])
        await self.db.commit()
        return assets_inserted, assets_updated, stock_records_inserted

    async def sync_mutual_funds(
        self,
        *,
        discover: bool = False,
        discovery_offset: int = 0,
    ) -> SyncSummary:
        discovered = 0
        provider = self.providers.mutual_funds()
        if discover:
            schemes = await provider.discover_schemes(offset=discovery_offset)
            if not schemes:
                raise ProviderResponseError("MFAPI scheme discovery returned no schemes")
            discovered = await self._persist_schemes(schemes)

        identifier_result = await self.db.execute(
            select(AssetIdentifier.asset_id, AssetIdentifier.external_id)
            .join(Asset, Asset.id == AssetIdentifier.asset_id)
            .where(
                AssetIdentifier.provider == "mfapi",
                AssetIdentifier.identifier_type == "scheme_code",
                Asset.asset_type == "mutual_fund",
                Asset.is_active.is_(True),
            )
            .order_by(AssetIdentifier.external_id)
            .limit(max(1, self.settings.market_data_mf_discovery_limit))
        )
        identifiers = identifier_result.all()
        if not identifiers:
            raise ProviderConfigurationError(
                "No MFAPI-linked schemes; run bounded mutual-fund discovery"
            )

        await self.db.commit()
        semaphore = asyncio.Semaphore(
            max(1, self.settings.market_data_max_concurrency)
        )

        async def fetch_nav(scheme_code: str):
            async with semaphore:
                return await provider.fetch_latest_nav(scheme_code)

        fetched = await asyncio.gather(
            *(fetch_nav(scheme_code) for _, scheme_code in identifiers)
        )
        updated, inserted, skipped = await self._persist_navs(identifiers, fetched)
        return SyncSummary(
            job="mutual_funds",
            provider="mfapi",
            discovered=discovered,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
        )

    async def sync_ipos(self) -> SyncSummary:
        provider = self.providers.ipos()
        if provider.minimum_poll_interval_seconds:
            previous = await self.db.execute(
                select(MarketDataSyncState.last_started_at).where(
                    MarketDataSyncState.job == "ipos",
                    MarketDataSyncState.provider == provider.provider_name,
                )
            )
            last_started_at = previous.scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if (
                last_started_at is not None
                and (now - last_started_at).total_seconds()
                < provider.minimum_poll_interval_seconds
            ):
                raise ProviderRateLimitError(
                    "Xflot requires at least 60 seconds between IPO catalog requests",
                    retry_after_seconds=provider.minimum_poll_interval_seconds,
                )
            await self.db.commit()
        records = await provider.fetch_ipos()
        inserted, updated, skipped = await self._persist_ipos(
            records,
            provider_name=provider.provider_name,
        )
        return SyncSummary(
            job="ipos",
            provider=provider.provider_name,
            discovered=len(records),
            inserted=inserted,
            updated=updated,
            skipped=skipped,
        )

    async def _discover_stocks(self, provider) -> int:
        catalog_result = await self.db.execute(
            select(Asset.symbol, Asset.exchange)
            .join(Stock, Stock.asset_id == Asset.id)
            .outerjoin(
                AssetIdentifier,
                and_(
                    AssetIdentifier.provider == provider.provider_name,
                    AssetIdentifier.identifier_type == "stock_symbol",
                    func.upper(AssetIdentifier.scope) == func.upper(Asset.exchange),
                    func.upper(AssetIdentifier.external_id)
                    == func.upper(Asset.symbol),
                ),
            )
            .where(
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
                Asset.symbol.is_not(None),
                func.upper(Asset.exchange).in_(("NSE", "BSE")),
                AssetIdentifier.id.is_(None),
            )
            .order_by(Asset.exchange, Asset.symbol)
            .limit(max(1, self.settings.market_data_stock_sync_limit))
        )
        configured_symbols = {
            f"{exchange.upper()}:{symbol.upper()}"
            for symbol, exchange in catalog_result.all()
            if symbol and exchange
        }
        if not configured_symbols:
            return 0
        instruments = provider.fetch_instruments(configured_symbols)
        if not instruments:
            raise ProviderResponseError(
                f"{provider.provider_name} discovery returned no catalog instruments"
            )

        identity_result = await self.db.execute(
            select(AssetIdentifier).where(
                AssetIdentifier.provider == provider.provider_name,
                AssetIdentifier.identifier_type == "stock_symbol",
                tuple_(AssetIdentifier.scope, AssetIdentifier.external_id).in_(
                    [(item.exchange, item.symbol) for item in instruments]
                ),
            )
        )
        identities = {
            f"{row.scope}:{row.external_id}": row
            for row in identity_result.scalars()
        }
        existing_asset_ids = {row.asset_id for row in identities.values()}
        assets_result = await self.db.execute(
            select(Asset).where(Asset.id.in_(existing_asset_ids))
        ) if existing_asset_ids else None
        assets = {
            asset.id: asset
            for asset in assets_result.scalars()
        } if assets_result is not None else {}

        symbols = {item.symbol for item in instruments}
        exchanges = {item.exchange for item in instruments}
        candidates_result = await self.db.execute(
            select(Asset).where(
                Asset.asset_type == "stock",
                Asset.symbol.in_(symbols),
                Asset.exchange.in_(exchanges),
            )
        )
        candidates: dict[tuple[str, str], list[Asset]] = {}
        for asset in candidates_result.scalars():
            candidates.setdefault((asset.symbol or "", asset.exchange or ""), []).append(asset)

        stock_ids_result = await self.db.execute(select(Stock.asset_id))
        stock_ids = set(stock_ids_result.scalars())
        occupied_ids = {identity.asset_id for identity in identities.values()}
        new_identities: list[AssetIdentifier] = []
        new_assets: list[Asset] = []
        new_stocks: list[Stock] = []
        for instrument in instruments:
            identity_key = f"{instrument.exchange}:{instrument.symbol}"
            identity = identities.get(identity_key)
            asset = assets.get(identity.asset_id) if identity else None
            if asset is None:
                matching = [
                    candidate
                    for candidate in candidates.get(
                        (instrument.symbol, instrument.exchange), []
                    )
                    if candidate.id not in occupied_ids
                ]
                if len(matching) == 1:
                    asset = matching[0]
                elif instrument.name:
                    asset = Asset(
                        id=uuid4(),
                        name=instrument.name,
                        symbol=instrument.symbol,
                        asset_type="stock",
                        exchange=instrument.exchange,
                        sector=instrument.sector,
                        is_active=True,
                    )
                    new_assets.append(asset)
                else:
                    continue
                new_identities.append(
                    AssetIdentifier(
                        asset_id=asset.id,
                        provider=provider.provider_name,
                        identifier_type="stock_symbol",
                        scope=instrument.exchange,
                        external_id=instrument.symbol,
                    )
                )
                occupied_ids.add(asset.id)
            self._update_asset(asset, instrument)
            if asset.id not in stock_ids:
                new_stocks.append(Stock(asset_id=asset.id))
                stock_ids.add(asset.id)
        self.db.add_all([*new_assets, *new_identities, *new_stocks])
        await self.db.commit()
        return len(new_identities)

    async def _persist_schemes(self, schemes: list[FundScheme]) -> int:
        codes = [scheme.scheme_code for scheme in schemes]
        identity_result = await self.db.execute(
            select(AssetIdentifier).where(
                AssetIdentifier.provider == "mfapi",
                AssetIdentifier.identifier_type == "scheme_code",
                AssetIdentifier.scope == "",
                AssetIdentifier.external_id.in_(codes),
            )
        )
        identities = {row.external_id: row for row in identity_result.scalars()}
        existing_ids = {row.asset_id for row in identities.values()}
        assets_result = await self.db.execute(
            select(Asset).where(Asset.id.in_(existing_ids))
        ) if existing_ids else None
        assets = {
            asset.id: asset
            for asset in assets_result.scalars()
        } if assets_result is not None else {}
        mutual_result = await self.db.execute(
            select(MutualFund.asset_id).where(MutualFund.asset_id.in_(existing_ids))
        ) if existing_ids else None
        mutual_ids = set(mutual_result.scalars()) if mutual_result is not None else set()

        alias_values = {
            value
            for scheme in schemes
            for value in (scheme.isin_growth, scheme.isin_div_reinvestment)
            if value
        }
        alias_result = await self.db.execute(
            select(AssetIdentifier).where(
                AssetIdentifier.provider == "mfapi",
                AssetIdentifier.identifier_type.in_(
                    ["isin_growth", "isin_div_reinvestment"]
                ),
                AssetIdentifier.scope == "mutual_fund",
                AssetIdentifier.external_id.in_(alias_values),
            )
        ) if alias_values else None
        if alias_result is not None:
            for alias in alias_result.scalars():
                identities[f"{alias.identifier_type}:{alias.external_id}"] = alias

        new_assets: list[Asset] = []
        new_identities: list[AssetIdentifier] = []
        new_funds: list[MutualFund] = []
        for scheme in schemes:
            identity = identities.get(scheme.scheme_code)
            asset = assets.get(identity.asset_id) if identity else None
            if asset is None:
                asset = Asset(
                    id=uuid4(),
                    name=scheme.name,
                    symbol=scheme.scheme_code,
                    asset_type="mutual_fund",
                    exchange=None,
                    is_active=True,
                )
                new_assets.append(asset)
                new_identities.append(
                    AssetIdentifier(
                        asset_id=asset.id,
                        provider="mfapi",
                        identifier_type="scheme_code",
                        scope="",
                        external_id=scheme.scheme_code,
                    )
                )
            self._update_asset(asset, scheme)
            if asset.id not in mutual_ids:
                new_funds.append(MutualFund(asset_id=asset.id))
                mutual_ids.add(asset.id)
            self._add_fund_isin_aliases(asset.id, scheme, identities, new_identities)
        self.db.add_all([*new_assets, *new_identities, *new_funds])
        await self.db.commit()
        return len(schemes)

    def _add_fund_isin_aliases(
        self,
        asset_id,
        scheme: FundScheme,
        identities: dict[str, AssetIdentifier],
        pending: list[AssetIdentifier],
    ) -> None:
        for identifier_type, value in (
            ("isin_growth", scheme.isin_growth),
            ("isin_div_reinvestment", scheme.isin_div_reinvestment),
        ):
            if not value:
                continue
            key = f"{identifier_type}:{value}"
            if key in identities:
                continue
            identities[key] = AssetIdentifier(
                asset_id=asset_id,
                provider="mfapi",
                identifier_type=identifier_type,
                scope="mutual_fund",
                external_id=value,
            )
            pending.append(identities[key])

    async def _persist_ipos(
        self,
        records: list[IPORecord],
        *,
        provider_name: str,
    ) -> tuple[int, int, int]:
        if not records:
            return 0, 0, 0
        unique_records: dict[str, IPORecord] = {}
        for record in records:
            previous = unique_records.get(record.ipo_id)
            if previous is None:
                unique_records[record.ipo_id] = record
                continue
            merged = record.model_dump()
            for field, value in previous.model_dump().items():
                if merged[field] is None:
                    merged[field] = value
            unique_records[record.ipo_id] = IPORecord.model_validate(merged)
        records = list(unique_records.values())
        external_ids = [record.ipo_id for record in records]
        identity_result = await self.db.execute(
            select(AssetIdentifier).where(
                AssetIdentifier.provider == provider_name,
                AssetIdentifier.identifier_type == "ipo_id",
                AssetIdentifier.scope == "ipo",
                AssetIdentifier.external_id.in_(external_ids),
            )
        )
        identities = {row.external_id: row for row in identity_result.scalars()}
        existing_ids = {row.asset_id for row in identities.values()}
        assets_result = await self.db.execute(
            select(Asset).where(Asset.id.in_(existing_ids))
        ) if existing_ids else None
        assets = {
            asset.id: asset
            for asset in assets_result.scalars()
        } if assets_result is not None else {}
        ipo_result = await self.db.execute(
            select(IPO).where(IPO.asset_id.in_(existing_ids))
        ) if existing_ids else None
        ipos = {ipo.asset_id: ipo for ipo in ipo_result.scalars()} if ipo_result else {}

        new_assets: list[Asset] = []
        new_identities: list[AssetIdentifier] = []
        new_ipos: list[IPO] = []
        inserted = updated = skipped = 0
        for record in records:
            identity = identities.get(record.ipo_id)
            asset = assets.get(identity.asset_id) if identity else None
            is_new = asset is None
            if asset is None:
                asset = Asset(
                    id=uuid4(),
                    name=record.name,
                    symbol=record.symbol,
                    asset_type="ipo",
                    sector=record.industry,
                    is_active=True,
                )
                ipo = IPO(asset_id=asset.id, ipo_status=record.status)
                self._update_ipo(ipo, record)
                new_assets.append(asset)
                new_ipos.append(ipo)
            else:
                ipo = ipos.get(asset.id)
                if ipo is None:
                    ipo = IPO(asset_id=asset.id, ipo_status=record.status)
                    new_ipos.append(ipo)
                    ipos[asset.id] = ipo
                self._update_asset(asset, record)
                self._update_ipo(ipo, record)
            if identity is None:
                new_identities.append(
                    AssetIdentifier(
                        asset_id=asset.id,
                        provider=provider_name,
                        identifier_type="ipo_id",
                        scope="ipo",
                        external_id=record.ipo_id,
                    )
                )
            if is_new:
                inserted += 1
            else:
                updated += 1
        self.db.add_all([*new_assets, *new_identities, *new_ipos])
        await self.db.commit()
        return inserted, updated, skipped

    async def _upsert_prices(
        self,
        rows: list[dict],
        *,
        commit: bool = True,
    ) -> tuple[int, int]:
        if not rows:
            return 0, 0
        unique_rows = {}
        for row in rows:
            key = (
                row["asset_id"],
                row["provider"],
                row["observation_type"],
                row["interval"],
                row["price_timestamp"],
            )
            unique_rows[key] = row
        rows = list(unique_rows.values())
        key_columns = (
            AssetPrice.asset_id,
            AssetPrice.provider,
            AssetPrice.observation_type,
            AssetPrice.interval,
            AssetPrice.price_timestamp,
        )
        row_keys = [
            (
                row["asset_id"],
                row["provider"],
                row["observation_type"],
                row["interval"],
                row["price_timestamp"],
            )
            for row in rows
        ]
        existing_result = await self.db.execute(
            select(*key_columns).where(tuple_(*key_columns).in_(row_keys))
        )
        existing = set(existing_result.all())
        statement = pg_insert(AssetPrice).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[
                "asset_id",
                "provider",
                "observation_type",
                "interval",
                "price_timestamp",
            ],
            index_where=text("provider <> 'legacy'"),
            set_={
                "price": statement.excluded.price,
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
        await self.db.execute(statement)
        if commit:
            await self.db.commit()
        inserted = sum(1 for key in row_keys if key not in existing)
        return inserted, len(rows) - inserted

    async def _persist_navs(
        self,
        identifiers: list[tuple],
        fetched: list[tuple[FundScheme, NavObservation]],
    ) -> tuple[int, int, int]:
        asset_by_code = {code: asset_id for asset_id, code in identifiers}
        asset_ids = list(asset_by_code.values())
        funds_result = await self.db.execute(
            select(MutualFund).where(MutualFund.asset_id.in_(asset_ids))
        )
        funds = {fund.asset_id: fund for fund in funds_result.scalars()}
        prices_result = await self.db.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id.in_(asset_ids),
                AssetPrice.observation_type == "nav",
            )
            .order_by(AssetPrice.price_timestamp.desc())
        )
        latest_by_asset: dict = {}
        for price in prices_result.scalars():
            latest_by_asset.setdefault(price.asset_id, price)

        price_rows = []
        skipped = 0
        for scheme, observation in fetched:
            asset_id = asset_by_code.get(observation.scheme_code)
            fund = funds.get(asset_id)
            if asset_id is None or fund is None:
                skipped += 1
                continue
            timestamp = datetime.combine(
                observation.nav_date,
                time.min,
                tzinfo=self.MARKET_TIMEZONE,
            )
            latest = latest_by_asset.get(asset_id)
            if latest and latest.price_timestamp.astimezone(
                self.MARKET_TIMEZONE
            ).date() > observation.nav_date:
                skipped += 1
                continue
            self._update_fund(fund, scheme)
            fund.nav = observation.nav
            price_rows.append(
                self._price_values(
                    asset_id=asset_id,
                    provider="mfapi",
                    observation_type="nav",
                    interval="daily",
                    timestamp=timestamp,
                    price=observation.nav,
                    close=observation.nav,
                )
            )
        inserted, updated = await self._upsert_prices(price_rows, commit=False)
        await self.db.commit()
        return updated, inserted, skipped

    @staticmethod
    def _price_values(
        *,
        asset_id,
        provider: str,
        observation_type: str,
        interval: str,
        timestamp: datetime,
        price: Decimal,
        open_price: Decimal | None = None,
        high: Decimal | None = None,
        low: Decimal | None = None,
        close: Decimal | None = None,
        volume: int | None = None,
    ) -> dict:
        return {
            "id": uuid4(),
            "asset_id": asset_id,
            "provider": provider,
            "observation_type": observation_type,
            "interval": interval,
            "price": price,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "price_timestamp": timestamp,
            "fetched_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _update_asset(asset: Asset, source) -> None:
        mappings = {
            "name": getattr(source, "name", None),
            "symbol": getattr(source, "symbol", None),
            "exchange": getattr(source, "exchange", None),
            "sector": getattr(source, "sector", None)
            or getattr(source, "industry", None),
        }
        for field, value in mappings.items():
            if value is not None:
                setattr(asset, field, value)

    @staticmethod
    def _update_fund(fund: MutualFund, scheme: FundScheme) -> None:
        for field, value in (
            ("fund_house", scheme.fund_house),
            ("category", scheme.category),
        ):
            if value is not None:
                setattr(fund, field, value)

    @staticmethod
    def _update_ipo(ipo: IPO, record: IPORecord) -> None:
        ipo.ipo_status = record.status
        for field, value in (
            ("issue_price_low", record.issue_price_low),
            ("issue_price_high", record.issue_price_high),
            ("lot_size", record.lot_size),
            ("issue_size", record.issue_size),
            ("open_date", record.open_date),
            ("close_date", record.close_date),
            ("listing_date", record.listing_date),
        ):
            if value is not None:
                setattr(ipo, field, value)
        if record.source_attribution is not None:
            ipo.source_attribution = record.source_attribution
        if record.source_disclaimer is not None:
            ipo.source_disclaimer = record.source_disclaimer