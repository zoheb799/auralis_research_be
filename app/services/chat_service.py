from uuid import UUID

from fastapi import HTTPException, status

from app.ai.orchestrator.chat_orchestrator import ChatOrchestrator
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository


class ChatService:
    MAX_CONTEXT_MESSAGES = 12

    def __init__(
        self,
        db,
        conversation_repository: ConversationRepository | None = None,
        message_repository: MessageRepository | None = None,
        orchestrator: ChatOrchestrator | None = None,
    ) -> None:
        self.db = db
        self.conversation_repository = conversation_repository or ConversationRepository(db)
        self.message_repository = message_repository or MessageRepository(db)
        self.orchestrator = (
            orchestrator
            if orchestrator is not None
            else ChatOrchestrator(db=db)
        )

    @classmethod
    def _limit_context_messages(
        cls,
        messages: list,
    ) -> list:
        if len(messages) <= cls.MAX_CONTEXT_MESSAGES:
            return messages
        return messages[-cls.MAX_CONTEXT_MESSAGES:]

    def _build_llm_prompt(
        self,
        *,
        current_message: str,
        prior_messages: list,
        current_user_message_id: UUID | None = None,
    ) -> str:
        relevant_history = [
            item
            for item in prior_messages
            if current_user_message_id is None
            or item.id != current_user_message_id
        ]
        recent_history = self._limit_context_messages(relevant_history)
        context_lines = [
            f"{item.role}: {item.content}"
            for item in recent_history
        ]
        context_block = (
            "\n".join(context_lines)
            if context_lines
            else "No previous messages."
        )

        return (
            "You are continuing this conversation.\n\n"
            f"Conversation history:\n{context_block}\n\n"
            f"Latest user message:\n{current_message.strip()}"
        )

    async def send_message(
        self,
        user_id: UUID,
        message: str,
        conversation_id: UUID | None = None,
    ) -> dict[str, str]:
        if not message or not message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content cannot be empty.",
            )

        conversation = None

        if conversation_id is not None:
            conversation = await self.conversation_repository.get_by_id(
                conversation_id,
                user_id,
            )
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )

        if conversation is None:
            title = message.strip()[:50] or "New conversation"
            conversation = Conversation(
                user_id=user_id,
                title=title,
            )
            conversation = await self.conversation_repository.create(conversation)

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=message.strip(),
        )
        user_message = await self.message_repository.create(user_message)

        prior_messages = await self.message_repository.get_all_by_conversation(conversation.id)
        llm_prompt = self._build_llm_prompt(
            current_message=message,
            prior_messages=prior_messages,
            current_user_message_id=user_message.id,
        )

        try:
            reply = await self.orchestrator.chat(llm_prompt)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to generate an assistant response.",
            ) from exc

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
        )
        assistant_message = await self.message_repository.create(assistant_message)

        return {
            "conversation_id": str(conversation.id),
            "reply": reply,
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "assistant_created_at": assistant_message.created_at,
        }


__all__ = ["ChatService"]
