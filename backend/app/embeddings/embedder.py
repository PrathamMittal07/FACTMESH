"""Embedding service using local sentence-transformers (all-mpnet-base-v2).

Creates vector embeddings for facts to enable similarity search via pgvector.
"""

import logging

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level model cache — loaded once, reused across calls
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazily load the embedding model (cached after first call)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info(f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


def build_fact_text(
    entity: str | None,
    metric: str | None,
    value: str | None,
    unit: str | None,
    time_period: str | None,
    scope: str | None,
    evidence_quote: str | None = None,
) -> str:
    """Build a composite text representation of a fact for embedding.

    Combines the structured fields into a single string that captures
    the semantic meaning for similarity comparison.
    """
    parts = []
    if entity:
        parts.append(entity)
    if metric:
        parts.append(metric)
    if value:
        parts.append(str(value))
    if unit:
        parts.append(unit)
    if time_period:
        parts.append(time_period)
    if scope:
        parts.append(scope)

    text = " ".join(parts)

    # If the structured fields produce a very short string, supplement
    # with the evidence quote for better semantic signal
    if len(text) < 20 and evidence_quote:
        text = f"{text} — {evidence_quote[:150]}"

    return text if text else "unknown fact"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings into vectors.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors (each is a list of floats).
    """
    if not texts:
        return []

    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=len(texts) > 50)
    return [emb.tolist() for emb in embeddings]


def embed_single(text: str) -> list[float]:
    """Embed a single text string into a vector."""
    return embed_texts([text])[0]
