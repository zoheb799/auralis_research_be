from decimal import Decimal

from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.signals import (
    InvestmentSignal,
    InvestmentSignals,
    SignalDirection,
)


class SignalEngine:

    @staticmethod
    def _historical_return_signal(
        analysis: HistoricalAnalysis,
    ) -> InvestmentSignal:

        value = analysis.period_return_percent

        if value is None:
            return InvestmentSignal(
                name="historical_return",
                direction=SignalDirection.NEUTRAL,
                value=None,
                explanation=(
                    "Historical return data is unavailable."
                ),
            )

        if value > Decimal("15"):
            direction = SignalDirection.POSITIVE
            explanation = (
                f"The asset gained {value:.2f}% "
                "during the analysis period."
            )

        elif value >= Decimal("0"):
            direction = SignalDirection.NEUTRAL
            explanation = (
                f"The asset gained {value:.2f}% "
                "during the analysis period."
            )

        else:
            direction = SignalDirection.NEGATIVE
            explanation = (
                f"The asset declined {abs(value):.2f}% "
                "during the analysis period."
            )

        return InvestmentSignal(
            name="historical_return",
            direction=direction,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _volatility_signal(
        analysis: HistoricalAnalysis,
    ) -> InvestmentSignal:

        value = analysis.volatility_percent

        if value is None:
            return InvestmentSignal(
                name="volatility",
                direction=SignalDirection.NEUTRAL,
                value=None,
                explanation="Volatility data is unavailable.",
            )

        if value < Decimal("2"):
            direction = SignalDirection.POSITIVE
            explanation = (
                f"Historical volatility was {value:.2f}%, "
                "indicating relatively lower price variability."
            )

        elif value <= Decimal("5"):
            direction = SignalDirection.NEUTRAL
            explanation = (
                f"Historical volatility was {value:.2f}%, "
                "indicating moderate price variability."
            )

        else:
            direction = SignalDirection.NEGATIVE
            explanation = (
                f"Historical volatility was {value:.2f}%, "
                "indicating relatively higher price variability."
            )

        return InvestmentSignal(
            name="volatility",
            direction=direction,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _valuation_signal(
        asset: MarketAssetData,
    ) -> InvestmentSignal:

        value = asset.pe_ratio

        if value is None:
            return InvestmentSignal(
                name="valuation",
                direction=SignalDirection.NEUTRAL,
                value=None,
                explanation="P/E ratio is unavailable.",
            )

        if value <= Decimal("15"):
            direction = SignalDirection.POSITIVE
            explanation = (
                f"The P/E ratio is {value:.2f}, "
                "which is relatively low."
            )

        elif value <= Decimal("30"):
            direction = SignalDirection.NEUTRAL
            explanation = (
                f"The P/E ratio is {value:.2f}, "
                "which falls within a moderate range."
            )

        else:
            direction = SignalDirection.NEGATIVE
            explanation = (
                f"The P/E ratio is {value:.2f}, "
                "which indicates a relatively higher valuation."
            )

        return InvestmentSignal(
            name="valuation",
            direction=direction,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _profitability_signal(
        asset: MarketAssetData,
    ) -> InvestmentSignal:

        value = asset.roe

        if value is None:
            return InvestmentSignal(
                name="profitability",
                direction=SignalDirection.NEUTRAL,
                value=None,
                explanation="ROE data is unavailable.",
            )

        if value >= Decimal("15"):
            direction = SignalDirection.POSITIVE
            explanation = (
                f"ROE is {value:.2f}%, "
                "indicating relatively strong profitability."
            )

        elif value >= Decimal("10"):
            direction = SignalDirection.NEUTRAL
            explanation = (
                f"ROE is {value:.2f}%, "
                "indicating moderate profitability."
            )

        else:
            direction = SignalDirection.NEGATIVE
            explanation = (
                f"ROE is {value:.2f}%, "
                "indicating relatively weaker profitability."
            )

        return InvestmentSignal(
            name="profitability",
            direction=direction,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _leverage_signal(
        asset: MarketAssetData,
    ) -> InvestmentSignal:

        value = asset.debt_to_equity

        if value is None:
            return InvestmentSignal(
                name="leverage",
                direction=SignalDirection.NEUTRAL,
                value=None,
                explanation="Debt-to-equity data is unavailable.",
            )

        if value <= Decimal("0.5"):
            direction = SignalDirection.POSITIVE
            explanation = (
                f"Debt-to-equity is {value:.2f}, "
                "indicating relatively lower leverage."
            )

        elif value <= Decimal("1.0"):
            direction = SignalDirection.NEUTRAL
            explanation = (
                f"Debt-to-equity is {value:.2f}, "
                "indicating moderate leverage."
            )

        else:
            direction = SignalDirection.NEGATIVE
            explanation = (
                f"Debt-to-equity is {value:.2f}, "
                "indicating relatively higher leverage."
            )

        return InvestmentSignal(
            name="leverage",
            direction=direction,
            value=value,
            explanation=explanation,
        )



    @staticmethod
    def _calculate_overall_direction(
        signals: list[InvestmentSignal],
    ) -> SignalDirection:
        scores = {
            SignalDirection.POSITIVE: 1,
            SignalDirection.NEUTRAL: 0,
            SignalDirection.NEGATIVE: -1,
        }

        available_signals = [
            signal
            for signal in signals
            if signal.value is not None
        ]

        if not available_signals:
            return SignalDirection.NEUTRAL

        total_score = sum(
            scores[signal.direction]
            for signal in available_signals
        )

        if total_score > 0:
            return SignalDirection.POSITIVE
        if total_score < 0:
            return SignalDirection.NEGATIVE

        return SignalDirection.NEUTRAL

    @classmethod
    def analyze(
        cls,
        *,
        asset: MarketAssetData,
        historical_analysis: HistoricalAnalysis,
    ) -> InvestmentSignals:

        historical_return = (
            cls._historical_return_signal(
                historical_analysis
            )
        )

        volatility = cls._volatility_signal(
            historical_analysis
        )

        valuation = cls._valuation_signal(
            asset
        )

        profitability = cls._profitability_signal(
            asset
        )

        leverage = cls._leverage_signal(
            asset
        )

        all_signals = [
            historical_return,
            volatility,
            valuation,
            profitability,
            leverage,
        ]

        overall_direction = (
            cls._calculate_overall_direction(
                all_signals
            )
        )

        return InvestmentSignals(
            historical_return=historical_return,
            volatility=volatility,
            valuation=valuation,
            profitability=profitability,
            leverage=leverage,
            overall_direction=overall_direction,
        )