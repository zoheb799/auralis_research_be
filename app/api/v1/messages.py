from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.message import (
    CreateMessageRequest,
    MessageResponse,
)
from app.services.message_service import MessageService


router = APIRouter(
    prefix="/conversations",
    tags=["Messages"],
)


def to_response(
    message,
) -> MessageResponse:
    return MessageResponse(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def create_message(
    conversation_id: UUID,
    data: CreateMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.chat_service import ChatService

    service = ChatService(db)
    result = await service.send_message(
        user_id=current_user.id,
        message=data.content,
        conversation_id=conversation_id,
    )

    return MessageResponse(
        id=result["assistant_message_id"],
        conversation_id=result["conversation_id"],
        role="assistant",
        content=result["reply"],
        created_at=result["assistant_created_at"],
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)

    messages = await service.get_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return [
        to_response(message)
        for message in messages
    ]