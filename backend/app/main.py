import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.core.config import settings
from app.models.database import engine, Base, SessionLocal
from app.models import entities  # noqa: F401
from app.services.rag import seed_knowledge_base
from fastapi import HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_knowledge_base(db)
    yield


app = FastAPI(
    title="SenAI Agentic CRM",
    description="AI-powered CRM with RAG, autonomous agent, and real-time email operations",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "openai_configured": bool(settings.openai_api_key)}
