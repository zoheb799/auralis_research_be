import asyncio

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.db.models.asset import Asset
from app.db.models.asset_price import AssetPrice


async def main() -> None:
    async with AsyncSessionLocal() as db:
        statement = (
            select(
                Asset.name,
                Asset.symbol,
                Asset.asset_type,
                func.count(AssetPrice.id).label("price_count"),
            )
            .outerjoin(
                AssetPrice,
                AssetPrice.asset_id == Asset.id,
            )
            .where(Asset.is_active.is_(True))
            .group_by(
                Asset.id,
                Asset.name,
                Asset.symbol,
                Asset.asset_type,
            )
            .order_by(Asset.name)
        )

        result = await db.execute(statement)

        for row in result.all():
            print(
                f"Name: {row.name} | "
                f"Symbol: {row.symbol} | "
                f"Type: {row.asset_type} | "
                f"Historical prices: {row.price_count}"
            )


if __name__ == "__main__":
    asyncio.run(main())