"""NFRA Compliance Engine — FastAPI application entry point."""

import asyncio
import logging
import time as _time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.routers.analytics import router as analytics_router
from app.routers.chat import router as chat_router
from app.routers.compliance import router as compliance_router
from app.routers.examination import router as examination_router
from app.routers.ingest import router as ingest_router
from app.routers.reports import router as reports_router
from app.routers.search import router as search_router
from app.services.analytics_engine import AnalyticsEngine
from app.services.compliance_engine import ComplianceEngine
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.examination_tool import ExaminationTool
from app.services.llm_service import LLMService
from app.services.mongo_service import MongoService
from app.services.report_generator import ReportGenerator
from app.services.vector_store import VectorStoreService
from app.pipelines.compliance_pipeline import CompliancePipeline
from app.pipelines.ingest_pipeline import IngestPipeline
from app.utils.chunking import ComplianceChunker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared services on startup; tear down on shutdown."""
    settings = get_settings()

    # ── MongoDB (optimised for Atlas) ────────────────────────────────────
    mongo_client: AsyncIOMotorClient = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=20,
        minPoolSize=5,
        maxIdleTimeMS=45_000,
        connectTimeoutMS=10_000,
        serverSelectionTimeoutMS=10_000,
        socketTimeoutMS=20_000,
        retryWrites=True,
        retryReads=True,
    )
    db = mongo_client[settings.MONGODB_DB_NAME]
    app.state.mongo_client = mongo_client
    app.state.db = db

    # Warm up the connection pool so first user request is fast
    try:
        await db.command("ping")
    except Exception:
        pass

    # ── MongoService ────────────────────────────────────────────────────
    mongo_service = MongoService(db)
    app.state.mongo_service = mongo_service
    await mongo_service.ensure_indexes()

    # ── VectorStoreService (ChromaDB) ───────────────────────────────────
    vector_store = VectorStoreService(persist_dir=settings.CHROMA_PERSIST_DIR)
    app.state.vector_store = vector_store

    # ── EmbeddingService (OpenAI) ───────────────────────────────────────
    embedding_service = EmbeddingService(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    app.state.embedding_service = embedding_service

    # ── LLMService (LangChain ChatOpenAI) ───────────────────────────────
    llm_service = LLMService(
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    app.state.llm_service = llm_service

    # ── DocumentProcessor (Unstructured) ────────────────────────────────
    document_processor = DocumentProcessor(
        api_key=settings.UNSTRUCTURED_API_KEY,
        api_url=settings.UNSTRUCTURED_API_URL,
    )
    app.state.document_processor = document_processor

    # ── IngestPipeline (processor → chunker → embeddings → store) ───────
    app.state.ingest_pipeline = IngestPipeline(
        document_processor=document_processor,
        embedding_service=embedding_service,
        vector_store=vector_store,
        mongo_service=mongo_service,
        chunker=ComplianceChunker(),
    )

    # ── ComplianceEngine (vector_store + embeddings + llm + mongo) ──────
    compliance_engine = ComplianceEngine(
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_service=llm_service,
        mongo_service=mongo_service,
    )
    app.state.compliance_engine = compliance_engine

    # ── CompliancePipeline (engine + mongo) ─────────────────────────────
    app.state.compliance_pipeline = CompliancePipeline(
        compliance_engine=compliance_engine,
        mongo_service=mongo_service,
    )

    # ── ReportGenerator (JSON / PDF / Excel) ──────────────────────────
    app.state.report_generator = ReportGenerator()

    # ── AnalyticsEngine (LangGraph agentic analytics) ────────────────
    app.state.analytics_engine = AnalyticsEngine(
        vector_store=vector_store,
        embedding_service=embedding_service,
        mongo_service=mongo_service,
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
    )

    # ── ExaminationTool (preliminary examination) ────────────────────
    app.state.examination_tool = ExaminationTool(
        mongo_service=mongo_service,
        vector_store=vector_store,
        embedding_service=embedding_service,
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
    )

    # Start background keep-alive ping to prevent Atlas connection going cold
    async def _keepalive():
        while True:
            await asyncio.sleep(120)
            try:
                await db.command("ping")
            except Exception:
                logger.debug("MongoDB keep-alive ping failed")

    keepalive_task = asyncio.create_task(_keepalive())

    yield

    # Shutdown
    keepalive_task.cancel()
    mongo_client.close()


app = FastAPI(
    title="NFRA Compliance Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
app.include_router(compliance_router, prefix="/api/compliance", tags=["compliance"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(examination_router, prefix="/api/examination", tags=["examination"])

# Create uploads directory if it doesn't exist, then mount
_uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for service availability."""
    return {"status": "healthy", "version": "0.1.0"}


_dashboard_cache: dict | None = None
_dashboard_cache_ts: float = 0
_DASHBOARD_CACHE_TTL = 10  # seconds


@app.get("/api/dashboard/stats")
async def dashboard_stats() -> dict:
    """Fast dashboard stats with server-side caching."""
    global _dashboard_cache, _dashboard_cache_ts

    now = _time.monotonic()
    if _dashboard_cache is not None and (now - _dashboard_cache_ts) < _DASHBOARD_CACHE_TTL:
        return _dashboard_cache

    mongo = app.state.mongo_service
    vs = app.state.vector_store

    try:
        docs_count, reports_count = await asyncio.gather(
            mongo.fast_count("documents"),
            mongo.fast_count("compliance_reports"),
        )
    except Exception:
        if _dashboard_cache is not None:
            return _dashboard_cache
        return {
            "documents_ingested": 0,
            "compliance_checks": 0,
            "average_score": 0,
            "active_frameworks": 0,
        }

    avg_score = 0.0
    if reports_count > 0:
        pipeline = [
            {"$group": {"_id": None, "avg": {"$avg": "$overall_compliance_score"}}},
        ]
        try:
            cursor = mongo._db["compliance_reports"].aggregate(pipeline)
            result = await cursor.to_list(length=1)
            if result:
                avg_score = round(result[0].get("avg", 0) or 0, 2)
        except Exception:
            pass

    fw_count = len(vs.list_collections())

    result_data = {
        "documents_ingested": docs_count,
        "compliance_checks": reports_count,
        "average_score": avg_score,
        "active_frameworks": fw_count,
    }

    _dashboard_cache = result_data
    _dashboard_cache_ts = now
    return result_data
