from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.financial_metrics import (
    calculate_financial_growth,
    calculate_margin,
    calculate_return,
    calculate_annualized_volatility,
)
from app.analysis.ipo_analysis import analyze_ipo
from app.analysis.mutual_fund_analysis import analyze_mutual_fund
from app.analysis.stock_analysis import analyze_stock
from app.repositories.ipo_repository import IPORepository
from app.repositories.mutual_fund_repository import MutualFundRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.analysis import (
    IPOAnalysisResponse,
    MutualFundAnalysisResponse,
    StockAnalysisResponse,
)


def analyze_stock_data(
    data: dict[str, Any],
) -> StockAnalysisResponse:
    """
    Analyze structured stock data and return
    a validated response.
    """

    result = analyze_stock(**data)

    return StockAnalysisResponse.model_validate(result)

async def get_stock_analysis(
    db: AsyncSession,
    asset_id: UUID,
) -> StockAnalysisResponse | None:
    """
    Fetch stock data from PostgreSQL and run
    the deterministic stock analysis engine.
    """

    repository = StockRepository(db)

    data = await repository.get_stock_analysis_data(
        asset_id
    )

    if data is None:
        return None

    stock = data["stock"]
    metrics = data["metrics"]
    prices = data["prices"]

    latest_metric = data["latest_metric"]
    previous_metric = data["previous_metric"]

    # -------------------------
    # Financial growth
    # -------------------------

    growth = calculate_financial_growth(
        current_revenue=(
            latest_metric.revenue
            if latest_metric
            else None
        ),
        previous_revenue=(
            previous_metric.revenue
            if previous_metric
            else None
        ),
        current_profit=(
            latest_metric.net_profit
            if latest_metric
            else None
        ),
        previous_profit=(
            previous_metric.net_profit
            if previous_metric
            else None
        ),
    )

    revenue_growth = growth["revenue_growth"]
    profit_growth = growth["profit_growth"]

    # -------------------------
    # Historical profit growth
    # -------------------------

    profit_growth_history: list[float] = []

    for index in range(len(metrics) - 1):
        current = metrics[index]
        previous = metrics[index + 1]

        history_growth = calculate_financial_growth(
            current_revenue=None,
            previous_revenue=None,
            current_profit=current.net_profit,
            previous_profit=previous.net_profit,
        )

        historical_profit_growth = history_growth[
            "profit_growth"
        ]

        if historical_profit_growth is not None:
            profit_growth_history.append(
                historical_profit_growth
            )

    # -------------------------
    # Profitability calculations
    # -------------------------

    operating_margin = None
    net_margin = None

    if latest_metric:
        operating_margin = calculate_margin(
            profit=latest_metric.operating_profit,
            revenue=latest_metric.revenue,
        )

        net_margin = calculate_margin(
            profit=latest_metric.net_profit,
            revenue=latest_metric.revenue,
        )

    # -------------------------
    # Market calculations
    # -------------------------

    return_1y = None
    volatility = None

    if prices:
        latest_price = prices[0]

        current_price = (
            latest_price.close
            if latest_price.close is not None
            else latest_price.price
        )

        # Find the price closest to one year ago.
        one_year_old_price = None

        if current_price is not None:
            latest_timestamp = (
                latest_price.price_timestamp
            )

            for price in prices[1:]:
                days_difference = (
                    latest_timestamp
                    - price.price_timestamp
                ).days

                if days_difference >= 365:
                    one_year_old_price = price
                    break

        if (
            one_year_old_price is not None
            and current_price is not None
        ):
            previous_price = (
                one_year_old_price.close
                if one_year_old_price.close is not None
                else one_year_old_price.price
            )

            return_1y = calculate_return(
                current_price=float(current_price),
                previous_price=(
                    float(previous_price)
                    if previous_price is not None
                    else None
                ),
            )

        # -------------------------
        # Volatility
        # -------------------------

        closing_prices = [
            float(
                price.close
                if price.close is not None
                else price.price
            )
            for price in reversed(prices)
            if (
                price.close is not None
                or price.price is not None
            )
        ]

        volatility = calculate_annualized_volatility(
            closing_prices
        )

    # -------------------------
    # Run analysis engine
    # -------------------------

    result = analyze_stock(
        revenue_growth=revenue_growth,
        profit_growth=profit_growth,
        roe=stock.roe,
        roce=(
            latest_metric.roce
            if latest_metric
            else None
        ),
        operating_margin=operating_margin,
        net_margin=net_margin,
        pe_ratio=stock.pe_ratio,
        debt_to_equity=stock.debt_to_equity,
        return_1y=return_1y,
        volatility=volatility,
        profit_growth_history=profit_growth_history,
    )

    # -------------------------
    # Validate API response
    # -------------------------

    return StockAnalysisResponse.model_validate(
        result
    )

def analyze_ipo_data(
    data: dict[str, Any],
) -> IPOAnalysisResponse:
    """
    Analyze structured IPO data and return
    a validated response.
    """

    result = analyze_ipo(**data)

    return IPOAnalysisResponse.model_validate(
        result
    )


async def get_ipo_analysis(
    db: AsyncSession,
    asset_id: UUID,
) -> IPOAnalysisResponse | None:
    repository = IPORepository(db)
    data = await repository.get_ipo_analysis_data(asset_id)

    if data is None:
        return None

    return analyze_ipo_data(data)


def analyze_mutual_fund_data(
    data: dict[str, Any],
) -> MutualFundAnalysisResponse:
    """
    Analyze structured mutual fund data and return
    a validated response.
    """

    result = analyze_mutual_fund(**data)

    return MutualFundAnalysisResponse.model_validate(
        result
    )


async def get_mutual_fund_analysis(
    db: AsyncSession,
    asset_id: UUID,
) -> MutualFundAnalysisResponse | None:
    repository = MutualFundRepository(db)
    data = await repository.get_mutual_fund_analysis_data(asset_id)

    if data is None:
        return None

    return analyze_mutual_fund_data(data)