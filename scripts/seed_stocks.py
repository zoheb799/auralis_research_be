import asyncio
import math
import random
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from decimal import Decimal

from sqlalchemy import delete, select

from app.db.models.asset import Asset
from app.db.models.asset_price import AssetPrice
from app.db.models.financial_metric import FinancialMetric
from app.db.models.stock import Stock
from app.db.session import AsyncSessionLocal


STOCKS = [
    {
        "name": "Reliance Industries",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "sector": "Energy",
        "price": 1450.0,
        "market_cap": 1960000,
        "pe_ratio": 24.2,
        "eps": 72.4,
        "dividend_yield": 0.35,
        "book_value": 1180.0,
        "debt_to_equity": 0.45,
        "roe": 18.6,
        "revenue": 950000,
        "profit": 79000,
        "revenue_growth": 10.5,
        "profit_growth": 18.0,
        "roce": 16.2,
        "volatility": 20,
        "trend": 0.0004,
    },
    {
        "name": "HDFC Bank",
        "symbol": "HDFCBANK",
        "exchange": "NSE",
        "sector": "Financial Services",
        "price": 1680.0,
        "market_cap": 1280000,
        "pe_ratio": 19.8,
        "eps": 84.8,
        "dividend_yield": 1.05,
        "book_value": 510.0,
        "debt_to_equity": 0.15,
        "roe": 16.8,
        "revenue": 310000,
        "profit": 70000,
        "revenue_growth": 14.0,
        "profit_growth": 16.5,
        "roce": 14.5,
        "volatility": 18,
        "trend": 0.0003,
    },
    {
        "name": "Tata Consultancy Services",
        "symbol": "TCS",
        "exchange": "NSE",
        "sector": "Information Technology",
        "price": 4200.0,
        "market_cap": 1520000,
        "pe_ratio": 31.5,
        "eps": 133.3,
        "dividend_yield": 1.25,
        "book_value": 410.0,
        "debt_to_equity": 0.08,
        "roe": 48.0,
        "revenue": 245000,
        "profit": 48000,
        "revenue_growth": 8.5,
        "profit_growth": 10.2,
        "roce": 52.0,
        "volatility": 17,
        "trend": 0.00025,
    },
    {
        "name": "Infosys",
        "symbol": "INFY",
        "exchange": "NSE",
        "sector": "Information Technology",
        "price": 1750.0,
        "market_cap": 720000,
        "pe_ratio": 27.5,
        "eps": 63.6,
        "dividend_yield": 2.1,
        "book_value": 290.0,
        "debt_to_equity": 0.05,
        "roe": 31.5,
        "revenue": 160000,
        "profit": 27000,
        "revenue_growth": 9.2,
        "profit_growth": 12.5,
        "roce": 35.0,
        "volatility": 19,
        "trend": 0.0002,
    },
    {
        "name": "ITC",
        "symbol": "ITC",
        "exchange": "NSE",
        "sector": "FMCG",
        "price": 520.0,
        "market_cap": 650000,
        "pe_ratio": 28.0,
        "eps": 18.6,
        "dividend_yield": 2.9,
        "book_value": 62.0,
        "debt_to_equity": 0.01,
        "roe": 29.0,
        "revenue": 72000,
        "profit": 21000,
        "revenue_growth": 6.5,
        "profit_growth": 8.0,
        "roce": 32.0,
        "volatility": 15,
        "trend": 0.00015,
    },
    {
        "name": "Larsen & Toubro",
        "symbol": "LT",
        "exchange": "NSE",
        "sector": "Infrastructure",
        "price": 3600.0,
        "market_cap": 495000,
        "pe_ratio": 32.0,
        "eps": 112.5,
        "dividend_yield": 0.75,
        "book_value": 680.0,
        "debt_to_equity": 1.05,
        "roe": 14.8,
        "revenue": 220000,
        "profit": 15000,
        "revenue_growth": 15.0,
        "profit_growth": 20.0,
        "roce": 13.5,
        "volatility": 24,
        "trend": 0.0005,
    },
    {
        "name": "Bharti Airtel",
        "symbol": "BHARTIARTL",
        "exchange": "NSE",
        "sector": "Telecommunication",
        "price": 1850.0,
        "market_cap": 1110000,
        "pe_ratio": 38.0,
        "eps": 48.7,
        "dividend_yield": 0.4,
        "book_value": 310.0,
        "debt_to_equity": 1.45,
        "roe": 12.5,
        "revenue": 150000,
        "profit": 9000,
        "revenue_growth": 12.0,
        "profit_growth": 15.0,
        "roce": 11.8,
        "volatility": 27,
        "trend": 0.00035,
    },
    {
        "name": "Wipro",
        "symbol": "WIPRO",
        "exchange": "NSE",
        "sector": "Information Technology",
        "price": 520.0,
        "market_cap": 272000,
        "pe_ratio": 22.5,
        "eps": 23.1,
        "dividend_yield": 1.8,
        "book_value": 215.0,
        "debt_to_equity": 0.18,
        "roe": 16.2,
        "revenue": 92000,
        "profit": 11500,
        "revenue_growth": 4.5,
        "profit_growth": 3.0,
        "roce": 18.0,
        "volatility": 23,
        "trend": 0.00005,
    },
    {
        "name": "Suzlon Energy",
        "symbol": "SUZLON",
        "exchange": "NSE",
        "sector": "Renewable Energy",
        "price": 72.0,
        "market_cap": 98000,
        "pe_ratio": 42.0,
        "eps": 1.7,
        "dividend_yield": 0.0,
        "book_value": 8.5,
        "debt_to_equity": 1.25,
        "roe": 11.5,
        "revenue": 62000,
        "profit": 3200,
        "revenue_growth": 18.0,
        "profit_growth": 25.0,
        "roce": 12.0,
        "volatility": 35,
        "trend": 0.0007,
    },
]


def decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 4)))


def generate_financial_metrics(
    stock: dict,
    asset_id,
) -> list[FinancialMetric]:
    """
    Generate three years of synthetic annual financial data.
    """

    current_revenue = stock["revenue"]
    current_profit = stock["profit"]

    revenue_growth = stock["revenue_growth"] / 100
    profit_growth = stock["profit_growth"] / 100

    metrics = []

    for years_ago in [2, 1, 0]:
        revenue = current_revenue / (
            (1 + revenue_growth) ** years_ago
        )

        profit = current_profit / (
            (1 + profit_growth) ** years_ago
        )

        operating_margin = (
            12
            + (stock["roe"] / 10)
        )

        operating_profit = revenue * (
            operating_margin / 100
        )

        debt = revenue * stock["debt_to_equity"] * 0.35
        cash = revenue * 0.12

        period_end = datetime(
            datetime.now().year - years_ago,
            3,
            31,
        ).date()

        metrics.append(
            FinancialMetric(
                asset_id=asset_id,
                period_type="annual",
                period_end=period_end,
                revenue=decimal(revenue),
                operating_profit=decimal(
                    operating_profit
                ),
                net_profit=decimal(profit),
                eps=decimal(stock["eps"]),
                total_debt=decimal(debt),
                cash=decimal(cash),
                roe=decimal(stock["roe"]),
                roce=decimal(stock["roce"]),
            )
        )

    return metrics


def generate_price_history(
    stock: dict,
    asset_id,
) -> list[AssetPrice]:
    """
    Generate approximately one year of synthetic
    daily price history.
    """

    random.seed(stock["symbol"])

    days = 365
    end_date = datetime.now(
        timezone.utc
    ).replace(
        hour=15,
        minute=30,
        second=0,
        microsecond=0,
    )

    start_price = stock["price"] * 0.85
    current_price = start_price

    prices = []

    daily_volatility = (
        stock["volatility"] / 100
    ) / math.sqrt(252)

    for day in range(days):
        timestamp = end_date - timedelta(
            days=days - day
        )

        # Skip weekends.
        if timestamp.weekday() >= 5:
            continue

        random_return = random.gauss(
            stock["trend"],
            daily_volatility,
        )

        current_price *= (
            1 + random_return
        )

        if current_price <= 0:
            current_price = stock["price"] * 0.5

        open_price = current_price * (
            1 + random.uniform(-0.01, 0.01)
        )

        high_price = max(
            open_price,
            current_price,
        ) * (
            1 + random.uniform(0, 0.015)
        )

        low_price = min(
            open_price,
            current_price,
        ) * (
            1 - random.uniform(0, 0.015)
        )

        volume = random.randint(
            100_000,
            10_000_000,
        )

        prices.append(
            AssetPrice(
                asset_id=asset_id,
                price=decimal(current_price),
                open=decimal(open_price),
                high=decimal(high_price),
                low=decimal(low_price),
                close=decimal(current_price),
                volume=volume,
                price_timestamp=timestamp,
            )
        )

    # Force the latest price close to our
    # configured demo price.
    if prices:
        latest = prices[-1]

        latest.price = decimal(
            stock["price"]
        )
        latest.close = decimal(
            stock["price"]
        )

    return prices


async def seed_stocks() -> None:
    async with AsyncSessionLocal() as db:
        print("Clearing existing seeded stock data...")

        asset_ids_result = await db.execute(
            select(Asset.id).where(
                Asset.asset_type == "stock"
            )
        )

        existing_asset_ids = (
            asset_ids_result.scalars().all()
        )

        if existing_asset_ids:
            await db.execute(
                delete(AssetPrice).where(
                    AssetPrice.asset_id.in_(
                        existing_asset_ids
                    )
                )
            )

            await db.execute(
                delete(FinancialMetric).where(
                    FinancialMetric.asset_id.in_(
                        existing_asset_ids
                    )
                )
            )

            await db.execute(
                delete(Stock).where(
                    Stock.asset_id.in_(
                        existing_asset_ids
                    )
                )
            )

            await db.execute(
                delete(Asset).where(
                    Asset.id.in_(
                        existing_asset_ids
                    )
                )
            )

            await db.commit()

        print("Seeding stocks...")

        for stock_data in STOCKS:
            asset = Asset(
                name=stock_data["name"],
                symbol=stock_data["symbol"],
                asset_type="stock",
                exchange=stock_data["exchange"],
                sector=stock_data["sector"],
                description=(
                    f"{stock_data['name']} "
                    "development dataset for Auralis."
                ),
                is_active=True,
            )

            db.add(asset)

            await db.flush()

            stock = Stock(
                asset_id=asset.id,
                market_cap=decimal(
                    stock_data["market_cap"]
                ),
                pe_ratio=decimal(
                    stock_data["pe_ratio"]
                ),
                eps=decimal(
                    stock_data["eps"]
                ),
                dividend_yield=decimal(
                    stock_data["dividend_yield"]
                ),
                book_value=decimal(
                    stock_data["book_value"]
                ),
                debt_to_equity=decimal(
                    stock_data["debt_to_equity"]
                ),
                roe=decimal(
                    stock_data["roe"]
                ),
            )

            db.add(stock)

            metrics = generate_financial_metrics(
                stock_data,
                asset.id,
            )

            db.add_all(metrics)

            prices = generate_price_history(
                stock_data,
                asset.id,
            )

            db.add_all(prices)

            print(
                f"  ✓ {stock_data['symbol']}"
            )

        await db.commit()

        print()
        print(
            f"Seeded {len(STOCKS)} stocks successfully."
        )


if __name__ == "__main__":
    asyncio.run(seed_stocks())