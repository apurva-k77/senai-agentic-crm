import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Contact, Email, ProcessingJob, Thread
from app.services.agent import run_agent
from app.services.heuristics import run_heuristics, sanitize_body
from app.services.llm import classify_email
from app.services.rag import search_knowledge
from app.services.sentiment import update_sender_trend
from app.services.web_intel import fetch_reputation


async def process_email_job(db: AsyncSession, email_id: int, job_id: str):
    job = await db.get(ProcessingJob, job_id)
    email = await db.get(Email, email_id)
    if not email or not job:
        return
    try:
        job.status = "processing"
        await db.commit()

        heur = run_heuristics(email.sender, email.subject, email.body)
        thread = await db.get(Thread, email.thread_fk)
        hist_result = await db.execute(
            select(Email).where(Email.thread_fk == email.thread_fk, Email.id != email.id).order_by(Email.timestamp)
        )
        history = [
            {"sender": e.sender, "subject": e.subject, "body": e.body, "timestamp": e.timestamp.isoformat()}
            for e in hist_result.scalars().all()
        ]
        query = f"{email.subject} {email.body}"
        rag_chunks = await search_knowledge(db, query, top_k=3)

        classification = await classify_email(
            email.sender, email.subject, email.body, history, rag_chunks, heur
        )

        if classification.confidence < settings.confidence_human_threshold:
            classification.requires_human = True
            classification.escalation_reason = classification.escalation_reason or "Confidence below 0.70"

        email.category = classification.category
        email.sentiment_score = classification.sentiment_score
        email.urgency = classification.urgency
        email.requires_human = classification.requires_human
        email.confidence = classification.confidence
        email.raw_entities = classification.detected_entities
        email.status = "Processing"

        if heur.is_security:
            email.category = "Legal"
            email.urgency = "Critical"
            email.requires_human = True
            classification.category = "Legal"
            classification.urgency = "Critical"
            classification.requires_human = True

        web_intel = None
        if "trustpilot" in email.body.lower() or "g2" in email.body.lower() or email.message_id == "msg_033":
            web_intel = (await fetch_reputation(db))["data"]

        await run_agent(db, email, classification, heur, rag_chunks, web_intel, dry_run=False)

        if heur.is_security:
            email.status = "Escalated"
        elif heur.is_spam:
            email.status = "Ignored"
        elif classification.requires_human:
            email.status = "Escalated"
        elif classification.suggested_reply:
            email.status = "Replied"

        await update_sender_trend(db, email.sender, classification.sentiment_score)

        # Update contact churn risk
        contact_r = await db.execute(select(Contact).where(Contact.email == email.sender))
        contact = contact_r.scalar_one_or_none()
        if contact and (classification.sentiment_score or 0) < -0.5:
            contact.churn_risk_score = min(1.0, contact.churn_risk_score + 0.15)
            contact.last_contact_at = datetime.utcnow()

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        await db.commit()
    except Exception as ex:
        job.status = "failed"
        job.error = str(ex)
        await db.commit()


def new_job_id() -> str:
    return str(uuid.uuid4())
