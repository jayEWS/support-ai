from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class WhatsAppAttachment(BaseModel):
    type: str
    url: str
    name: Optional[str] = None

class WhatsAppMessage(BaseModel):
    sender: str
    text: Optional[str] = ""
    attachments: List[WhatsAppAttachment] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_id: str # For idempotency

class IntentType(str):
    SIMPLE = "simple"
    DEEP_REASONING = "deep_reasoning"
    ESCALATION = "escalation"
    TICKET_UPDATE = "ticket_update"
    CRITICAL = "critical"

class IntentClassification(BaseModel):
    intent: str
    confidence: float
    reason: Optional[str] = None

class CustomerInfo(BaseModel):
    identifier: str
    name: Optional[str] = None
    company: Optional[str] = None
    outlet: Optional[str] = None
    position: Optional[str] = None
    is_new: bool = False

class RAGResponse(BaseModel):
    answer: str
    confidence: float
    source_documents: List[str] = []
    retrieval_method: Optional[str] = None
    num_retrieved: Optional[int] = None

class TicketCreate(BaseModel):
    user_id: str
    summary: str
    description: str
    priority: str = "Medium"

class TicketResponse(BaseModel):
    id: int
    status: str
    summary: str
    created_at: datetime
