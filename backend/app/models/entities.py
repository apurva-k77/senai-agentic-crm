from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="Active")  # VIP|Blocked|Active|Churned
    account_value: Mapped[float] = mapped_column(Float, default=0.0)
    churn_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime)


class Thread(Base):
    __tablename__ = "threads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(512))
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="Open")
    assigned_to: Mapped[str | None] = mapped_column(String(128))
    emails: Mapped[list["Email"]] = relationship(back_populates="thread", order_by="Email.timestamp")


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        Index("ix_emails_sender_timestamp", "sender", "timestamp"),
        Index("ix_emails_thread_timestamp", "thread_fk", "timestamp"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_fk: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sender: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    body_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(64))
    urgency: Mapped[str | None] = mapped_column(String(32))
    requires_human: Mapped[bool | None] = mapped_column(Boolean)
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_entities: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="Received")
    job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    thread: Mapped["Thread"] = relationship(back_populates="emails")
    actions: Mapped[list["Action"]] = relationship(back_populates="email")


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), index=True)
    agent_reasoning_log: Mapped[dict | list | None] = mapped_column(JSON)
    action_type: Mapped[str] = mapped_column(String(64))
    proposed_content: Mapped[str | None] = mapped_column(Text)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    email: Mapped["Email"] = relationship(back_populates="actions")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_doc: Mapped[str] = mapped_column(String(255))
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)  # vector stored as JSON for SQLite
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebIntelligenceCache(Base):
    __tablename__ = "web_intelligence_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(512))
    target_entity: Mapped[str] = mapped_column(String(255), index=True)
    scraped_data: Mapped[dict] = mapped_column(JSON)
    scraped_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(128))
    performed_by: Mapped[str] = mapped_column(String(128))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    diff: Mapped[dict | None] = mapped_column(JSON)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
