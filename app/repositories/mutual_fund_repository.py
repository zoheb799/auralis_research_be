from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.mutual_fund import MutualFund


class MutualFundRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_mutual_fund_detail(
        self,
        asset_id,
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            select(Asset, MutualFund)
            .join(
                MutualFund,
                MutualFund.asset_id == Asset.id,
            )
            .where(
                MutualFund.asset_id == asset_id,
                Asset.asset_type == "mutual_fund",
                Asset.is_active.is_(True),
            )
        )

        row = result.first()
        if row is None:
            return None

        asset, fund = row
        return {
            "asset": asset,
            "fund": fund,
        }

    async def get_mutual_fund_analysis_data(
        self,
        asset_id,
    ) -> dict[str, Any] | None:
        row = await self.get_mutual_fund_detail(asset_id)
        if row is None:
            return None

        asset, fund = row["asset"], row["fund"]

        return {
            "asset": asset,
            "fund": fund,
            "return_1y": None,
            "return_3y": None,
            "return_5y": None,
            "benchmark_return_1y": None,
            "expense_ratio": (
                float(fund.expense_ratio)
                if fund.expense_ratio is not None
                else None
            ),
            "volatility": None,
            "sharpe_ratio": None,
            "top_10_percentage": None,
            "positive_periods": None,
            "total_periods": None,
        }

    async def list_mutual_funds(
        self,
        search: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:

        query = (
            select(Asset, MutualFund)
            .join(
                MutualFund,
                MutualFund.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "mutual_fund",
                Asset.is_active.is_(True),
            )
        )

        count_query = (
            select(func.count())
            .select_from(Asset)
            .join(
                MutualFund,
                MutualFund.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "mutual_fund",
                Asset.is_active.is_(True),
            )
        )

        if search:
            value = f"%{search.strip()}%"

            condition = (
                (Asset.name.ilike(value))
                | (Asset.symbol.ilike(value))
                | (MutualFund.fund_house.ilike(value))
            )

            query = query.where(condition)
            count_query = count_query.where(condition)

        if category:
            query = query.where(
                MutualFund.category == category
            )
            count_query = count_query.where(
                MutualFund.category == category
            )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(
            query
            .order_by(Asset.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        items = []

        for asset, fund in result.all():
            items.append(
                {
                    "id": asset.id,
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "fund_house": fund.fund_house,
                    "category": fund.category,
                    "nav": (
                        float(fund.nav)
                        if fund.nav is not None
                        else None
                    ),
                    "aum": (
                        float(fund.aum)
                        if fund.aum is not None
                        else None
                    ),
                    "expense_ratio": (
                        float(fund.expense_ratio)
                        if fund.expense_ratio is not None
                        else None
                    ),
                    "risk_level": fund.risk_level,
                }
            )

        return items, total