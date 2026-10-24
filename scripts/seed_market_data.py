import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, text

from app.db.models.asset import Asset
from app.db.models.ipo import IPO
from app.db.models.mutual_fund import MutualFund
from app.db.models.stock import Stock
from app.db.models.asset_price import AssetPrice
from app.db.models.financial_metric import FinancialMetric
from app.db.session import AsyncSessionLocal


IPO_DATA = [
    {
        "name": "Astra Tech",
        "symbol": "ASTRTECH",
        "exchange": "NSE",
        "sector": "Technology",
        "description": "Astra Tech is a digital infrastructure company focused on enterprise cloud and network services.",
        "issue_price_low": 220.0,
        "issue_price_high": 240.0,
        "lot_size": 50,
        "issue_size": 1500.0,
        "fresh_issue_size": 900.0,
        "ofs_size": 600.0,
        "open_date": date(2026, 9, 10),
        "close_date": date(2026, 9, 12),
        "listing_date": date(2026, 9, 17),
        "ipo_status": "upcoming",
    },
    {
        "name": "BluePeak Infra",
        "symbol": "BLUEPEAK",
        "exchange": "BSE",
        "sector": "Infrastructure",
        "description": "BluePeak Infra develops urban transport and logistics network assets.",
        "issue_price_low": 320.0,
        "issue_price_high": 350.0,
        "lot_size": 40,
        "issue_size": 1800.0,
        "fresh_issue_size": 1100.0,
        "ofs_size": 700.0,
        "open_date": date(2026, 8, 20),
        "close_date": date(2026, 8, 22),
        "listing_date": date(2026, 8, 27),
        "ipo_status": "open",
    },
    {
        "name": "Crest BioLabs",
        "symbol": "CRESTBIO",
        "exchange": "NSE",
        "sector": "Healthcare",
        "description": "Crest BioLabs is a biopharma and diagnostics firm with a strong clinical pipeline.",
        "issue_price_low": 410.0,
        "issue_price_high": 440.0,
        "lot_size": 25,
        "issue_size": 2100.0,
        "fresh_issue_size": 1400.0,
        "ofs_size": 700.0,
        "open_date": date(2026, 7, 5),
        "close_date": date(2026, 7, 8),
        "listing_date": date(2026, 7, 14),
        "ipo_status": "listed",
    },
]

MUTUAL_FUND_DATA = [
    {
        "name": "Aurum Equity Growth Fund",
        "symbol": "AURUMEQ",
        "exchange": "NSE",
        "sector": "Equity",
        "description": "Growth-oriented large-cap mutual fund with a quality-stock selection mandate.",
        "fund_house": "Aurum Asset Management",
        "category": "Large Cap",
        "nav": 58.42,
        "aum": 2450000000.0,
        "expense_ratio": 0.72,
        "risk_level": "Moderate",
    },
    {
        "name": "Nimbus Index Tracker",
        "symbol": "NIMBINDEX",
        "exchange": "BSE",
        "sector": "Index",
        "description": "Passive index fund tracking the benchmark with low-cost market exposure.",
        "fund_house": "Nimbus Capital",
        "category": "Index",
        "nav": 33.18,
        "aum": 1850000000.0,
        "expense_ratio": 0.2,
        "risk_level": "Moderate",
    },
    {
        "name": "Solstice Flexi Cap",
        "symbol": "SOLFLEX",
        "exchange": "NSE",
        "sector": "Equity",
        "description": "Flexi-cap strategy focused on balanced exposure across large, mid, and small caps.",
        "fund_house": "Solstice Ventures",
        "category": "Flexi Cap",
        "nav": 74.6,
        "aum": 4200000000.0,
        "expense_ratio": 0.95,
        "risk_level": "High",
    },
]


def decimal(value):
    return Decimal(str(value))


async def clear_asset_type(db, asset_type: str) -> None:
    asset_ids_result = await db.execute(
        select(Asset.id).where(Asset.asset_type == asset_type)
    )
    asset_ids = asset_ids_result.scalars().all()

    if not asset_ids:
        return

    if asset_type == "stock":
        await db.execute(
            delete(AssetPrice).where(AssetPrice.asset_id.in_(asset_ids))
        )
        await db.execute(
            delete(FinancialMetric).where(FinancialMetric.asset_id.in_(asset_ids))
        )
        await db.execute(delete(Stock).where(Stock.asset_id.in_(asset_ids)))

    elif asset_type == "ipo":
        await db.execute(delete(IPO).where(IPO.asset_id.in_(asset_ids)))

    elif asset_type == "mutual_fund":
        await db.execute(
            delete(MutualFund).where(MutualFund.asset_id.in_(asset_ids))
        )

    await db.execute(delete(Asset).where(Asset.id.in_(asset_ids)))


async def seed_ipos(db) -> None:
    for item in IPO_DATA:
        asset = Asset(
            name=item["name"],
            symbol=item["symbol"],
            asset_type="ipo",
            exchange=item["exchange"],
            sector=item["sector"],
            description=item["description"],
            is_active=True,
        )
        db.add(asset)
        await db.flush()

        db.add(
            IPO(
                asset_id=asset.id,
                issue_price_low=decimal(item["issue_price_low"]),
                issue_price_high=decimal(item["issue_price_high"]),
                lot_size=item["lot_size"],
                issue_size=decimal(item["issue_size"]),
                open_date=item["open_date"],
                close_date=item["close_date"],
                listing_date=item["listing_date"],
                ipo_status=item["ipo_status"],
            )
        )


async def seed_mutual_funds(db) -> None:
    for item in MUTUAL_FUND_DATA:
        asset = Asset(
            name=item["name"],
            symbol=item["symbol"],
            asset_type="mutual_fund",
            exchange=item["exchange"],
            sector=item["sector"],
            description=item["description"],
            is_active=True,
        )
        db.add(asset)
        await db.flush()

        db.add(
            MutualFund(
                asset_id=asset.id,
                fund_house=item["fund_house"],
                category=item["category"],
                nav=decimal(item["nav"]),
                aum=decimal(item["aum"]),
                expense_ratio=decimal(item["expense_ratio"]),
                risk_level=item["risk_level"],
            )
        )


async def ensure_ipo_table(db) -> None:
    exists = await db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'ipos'
            )
            """
        )
    )
    if not exists.scalar():
        await db.execute(
            text(
                """
                CREATE TABLE ipos (
                    asset_id UUID PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
                    issue_price_low NUMERIC(12, 2),
                    issue_price_high NUMERIC(12, 2),
                    lot_size INTEGER,
                    issue_size NUMERIC(20, 2),
                    open_date DATE,
                    close_date DATE,
                    listing_date DATE,
                    ipo_status VARCHAR(30) NOT NULL DEFAULT 'upcoming',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )


async def seed_market_data() -> None:
    try:
        from scripts.seed_stocks import seed_stocks
    except ImportError:
        seed_stocks = None

    if seed_stocks is not None:
        await seed_stocks()

    async with AsyncSessionLocal() as db:
        await ensure_ipo_table(db)
        await clear_asset_type(db, "ipo")
        await clear_asset_type(db, "mutual_fund")

        await seed_ipos(db)
        await seed_mutual_funds(db)

        await db.commit()
        print("Seeded IPO and mutual fund market data.")


if __name__ == "__main__":
    asyncio.run(seed_market_data())
