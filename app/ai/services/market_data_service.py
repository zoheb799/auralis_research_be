from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas.market_data import MarketAssetData
from app.db.models.asset import Asset
from app.db.models.asset_price import AssetPrice
from app.db.models.ipo import IPO
from app.db.models.mutual_fund import MutualFund
from app.db.models.stock import Stock


class MarketDataService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_asset(
        self,
        asset_id: UUID,
    ) -> MarketAssetData | None:

        asset_result = await self.db.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.is_active.is_(True),
            )
        )

        asset = asset_result.scalar_one_or_none()

        if asset is None:
            return None

        return await self._build_market_data(asset)



    async def search_assets(
        self,
        *,
        query: str | None = None,
        asset_type: str | None = None,
        limit: int = 20,
    ) -> list[MarketAssetData]:
        statement = select(Asset).where(
            Asset.is_active.is_(True)
        )

        if asset_type:
            statement = statement.where(
                Asset.asset_type == asset_type
            )

        search_term = (query or "").strip()

        if search_term:
            exact_term = search_term.lower()
            contains_term = f"%{search_term}%"
            prefix_term = f"{search_term}%"

            statement = statement.where(
                Asset.name.ilike(contains_term)
                | Asset.symbol.ilike(contains_term)
            )

            statement = statement.order_by(
                case(
                    (Asset.symbol.ilike(exact_term), 0),
                    (Asset.name.ilike(exact_term), 1),
                    (Asset.symbol.ilike(prefix_term), 2),
                    (Asset.name.ilike(prefix_term), 3),
                    else_=4,
                ),
                Asset.name.asc(),
                Asset.symbol.asc(),
            )
        else:
            statement = statement.order_by(
                Asset.name.asc(),
                Asset.symbol.asc(),
            )

        statement = statement.limit(max(1, min(limit, 100)))

        result = await self.db.execute(statement)
        assets = result.scalars().all()

        market_data: list[MarketAssetData] = []

        for asset in assets:
            data = await self._build_market_data(asset)
            market_data.append(data)

        return market_data

    async def _build_market_data(
        self,
        asset: Asset,
    ) -> MarketAssetData:

        price_result = await self.db.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset.id
            )
            .order_by(
                AssetPrice.price_timestamp.desc()
            )
            .limit(1)
        )

        latest_price = price_result.scalar_one_or_none()

        stock_result = await self.db.execute(
            select(Stock).where(
                Stock.asset_id == asset.id
            )
        )

        stock = stock_result.scalar_one_or_none()

        ipo_result = await self.db.execute(
            select(IPO).where(
                IPO.asset_id == asset.id
            )
        )

        ipo = ipo_result.scalar_one_or_none()

        mutual_fund_result = await self.db.execute(
            select(MutualFund).where(
                MutualFund.asset_id == asset.id
            )
        )

        mutual_fund = mutual_fund_result.scalar_one_or_none()

        return MarketAssetData(
            asset_id=asset.id,
            name=asset.name,
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            exchange=asset.exchange,
            sector=asset.sector,

            current_price=(
                latest_price.price
                if latest_price
                else None
            ),

            price_timestamp=(
                latest_price.price_timestamp
                if latest_price
                else None
            ),
            price_observation_type=(
                latest_price.observation_type
                if latest_price
                else None
            ),
            price_interval=(
                latest_price.interval
                if latest_price
                else None
            ),

            market_cap=(
                stock.market_cap
                if stock
                else None
            ),
            pe_ratio=(
                stock.pe_ratio
                if stock
                else None
            ),
            eps=(
                stock.eps
                if stock
                else None
            ),
            dividend_yield=(
                stock.dividend_yield
                if stock
                else None
            ),
            book_value=(
                stock.book_value
                if stock
                else None
            ),
            debt_to_equity=(
                stock.debt_to_equity
                if stock
                else None
            ),
            roe=(
                stock.roe
                if stock
                else None
            ),

            nav=(
                mutual_fund.nav
                if mutual_fund
                else None
            ),
            aum=(
                mutual_fund.aum
                if mutual_fund
                else None
            ),
            expense_ratio=(
                mutual_fund.expense_ratio
                if mutual_fund
                else None
            ),
            risk_level=(
                mutual_fund.risk_level
                if mutual_fund
                else None
            ),

            issue_price_low=(
                ipo.issue_price_low
                if ipo
                else None
            ),
            issue_price_high=(
                ipo.issue_price_high
                if ipo
                else None
            ),
            lot_size=(
                ipo.lot_size
                if ipo
                else None
            ),
            issue_size=(
                ipo.issue_size
                if ipo
                else None
            ),
            ipo_status=(
                ipo.ipo_status
                if ipo
                else None
            ),
        )