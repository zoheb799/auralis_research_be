from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.services.chat_service import ChatService


class FakeConversationRepository:
    def __init__(self):
        self.created = None
        self.fetched = None

    async def get_by_id(self, conversation_id, user_id):
        return self.fetched

    async def create(self, conversation):
        self.created = conversation
        conversation.id = uuid4()
        return conversation


class FakeMessageRepository:
    def __init__(self):
        self.saved = []

    async def create(self, message):
        self.saved.append(message)
        message.id = message.id or uuid4()
        return message

    async def get_all_by_conversation(self, conversation_id):
        return [
            item for item in self.saved if item.conversation_id == conversation_id
        ]


class FakeOrchestrator:
    def __init__(self, response="Hi, I am responding to: "):
        self.response = response
        self.calls = []

    async def chat(self, user_message):
        self.calls.append(user_message)
        return self.response + user_message


@pytest.mark.asyncio
async def test_chat_service_creates_conversation_for_new_thread():
    conversation_repo = FakeConversationRepository()
    message_repo = FakeMessageRepository()
    service = ChatService(
        db=None,
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        orchestrator=FakeOrchestrator(),
    )

    result = await service.send_message(
        user_id=uuid4(),
        message="Tell me about AI",
        conversation_id=None,
    )

    assert result["conversation_id"] is not None
    assert result["reply"].startswith("Hi, I am responding to:")
    assert len(message_repo.saved) == 2
    assert message_repo.saved[0].role == "user"
    assert message_repo.saved[1].role == "assistant"


@pytest.mark.asyncio
async def test_chat_service_uses_existing_conversation():
    conversation = Conversation(user_id=uuid4(), title="My chat")
    conversation.id = uuid4()

    conversation_repo = FakeConversationRepository()
    conversation_repo.fetched = conversation
    message_repo = FakeMessageRepository()
    service = ChatService(
        db=None,
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        orchestrator=FakeOrchestrator(),
    )

    result = await service.send_message(
        user_id=conversation.user_id,
        message="Follow up",
        conversation_id=conversation.id,
    )

    assert result["conversation_id"] == str(conversation.id)
    assert result["reply"]


@pytest.mark.asyncio
async def test_chat_service_builds_context_from_same_conversation_only():
    conversation = Conversation(user_id=uuid4(), title="Same thread")
    conversation.id = uuid4()

    other_conversation = Conversation(user_id=uuid4(), title="Other thread")
    other_conversation.id = uuid4()

    conversation_repo = FakeConversationRepository()
    conversation_repo.fetched = conversation

    message_repo = FakeMessageRepository()
    message_repo.saved = [
        Message(conversation_id=conversation.id, role="user", content="hello"),
        Message(conversation_id=conversation.id, role="assistant", content="hi"),
        Message(conversation_id=other_conversation.id, role="user", content="unrelated"),
    ]

    orchestrator = FakeOrchestrator()
    service = ChatService(
        db=None,
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        orchestrator=orchestrator,
    )

    await service.send_message(
        user_id=conversation.user_id,
        message="Follow up",
        conversation_id=conversation.id,
    )

    llm_prompt = orchestrator.calls[0]
    assert "Latest user message:\nFollow up" in llm_prompt
    assert "user: hello" in llm_prompt
    assert "assistant: hi" in llm_prompt
    assert "unrelated" not in llm_prompt
    assert llm_prompt.count("Latest user message:") == 1


@pytest.mark.asyncio
async def test_chat_service_limits_context_to_recent_messages():
    conversation = Conversation(user_id=uuid4(), title="Long thread")
    conversation.id = uuid4()

    conversation_repo = FakeConversationRepository()
    conversation_repo.fetched = conversation

    message_repo = FakeMessageRepository()
    message_repo.saved = [
        Message(conversation_id=conversation.id, role="user", content=f"m{i}")
        for i in range(20)
    ]
    message_repo.saved += [
        Message(conversation_id=conversation.id, role="assistant", content=f"a{i}")
        for i in range(20)
    ]

    orchestrator = FakeOrchestrator()
    service = ChatService(
        db=None,
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        orchestrator=orchestrator,
    )

    await service.send_message(
        user_id=conversation.user_id,
        message="Current question",
        conversation_id=conversation.id,
    )

    llm_prompt = orchestrator.calls[0]
    assert "m0" not in llm_prompt
    assert "assistant: a8" in llm_prompt
    assert "assistant: a19" in llm_prompt
    assert "Current question" in llm_prompt


@pytest.mark.asyncio
async def test_chat_service_raises_when_llm_generation_fails():
    conversation = Conversation(user_id=uuid4(), title="Failed")
    conversation.id = uuid4()

    conversation_repo = FakeConversationRepository()
    conversation_repo.fetched = conversation

    message_repo = FakeMessageRepository()

    class FailingOrchestrator:
        async def chat(self, user_message):
            raise RuntimeError("LLM down")

    service = ChatService(
        db=None,
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        orchestrator=FailingOrchestrator(),
    )

    with pytest.raises(HTTPException, match="Failed to generate an assistant response"):
        await service.send_message(
            user_id=conversation.user_id,
            message="Will this fail?",
            conversation_id=conversation.id,
        )

    assert len(message_repo.saved) == 1
    assert message_repo.saved[0].role == "user"