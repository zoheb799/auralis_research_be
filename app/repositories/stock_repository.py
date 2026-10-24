from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.asset_price import AssetPrice
from app.db.models.financial_metric import FinancialMetric
from app.db.models.stock import Stock


class StockRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_stocks(
        self,
        search: str | None = None,
        sort: str = "name",
        order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:

        # ---------------------------------------------------------
        # Latest + previous price for every stock.
        #
        # row_number = 1 → latest
        # row_number = 2 → previous trading price
        # ---------------------------------------------------------

        price_rank = func.row_number().over(
            partition_by=AssetPrice.asset_id,
            order_by=(
                AssetPrice.price_timestamp.desc(),
                case((AssetPrice.observation_type == "eod", 0), else_=1),
            ),
        ).label("price_rank")

        ranked_prices = (
            select(
                AssetPrice.asset_id.label("asset_id"),
                AssetPrice.price.label("price"),
                AssetPrice.close.label("close"),
                AssetPrice.observation_type.label("observation_type"),
                AssetPrice.interval.label("interval"),
                price_rank,
            )
            .subquery()
        )

        latest_price = (
            select(
                ranked_prices.c.asset_id,
                ranked_prices.c.price,
                ranked_prices.c.close,
                ranked_prices.c.observation_type,
                ranked_prices.c.interval,
            )
            .where(ranked_prices.c.price_rank == 1)
            .subquery()
        )

        previous_price = (
            select(
                ranked_prices.c.asset_id,
                ranked_prices.c.price,
                ranked_prices.c.close,
                ranked_prices.c.observation_type,
                ranked_prices.c.interval,
            )
            .where(ranked_prices.c.price_rank == 2)
            .subquery()
        )

        current_price = func.coalesce(
            latest_price.c.close,
            latest_price.c.price,
        )

        previous_price_value = func.coalesce(
            previous_price.c.close,
            previous_price.c.price,
        )

        change_percent = (
            (
                (current_price - previous_price_value)
                / func.nullif(previous_price_value, 0)
            )
            * 100
        ).label("change_percent")

        # ---------------------------------------------------------
        # Main query
        # ---------------------------------------------------------

        query = (
            select(
                Asset,
                Stock,
                current_price.label("current_price"),
                change_percent,
                latest_price.c.observation_type.label("price_data_type"),
                latest_price.c.interval.label("price_interval"),
            )
            .join(
                Stock,
                Stock.asset_id == Asset.id,
            )
            .outerjoin(
                latest_price,
                latest_price.c.asset_id == Asset.id,
            )
            .outerjoin(
                previous_price,
                previous_price.c.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
            )
        )

        # ---------------------------------------------------------
        # Search
        # ---------------------------------------------------------

        if search:
            search_value = f"%{search.strip()}%"

            query = query.where(
                (Asset.name.ilike(search_value))
                | (Asset.symbol.ilike(search_value))
            )

        # ---------------------------------------------------------
        # Sorting
        # ---------------------------------------------------------

        if sort == "price":
            sort_column = current_price
        elif sort == "symbol":
            sort_column = Asset.symbol
        else:
            sort_column = Asset.name

        if order == "desc":
            query = query.order_by(
                sort_column.desc().nullslast()
            )
        else:
            query = query.order_by(
                sort_column.asc().nullsfirst()
            )

        # ---------------------------------------------------------
        # Total count
        # ---------------------------------------------------------

        count_query = (
            select(func.count())
            .select_from(Asset)
            .join(
                Stock,
                Stock.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
            )
        )

        if search:
            search_value = f"%{search.strip()}%"

            count_query = count_query.where(
                (Asset.name.ilike(search_value))
                | (Asset.symbol.ilike(search_value))
            )

        count_result = await self.db.execute(count_query)

        total = count_result.scalar_one()

        # ---------------------------------------------------------
        # Pagination
        # ---------------------------------------------------------

        offset = (page - 1) * page_size

        query = (
            query
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(query)

        rows = result.all()

        items = []

        for asset, stock, price, change, price_data_type, price_interval in rows:
            items.append(
                {
                    "id": asset.id,
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "exchange": asset.exchange,
                    "sector": asset.sector,
                    "price": (
                        float(price)
                        if price is not None
                        else None
                    ),
                    "change_percent": (
                        round(float(change), 2)
                        if change is not None
                        else None
                    ),
                    "price_data_type": price_data_type,
                    "price_interval": price_interval,
                }
            )

        return items, total

    async def get_stock_detail(
        self,
        asset_id: UUID,
    ) -> dict[str, Any] | None:

        # ---------------------------------------------------------
        # Stock + Asset
        # ---------------------------------------------------------

        stock_result = await self.db.execute(
            select(Stock, Asset)
            .join(
                Asset,
                Stock.asset_id == Asset.id,
            )
            .where(
                Stock.asset_id == asset_id,
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
            )
        )

        row = stock_result.first()

        if row is None:
            return None

        stock, asset = row

        # ---------------------------------------------------------
        # Price history
        # ---------------------------------------------------------

        prices_result = await self.db.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
            )
            .order_by(
                AssetPrice.price_timestamp.desc(),
                case((AssetPrice.observation_type == "eod", 0), else_=1),
            )
            .limit(365)
        )

        prices = prices_result.scalars().all()

        current_price = None
        change_percent = None

        if prices:

            current = prices[0]

            current_price = (
                current.close
                if current.close is not None
                else current.price
            )

        if len(prices) >= 2:

            previous = prices[1]

            previous_price = (
                previous.close
                if previous.close is not None
                else previous.price
            )

            if (
                current_price is not None
                and previous_price is not None
                and previous_price != 0
            ):
                change_percent = (
                    (
                        float(current_price)
                        - float(previous_price)
                    )
                    / float(previous_price)
                ) * 100

        # ---------------------------------------------------------
        # Financial history
        # ---------------------------------------------------------

        metrics_result = await self.db.execute(
            select(FinancialMetric)
            .where(
                FinancialMetric.asset_id == asset_id,
            )
            .order_by(
                FinancialMetric.period_end.desc(),
            )
        )

        metrics = metrics_result.scalars().all()

        return {
            "asset": asset,
            "stock": stock,
            "prices": prices,
            "metrics": metrics,
            "current_price": (
                float(current_price)
                if current_price is not None
                else None
            ),
            "change_percent": (
                round(change_percent, 2)
                if change_percent is not None
                else None
            ),
        }

    async def get_stock_analysis_data(
        self,
        asset_id: UUID,
    ) -> dict[str, Any] | None:

        stock_result = await self.db.execute(
            select(Stock, Asset)
            .join(
                Asset,
                Stock.asset_id == Asset.id,
            )
            .where(
                Stock.asset_id == asset_id,
                Asset.asset_type == "stock",
                Asset.is_active.is_(True),
            )
        )

        row = stock_result.first()

        if row is None:
            return None

        stock, asset = row

        metrics_result = await self.db.execute(
            select(FinancialMetric)
            .where(
                FinancialMetric.asset_id == asset_id,
            )
            .order_by(
                FinancialMetric.period_end.desc(),
            )
            .limit(10)
        )

        metrics = metrics_result.scalars().all()

        prices_result = await self.db.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
            )
            .order_by(
                AssetPrice.price_timestamp.desc(),
            )
            .limit(365)
        )

        prices = prices_result.scalars().all()

        latest_metric = metrics[0] if metrics else None
        previous_metric = metrics[1] if len(metrics) > 1 else None

        latest_price = prices[0] if prices else None

        return {
            "asset": asset,
            "stock": stock,
            "latest_metric": latest_metric,
            "previous_metric": previous_metric,
            "metrics": metrics,
            "latest_price": latest_price,
            "prices": prices,
        }