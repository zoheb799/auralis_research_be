
from app.ai.schemas.research import ResearchRequest
from app.ai.schemas.research_explanation import ResearchExplanation
from app.ai.schemas.research_result import ResearchAssetResult
from app.ai.services.ai_service import AIService


RESEARCH_EXPLANATION_SYSTEM_PROMPT = """
You are Auralis, an evidence-based investment research assistant.

Your job is to answer the user's original question naturally, not to dump a rigid report.

Rules:
1. Start with a direct answer to the user's actual question in plain language.
2. Keep the response conversational and useful, not template-driven.
3. Use only facts supported by the supplied research data.
4. Never invent prices, returns, financial metrics, or company facts.
5. If data is missing or stale, state the limitation clearly.
6. Explain the key reasoning in a way that is easy to follow.
7. Use bullets, headings, or a short table only when they help answer the question.
8. Explain both favorable findings and risks without sounding like a buy recommendation.
9. Do not guarantee profits or predict certain outcomes.
10. Treat the user's budget and preferences as context, not proof that an asset is suitable.
11. The summary field should be the actual answer to the user's question, not just a heading.
12. Return only the requested structured response.
"""


class ResearchExplanationService:
    def __init__(self, ai_service: AIService) -> None:
        self.ai_service = ai_service

    async def explain(
        self,
        research_results: list[ResearchAssetResult],
        request: ResearchRequest,
        user_question: str | None = None,
    ) -> ResearchExplanation:
        evidence = [
            result.model_dump(mode="json")
            for result in research_results
        ]

        original_question = (
            user_question
            or request.user_question
            or "What should I know about this research?"
        )

        user_prompt = (
            "Answer the user's actual question first.\n\n"
            f"User question:\n{original_question}\n\n"
            "User research context:\n"
            f"{request.model_dump(mode='json')}\n\n"
            "Use the supplied request and research evidence as your sources. "
            "Start with a direct, conversational answer. Then explain the key "
            "reasoning, evidence, and any important risks or limitations. "
            "Do not fill missing fields with guesses. If data is missing or stale, "
            "say so plainly. Do not guarantee profits or present a favorable signal "
            "as a buy instruction. The user's budget does not establish affordability "
            "or suitability by itself.\n\n"
            f"Research evidence:\n{evidence}"
        )

        return await self.ai_service.generate_structured(
            system_prompt=RESEARCH_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ResearchExplanation,
        )


__all__ = ["ResearchExplanationService"]