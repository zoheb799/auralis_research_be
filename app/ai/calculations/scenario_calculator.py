from decimal import Decimal, ROUND_DOWN

from app.ai.schemas.analysis import InvestmentScenario
from app.ai.schemas.market_data import MarketAssetData


class ScenarioCalculator:

    @staticmethod
    def calculate(
        *,
        asset: MarketAssetData,
        investment_amount: Decimal,
        scenario_returns: list[Decimal],
    ) -> list[InvestmentScenario]:

        if asset.current_price is None:
            return []

        if asset.current_price <= 0:
            return []

        if investment_amount <= 0:
            return []

        shares_decimal = (
            investment_amount / asset.current_price
        )

        shares = int(
            shares_decimal.to_integral_value(
                rounding=ROUND_DOWN
            )
        )

        if shares <= 0:
            return []

        invested_amount = (
            asset.current_price * shares
        )

        remaining_amount = (
            investment_amount - invested_amount
        )

        scenarios: list[InvestmentScenario] = []

        for return_percent in scenario_returns:

            multiplier = (
                Decimal("1")
                + (return_percent / Decimal("100"))
            )

            scenario_price = (
                asset.current_price * multiplier
            )

            scenario_value = (
                scenario_price * shares
            )

            profit_loss = (
                scenario_value - invested_amount
            )

            scenarios.append(
                InvestmentScenario(
                    asset_id=asset.asset_id,
                    asset_name=asset.name,
                    symbol=asset.symbol,
                    investment_amount=investment_amount,
                    current_price=asset.current_price,
                    shares=shares,
                    invested_amount=invested_amount,
                    remaining_amount=remaining_amount,
                    scenario_return_percent=return_percent,
                    scenario_price=scenario_price,
                    scenario_value=scenario_value,
                    profit_loss=profit_loss,
                )
            )

        return scenarios