from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class IngestEmailPayload(BaseModel):
    message_id: str
    thread_id: str
    sender: str
    subject: str | None = ""
    body: str | None = ""
    timestamp: str | datetime
    sender_name: str | None = None
    company: str | None = None

    @field_validator("subject", "body", mode="before")
    @classmethod
    def empty_to_str(cls, v):
        return v if v is not None else ""

    @field_validator("sender")
    @classmethod
    def valid_sender(cls, v: str):
        if "@" not in v:
            raise ValueError("sender must be a valid email")
        return v.lower().strip()


class ClassificationResult(BaseModel):
    category: str
    sentiment: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    urgency: str
    requires_human: bool
    escalation_reason: str | None = None
    suggested_reply: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    detected_entities: dict = Field(default_factory=dict)
