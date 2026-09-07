"""Facts API routes — list, filter, detail, relationships."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Fact, Document, Relationship
from app.schemas.models import FactOut, FactDetail, RelationshipOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/facts", tags=["facts"])


@router.get("", response_model=list[FactOut])
async def list_facts(
    db: AsyncSession = Depends(get_db),
    document_id: UUID | None = Query(None, description="Filter by document"),
    entity: str | None = Query(None, description="Filter by entity (case-insensitive partial match)"),
    metric: str | None = Query(None, description="Filter by metric (case-insensitive partial match)"),
    fact_type: str | None = Query(None, description="Filter by fact type"),
    time_period: str | None = Query(None, description="Filter by time period"),
    min_confidence: float | None = Query(None, description="Minimum confidence"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List/filter facts across all documents."""
    query = select(Fact)

    if document_id:
        query = query.where(Fact.document_id == document_id)
    if entity:
        query = query.where(Fact.entity.ilike(f"%{entity}%"))
    if metric:
        query = query.where(Fact.metric.ilike(f"%{metric}%"))
    if fact_type:
        query = query.where(Fact.fact_type == fact_type)
    if time_period:
        query = query.where(Fact.time_period.ilike(f"%{time_period}%"))
    if min_confidence is not None:
        query = query.where(Fact.confidence >= min_confidence)

    query = query.order_by(Fact.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    facts = result.scalars().all()

    out = []
    for fact in facts:
        # Get document filename
        doc_result = await db.execute(
            select(Document.filename).where(Document.id == fact.document_id)
        )
        doc_filename = doc_result.scalar_one_or_none()

        out.append(
            FactOut(
                id=fact.id,
                document_id=fact.document_id,
                page_number=fact.page_number,
                fact_type=fact.fact_type,
                entity=fact.entity,
                metric=fact.metric,
                value=fact.value,
                normalized_value=float(fact.normalized_value) if fact.normalized_value else None,
                unit=fact.unit,
                time_period=fact.time_period,
                scope=fact.scope,
                evidence_quote=fact.evidence_quote,
                confidence=fact.confidence,
                attributes=fact.attributes,
                created_at=fact.created_at,
                document_filename=doc_filename,
            )
        )

    return out


@router.get("/{fact_id}", response_model=FactDetail)
async def get_fact(fact_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get fact detail including evidence and related facts."""
    result = await db.execute(select(Fact).where(Fact.id == fact_id))
    fact = result.scalar_one_or_none()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    # Get document filename
    doc_result = await db.execute(
        select(Document.filename).where(Document.id == fact.document_id)
    )
    doc_filename = doc_result.scalar_one_or_none()

    # Get relationships involving this fact
    rel_result = await db.execute(
        select(Relationship).where(
            (Relationship.fact_a_id == fact_id) | (Relationship.fact_b_id == fact_id)
        )
    )
    relationships = rel_result.scalars().all()

    rel_out = []
    for rel in relationships:
        # Load both facts for each relationship
        fa = await db.execute(select(Fact).where(Fact.id == rel.fact_a_id))
        fb = await db.execute(select(Fact).where(Fact.id == rel.fact_b_id))
        fact_a = fa.scalar_one_or_none()
        fact_b = fb.scalar_one_or_none()

        fa_doc = await db.execute(select(Document.filename).where(Document.id == fact_a.document_id)) if fact_a else None
        fb_doc = await db.execute(select(Document.filename).where(Document.id == fact_b.document_id)) if fact_b else None

        rel_out.append(
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

    return FactDetail(
        id=fact.id,
        document_id=fact.document_id,
        page_number=fact.page_number,
        fact_type=fact.fact_type,
        entity=fact.entity,
        metric=fact.metric,
        value=fact.value,
        normalized_value=float(fact.normalized_value) if fact.normalized_value else None,
        unit=fact.unit,
        time_period=fact.time_period,
        scope=fact.scope,
        evidence_quote=fact.evidence_quote,
        confidence=fact.confidence,
        attributes=fact.attributes,
        created_at=fact.created_at,
        document_filename=doc_filename,
        relationships=rel_out,
    )


@router.get("/{fact_id}/relationships", response_model=list[RelationshipOut])
async def get_fact_relationships(fact_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all relationships involving a specific fact."""
    # Verify fact exists
    fact_result = await db.execute(select(Fact).where(Fact.id == fact_id))
    if not fact_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Fact not found.")

    rel_result = await db.execute(
        select(Relationship).where(
            (Relationship.fact_a_id == fact_id) | (Relationship.fact_b_id == fact_id)
        ).order_by(Relationship.confidence.desc())
    )
    relationships = rel_result.scalars().all()

    out = []
    for rel in relationships:
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
