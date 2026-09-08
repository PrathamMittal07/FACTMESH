"""FactMesh configuration - loads settings from backend/.env"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://factmesh:factmesh@localhost:5432/factmesh",
        alias="DATABASE_URL",
    )

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Gemini model to use (default: flash for speed + cost, override to pro for quality)
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
