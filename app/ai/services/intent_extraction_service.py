
import re

from app.ai.schemas.intent import (
    AssetType,
    IntentType,
    InvestmentHorizon,
    InvestmentIntent,
)
from app.ai.services.ai_service import AIService


INTENT_EXTRACTION_SYSTEM_PROMPT = """
You are the intent extraction component of Auralis,
an investment research application.

Classify the user's request into the correct intent category
before deciding any workflow.

Rules:
1. Use intent_type to classify the request as one of:
   general_chat, explanation, specific_research, comparison,
   broad_discovery, or portfolio_planning.
2. Do not invent an asset name, investment amount, or comparison target.
3. Use UNKNOWN when the asset type or investment horizon cannot be determined.
4. Preserve the user's original query exactly.
5. Extract an asset name or comparison targets only when the user identifies them.
6. Interpret amounts only when explicitly stated.
7. Do not provide investment advice or recommendations.
8. Do not infer a guaranteed profit objective.
9. Return only the requested structured output.
"""


def _tokenize(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[a-zA-Z0-9]+", text)
    }


# These words describe a broad research request rather than
# identifying a particular asset.
GENERIC_QUERY_WORDS = {
    "a", "an", "the", "me", "my", "for", "in", "of", "on",
    "to", "with", "and", "or", "please", "show", "find",
    "give", "list", "explore", "what", "are", "is", "best",
    "good", "top", "latest", "available", "some", "any",
    "opportunity", "opportunities", "option", "options",
    "investment", "investments", "invest", "research",
    "analyze", "analyse", "analysis", "compare", "evaluate",
    "assess", "market", "markets", "potential", "promising",
    "this", "that", "these", "those", "quarter", "year",
    "month", "months", "today", "currently", "current",
    "short", "long", "term", "shortterm", "longterm",
    "short-term", "long-term", "horizon",
}

ASSET_TYPE_PATTERNS = {
    AssetType.STOCK: re.compile(
        r"\b(stocks?|shares?)\b", re.IGNORECASE
    ),
    AssetType.IPO: re.compile(
        r"\bipo(?:s)?\b", re.IGNORECASE
    ),
    AssetType.MUTUAL_FUND: re.compile(
        r"\bmutual\s+funds?\b", re.IGNORECASE
    ),
}

AMOUNT_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr\s*)?\s*"
    r"\d[\d,]*(?:\.\d+)?\s*"
    r"(?:k|thousand|lakh|lakhs|lac|lacs|million|crore|crores)?",
    re.IGNORECASE,
)


class IntentExtractionService:
    def __init__(self, ai_service: AIService) -> None:
        self.ai_service = ai_service

    async def extract(
        self,
        user_query: str,
    ) -> InvestmentIntent:
        query = user_query.strip()

        if not query:
            raise ValueError("User query cannot be empty.")

        fast_intent = self._extract_simple_intent(query)

        if fast_intent is not None:
            return fast_intent

        # Preserve the existing LLM fallback for requests that
        # need more interpretation or may name a specific asset.
        return await self.ai_service.generate_structured(
            system_prompt=INTENT_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=(
                "Classify the user's request before deciding any workflow. "
                "Do not answer the message.\n\n"
                f"User message:\n{query}"
            ),
            response_model=InvestmentIntent,
        )

    @staticmethod
    def _extract_simple_intent(
        query: str,
    ) -> InvestmentIntent | None:
        normalized = " ".join(query.split())

        if not normalized:
            return None

        general_chat = re.search(
            r"\b(hi|hello|hey|good morning|good evening|how are you|what's up|thanks)\b",
            normalized,
            re.IGNORECASE,
        )
        if general_chat:
            return InvestmentIntent(
                intent_type=IntentType.GENERAL_CHAT,
                user_query=normalized,
            )

        explanation_keywords = {
            "ratio",
            "pe",
            "p/e",
            "roe",
            "debt",
            "valuation",
            "market cap",
            "definition",
            "mean",
            "meaning",
            "what does",
            "what is",
            "explain",
            "define",
        }
        explanation_tokens = _tokenize(normalized)
        if any(keyword in explanation_tokens for keyword in {"ratio", "pe", "roe", "valuation", "debt", "cap"}) or re.search(
            r"\b(what does|what is|explain|define|meaning of)\b",
            normalized,
            re.IGNORECASE,
        ):
            return InvestmentIntent(
                intent_type=IntentType.EXPLANATION,
                user_query=normalized,
            )

        comparison = re.search(
            r"\b(compare|comparison)\b.*\b(and|vs|versus)\b|\b[a-zA-Z0-9.-]+\s+(vs|versus)\s+[a-zA-Z0-9.-]+",
            normalized,
            re.IGNORECASE,
        )
        if comparison:
            return InvestmentIntent(
                intent_type=IntentType.COMPARISON,
                user_query=normalized,
            )

        portfolio = re.search(
            r"\b(portfolio|allocate|allocation|budget|risk tolerance|invest\s+\d+|for\s+\d+\s*(year|years|month|months))\b",
            normalized,
            re.IGNORECASE,
        )
        if portfolio:
            return InvestmentIntent(
                intent_type=IntentType.PORTFOLIO_PLANNING,
                user_query=normalized,
            )

        broad_discovery = re.search(
            r"\b(find|discover|best|top|low debt|consistent growth|valuation|growth|sector|risk|quality|undervalued|small cap|mid cap|large cap)\b",
            normalized,
            re.IGNORECASE,
        )
        if broad_discovery:
            return InvestmentIntent(
                intent_type=IntentType.BROAD_DISCOVERY,
                user_query=normalized,
            )

        matches = [
            asset_type
            for asset_type, pattern in ASSET_TYPE_PATTERNS.items()
            if pattern.search(query)
        ]

        if len(matches) != 1:
            return None

        if AMOUNT_PATTERN.search(query):
            return None

        remaining = query

        for pattern in ASSET_TYPE_PATTERNS.values():
            remaining = pattern.sub(" ", remaining)

        remaining = re.sub(r"[^\w\s-]", " ", remaining)

        words = [
            word.casefold()
            for word in remaining.split()
            if word.casefold() not in GENERIC_QUERY_WORDS
        ]

        if words:
            return None

        horizon = InvestmentHorizon.UNKNOWN

        if re.search(r"\b(long[-\s]?term)\b", query, re.IGNORECASE):
            horizon = InvestmentHorizon.LONG_TERM
        elif re.search(
            r"\b(short[-\s]?term)\b", query, re.IGNORECASE
        ):
            horizon = InvestmentHorizon.SHORT_TERM

        return InvestmentIntent(
            intent_type=IntentType.SPECIFIC_RESEARCH,
            asset_type=matches[0],
            horizon=horizon,
            user_query=query,
        )