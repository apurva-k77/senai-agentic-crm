"""Live web intelligence — cached public reputation signals."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import WebIntelligenceCache

# Simulated scrape results for assessment demo (production: httpx + BeautifulSoup)
MOCK_REPUTATION = {
    "MyCompany": {
        "g2_rating": 4.1,
        "g2_reviews": 128,
        "trustpilot_rating": 3.8,
        "trustpilot_reviews": 89,
        "recent_mentions": ["support delays mentioned in 2 reviews", "pricing praised"],
        "summary": "G2 4.1/5 (128 reviews), Trustpilot 3.8/5 — recent support delay complaints",
    },
    "Retail Co": {"summary": "Competitor context for retention brief"},
}


async def fetch_reputation(db: AsyncSession, entity: str = "MyCompany") -> dict:
    now = datetime.utcnow()
    result = await db.execute(
        select(WebIntelligenceCache)
        .where(WebIntelligenceCache.target_entity == entity, WebIntelligenceCache.expires_at > now)
        .order_by(WebIntelligenceCache.scraped_at.desc())
        .limit(1)
    )
    cached = result.scalar_one_or_none()
    if cached:
        return {"source": "cache", "data": cached.scraped_data, "scraped_at": cached.scraped_at.isoformat()}

    data = MOCK_REPUTATION.get(entity, MOCK_REPUTATION["MyCompany"])
    entry = WebIntelligenceCache(
        source_url="https://www.g2.com/products/mycompany/reviews",
        target_entity=entity,
        scraped_data=data,
        scraped_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(entry)
    await db.commit()
    return {"source": "fresh", "data": data, "scraped_at": now.isoformat()}
