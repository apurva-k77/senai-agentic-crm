from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import KnowledgeChunk
from app.services.embeddings import cosine_similarity, embed_text


async def seed_knowledge_base(db: AsyncSession):
    result = await db.execute(select(KnowledgeChunk).limit(1))
    if result.scalar_one_or_none():
        return
    kb_dir = Path(settings.knowledge_dir)
    for path in kb_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 40]
        for i, chunk in enumerate(chunks):
            db.add(KnowledgeChunk(
                source_doc=f"{path.name}#chunk{i}",
                chunk_text=chunk,
                embedding=embed_text(chunk),
            ))
    await db.commit()


async def search_knowledge(db: AsyncSession, query: str, top_k: int = 3) -> list[dict]:
    q_emb = embed_text(query)
    result = await db.execute(select(KnowledgeChunk))
    chunks = result.scalars().all()
    scored = []
    for c in chunks:
        score = cosine_similarity(q_emb, c.embedding or [])
        scored.append({"id": c.id, "source_doc": c.source_doc, "chunk_text": c.chunk_text, "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
