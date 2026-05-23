"""Application configuration.

All settings are loaded from environment variables (or a `.env` file).
Provider selection is env-driven so backends can be swapped without code changes.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Provider selection (factory keys) ===
    LLM_PROVIDER: str = "groq"
    EMBEDDING_PROVIDER: str = "sentence_transformers"
    VECTOR_STORE: str = "chroma"
    CHAT_HISTORY_STORE: str = "mongodb"

    # === Secrets / connections (validated at point-of-use, not import) ===
    GROQ_API_KEY: str = ""
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "rag_chatbot"

    # === Models ===
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # === RAG tuning ===
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K: int = 4
    HISTORY_TURNS: int = 6
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 1024

    # === Storage ===
    CHROMA_PATH: str = "./chroma_db"
    UPLOAD_DIR: str = "./uploads"
    CHROMA_COLLECTION: str = "documents"

    # === Upload limits ===
    MAX_UPLOAD_MB: int = 20

    # === CORS ===
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
