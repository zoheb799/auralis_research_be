from typing import TypeVar

from pydantic import BaseModel

from app.ai.llm.factory import get_llm_provider
from app.ai.llm.provider import LLMProvider


T = TypeVar("T", bound=BaseModel)


class AIService:

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_llm_provider()

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return await self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        response = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_model.model_json_schema(),
        )

        return response_model.model_validate_json(response)


__all__ = ["AIService"]