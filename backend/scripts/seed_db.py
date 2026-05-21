"""Load all emails from dataset into the CRM."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.database import SessionLocal, engine, Base
from app.models import entities  # noqa
from app.schemas.email import IngestEmailPayload
from app.services.ingest import ingest_email
from app.services.rag import seed_knowledge_base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    path = Path(__file__).resolve().parents[2] / "data" / "email-data-advanced.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    async with SessionLocal() as db:
        await seed_knowledge_base(db)
        for item in sorted(data["emails"], key=lambda x: x["timestamp"]):
            try:
                await ingest_email(db, IngestEmailPayload(**item))
            except Exception as e:
                if "duplicate" not in str(e).lower():
                    print(f"Skip {item['message_id']}: {e}")
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
