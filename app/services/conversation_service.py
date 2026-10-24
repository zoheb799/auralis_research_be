from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.repositories.conversation_repository import (
    ConversationRepository,
)


class ConversationService:

    def __init__(self, db: AsyncSession):
        self.repository = ConversationRepository(db)

    async def create(
        self,
        user_id: UUID,
        title: str,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )

        return await self.repository.create(
            conversation
        )

    async def get_by_id(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> Conversation:
        conversation = await self.repository.get_by_id(
            conversation_id,
            user_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return conversation

    async def get_all(
        self,
        user_id: UUID,
    ) -> list[Conversation]:
        return await self.repository.get_all_by_user(
            user_id
        )

    async def update(
        self,
        conversation_id: UUID,
        user_id: UUID,
        title: str,
    ) -> Conversation:
        conversation = await self.get_by_id(
            conversation_id,
            user_id,
        )

        return await self.repository.update(
            conversation,
            title,
        )

    async def delete(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        conversation = await self.get_by_id(
            conversation_id,
            user_id,
        )

        await self.repository.delete(
            conversation
        )