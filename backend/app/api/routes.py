from datetime import datetime, timedelta
from collections import Counter

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, error_envelope
from app.models.database import get_db
from app.models.entities import (
    Action, AuditLog, Contact, Draft, Email, ProcessingJob, Thread,
)
from app.schemas.email import IngestEmailPayload
from app.services.ingest import ingest_email
from app.services.rag import search_knowledge
from app.services.sentiment import sentiment_trend_series
from app.services.web_intel import fetch_reputation
from app.services.processor import process_email_job
from app.services.agent import run_agent
from app.services.heuristics import run_heuristics
from app.services.llm import classify_email
from app.services.rag import search_knowledge as rag_search
from app.services.stream import start_stream_background

router = APIRouter()
_ws_clients: list[WebSocket] = []


async def broadcast(event: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for d in dead:
        _ws_clients.remove(d)


@router.post("/api/ingest")
async def api_ingest(payload: IngestEmailPayload, db: AsyncSession = Depends(get_db)):
    try:
        result = await ingest_email(db, payload)
        await broadcast({"type": "email_ingested", "data": result})
        return {"success": True, **result}
    except AppError as e:
        raise e


@router.get("/api/status/{job_id}")
async def api_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise AppError("JOB_NOT_FOUND", f"No job {job_id}", status=404)
    return {"job_id": job_id, "status": job.status, "email_id": job.email_id, "error": job.error}


@router.get("/dashboard/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Email.id)))
    escalated = await db.scalar(select(func.count(Email.id)).where(Email.status == "Escalated"))
    replied = await db.scalar(select(func.count(Email.id)).where(Email.status == "Replied"))
    critical = await db.scalar(select(func.count(Email.id)).where(Email.urgency == "Critical"))
    spam = await db.scalar(select(func.count(Email.id)).where(Email.category == "Spam"))
    pending = await db.scalar(
        select(func.count(Email.id)).where(Email.requires_human == True, Email.status.in_(["Received", "Processing", "Escalated"]))
    )
    return {
        "pending": pending or 0,
        "replied": replied or 0,
        "escalated": escalated or 0,
        "critical": critical or 0,
        "spam": spam or 0,
        "total": total or 0,
    }


@router.get("/threads/{contact_email}")
async def get_threads(contact_email: str, db: AsyncSession = Depends(get_db)):
    contact_email = contact_email.lower()
    result = await db.execute(
        select(Thread)
        .where(Thread.sender_email == contact_email)
        .options(selectinload(Thread.emails))
    )
    threads = result.scalars().all()
    out = []
    for t in threads:
        emails = sorted(t.emails, key=lambda e: e.timestamp)
        actions_all = []
        for e in emails:
            ar = await db.execute(select(Action).where(Action.email_id == e.id))
            actions_all.extend([
                {
                    "email_id": e.id,
                    "message_id": e.message_id,
                    "action_type": a.action_type,
                    "proposed_content": a.proposed_content,
                    "agent_reasoning_log": a.agent_reasoning_log,
                    "is_approved": a.is_approved,
                }
                for a in ar.scalars().all()
            ])
        out.append({
            "thread_id": t.thread_id,
            "subject": t.subject,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "emails": [
                {
                    "id": e.id,
                    "message_id": e.message_id,
                    "sender": e.sender,
                    "subject": e.subject,
                    "body": e.body,
                    "timestamp": e.timestamp.isoformat(),
                    "sentiment_score": e.sentiment_score,
                    "category": e.category,
                    "urgency": e.urgency,
                    "requires_human": e.requires_human,
                    "confidence": e.confidence,
                    "raw_entities": e.raw_entities,
                    "status": e.status,
                }
                for e in emails
            ],
            "actions": actions_all,
        })
    if not out:
        raise AppError("NOT_FOUND", f"No threads for {contact_email}", status=404)
    return {"contact_email": contact_email, "threads": out}


@router.get("/emails")
async def list_emails(
    tab: str = Query("all"),
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Email).order_by(Email.timestamp.desc())
    if tab == "human":
        stmt = stmt.where(Email.requires_human == True, Email.status != "Ignored")
    elif tab == "auto":
        stmt = stmt.where(Email.status == "Replied")
    elif tab == "escalated":
        stmt = stmt.where(Email.status == "Escalated")
    elif tab == "spam":
        stmt = stmt.where(or_(Email.category == "Spam", Email.status == "Ignored"))
    if q:
        stmt = stmt.where(or_(Email.subject.contains(q), Email.body.contains(q)))
    result = await db.execute(stmt.limit(200))
    emails = result.scalars().all()
    return {"emails": [
        {
            "id": e.id, "message_id": e.message_id, "thread_fk": e.thread_fk,
            "sender": e.sender, "subject": e.subject, "body": e.body[:300],
            "timestamp": e.timestamp.isoformat(), "category": e.category,
            "urgency": e.urgency, "sentiment_score": e.sentiment_score,
            "requires_human": e.requires_human, "status": e.status, "confidence": e.confidence,
        }
        for e in emails
    ]}


@router.post("/respond/{email_id}")
async def respond(email_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    email = await db.get(Email, email_id)
    if not email:
        raise AppError("NOT_FOUND", "Email not found", status=404)
    content = body.get("content", "")
    email.status = "Replied"
    db.add(AuditLog(entity_type="email", entity_id=str(email_id), action="reply_sent", performed_by=body.get("user", "user"), diff={"content": content[:200]}))
    await db.commit()
    await broadcast({"type": "email_updated", "email_id": email_id})
    return {"email_id": email_id, "status": "Replied"}


@router.patch("/drafts/{draft_id}")
async def edit_draft(draft_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise AppError("NOT_FOUND", "Draft not found", status=404)
    draft.content = body.get("content", draft.content)
    await db.commit()
    return {"id": draft.id, "content": draft.content}


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    draft = await db.get(Draft, draft_id)
    if not draft:
        raise AppError("NOT_FOUND", "Draft not found", status=404)
    draft.status = "approved"
    email = await db.get(Email, draft.email_id)
    if email:
        email.status = "Replied"
    db.add(AuditLog(entity_type="draft", entity_id=str(draft_id), action="approved", performed_by=body.get("approved_by", "user"), diff={}))
    await db.commit()
    return {"draft_id": draft_id, "status": "sent"}


@router.get("/analytics/sentiment-trend")
async def sentiment_trend(
    sender: str | None = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    series = await sentiment_trend_series(db, sender, days)
    return {"sender": sender, "days": days, "series": series}


@router.get("/analytics/category-breakdown")
async def category_breakdown(days: int = Query(30), db: AsyncSession = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(select(Email.category, func.count(Email.id)).where(Email.timestamp >= since).group_by(Email.category))
    rows = result.all()
    return {"days": days, "breakdown": {c or "Unknown": n for c, n in rows}}


@router.get("/analytics/response-heatmap")
async def response_heatmap(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Email).where(Email.status == "Replied"))
    emails = result.scalars().all()
    heat = [0] * 24
    for e in emails:
        heat[e.timestamp.hour] += 1
    return {"heatmap_by_hour": heat}


@router.get("/analytics/at-risk")
async def at_risk(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=48)
    contacts = (await db.execute(select(Contact).where(Contact.churn_risk_score > 0.5))).scalars().all()
    stale = (await db.execute(select(Thread).where(Thread.status == "Open", Thread.last_updated_at < cutoff))).scalars().all()
    return {
        "high_churn_risk": [{"email": c.email, "score": c.churn_risk_score, "account_value": c.account_value} for c in contacts],
        "stale_threads_48h": [{"thread_id": t.thread_id, "sender": t.sender_email} for t in stale],
    }


@router.get("/analytics/agent-performance")
async def agent_performance(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Email.id))) or 1
    auto = await db.scalar(select(func.count(Action.id)).where(Action.action_type == "Auto-Reply")) or 0
    esc = await db.scalar(select(func.count(Action.id)).where(Action.action_type == "Escalate")) or 0
    avg_conf = await db.scalar(select(func.avg(Email.confidence)).where(Email.confidence.isnot(None))) or 0
    return {
        "auto_reply_rate": round(auto / total, 3),
        "escalation_rate": round(esc / total, 3),
        "average_confidence": round(float(avg_conf), 3),
    }


@router.get("/rag/search")
async def rag_search_endpoint(q: str = Query(...), db: AsyncSession = Depends(get_db)):
    chunks = await search_knowledge(db, q, top_k=3)
    return {"query": q, "chunks": chunks}


@router.get("/intelligence/reputation")
async def reputation(entity: str = "MyCompany", db: AsyncSession = Depends(get_db)):
    return await fetch_reputation(db, entity)


@router.post("/agent/dry-run/{email_id}")
async def agent_dry_run(email_id: int, db: AsyncSession = Depends(get_db)):
    email = await db.get(Email, email_id)
    if not email:
        raise AppError("NOT_FOUND", "Email not found", status=404)
    heur = run_heuristics(email.sender, email.subject, email.body)
    hist = (await db.execute(select(Email).where(Email.thread_fk == email.thread_fk, Email.id != email.id))).scalars().all()
    history = [{"sender": e.sender, "subject": e.subject, "body": e.body, "timestamp": e.timestamp.isoformat()} for e in hist]
    rag_chunks = await rag_search(db, f"{email.subject} {email.body}")
    from app.services.llm import classify_email as clf
    classification = await clf(email.sender, email.subject, email.body, history, rag_chunks, heur)
    web = None
    if "trustpilot" in email.body.lower():
        web = (await fetch_reputation(db))["data"]
    result = await run_agent(db, email, classification, heur, rag_chunks, web, dry_run=True)
    return {"email_id": email_id, "classification": classification.model_dump(), **result}


@router.get("/audit/{entity_type}/{entity_id}")
async def audit_history(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.timestamp.desc())
    )
    logs = result.scalars().all()
    return {"entries": [
        {"id": l.id, "action": l.action, "performed_by": l.performed_by, "timestamp": l.timestamp.isoformat(), "diff": l.diff}
        for l in logs
    ]}


@router.get("/contacts/{email}")
async def get_contact(email: str, db: AsyncSession = Depends(get_db)):
    email = email.lower()
    c = (await db.execute(select(Contact).where(Contact.email == email))).scalar_one_or_none()
    if not c:
        raise AppError("NOT_FOUND", "Contact not found", status=404)
    threads = (await db.execute(select(Thread).where(Thread.sender_email == email))).scalars().all()
    return {
        "email": c.email, "name": c.name, "company": c.company, "status": c.status,
        "account_value": c.account_value, "churn_risk_score": c.churn_risk_score,
        "open_threads": [t.thread_id for t in threads if t.status == "Open"],
    }


@router.patch("/contacts/{email}/status")
async def patch_contact_status(email: str, body: dict, db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(Contact).where(Contact.email == email.lower()))).scalar_one_or_none()
    if not c:
        raise AppError("NOT_FOUND", "Contact not found", status=404)
    old = c.status
    c.status = body.get("status", c.status)
    db.add(AuditLog(entity_type="contact", entity_id=email, action="status_update", performed_by="user", diff={"old": old, "new": c.status}))
    await db.commit()
    return {"email": c.email, "status": c.status}


@router.post("/api/stream/start")
async def stream_start(rate: float = Query(1.0)):
    ok = start_stream_background(rate)
    return {"started": ok, "rate": rate}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


@router.post("/emails/{email_id}/bulk")
async def bulk_action(email_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    email = await db.get(Email, email_id)
    if not email:
        raise AppError("NOT_FOUND", "Email not found", status=404)
    action = body.get("action")
    if action == "spam":
        email.category, email.status = "Spam", "Ignored"
    elif action == "archive":
        thread = await db.get(Thread, email.thread_fk)
        if thread:
            thread.status = "Resolved"
    elif action == "assign":
        thread = await db.get(Thread, email.thread_fk)
        if thread:
            thread.assigned_to = body.get("assignee")
    await db.commit()
    return {"ok": True}
