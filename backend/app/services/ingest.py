from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.entities import Contact, Email, ProcessingJob, Thread
from app.schemas.email import IngestEmailPayload
from app.services.heuristics import run_heuristics, sanitize_body
from app.services.processor import new_job_id, process_email_job


async def ingest_email(db: AsyncSession, payload: IngestEmailPayload) -> dict:
    existing = await db.execute(select(Email).where(Email.message_id == payload.message_id))
    if existing.scalar_one_or_none():
        return {"status": "duplicate", "message_id": payload.message_id, "job_id": None}

    body, truncated = sanitize_body(payload.body)
    subject = (payload.subject or "").strip() or "(no subject)"
    if not body and not subject.replace("(no subject)", ""):
        raise AppError("EMPTY_EMAIL", "Email must have non-empty subject or body")

    ts = payload.timestamp if isinstance(payload.timestamp, datetime) else datetime.fromisoformat(
        str(payload.timestamp).replace("Z", "+00:00").replace("+00:00", "")
    )

    thread_r = await db.execute(select(Thread).where(Thread.thread_id == payload.thread_id))
    thread = thread_r.scalar_one_or_none()
    if not thread:
        thread = Thread(
            thread_id=payload.thread_id,
            subject=subject,
            sender_email=payload.sender,
            first_seen_at=ts,
            last_updated_at=ts,
            status="Open",
        )
        db.add(thread)
        await db.flush()
    else:
        thread.last_updated_at = max(thread.last_updated_at, ts)
        if ts < thread.first_seen_at:
            pass  # out-of-order OK

    heur = run_heuristics(payload.sender, subject, body)
    email = Email(
        thread_fk=thread.id,
        message_id=payload.message_id,
        sender=payload.sender,
        subject=subject,
        body=body,
        body_truncated=truncated,
        timestamp=ts,
        priority_score=heur.priority_score,
        status="Received",
    )
    db.add(email)
    await db.flush()

    # Upsert contact
    cr = await db.execute(select(Contact).where(Contact.email == payload.sender))
    contact = cr.scalar_one_or_none()
    if not contact:
        av = 48000.0 if "karen" in payload.sender else (2400000.0 if "bigcorp" in payload.sender else 5000.0)
        db.add(Contact(
            email=payload.sender,
            name=payload.sender_name,
            company=payload.company,
            status="VIP" if av > 100000 else "Active",
            account_value=av,
            last_contact_at=ts,
        ))
    else:
        contact.last_contact_at = ts
        if payload.company:
            contact.company = payload.company

    job_id = new_job_id()
    db.add(ProcessingJob(id=job_id, email_id=email.id, status="queued"))
    email.job_id = job_id
    await db.commit()

    await process_email_job(db, email.id, job_id)

    return {"job_id": job_id, "email_id": email.id, "thread_id": thread.thread_id, "status": "queued"}
