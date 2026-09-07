"""Relationships API routes — browse and filter cross-document relationships."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Fact, Document, Relationship
from app.schemas.models import RelationshipOut, FactOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/relationships", tags=["relationships"])


@router.get("", response_model=list[RelationshipOut])
async def list_relationships(
    db: AsyncSession = Depends(get_db),
    relationship_type: str | None = Query(None, description="Filter by type: corroborates, contradicts, contextual_difference"),
    min_confidence: float | None = Query(None, description="Minimum confidence"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Browse all relationships, filterable by type."""
    query = select(Relationship)

    if relationship_type:
        query = query.where(Relationship.relationship_type == relationship_type)
    if min_confidence is not None:
        query = query.where(Relationship.confidence >= min_confidence)

    query = query.order_by(Relationship.confidence.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    relationships = result.scalars().all()

    out = []
    for rel in relationships:
        # Load full fact data for both sides
        fa = await db.execute(select(Fact).where(Fact.id == rel.fact_a_id))
        fb = await db.execute(select(Fact).where(Fact.id == rel.fact_b_id))
        fact_a = fa.scalar_one_or_none()
        fact_b = fb.scalar_one_or_none()

        fa_doc = await db.execute(select(Document.filename).where(Document.id == fact_a.document_id)) if fact_a else None
        fb_doc = await db.execute(select(Document.filename).where(Document.id == fact_b.document_id)) if fact_b else None

        out.append(
            RelationshipOut(
                id=rel.id,
                fact_a_id=rel.fact_a_id,
                fact_b_id=rel.fact_b_id,
                relationship_type=rel.relationship_type,
                reasoning=rel.reasoning,
                confidence=rel.confidence,
                created_at=rel.created_at,
                fact_a=FactOut(
                    id=fact_a.id, document_id=fact_a.document_id, page_number=fact_a.page_number,
                    fact_type=fact_a.fact_type, entity=fact_a.entity, metric=fact_a.metric,
                    value=fact_a.value, normalized_value=float(fact_a.normalized_value) if fact_a.normalized_value else None,
                    unit=fact_a.unit, time_period=fact_a.time_period, scope=fact_a.scope,
                    evidence_quote=fact_a.evidence_quote, confidence=fact_a.confidence,
                    attributes=fact_a.attributes, created_at=fact_a.created_at,
                    document_filename=fa_doc.scalar_one_or_none() if fa_doc else None,
                ) if fact_a else None,
                fact_b=FactOut(
                    id=fact_b.id, document_id=fact_b.document_id, page_number=fact_b.page_number,
                    fact_type=fact_b.fact_type, entity=fact_b.entity, metric=fact_b.metric,
                    value=fact_b.value, normalized_value=float(fact_b.normalized_value) if fact_b.normalized_value else None,
                    unit=fact_b.unit, time_period=fact_b.time_period, scope=fact_b.scope,
                    evidence_quote=fact_b.evidence_quote, confidence=fact_b.confidence,
                    attributes=fact_b.attributes, created_at=fact_b.created_at,
                    document_filename=fb_doc.scalar_one_or_none() if fb_doc else None,
                ) if fact_b else None,
            )
        )

    return out
