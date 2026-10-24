from datetime import datetime
from math import sqrt
from typing import Optional


def calculate_growth(
    current: Optional[float],
    previous: Optional[float],
) -> Optional[float]:
    """
    Calculate percentage growth between two values.
    """

    if current is None or previous is None:
        return None

    if previous == 0:
        return None

    return ((current - previous) / abs(previous)) * 100


def calculate_margin(
    profit: Optional[float],
    revenue: Optional[float],
) -> Optional[float]:
    """
    Calculate profit margin as a percentage.
    """

    if profit is None or revenue is None:
        return None

    if revenue == 0:
        return None

    return (profit / revenue) * 100


def calculate_debt_to_equity(
    total_debt: Optional[float],
    equity: Optional[float],
) -> Optional[float]:
    """
    Calculate debt-to-equity ratio.
    """

    if total_debt is None or equity is None:
        return None

    if equity == 0:
        return None

    return total_debt / equity


def calculate_financial_growth(
    current_revenue: Optional[float],
    previous_revenue: Optional[float],
    current_profit: Optional[float],
    previous_profit: Optional[float],
) -> dict:
    """
    Calculate revenue and profit growth between two financial periods.
    """

    return {
        "revenue_growth": calculate_growth(
            current_revenue,
            previous_revenue,
        ),
        "profit_growth": calculate_growth(
            current_profit,
            previous_profit,
        ),
    }
def calculate_return(
    current_price: Optional[float],
    previous_price: Optional[float],
) -> Optional[float]:
    """
    Calculate percentage return between two prices.
    """

    if current_price is None or previous_price is None:
        return None

    if previous_price == 0:
        return None

    return (
        (current_price - previous_price)
        / previous_price
    ) * 100


def calculate_annualized_volatility(
    prices: list[float],
) -> Optional[float]:
    """
    Calculate annualized volatility from a sequence
    of daily closing prices.

    Uses simple daily returns and a 252-trading-day
    annualization factor.
    """

    if len(prices) < 2:
        return None

    returns: list[float] = []

    for index in range(1, len(prices)):
        previous_price = prices[index - 1]
        current_price = prices[index]

        if previous_price == 0:
            continue

        daily_return = (
            (current_price - previous_price)
            / previous_price
        )

        returns.append(daily_return)

    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)

    squared_differences = [
        (value - mean_return) ** 2
        for value in returns
    ]

    variance = (
        sum(squared_differences)
        / (len(returns) - 1)
    )

    standard_deviation = sqrt(variance)

    return standard_deviation * sqrt(252) * 100