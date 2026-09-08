"""Candidate-pair matcher using pgvector cosine similarity.

Finds facts that are semantically similar enough to warrant
reconciliation by the LLM (Gemini), without comparing every
fact to every other fact.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


async def find_candidate_pairs(
    session: AsyncSession,
    fact_id: uuid.UUID,
    k: int | None = None,
    threshold: float | None = None,
    exclude_same_document: bool = False,
) -> list[dict]:
    """Find the K nearest neighbor facts by cosine similarity.

    Args:
        session: Async database session.
        fact_id: The fact to find neighbors for.
        k: Max number of neighbors (default from settings).
        threshold: Min cosine similarity (default from settings).
        exclude_same_document: If True, skip facts from the same document.

    Returns:
        List of dicts with keys: fact_id, similarity, entity, metric, value,
        time_period, scope, document_id, page_number, evidence_quote.
    """
    if k is None:
        k = settings.similarity_k
    if threshold is None:
        threshold = settings.similarity_threshold

    # Build the query using pgvector's <=> operator (cosine distance)
    # cosine_similarity = 1 - cosine_distance
    query_parts = [
        """
        SELECT
            f2.id as fact_id,
            1 - (f1.embedding <=> f2.embedding) as similarity,
            f2.entity,
            f2.metric,
            f2.value,
            f2.unit,
            f2.time_period,
            f2.scope,
            f2.document_id,
            f2.page_number,
            f2.evidence_quote,
            f2.fact_type,
            f2.confidence
        FROM facts f1, facts f2
        WHERE f1.id = :fact_id
          AND f2.id != :fact_id
          AND f1.embedding IS NOT NULL
          AND f2.embedding IS NOT NULL
          AND 1 - (f1.embedding <=> f2.embedding) >= :threshold
        """
    ]

    if exclude_same_document:
        query_parts.append("AND f2.document_id != f1.document_id")

    query_parts.append(
        """
        ORDER BY f1.embedding <=> f2.embedding
        LIMIT :k
        """
    )

    query = text("".join(query_parts))

    result = await session.execute(
        query,
        {"fact_id": str(fact_id), "threshold": threshold, "k": k},
    )

    candidates = []
    for row in result.mappings():
        candidates.append(
            {
                "fact_id": row["fact_id"],
                "similarity": float(row["similarity"]),
                "entity": row["entity"],
                "metric": row["metric"],
                "value": row["value"],
                "unit": row["unit"],
                "time_period": row["time_period"],
                "scope": row["scope"],
                "document_id": row["document_id"],
                "page_number": row["page_number"],
                "evidence_quote": row["evidence_quote"],
                "fact_type": row["fact_type"],
                "confidence": float(row["confidence"]) if row["confidence"] else None,
            }
        )

    logger.info(
        f"Found {len(candidates)} candidate pairs for fact {fact_id} "
        f"(k={k}, threshold={threshold})"
    )
    return candidates


async def find_all_candidate_pairs(
    session: AsyncSession,
    document_id: uuid.UUID | None = None,
    k: int | None = None,
    threshold: float | None = None,
) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    """Find all candidate pairs across the entire fact store (or for a specific document).

    Used after ingesting a new document to find which of its facts
    should be reconciled against existing facts.

    Args:
        session: Async database session.
        document_id: If provided, only find pairs involving facts from this document.
        k: Max neighbors per fact.
        threshold: Min cosine similarity.

    Returns:
        List of (fact_a_id, fact_b_id, similarity) tuples, deduplicated
        so each pair appears only once.
    """
    if k is None:
        k = settings.similarity_k
    if threshold is None:
        threshold = settings.similarity_threshold

    # Get all facts (optionally filtered by document) that have embeddings
    if document_id:
        facts_query = text(
            "SELECT id FROM facts WHERE document_id = :doc_id AND embedding IS NOT NULL"
        )
        result = await session.execute(facts_query, {"doc_id": str(document_id)})
    else:
        facts_query = text("SELECT id FROM facts WHERE embedding IS NOT NULL")
        result = await session.execute(facts_query)

    fact_ids = [row[0] for row in result.fetchall()]
    logger.info(f"Finding candidate pairs for {len(fact_ids)} facts")

    seen_pairs: set[tuple] = set()
    all_pairs: list[tuple[uuid.UUID, uuid.UUID, float]] = []

    for fid in fact_ids:
        candidates = await find_candidate_pairs(
            session, fid, k=k, threshold=threshold, exclude_same_document=True
        )
        for c in candidates:
            # Deduplicate: normalize pair ordering
            pair_key = tuple(sorted([str(fid), str(c["fact_id"])]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                all_pairs.append((fid, c["fact_id"], c["similarity"]))

    logger.info(f"Found {len(all_pairs)} unique candidate pairs")
    return all_pairs
