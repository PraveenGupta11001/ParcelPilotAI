from pydantic import BaseModel
from typing import Optional, List

class ChatMessageSchema(BaseModel):
    """Pydantic schema representing a single message in the chat history.

    Attributes:
        role: Sender role identifier (e.g. 'user', 'assistant').
        content: The text content of the message.
    """
    role: str
    content: str

class ChatRequest(BaseModel):
    """Pydantic schema for sending a new chatbot query.

    Attributes:
        message: The natural language query from the user.
        chat_history: Historical list of preceding ChatMessageSchema logs.
        session_id: Optional existing session ID to continue discussion.
        stream: Optional flag to trigger chunked server-sent events (SSE).
    """
    message: str
    chat_history: List[ChatMessageSchema]
    session_id: Optional[int] = None
    stream: Optional[bool] = False

class CreateSessionRequest(BaseModel):
    """Pydantic schema for creating a new empty conversation session.

    Attributes:
        title: Descriptive name or heading for the new chat session.
    """
    title: str

class ConfirmRequest(BaseModel):
    """Pydantic schema for executing a proposed support action.

    Attributes:
        proposal_id: Unique database ID of the target proposal action.
    """
    proposal_id: int
