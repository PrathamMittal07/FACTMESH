"""Ingestion pipeline — orchestrates: parse -> extract -> embed -> reconcile.

This is the main workflow that runs when a new PDF is uploaded.
It processes incrementally: new documents only match against
existing facts, not re-process old documents.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, Fact, Relationship, ExtractionIssue
from app.ingestion.pdf_parser import parse_pdf
from app.extraction.fact_extractor import extract_facts_from_pages
from app.embeddings.embedder import build_fact_text, embed_texts
from app.reconciliation.matcher import find_all_candidate_pairs
from app.reconciliation.reconciler import reconcile_fact_pair

logger = logging.getLogger(__name__)


async def ingest_document(
    session: AsyncSession,
    file_path: str | Path,
    original_filename: str | None = None,
) -> uuid.UUID:
    """Full ingestion pipeline for a single PDF.

    Steps:
        1. Parse PDF -> page chunks
        2. Check SHA-256 dedup
        3. Create document record
        4. Extract facts via Claude
        5. Embed facts via sentence-transformers
        6. Store facts + embeddings
        7. Find candidate pairs via pgvector similarity
        8. Reconcile candidate pairs via Claude
        9. Store relationships

    Args:
        session: Async database session.
        file_path: Path to the PDF file.
        original_filename: Display name (defaults to file basename).

    Returns:
        The document UUID.

    Raises:
        ValueError: If the document has already been ingested (same SHA-256).
        FileNotFoundError: If the PDF file doesn't exist.
    """
    file_path = Path(file_path)
    if original_filename is None:
        original_filename = file_path.name

    # Step 1: Parse PDF
    logger.info(f"Step 1: Parsing PDF '{original_filename}'...")
    parse_result = parse_pdf(file_path)

    # Step 2: Check SHA-256 dedup
    existing = await session.execute(
        select(Document).where(Document.sha256 == parse_result.sha256)
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        raise ValueError(
            f"Document already ingested: '{existing_doc.filename}' "
            f"(id={existing_doc.id}, sha256={parse_result.sha256[:16]}...)"
        )

    # Step 3: Create document record
    logger.info(f"Step 3: Creating document record...")
    doc = Document(
        filename=original_filename,
        page_count=parse_result.page_count,
        status="processing",
        sha256=parse_result.sha256,
    )
    session.add(doc)
    await session.flush()  # get the generated UUID
    doc_id = doc.id
    logger.info(f"  Document ID: {doc_id}")

    # Log empty pages as extraction issues
    for page_num in parse_result.empty_pages:
        issue = ExtractionIssue(
            document_id=doc_id,
            page_number=page_num,
            issue_type="parse_error",
            raw_text_snippet=None,
            detail=f"Page {page_num} has no extractable text (may be image-only/scanned).",
        )
        session.add(issue)

    try:
        # Step 4: Extract facts via Claude
        logger.info(f"Step 4: Extracting facts from {len(parse_result.pages)} pages...")
        extraction_result = extract_facts_from_pages(
            pages=parse_result.pages,
            doc_filename=original_filename,
        )
        logger.info(
            f"  Extracted {len(extraction_result.facts)} facts, "
            f"{len(extraction_result.issues)} issues"
        )

        # Log extraction issues
        for issue_data in extraction_result.issues:
            issue = ExtractionIssue(
                document_id=doc_id,
                page_number=issue_data.get("page_number"),
                issue_type=issue_data.get("issue_type", "unknown"),
                raw_text_snippet=issue_data.get("raw_text_snippet"),
                detail=issue_data.get("detail"),
            )
            session.add(issue)

        # Step 5: Embed facts
        logger.info(f"Step 5: Embedding {len(extraction_result.facts)} facts...")
        fact_texts = [
            build_fact_text(
                entity=f.entity,
                metric=f.metric,
                value=f.value,
                unit=f.unit,
                time_period=f.time_period,
                scope=f.scope,
                evidence_quote=f.evidence_quote,
            )
            for f in extraction_result.facts
        ]
        embeddings = embed_texts(fact_texts) if fact_texts else []

        # Step 6: Store facts + embeddings
        logger.info(f"Step 6: Storing facts...")
        fact_records: list[Fact] = []
        for i, candidate in enumerate(extraction_result.facts):
            fact = Fact(
                document_id=doc_id,
                page_number=candidate.page_number,
                fact_type=candidate.fact_type,
                entity=candidate.entity,
                metric=candidate.metric,
                value=candidate.value,
                normalized_value=candidate.normalized_value,
                unit=candidate.unit,
                time_period=candidate.time_period,
                scope=candidate.scope,
                evidence_quote=candidate.evidence_quote,
                confidence=candidate.confidence,
                attributes=candidate.attributes,
                embedding=embeddings[i] if i < len(embeddings) else None,
            )
            session.add(fact)
            fact_records.append(fact)

        await session.flush()  # get generated UUIDs for facts
        logger.info(f"  Stored {len(fact_records)} facts")

        # Step 7: Find candidate pairs
        logger.info(f"Step 7: Finding candidate pairs via similarity search...")
        candidate_pairs = await find_all_candidate_pairs(
            session, document_id=doc_id
        )
        logger.info(f"  Found {len(candidate_pairs)} candidate pairs")

        # Step 8: Check which pairs already have relationships
        # (avoids re-reconciling if a document is re-processed)
        new_pairs = []
        for fact_a_id, fact_b_id, similarity in candidate_pairs:
            # Check if relationship already exists
            existing_rel = await session.execute(
                select(Relationship).where(
                    ((Relationship.fact_a_id == fact_a_id) & (Relationship.fact_b_id == fact_b_id))
                    | ((Relationship.fact_a_id == fact_b_id) & (Relationship.fact_b_id == fact_a_id))
                )
            )
            if existing_rel.scalar_one_or_none() is None:
                new_pairs.append((fact_a_id, fact_b_id, similarity))

        logger.info(f"  {len(new_pairs)} new pairs to reconcile")

        # Step 9: Reconcile candidate pairs via Claude
        logger.info(f"Step 8: Reconciling {len(new_pairs)} fact pairs...")
        relationships_created = 0
        for pair_idx, (fact_a_id, fact_b_id, similarity) in enumerate(new_pairs):
            # Load full fact data for reconciliation
            fact_a_result = await session.execute(
                select(Fact).where(Fact.id == fact_a_id)
            )
            fact_a_record = fact_a_result.scalar_one_or_none()

            fact_b_result = await session.execute(
                select(Fact).where(Fact.id == fact_b_id)
            )
            fact_b_record = fact_b_result.scalar_one_or_none()

            if not fact_a_record or not fact_b_record:
                continue

            # Get document filenames for context
            doc_a_result = await session.execute(
                select(Document.filename).where(Document.id == fact_a_record.document_id)
            )
            doc_a_filename = doc_a_result.scalar_one_or_none() or "Unknown"

            doc_b_result = await session.execute(
                select(Document.filename).where(Document.id == fact_b_record.document_id)
            )
            doc_b_filename = doc_b_result.scalar_one_or_none() or "Unknown"

            fact_a_dict = {
                "entity": fact_a_record.entity,
                "metric": fact_a_record.metric,
                "value": fact_a_record.value,
                "unit": fact_a_record.unit,
                "time_period": fact_a_record.time_period,
                "scope": fact_a_record.scope,
                "evidence_quote": fact_a_record.evidence_quote,
                "page_number": fact_a_record.page_number,
                "document_filename": doc_a_filename,
                "fact_type": fact_a_record.fact_type,
            }
            fact_b_dict = {
                "entity": fact_b_record.entity,
                "metric": fact_b_record.metric,
                "value": fact_b_record.value,
                "unit": fact_b_record.unit,
                "time_period": fact_b_record.time_period,
                "scope": fact_b_record.scope,
                "evidence_quote": fact_b_record.evidence_quote,
                "page_number": fact_b_record.page_number,
                "document_filename": doc_b_filename,
                "fact_type": fact_b_record.fact_type,
            }

            logger.info(
                f"  Pair {pair_idx + 1}/{len(new_pairs)} "
                f"(similarity={similarity:.3f}): "
                f"{fact_a_record.entity}/{fact_a_record.metric} vs "
                f"{fact_b_record.entity}/{fact_b_record.metric}"
            )

            reconciliation = reconcile_fact_pair(fact_a_dict, fact_b_dict)

            if reconciliation and reconciliation["relationship_type"] != "unrelated":
                rel = Relationship(
                    fact_a_id=fact_a_id,
                    fact_b_id=fact_b_id,
                    relationship_type=reconciliation["relationship_type"],
                    reasoning=reconciliation["reasoning"],
                    confidence=reconciliation["confidence"],
                )
                session.add(rel)
                relationships_created += 1

        logger.info(f"  Created {relationships_created} relationships")

        # Mark document as done
        doc.status = "done"
        await session.commit()
        logger.info(f"Document '{original_filename}' ingestion complete!")

    except Exception as e:
        logger.error(f"Ingestion failed for '{original_filename}': {e}")
        doc.status = "failed"
        issue = ExtractionIssue(
            document_id=doc_id,
            page_number=None,
            issue_type="parse_error",
            raw_text_snippet=None,
            detail=f"Pipeline failure: {str(e)}",
        )
        session.add(issue)
        await session.commit()
        raise

    return doc_id
