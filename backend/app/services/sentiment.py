"""Layer 3 — sentiment trend tracking per sender."""
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Email


async def update_sender_trend(db: AsyncSession, sender: str, new_score: float) -> dict | None:
    """Return escalation alert if 3+ consecutive negative emails."""
    since = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(Email)
        .where(Email.sender == sender, Email.timestamp >= since, Email.sentiment_score.isnot(None))
        .order_by(Email.timestamp.desc())
        .limit(10)
    )
    emails = list(result.scalars().all())
    if not emails:
        return None
    scores = [e.sentiment_score for e in reversed(emails)]
    window = 5
    moving_avg = sum(scores[-window:]) / min(len(scores), window)
    consecutive_neg = 0
    for e in emails:
        if (e.sentiment_score or 0) < -0.3:
            consecutive_neg += 1
        else:
            break
    alert = None
    if consecutive_neg >= 3:
        alert = {
            "type": "sentiment_deterioration",
            "sender": sender,
            "consecutive_negative": consecutive_neg,
            "message": f"{sender}: {consecutive_neg} consecutive negative emails — escalation recommended",
        }
    return {"moving_average": round(moving_avg, 3), "samples": len(scores), "alert": alert}


async def sentiment_trend_series(db: AsyncSession, sender: str | None = None, days: int = 30) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=days)
    q = select(Email).where(Email.timestamp >= since, Email.sentiment_score.isnot(None))
    if sender:
        q = q.where(Email.sender == sender)
    q = q.order_by(Email.timestamp)
    result = await db.execute(q)
    emails = result.scalars().all()
    by_day: dict[str, list[float]] = defaultdict(list)
    for e in emails:
        key = e.timestamp.strftime("%Y-%m-%d")
        by_day[key].append(e.sentiment_score)
    series = []
    for day in sorted(by_day.keys()):
        vals = by_day[day]
        series.append({"date": day, "avg_sentiment": round(sum(vals) / len(vals), 3), "count": len(vals)})
    return series
