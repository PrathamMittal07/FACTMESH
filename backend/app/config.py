"""FactMesh configuration - loads settings from backend/.env"""

from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field

# Absolute path to backend/.env — works regardless of the process CWD
# (repo root, backend/, or anywhere else).
_BACKEND_ENV = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://factmesh:factmesh@localhost:5432/factmesh",
        alias="DATABASE_URL",
    )

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Gemini model to use (default: gemini-3.6-flash (latest fast), override to gemini-2.5-pro for highest quality)
    gemini_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_MODEL")

    # Embedding model (local sentence-transformers, no API key needed)
    embedding_model: str = Field(default="all-mpnet-base-v2", alias="EMBEDDING_MODEL")

    # Similarity search tuning
    similarity_threshold: float = Field(default=0.65, alias="SIMILARITY_THRESHOLD")
    similarity_k: int = Field(default=10, alias="SIMILARITY_K")

    # Confidence thresholds
    confidence_flag_threshold: float = Field(
        default=0.6, alias="CONFIDENCE_FLAG_THRESHOLD"
    )
    confidence_reject_threshold: float = Field(
        default=0.3, alias="CONFIDENCE_REJECT_THRESHOLD"
    )

    # LLM quota pacing (free-tier keys are rate-limited, e.g. 20 req/min)
    llm_batch_delay_sec: float = Field(default=4.0, alias="LLM_BATCH_DELAY_SEC")
    llm_max_retries: int = Field(default=6, alias="LLM_MAX_RETRIES")
    llm_retry_base_sec: float = Field(default=10.0, alias="LLM_RETRY_BASE_SEC")

    model_config = {
        "env_file": str(_BACKEND_ENV),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
