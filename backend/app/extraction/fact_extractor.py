"""Fact extractor using Claude claude-sonnet-4-6 with structured tool-use.

Sends page text to Claude and receives structured atomic facts.
No document-specific logic — the LLM decides what counts as a fact.
"""

import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.config import settings
from app.extraction.prompts import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    FACT_EXTRACTION_TOOL_SCHEMA,
)
from app.ingestion.pdf_parser import PageChunk

logger = logging.getLogger(__name__)


@dataclass
class CandidateFact:
    """A fact candidate extracted by the LLM before storage."""

    page_number: int
    fact_type: str
    entity: str | None
    metric: str | None
    value: str | None
    normalized_value: float | None
    unit: str | None
    time_period: str | None
    scope: str | None
    evidence_quote: str
    confidence: float
    attributes: dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of extracting facts from a set of page chunks."""

    facts: list[CandidateFact] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)  # issues to log
    pages_processed: int = 0
    total_tokens_used: int = 0


def _build_page_message(chunk: PageChunk, doc_filename: str) -> str:
    """Build the user message for a single page extraction call."""
    return (
        f"Document: {doc_filename}\n"
        f"Page: {chunk.page_number}\n"
        f"---BEGIN PAGE TEXT---\n"
        f"{chunk.text}\n"
        f"---END PAGE TEXT---\n\n"
        f"Extract all atomic facts from this page. Use the extract_facts tool."
    )


def _batch_pages(pages: list[PageChunk], max_chars: int = 12000) -> list[list[PageChunk]]:
    """Group pages into batches that fit within a character budget.

    We batch multiple short pages together to reduce API calls,
    but keep long pages as single batches.
    """
    batches: list[list[PageChunk]] = []
    current_batch: list[PageChunk] = []
    current_chars = 0

    for page in pages:
        if current_chars + page.char_count > max_chars and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(page)
        current_chars += page.char_count

    if current_batch:
        batches.append(current_batch)

    return batches


def _build_batch_message(chunks: list[PageChunk], doc_filename: str) -> str:
    """Build the user message for a batch of pages."""
    parts = [f"Document: {doc_filename}\n"]
    for chunk in chunks:
        parts.append(
            f"\n--- PAGE {chunk.page_number} ---\n"
            f"{chunk.text}\n"
            f"--- END PAGE {chunk.page_number} ---\n"
        )
    parts.append(
        "\nExtract all atomic facts from all pages above. "
        "For each fact, include the correct page_number. "
        "Use the extract_facts tool."
    )
    return "".join(parts)


def extract_facts_from_pages(
    pages: list[PageChunk],
    doc_filename: str,
    confidence_flag_threshold: float | None = None,
    confidence_reject_threshold: float | None = None,
) -> ExtractionResult:
    """Extract facts from a list of page chunks using Claude.

    Args:
        pages: List of PageChunk objects from the PDF parser.
        doc_filename: Original filename for context.
        confidence_flag_threshold: Below this, facts are flagged (default from settings).
        confidence_reject_threshold: Below this, facts become issues only (default from settings).

    Returns:
        ExtractionResult with candidate facts and any issues.
    """
    if confidence_flag_threshold is None:
        confidence_flag_threshold = settings.confidence_flag_threshold
    if confidence_reject_threshold is None:
        confidence_reject_threshold = settings.confidence_reject_threshold

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    result = ExtractionResult()

    batches = _batch_pages(pages)
    logger.info(
        f"Extracting facts from {len(pages)} pages in {len(batches)} batches "
        f"for '{doc_filename}'"
    )

    for batch_idx, batch in enumerate(batches):
        page_numbers = [p.page_number for p in batch]
        logger.info(f"  Batch {batch_idx + 1}/{len(batches)}: pages {page_numbers}")

        message_text = _build_batch_message(batch, doc_filename)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=FACT_EXTRACTION_SYSTEM_PROMPT,
                tools=[FACT_EXTRACTION_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "extract_facts"},
                messages=[{"role": "user", "content": message_text}],
            )

            result.total_tokens_used += (
                response.usage.input_tokens + response.usage.output_tokens
            )
            result.pages_processed += len(batch)

            # Parse tool use response
            for block in response.content:
                if block.type == "tool_use" and block.name == "extract_facts":
                    tool_input = block.input
                    raw_facts = tool_input.get("facts", [])
                    page_notes = tool_input.get("page_notes")

                    if page_notes:
                        # Log page-level notes as issues
                        for page in batch:
                            result.issues.append(
                                {
                                    "page_number": page.page_number,
                                    "issue_type": "extraction_note",
                                    "raw_text_snippet": page.text[:200] if page.text else None,
                                    "detail": page_notes,
                                }
                            )

                    for raw_fact in raw_facts:
                        confidence = raw_fact.get("confidence", 0.5)

                        # Determine the page number for this fact
                        # The LLM should have included it if processing multiple pages
                        fact_page = raw_fact.get("page_number")
                        if fact_page is None:
                            # If single page in batch, use that page's number
                            fact_page = batch[0].page_number if len(batch) == 1 else page_numbers[0]

                        candidate = CandidateFact(
                            page_number=fact_page,
                            fact_type=raw_fact.get("fact_type", "unknown"),
                            entity=raw_fact.get("entity"),
                            metric=raw_fact.get("metric"),
                            value=raw_fact.get("value"),
                            normalized_value=raw_fact.get("normalized_value"),
                            unit=raw_fact.get("unit"),
                            time_period=raw_fact.get("time_period"),
                            scope=raw_fact.get("scope"),
                            evidence_quote=raw_fact.get("evidence_quote", ""),
                            confidence=confidence,
                            attributes=raw_fact.get("attributes", {}),
                        )

                        if confidence < confidence_reject_threshold:
                            # Too low confidence — log as issue only, don't store as fact
                            result.issues.append(
                                {
                                    "page_number": candidate.page_number,
                                    "issue_type": "low_confidence",
                                    "raw_text_snippet": candidate.evidence_quote[:200],
                                    "detail": (
                                        f"Rejected fact (confidence={confidence:.2f} < "
                                        f"{confidence_reject_threshold}): "
                                        f"{candidate.entity} / {candidate.metric} = {candidate.value}"
                                    ),
                                }
                            )
                        else:
                            result.facts.append(candidate)

                            if confidence < confidence_flag_threshold:
                                # Low-ish confidence — store fact but also log as issue
                                result.issues.append(
                                    {
                                        "page_number": candidate.page_number,
                                        "issue_type": "low_confidence",
                                        "raw_text_snippet": candidate.evidence_quote[:200],
                                        "detail": (
                                            f"Flagged fact (confidence={confidence:.2f} < "
                                            f"{confidence_flag_threshold}): "
                                            f"{candidate.entity} / {candidate.metric} = {candidate.value}"
                                        ),
                                    }
                                )

        except anthropic.APIError as e:
            logger.error(f"  Claude API error on batch {batch_idx + 1}: {e}")
            for page in batch:
                result.issues.append(
                    {
                        "page_number": page.page_number,
                        "issue_type": "llm_refused",
                        "raw_text_snippet": page.text[:200] if page.text else None,
                        "detail": f"Claude API error: {str(e)}",
                    }
                )
        except Exception as e:
            logger.error(f"  Unexpected error on batch {batch_idx + 1}: {e}")
            for page in batch:
                result.issues.append(
                    {
                        "page_number": page.page_number,
                        "issue_type": "parse_error",
                        "raw_text_snippet": page.text[:200] if page.text else None,
                        "detail": f"Extraction error: {str(e)}",
                    }
                )

    logger.info(
        f"Extraction complete: {len(result.facts)} facts, "
        f"{len(result.issues)} issues, "
        f"{result.total_tokens_used} tokens used"
    )
    return result
