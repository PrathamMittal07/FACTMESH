"""Extraction Issues API routes — browse failures and flagged extractions."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import ExtractionIssue, Document
from app.schemas.models import IssueOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("", response_model=list[IssueOut])
async def list_issues(
    db: AsyncSession = Depends(get_db),
    document_id: UUID | None = Query(None, description="Filter by document"),
    issue_type: str | None = Query(None, description="Filter by issue type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List extraction/reasoning issues (failures, low confidence, ambiguities)."""
    query = select(ExtractionIssue)

    if document_id:
        query = query.where(ExtractionIssue.document_id == document_id)
    if issue_type:
        query = query.where(ExtractionIssue.issue_type == issue_type)

    query = query.order_by(ExtractionIssue.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    issues = result.scalars().all()

    out = []
    for issue in issues:
        doc_result = await db.execute(
            select(Document.filename).where(Document.id == issue.document_id)
        )
        doc_filename = doc_result.scalar_one_or_none()

        out.append(
            IssueOut(
                id=issue.id,
                document_id=issue.document_id,
                page_number=issue.page_number,
                issue_type=issue.issue_type,
                raw_text_snippet=issue.raw_text_snippet,
                detail=issue.detail,
                created_at=issue.created_at,
                document_filename=doc_filename,
            )
        )

    return out
