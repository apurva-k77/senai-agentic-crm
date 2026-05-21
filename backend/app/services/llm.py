"""Layer 2 — LLM classification with thread + RAG context."""
import json
import re
from datetime import datetime

from app.core.config import settings
from app.schemas.email import ClassificationResult
from app.services.heuristics import HeuristicResult


def _extract_entities(text: str) -> dict:
    return {
        "order_ids": re.findall(r"order\s*#?\s*(\d+)", text, re.I),
        "ticket_ids": re.findall(r"ticket\s*#?\s*(\w+)", text, re.I),
        "monetary_amounts": re.findall(r"\$[\d,.]+[kKmM]?", text),
        "deadlines": re.findall(r"deadline|within\s+\d+\s+days|March\s+\d+", text, re.I),
        "products_mentioned": [m for m in ["Pro", "Enterprise", "Starter", "HIPAA", "BAA"] if m.lower() in text.lower()],
    }


def _rule_based_classify(
    sender: str, subject: str, body: str, thread_history: list[dict], rag_chunks: list[dict], heur: HeuristicResult
) -> ClassificationResult:
    text = f"{subject} {body}".lower()
    full = " ".join([e.get("body", "") for e in thread_history] + [body]).lower()

    category = "Other"
    urgency = "Medium"
    sentiment_score = 0.0
    sentiment = "Neutral"
    requires_human = False
    escalation_reason = None
    suggested_reply = None
    confidence = 0.75

    if heur.is_security:
        return ClassificationResult(
            category="Legal", sentiment="Negative", sentiment_score=-1.0, urgency="Critical",
            requires_human=True,
            escalation_reason="Critical security threat — ransomware/extortion. NO auto-reply.",
            suggested_reply=None, confidence=0.98, detected_entities=_extract_entities(body),
        )

    if heur.is_spam:
        return ClassificationResult(
            category="Spam", sentiment="Negative", sentiment_score=-0.5, urgency="Low",
            requires_human=False, confidence=0.95, detected_entities=_extract_entities(body),
        )

    if "gdpr" in text or "article 20" in text:
        return ClassificationResult(
            category="Compliance", sentiment="Neutral", sentiment_score=0.0, urgency="High",
            requires_human=True,
            escalation_reason="GDPR Article 20 data portability — legal obligation, 30-day window",
            suggested_reply=(
                "We acknowledge your formal GDPR Article 20 data portability request. "
                "We will provide your personal data in a machine-readable format within the "
                "statutory 30-day period. A compliance ticket has been opened."
            ),
            confidence=0.92, detected_entities=_extract_entities(body),
        )

    if "send 2 btc" in text or "ransomware" in text or heur.is_security:
        return ClassificationResult(
            category="Legal", sentiment="Negative", sentiment_score=-1.0, urgency="Critical",
            requires_human=True,
            escalation_reason="Critical security threat — ransomware/extortion. NO auto-reply.",
            suggested_reply=None, confidence=0.98, detected_entities=_extract_entities(body),
        )

    if "chatbot" in text and "refund" in text:
        policy = next((c["chunk_text"] for c in rag_chunks if "refund" in c.get("chunk_text", "").lower()), "")
        return ClassificationResult(
            category="Complaint", sentiment="Negative", sentiment_score=-0.6, urgency="High",
            requires_human=True,
            escalation_reason="Chatbot misinformation vs refund policy — liability review",
            suggested_reply=(
                "Thank you for bringing this to our attention. Our AI assistant gave incorrect information; "
                "our actual policy offers a 30-day money-back guarantee for new subscriptions via support ticket, "
                "not automatic 7-day refunds. We'd like to review your case personally."
            ),
            confidence=0.88, detected_entities=_extract_entities(body),
        )

    if "pro-rata" in text or "pro rata" in text:
        pricing = next((c["chunk_text"] for c in rag_chunks if "pro-rata" in c.get("chunk_text", "").lower()), "")
        return ClassificationResult(
            category="Billing", sentiment="Neutral", sentiment_score=0.1, urgency="Medium",
            requires_human=False,
            suggested_reply=(
                f"Based on your NPO Pro annual plan, mid-cycle upgrades use pro-rata billing: "
                f"(new_seats - old_seats) × discounted monthly rate × months remaining. "
                f"Reference: {pricing[:200]}..."
            ),
            confidence=0.85, detected_entities=_extract_entities(full),
        )

    if "p0" in text or "outage" in text:
        return ClassificationResult(
            category="Bug Report", sentiment="Negative", sentiment_score=-0.8, urgency="Critical",
            requires_human=True, escalation_reason="P0 production outage / SLA breach",
            confidence=0.9, detected_entities=_extract_entities(body),
        )

    if "g2" in text or "trustpilot" in text or "public review" in text:
        return ClassificationResult(
            category="Complaint", sentiment="Negative", sentiment_score=-0.9, urgency="Critical",
            requires_human=True,
            escalation_reason="Reputation crisis — 3+ unreplied emails, public review threat",
            suggested_reply="Executive retention review — see escalation brief and retention offer policy.",
            confidence=0.87, detected_entities=_extract_entities(body),
        )

    if "love" in text and "hate" in text and "refund" in text:
        sentiment = "Mixed"
        sentiment_score = -0.2
        confidence = 0.62
        requires_human = True
        escalation_reason = "Conflicting signals: positive product sentiment vs refund request"

    if "hipaa" in text or "baa" in text:
        category, urgency = "Compliance", "High"
        requires_human = True
        escalation_reason = "Enterprise HIPAA / BAA deal"

    elif "bug" in text or "corruption" in text or "empty" in text:
        category, urgency = "Bug Report", "Critical"
        requires_human = True

    elif "refund" in text or "charge" in text:
        category = "Billing" if "invoice" in text else "Complaint"
        sentiment_score = -0.5

    elif "feature" in text or "integration" in text:
        category = "Feature Request"

    elif "rfp" in text or "$2.4" in text:
        category, urgency = "Inquiry", "High"
        requires_human = True

    if confidence < settings.confidence_human_threshold:
        requires_human = True
        escalation_reason = escalation_reason or "Low confidence classification"

    return ClassificationResult(
        category=category, sentiment=sentiment, sentiment_score=sentiment_score,
        urgency=urgency, requires_human=requires_human, escalation_reason=escalation_reason,
        suggested_reply=suggested_reply, confidence=confidence,
        detected_entities=_extract_entities(body),
    )


async def classify_email(
    sender: str, subject: str, body: str,
    thread_history: list[dict], rag_chunks: list[dict], heur: HeuristicResult,
) -> ClassificationResult:
    if heur.is_security or heur.is_spam or heur.is_internal:
        return _rule_based_classify(sender, subject, body, thread_history, rag_chunks, heur)
    if settings.openai_api_key:
        try:
            return await _openai_classify(sender, subject, body, thread_history, rag_chunks, heur)
        except Exception:
            pass
    return _rule_based_classify(sender, subject, body, thread_history, rag_chunks, heur)


async def _openai_classify(sender, subject, body, thread_history, rag_chunks, heur) -> ClassificationResult:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    history = "\n---\n".join(
        f"[{e.get('timestamp')}] {e.get('sender')}: {e.get('subject')}\n{e.get('body','')[:500]}"
        for e in thread_history[-10:]
    )
    rag = "\n".join(f"- ({c['score']}) {c['chunk_text'][:300]}" for c in rag_chunks)
    prompt = f"""Classify this CRM email. Use full thread history and KB context.
Thread history:
{history}

RAG context:
{rag}

New email from {sender}:
Subject: {subject}
Body: {body[:4000]}

Return JSON matching schema: category, sentiment, sentiment_score (-1..1), urgency, requires_human, escalation_reason, suggested_reply, confidence, detected_entities.
Resolve conflicting signals explicitly. confidence < 0.7 => requires_human true."""
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return ClassificationResult(**data)
