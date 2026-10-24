from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message


class MessageRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        message: Message,
    ) -> Message:
        self.db.add(message)

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_all_by_conversation(
        self,
        conversation_id: UUID,
    ) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )

        return list(result.scalars().all())