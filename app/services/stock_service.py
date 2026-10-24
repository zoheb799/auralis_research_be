from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.stock_repository import StockRepository
from app.schemas.stock import (
    FinancialHistoryItem,
    PriceHistoryItem,
    StockDetailResponse,
    StockFundamentals,
    StockListItem,
    StockListResponse,
)


async def list_stocks(
    db: AsyncSession,
    search: str | None = None,
    sort: str = "name",
    order: str = "asc",
    page: int = 1,
    page_size: int = 20,
) -> StockListResponse:

    repository = StockRepository(db)

    items, total = await repository.list_stocks(
        search=search,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )

    return StockListResponse(
        items=[
            StockListItem(**item)
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_stock_detail(
    db: AsyncSession,
    asset_id: UUID,
) -> StockDetailResponse | None:

    repository = StockRepository(db)

    data = await repository.get_stock_detail(
        asset_id=asset_id,
    )

    if data is None:
        return None

    asset = data["asset"]
    stock = data["stock"]

    fundamentals = StockFundamentals(
        market_cap=(
            float(stock.market_cap)
            if stock.market_cap is not None
            else None
        ),
        pe_ratio=(
            float(stock.pe_ratio)
            if stock.pe_ratio is not None
            else None
        ),
        eps=(
            float(stock.eps)
            if stock.eps is not None
            else None
        ),
        dividend_yield=(
            float(stock.dividend_yield)
            if stock.dividend_yield is not None
            else None
        ),
        book_value=(
            float(stock.book_value)
            if stock.book_value is not None
            else None
        ),
        debt_to_equity=(
            float(stock.debt_to_equity)
            if stock.debt_to_equity is not None
            else None
        ),
        roe=(
            float(stock.roe)
            if stock.roe is not None
            else None
        ),
    )

    financial_history = [
        FinancialHistoryItem(
            period_type=metric.period_type,
            period_end=metric.period_end,
            revenue=(
                float(metric.revenue)
                if metric.revenue is not None
                else None
            ),
            operating_profit=(
                float(metric.operating_profit)
                if metric.operating_profit is not None
                else None
            ),
            net_profit=(
                float(metric.net_profit)
                if metric.net_profit is not None
                else None
            ),
            eps=(
                float(metric.eps)
                if metric.eps is not None
                else None
            ),
        )
        for metric in data["metrics"]
    ]

    price_history = [
        PriceHistoryItem(
            price=float(
                price.close
                if price.close is not None
                else price.price
            ),
            open=(
                float(price.open)
                if price.open is not None
                else None
            ),
            high=(
                float(price.high)
                if price.high is not None
                else None
            ),
            low=(
                float(price.low)
                if price.low is not None
                else None
            ),
            close=(
                float(price.close)
                if price.close is not None
                else None
            ),
            volume=price.volume,
            price_timestamp=price.price_timestamp,
            data_type=price.observation_type,
            interval=price.interval,
        )
        for price in data["prices"]
    ]

    return StockDetailResponse(
        id=asset.id,
        name=asset.name,
        symbol=asset.symbol,
        exchange=asset.exchange,
        sector=asset.sector,
        price=data["current_price"],
        change_percent=data["change_percent"],
        price_data_type=(
            data["prices"][0].observation_type
            if data["prices"]
            else None
        ),
        price_interval=(
            data["prices"][0].interval
            if data["prices"]
            else None
        ),
        fundamentals=fundamentals,
        financial_history=financial_history,
        price_history=price_history,
    )