"""Document API routes — upload, list, detail."""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, async_session_factory
from app.db.models import Document, Fact, ExtractionIssue, Relationship
from app.ingestion.pipeline import ingest_document
from app.schemas.models import DocumentOut, DocumentDetail, UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Directory for storing uploaded PDFs
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def _run_ingestion(file_path: str, original_filename: str):
    """Background task to run the full ingestion pipeline."""
    async with async_session_factory() as session:
        try:
            await ingest_document(session, file_path, original_filename)
        except Exception as e:
            logger.error(f"Background ingestion failed: {e}")
            # Document status is set to 'failed' inside ingest_document


@router.post("", response_model=UploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF document and kick off background ingestion."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save uploaded file to disk
    upload_path = UPLOAD_DIR / file.filename
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Quick SHA-256 check for dedup before starting background task
    from app.ingestion.pdf_parser import compute_sha256

    sha256 = compute_sha256(upload_path)
    existing = await db.execute(select(Document).where(Document.sha256 == sha256))
    if existing.scalar_one_or_none():
        upload_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=f"This PDF has already been uploaded (sha256={sha256[:16]}...).",
        )

    # Create a preliminary document record
    doc = Document(
        filename=file.filename,
        status="processing",
        sha256=sha256,
    )
    db.add(doc)
    await db.flush()
    doc_id = doc.id

    # Kick off background ingestion
    background_tasks.add_task(_run_ingestion, str(upload_path), file.filename)

    return UploadResponse(
        document_id=doc_id,
        message=f"Document '{file.filename}' uploaded. Ingestion started in background.",
        status="processing",
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all uploaded documents with status."""
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc())
    )
    documents = result.scalars().all()

    out = []
    for doc in documents:
        # Get fact and issue counts
        fact_count_result = await db.execute(
            select(func.count(Fact.id)).where(Fact.document_id == doc.id)
        )
        issue_count_result = await db.execute(
            select(func.count(ExtractionIssue.id)).where(
                ExtractionIssue.document_id == doc.id
            )
        )
        out.append(
            DocumentOut(
                id=doc.id,
                filename=doc.filename,
                uploaded_at=doc.uploaded_at,
                page_count=doc.page_count,
                status=doc.status,
                sha256=doc.sha256,
                fact_count=fact_count_result.scalar() or 0,
                issue_count=issue_count_result.scalar() or 0,
            )
        )

    return out


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get document detail with counts."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    fact_count = (
        await db.execute(
            select(func.count(Fact.id)).where(Fact.document_id == doc.id)
        )
    ).scalar() or 0

    issue_count = (
        await db.execute(
            select(func.count(ExtractionIssue.id)).where(
                ExtractionIssue.document_id == doc.id
            )
        )
    ).scalar() or 0

    # Count relationships involving facts from this document
    fact_ids_result = await db.execute(
        select(Fact.id).where(Fact.document_id == doc.id)
    )
    fact_ids = [row[0] for row in fact_ids_result.fetchall()]
    relationship_count = 0
    if fact_ids:
        rel_count_result = await db.execute(
            select(func.count(Relationship.id)).where(
                (Relationship.fact_a_id.in_(fact_ids))
                | (Relationship.fact_b_id.in_(fact_ids))
            )
        )
        relationship_count = rel_count_result.scalar() or 0

    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        uploaded_at=doc.uploaded_at,
        page_count=doc.page_count,
        status=doc.status,
        sha256=doc.sha256,
        fact_count=fact_count,
        issue_count=issue_count,
        relationship_count=relationship_count,
    )
