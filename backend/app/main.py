"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routes import chat as chat_routes
from app.routes import upload as upload_routes
from app.services.chat_history import get_history_store
from app.services.embeddings import get_embedder
from app.services.llm_service import get_llm
from app.services.vector_store import get_vector_store

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage dirs exist (gitignored, so absent on fresh clones).
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CHROMA_PATH).mkdir(parents=True, exist_ok=True)

    # Eagerly construct singletons so misconfig (bad URI, missing API key,
    # missing model) surfaces at startup rather than on the first request.
    # get_* are lru_cached — these calls warm the cache.
    get_embedder()
    get_vector_store()
    get_llm()
    get_history_store()

    yield

    # Cleanup
    try:
        get_history_store().close()  # type: ignore[attr-defined]
    except Exception:
        pass


app = FastAPI(
    title="RAG Chatbot API",
    description="Retrieval-Augmented Generation chatbot backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_routes.router)
app.include_router(chat_routes.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness + dependency status."""
    # MongoDB
    try:
        mongo_ok = await get_history_store().ping()
        mongodb_status = "connected" if mongo_ok else "unreachable"
    except Exception as e:
        mongodb_status = f"error: {type(e).__name__}"

    # Vector store
    try:
        _ = get_vector_store().count()
        vs_status = "ready"
    except Exception as e:
        vs_status = f"error: {type(e).__name__}"

    # LLM (just check the provider is constructed; we don't make a real API call)
    try:
        get_llm()
        llm_status = "configured"
    except Exception as e:
        llm_status = f"error: {type(e).__name__}"

    return HealthResponse(
        status="ok",
        mongodb=mongodb_status,
        vector_store=vs_status,
        llm=llm_status,
    )
