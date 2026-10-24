
from app.ai.schemas.recommendation import (
    RecommendationLabel,
    RecommendationResult,
)
from app.ai.schemas.signals import (
    InvestmentSignal,
    InvestmentSignals,
    SignalDirection,
)


class RecommendationEngine:
    MINIMUM_SIGNALS = 3
    FAVORABLE_THRESHOLD = 0.4
    UNFAVORABLE_THRESHOLD = -0.4

    @staticmethod
    def _get_signals(
        signals: InvestmentSignals,
    ) -> list[InvestmentSignal]:
        return [
            signals.historical_return,
            signals.volatility,
            signals.valuation,
            signals.profitability,
            signals.leverage,
        ]

    @classmethod
    def evaluate(
        cls,
        signals: InvestmentSignals,
    ) -> RecommendationResult:
        all_signals = cls._get_signals(signals)

        # A signal without a value is missing evidence,
        # not a neutral assessment.
        available = [
            signal
            for signal in all_signals
            if signal.value is not None
        ]

        positive = [
            signal
            for signal in available
            if signal.direction == SignalDirection.POSITIVE
        ]
        neutral = [
            signal
            for signal in available
            if signal.direction == SignalDirection.NEUTRAL
        ]
        negative = [
            signal
            for signal in available
            if signal.direction == SignalDirection.NEGATIVE
        ]

        if not available:
            score = 0.0
        else:
            score = (
                len(positive) - len(negative)
            ) / len(available)

        reasons = [
            signal.explanation for signal in positive
        ]
        risks = [
            signal.explanation for signal in negative
        ]

        limitations = [
            f"{signal.name.replace('_', ' ').title()} data is unavailable."
            for signal in all_signals
            if signal.value is None
        ]

        if len(available) < cls.MINIMUM_SIGNALS:
            label = RecommendationLabel.INSUFFICIENT_DATA
            explanation = (
                "There is not enough available signal data "
                "to produce a meaningful research assessment."
            )
        elif score >= cls.FAVORABLE_THRESHOLD:
            label = RecommendationLabel.FAVORABLE_FOR_RESEARCH
            explanation = (
                "The available signals are predominantly positive. "
                "This supports further research, not a guarantee "
                "of investment performance."
            )
        elif score <= cls.UNFAVORABLE_THRESHOLD:
            label = RecommendationLabel.UNFAVORABLE
            explanation = (
                "The available signals are predominantly negative. "
                "Review the underlying risks before considering "
                "this asset further."
            )
        else:
            label = RecommendationLabel.MIXED
            explanation = (
                "The available signals are mixed or inconclusive. "
                "More research may be needed."
            )

        return RecommendationResult(
            label=label,
            score=round(score, 4),
            available_signals=len(available),
            positive_signals=len(positive),
            neutral_signals=len(neutral),
            negative_signals=len(negative),
            reasons=reasons,
            risks=risks,
            limitations=limitations,
            explanation=explanation,
            overall_signal_direction=signals.overall_direction,
        )