from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.db.models.ipo import IPO


class IPORepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ipo_detail(
        self,
        asset_id,
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            select(Asset, IPO)
            .join(
                IPO,
                IPO.asset_id == Asset.id,
            )
            .where(
                IPO.asset_id == asset_id,
                Asset.asset_type == "ipo",
                Asset.is_active.is_(True),
            )
        )

        row = result.first()
        if row is None:
            return None

        asset, ipo = row
        return {
            "asset": asset,
            "ipo": ipo,
        }

    async def get_ipo_analysis_data(
        self,
        asset_id,
    ) -> dict[str, Any] | None:
        row = await self.get_ipo_detail(asset_id)
        if row is None:
            return None

        asset, ipo = row["asset"], row["ipo"]

        return {
            "asset": asset,
            "ipo": ipo,
            "current_revenue": None,
            "previous_revenue": None,
            "current_profit": None,
            "previous_profit": None,
            "roe": None,
            "roce": None,
            "operating_margin": None,
            "net_margin": None,
            "pe_ratio": None,
            "debt_to_equity": None,
            "issue_price_low": (
                float(ipo.issue_price_low)
                if ipo.issue_price_low is not None
                else None
            ),
            "issue_price_high": (
                float(ipo.issue_price_high)
                if ipo.issue_price_high is not None
                else None
            ),
            "lot_size": ipo.lot_size,
            "issue_size": (
                float(ipo.issue_size)
                if ipo.issue_size is not None
                else None
            ),
            "fresh_issue_size": None,
            "ofs_size": None,
        }

    async def list_ipos(
        self,
        search: str | None = None,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:

        query = (
            select(Asset, IPO)
            .join(
                IPO,
                IPO.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "ipo",
                Asset.is_active.is_(True),
            )
        )

        count_query = (
            select(func.count())
            .select_from(Asset)
            .join(
                IPO,
                IPO.asset_id == Asset.id,
            )
            .where(
                Asset.asset_type == "ipo",
                Asset.is_active.is_(True),
            )
        )

        if search:
            value = f"%{search.strip()}%"

            condition = (
                (Asset.name.ilike(value))
                | (Asset.symbol.ilike(value))
                | (Asset.description.ilike(value))
            )

            query = query.where(condition)
            count_query = count_query.where(condition)

        if status_filter:
            normalized_status = status_filter.strip()
            query = query.where(IPO.ipo_status == normalized_status)
            count_query = count_query.where(IPO.ipo_status == normalized_status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(
            query
            .order_by(Asset.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        items = []

        for asset, ipo in result.all():
            items.append(
                {
                    "id": asset.id,
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "issue_price_low": (
                        float(ipo.issue_price_low)
                        if ipo.issue_price_low is not None
                        else None
                    ),
                    "issue_price_high": (
                        float(ipo.issue_price_high)
                        if ipo.issue_price_high is not None
                        else None
                    ),
                    "issue_size": (
                        float(ipo.issue_size)
                        if ipo.issue_size is not None
                        else None
                    ),
                    "open_date": (
                        ipo.open_date.isoformat()
                        if ipo.open_date is not None
                        else None
                    ),
                    "close_date": (
                        ipo.close_date.isoformat()
                        if ipo.close_date is not None
                        else None
                    ),
                    "listing_date": (
                        ipo.listing_date.isoformat()
                        if ipo.listing_date is not None
                        else None
                    ),
                    "ipo_status": ipo.ipo_status,
                    "source_attribution": ipo.source_attribution,
                    "source_disclaimer": ipo.source_disclaimer,
                }
            )

        return items, total