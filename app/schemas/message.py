from datetime import datetime

from pydantic import BaseModel, Field


class CreateMessageRequest(BaseModel):
    content: str = Field(
        min_length=1,
    )


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime