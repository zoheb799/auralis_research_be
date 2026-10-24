
from decimal import Decimal

from app.ai.schemas.analysis import HistoricalAnalysis
from app.ai.schemas.market_data import MarketAssetData
from app.ai.schemas.risk import (
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)


class RiskAssessmentEngine:
    MINIMUM_ASSESSED_FACTORS = 2

    @staticmethod
    def _volatility_risk(
        analysis: HistoricalAnalysis | None,
    ) -> RiskFactor:
        value = (
            analysis.volatility_percent
            if analysis is not None
            else None
        )

        if value is None:
            return RiskFactor(
                name="volatility",
                level=RiskLevel.UNKNOWN,
                explanation="Historical volatility data is unavailable.",
            )

        if value < Decimal("2"):
            level = RiskLevel.LOW
            explanation = (
                "Observed historical volatility was relatively low "
                "under our prototype thresholds."
            )
        elif value <= Decimal("5"):
            level = RiskLevel.MODERATE
            explanation = (
                "Observed historical volatility was moderate "
                "under our prototype thresholds."
            )
        else:
            level = RiskLevel.HIGH
            explanation = (
                "Observed historical volatility was high "
                "under our prototype thresholds."
            )

        return RiskFactor(
            name="volatility",
            level=level,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _leverage_risk(
        asset: MarketAssetData,
    ) -> RiskFactor:
        value = asset.debt_to_equity

        if value is None:
            return RiskFactor(
                name="leverage",
                level=RiskLevel.UNKNOWN,
                explanation="Debt-to-equity data is unavailable.",
            )

        if value < 0:
            return RiskFactor(
                name="leverage",
                level=RiskLevel.UNKNOWN,
                value=value,
                explanation=(
                    "The debt-to-equity value is negative. "
                    "Its interpretation requires financial-statement "
                    "context and data validation."
                ),
            )

        if value <= Decimal("0.5"):
            level = RiskLevel.LOW
            explanation = (
                "Debt-to-equity falls within the prototype's "
                "lower-leverage range."
            )
        elif value <= Decimal("1.0"):
            level = RiskLevel.MODERATE
            explanation = (
                "Debt-to-equity falls within the prototype's "
                "moderate-leverage range."
            )
        else:
            level = RiskLevel.HIGH
            explanation = (
                "Debt-to-equity falls within the prototype's "
                "higher-leverage range."
            )

        return RiskFactor(
            name="leverage",
            level=level,
            value=value,
            explanation=explanation,
        )

    @staticmethod
    def _valuation_risk(
        asset: MarketAssetData,
    ) -> RiskFactor:
        value = asset.pe_ratio

        if value is None:
            return RiskFactor(
                name="valuation",
                level=RiskLevel.UNKNOWN,
                explanation="P/E ratio data is unavailable.",
            )

        if value <= 0:
            return RiskFactor(
                name="valuation",
                level=RiskLevel.UNKNOWN,
                value=value,
                explanation=(
                    "P/E is zero or negative. Standard P/E thresholds "
                    "are not meaningful in this case."
                ),
            )

        if value <= Decimal("15"):
            level = RiskLevel.LOW
            explanation = (
                "P/E is in the prototype's lower valuation-risk "
                "range; this does not establish that the asset "
                "is undervalued."
            )
        elif value <= Decimal("30"):
            level = RiskLevel.MODERATE
            explanation = (
                "P/E is in the prototype's moderate valuation-risk "
                "range; sector comparisons are still needed."
            )
        else:
            level = RiskLevel.HIGH
            explanation = (
                "P/E is in the prototype's higher valuation-risk "
                "range; elevated valuation can increase sensitivity "
                "to changing expectations."
            )

        return RiskFactor(
            name="valuation",
            level=level,
            value=value,
            explanation=explanation,
        )

    @classmethod
    def assess(
        cls,
        *,
        asset: MarketAssetData,
        historical_analysis: HistoricalAnalysis | None,
    ) -> RiskAssessment:
        factors = [
            cls._volatility_risk(historical_analysis),
            cls._leverage_risk(asset),
            cls._valuation_risk(asset),
        ]

        assessed = [
            factor
            for factor in factors
            if factor.level != RiskLevel.UNKNOWN
        ]

        unavailable = [
            factor.name
            for factor in factors
            if factor.level == RiskLevel.UNKNOWN
        ]

        if len(assessed) < cls.MINIMUM_ASSESSED_FACTORS:
            overall_level = RiskLevel.UNKNOWN
            explanation = (
                "There is insufficient evidence to classify overall "
                "risk. Important risk data is missing or cannot be "
                "interpreted using the current rules."
            )
        else:
            high_count = sum(
                factor.level == RiskLevel.HIGH
                for factor in assessed
            )
            moderate_count = sum(
                factor.level == RiskLevel.MODERATE
                for factor in assessed
            )

            if high_count >= 2:
                overall_level = RiskLevel.HIGH
            elif high_count >= 1 or moderate_count >= 2:
                overall_level = RiskLevel.MODERATE
            else:
                overall_level = RiskLevel.LOW

            explanation = (
                "The overall classification summarizes the available "
                "volatility, leverage and valuation indicators. "
                "It is a prototype assessment, not a prediction "
                "of future losses."
            )

        return RiskAssessment(
            overall_level=overall_level,
            factors=factors,
            assessed_factors=len(assessed),
            unavailable_factors=unavailable,
            explanation=explanation,
        )