"""Replay dataset at configurable rate."""
import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.models.database import SessionLocal
from app.schemas.email import IngestEmailPayload
from app.services.ingest import ingest_email

_stream_task: asyncio.Task | None = None


async def replay_dataset(rate: float | None = None):
    global _stream_task
    rate = rate or settings.stream_rate
    path = Path(settings.stream_dataset)
    data = json.loads(path.read_text(encoding="utf-8"))
    emails = sorted(data["emails"], key=lambda e: e.get("timestamp", ""))
    interval = 1.0 / max(rate, 0.1)

    async with SessionLocal() as db:
        for item in emails:
            payload = IngestEmailPayload(**item)
            try:
                await ingest_email(db, payload)
            except Exception:
                pass
            await asyncio.sleep(interval)


def start_stream_background(rate: float | None = None):
    global _stream_task
    if _stream_task and not _stream_task.done():
        return False
    _stream_task = asyncio.create_task(replay_dataset(rate))
    return True
