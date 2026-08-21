from pydantic import BaseModel
from typing import Optional, List

class ChatMessageSchema(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    chat_history: List[ChatMessageSchema]
    session_id: Optional[int] = None

class CreateSessionRequest(BaseModel):
    title: str

class ConfirmRequest(BaseModel):
    proposal_id: int
