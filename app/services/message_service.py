from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message
from app.repositories.conversation_repository import (
    ConversationRepository,
)
from app.repositories.message_repository import (
    MessageRepository,
)


class MessageService:

    def __init__(self, db: AsyncSession):
        self.message_repository = MessageRepository(db)
        self.conversation_repository = ConversationRepository(db)

    async def create_user_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
    ) -> Message:

        conversation = await self.conversation_repository.get_by_id(
            conversation_id,
            user_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )

        return await self.message_repository.create(
            message
        )

    async def get_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> list[Message]:

        conversation = await self.conversation_repository.get_by_id(
            conversation_id,
            user_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return await self.message_repository.get_all_by_conversation(
            conversation_id
        )