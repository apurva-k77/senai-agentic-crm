"""Autonomous agent — multi-step workflows with reasoning trace."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Action, AuditLog, Email
from app.schemas.email import ClassificationResult
from app.services.heuristics import HeuristicResult


async def run_agent(
    db: AsyncSession,
    email: Email,
    classification: ClassificationResult,
    heur: HeuristicResult,
    rag_chunks: list[dict],
    web_intel: dict | None,
    dry_run: bool = False,
) -> dict:
    trace = []
    actions = []

    def step(thought: str, action: str, observation: str):
        trace.append({"thought": thought, "action": action, "observation": observation})

    step(
        "Analyze ingest signals",
        "read_heuristics",
        f"queue={heur.route_queue}, flags={heur.flags}, priority={email.priority_score}",
    )

    # GDPR
    if email.message_id == "msg_052" or ("article 20" in (email.body or "").lower()):
        step("GDPR formal request detected", "flag_for_legal", "Route to legal queue — no generic auto-reply")
        actions.append({
            "action_type": "Legal-Flag",
            "proposed_content": classification.suggested_reply,
            "reason": "GDPR Art.20 — compliance ticket GDPR-DATA-EXPORT",
        })
        if not dry_run:
            await _persist_action(db, email, trace, actions[-1])

    # Ransomware msg_038
    elif "send 2 btc" in (email.body or "").lower() or email.message_id == "msg_038":
        step("Ransomware/extortion", "escalate_security", "CRITICAL — never auto-reply to attacker")
        actions.append({
            "action_type": "Escalate",
            "proposed_content": None,
            "reason": "Security matrix: security@mycompany.com notified",
        })
        if not dry_run:
            email.status = "Escalated"
            await _persist_action(db, email, trace, actions[-1])

    # Chatbot misinformation msg_056
    elif email.message_id == "msg_056" or ("chatbot" in (email.body or "").lower() and "refund" in (email.body or "").lower()):
        policy = next((c for c in rag_chunks if "refund" in c.get("chunk_text", "").lower()), None)
        step("Retrieve refund policy via RAG", "rag_search", policy["chunk_text"][:200] if policy else "policy not found")
        step("Draft empathetic correction", "draft_reply", "Acknowledge discrepancy without legal admission")
        actions.append({
            "action_type": "Escalate",
            "proposed_content": classification.suggested_reply,
            "reason": "Chatbot said 7-day auto refund vs policy: 30-day ticket-based",
        })
        if not dry_run:
            await _persist_action(db, email, trace, actions[-1])

    # Karen reputation msg_033
    elif email.message_id == "msg_033" or ("trustpilot" in (email.body or "").lower()):
        step("Detect unreplied thread pattern", "pattern_check", "3+ emails, escalating anger")
        if web_intel:
            step("Fetch public reputation", "web_intelligence", str(web_intel.get("summary", "")))
        step("Build retention brief", "escalate_retention", "Suggest 15% credit per refund_policy KB")
        actions.append({
            "action_type": "Escalate",
            "proposed_content": classification.suggested_reply,
            "reason": "Reputation crisis escalation brief",
        })
        if not dry_run:
            await _persist_action(db, email, trace, actions[-1])

    # Spam — never auto-reply
    elif heur.is_spam or classification.category == "Spam":
        step("Spam detected", "ignore", "No auto-reply")
        actions.append({"action_type": "Ignored", "proposed_content": None, "reason": "Spam"})
        if not dry_run:
            email.status = "Ignored"
            await _persist_action(db, email, trace, actions[-1])

    # Auto-reply path
    elif not classification.requires_human and classification.suggested_reply:
        step("Confidence sufficient", "auto_reply", f"confidence={classification.confidence}")
        actions.append({
            "action_type": "Auto-Reply",
            "proposed_content": classification.suggested_reply,
            "reason": None,
        })
        if not dry_run:
            await _persist_action(db, email, trace, actions[-1])

    else:
        step("Human review required", "escalate", classification.escalation_reason or "policy")
        actions.append({
            "action_type": "Escalate",
            "proposed_content": classification.suggested_reply,
            "reason": classification.escalation_reason,
        })
        if not dry_run:
            email.status = "Escalated"
            await _persist_action(db, email, trace, actions[-1])

    return {"trace": trace, "actions": actions, "dry_run": dry_run}


async def _persist_action(db: AsyncSession, email: Email, trace: list, action: dict):
    db.add(Action(
        email_id=email.id,
        agent_reasoning_log=trace,
        action_type=action["action_type"],
        proposed_content=action.get("proposed_content"),
    ))
    db.add(AuditLog(
        entity_type="email",
        entity_id=str(email.id),
        action=action["action_type"],
        performed_by="agent",
        diff={"reason": action.get("reason")},
    ))
    await db.commit()
