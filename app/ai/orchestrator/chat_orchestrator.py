
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.system import AURALIS_SYSTEM_PROMPT
from app.ai.schemas.intent import AssetType, IntentType, InvestmentIntent
from app.ai.schemas.research import ResearchRequest
from app.ai.services.ai_service import AIService
from app.ai.services.historical_analysis_service import (
    HistoricalAnalysisService,
)
from app.ai.services.intent_extraction_service import (
    IntentExtractionService,
)
from app.ai.services.market_data_service import MarketDataService
from app.ai.services.research_explanation_service import (
    ResearchExplanationService,
)
from app.ai.services.research_service import ResearchService


RESEARCH_TRIGGERS = (
    # Research actions
    "analyze",
    "analyse",
    "research",
    "compare",
    "evaluate",
    "assess",
    "investigate",

    # Investment-related requests
    "stock",
    "stocks",
    "share",
    "shares",
    "ipo",
    "mutual fund",
    "mutual funds",
    "investment",
    "invest",
    "portfolio",
    "market opportunities",
    "investment opportunities",
    "where should i invest",
    "where can i invest",
    "where to invest",
    "what should i invest in",
    "what can i invest in",
    "how should i invest",
    "investment options",
    "i have to invest",
)

LATEST_MESSAGE_MARKER = "Latest user message:\n"
logger = logging.getLogger(__name__)


class ChatOrchestrator:
    def __init__(
        self,
        ai_service: AIService | None = None,
        research_service: ResearchService | None = None,
        intent_extraction_service: IntentExtractionService | None = None,
        research_explanation_service: ResearchExplanationService | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        self.ai_service = (
            ai_service if ai_service is not None else AIService()
        )

        # Build the production research pipeline when a DB session
        # is provided and custom services have not been supplied.
        if db is not None and all(
            dependency is None
            for dependency in (
                research_service,
                intent_extraction_service,
                research_explanation_service,
            )
        ):
            market_data_service = MarketDataService(db)
            historical_analysis_service = HistoricalAnalysisService(db)

            research_service = ResearchService(
                market_data_service=market_data_service,
                historical_analysis_service=historical_analysis_service,
            )

            intent_extraction_service = IntentExtractionService(
                self.ai_service
            )

            research_explanation_service = ResearchExplanationService(
                self.ai_service
            )

        self.research_service = research_service
        self.intent_extraction_service = intent_extraction_service
        self.research_explanation_service = research_explanation_service

    async def chat(self, user_message: str) -> str:
        latest_message = self._extract_latest_message(user_message)

        dependencies_available = all(
            dependency is not None
            for dependency in (
                self.research_service,
                self.intent_extraction_service,
                self.research_explanation_service,
            )
        )

        if dependencies_available:
            intent = await self.intent_extraction_service.extract(
                latest_message
            )

            logger.info(
                "AURALIS_INTENT: %s",
                {
                    "intent_type": intent.intent_type.value,
                    "asset_type": intent.asset_type.value,
                    "investment_amount": intent.investment_amount,
                    "horizon": intent.horizon.value,
                    "duration_months": intent.duration_months,
                    "risk_preference": intent.risk_preference,
                    "asset_name": intent.asset_name,
                    "comparison_targets": intent.comparison_targets,
                    "discovery_criteria": intent.discovery_criteria,
                    "constraints": intent.constraints,
                    "clarification_needed": intent.clarification_needed,
                },
            )

            if intent.intent_type in {
                IntentType.GENERAL_CHAT,
                IntentType.EXPLANATION,
            }:
                return await self.ai_service.generate(
                    system_prompt=AURALIS_SYSTEM_PROMPT,
                    user_prompt=user_message,
                )

            if intent.intent_type in {
                IntentType.SPECIFIC_RESEARCH,
                IntentType.COMPARISON,
                IntentType.BROAD_DISCOVERY,
                IntentType.PORTFOLIO_PLANNING,
            }:
                is_specific_research = (
                    intent.asset_type != AssetType.UNKNOWN
                    or bool(intent.asset_name)
                )
                is_broad_research = (
                    intent.intent_type == IntentType.BROAD_DISCOVERY
                    or self._is_broad_investment_query(latest_message)
                )

                if is_specific_research or is_broad_research:
                    return await self._run_research(
                        intent,
                        user_question=latest_message,
                    )

        # Preserve the existing normal-chat behavior and conversation
        # history when research is not applicable or unavailable.
        return await self.ai_service.generate(
            system_prompt=AURALIS_SYSTEM_PROMPT,
            user_prompt=user_message,
        )

    async def _run_research(
        self,
        intent: InvestmentIntent,
        user_question: str | None = None,
    ) -> str:
        request = ResearchRequest(
            asset_type=intent.asset_type,
            investment_amount=intent.investment_amount,
            horizon=intent.horizon,
            duration_months=intent.duration_months,
            objective=intent.objective,
            risk_preference=intent.risk_preference,
            asset_name=intent.asset_name,
            user_question=user_question,
        )

        results = await self.research_service.research(request)

        if not results:
            asset_description = (
                f" for '{intent.asset_name}'"
                if intent.asset_name
                else ""
            )

            return (
                f"No matching research data was found{asset_description} "
                "in Auralis's current database. No investment conclusion "
                "can be drawn from the available data. Please check the "
                "asset name or try again when matching data is available."
            )

        explanation = await self.research_explanation_service.explain(
            research_results=results,
            request=request,
            user_question=request.user_question,
        )

        sections = [explanation.summary]

        if explanation.key_findings:
            sections.append(
                "Key findings:\n"
                + "\n".join(
                    f"- {finding}"
                    for finding in explanation.key_findings
                )
            )

        if explanation.risks:
            sections.append(
                "Risks:\n"
                + "\n".join(
                    f"- {risk}"
                    for risk in explanation.risks
                )
            )

        if explanation.limitations:
            sections.append(
                "Limitations:\n"
                + "\n".join(
                    f"- {limitation}"
                    for limitation in explanation.limitations
                )
            )

        if explanation.disclaimer:
            sections.append(
                f"Disclaimer: {explanation.disclaimer}"
            )

        return "\n\n".join(sections)

    @staticmethod
    def _extract_latest_message(message: str) -> str:
        if LATEST_MESSAGE_MARKER in message:
            return message.rsplit(
                LATEST_MESSAGE_MARKER, 1
            )[1].strip()

        return message.strip()

    @staticmethod
    def _should_attempt_research(message: str) -> bool:
        normalized_message = message.casefold()

        return any(
            trigger in normalized_message
            for trigger in RESEARCH_TRIGGERS
        )

    @staticmethod
    def _is_broad_investment_query(message: str) -> bool:
        normalized = " ".join(message.casefold().split())

        broad_phrases = (
            "where should i invest",
            "where can i invest",
            "where to invest",
            "what should i invest in",
            "what can i invest in",
            "how should i invest",
            "investment options",
            "investment opportunities",
            "i have to invest",
        )

        return any(
            phrase in normalized
            for phrase in broad_phrases
        )


__all__ = ["ChatOrchestrator"]