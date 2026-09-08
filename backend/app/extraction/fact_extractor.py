"""Fact extractor using Google Gemini with structured JSON output.

Sends batches of page text to Gemini and receives structured atomic facts
as JSON. Uses gemini-2.0-flash by default (configurable via GEMINI_MODEL env).
"""

import json
import logging
from dataclasses import dataclass, field

import google.generativeai as genai

from app.config import settings
from app.extraction.prompts import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    FACT_EXTRACTION_JSON_SCHEMA,
)
from app.ingestion.pdf_parser import PageChunk

logger = logging.getLogger(__name__)

# Configure Gemini once at import time
genai.configure(api_key=settings.gemini_api_key)


@dataclass
class CandidateFact:
    """A fact candidate before confidence filtering."""
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
    """Result of extracting facts from a document."""
    facts: list[CandidateFact] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    total_tokens_used: int = 0
    pages_processed: int = 0


# Batch sizes: small for dense financial pages, larger for text-heavy pages
_MIN_BATCH = 3
_MAX_BATCH = 5


def _batch_pages(pages: list[PageChunk]) -> list[list[PageChunk]]:
    """Group pages into batches for the LLM."""
    batches = []
    current_batch: list[PageChunk] = []
    current_chars = 0

    for page in pages:
        page_chars = len(page.text or "")
        # Start a new batch if current one is large enough
        if current_batch and (
            len(current_batch) >= _MAX_BATCH or current_chars + page_chars > 8000
        ):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(page)
        current_chars += page_chars

        if len(current_batch) >= _MIN_BATCH and current_chars > 4000:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

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
        "Return ONLY a valid JSON object matching the schema provided."
    )
    return "".join(parts)


def extract_facts_from_pages(
    pages: list[PageChunk],
    doc_filename: str,
    confidence_flag_threshold: float | None = None,
    confidence_reject_threshold: float | None = None,
) -> ExtractionResult:
    """Extract facts from a list of page chunks using Gemini.

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

    # Build the Gemini model with JSON output mode
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=FACT_EXTRACTION_SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=FACT_EXTRACTION_JSON_SCHEMA,
            temperature=0.1,  # Low temperature for consistent structured output
        ),
    )

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
            response = model.generate_content(message_text)

            # Track token usage
            if response.usage_metadata:
                result.total_tokens_used += (
                    (response.usage_metadata.prompt_token_count or 0)
                    + (response.usage_metadata.candidates_token_count or 0)
                )
            result.pages_processed += len(batch)

            # Parse the JSON response
            raw_json = response.text
            try:
                tool_input = json.loads(raw_json)
            except json.JSONDecodeError as e:
                logger.warning(f"  Batch {batch_idx + 1}: JSON parse failed: {e}")
                for page in batch:
                    result.issues.append({
                        "page_number": page.page_number,
                        "issue_type": "parse_error",
                        "raw_text_snippet": page.text[:200] if page.text else None,
                        "detail": f"JSON decode error: {str(e)}",
                    })
                continue

            raw_facts = tool_input.get("facts", [])
            page_notes = tool_input.get("page_notes")

            if page_notes:
                for page in batch:
                    result.issues.append({
                        "page_number": page.page_number,
                        "issue_type": "extraction_note",
                        "raw_text_snippet": page.text[:200] if page.text else None,
                        "detail": page_notes,
                    })

            for raw_fact in raw_facts:
                confidence = raw_fact.get("confidence", 0.5)

                fact_page = raw_fact.get("page_number")
                if fact_page is None:
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
                    result.issues.append({
                        "page_number": candidate.page_number,
                        "issue_type": "low_confidence",
                        "raw_text_snippet": candidate.evidence_quote[:200],
                        "detail": (
                            f"Rejected fact (confidence={confidence:.2f} < "
                            f"{confidence_reject_threshold}): "
                            f"{candidate.entity} / {candidate.metric} = {candidate.value}"
                        ),
                    })
                else:
                    result.facts.append(candidate)
                    if confidence < confidence_flag_threshold:
                        result.issues.append({
                            "page_number": candidate.page_number,
                            "issue_type": "low_confidence",
                            "raw_text_snippet": candidate.evidence_quote[:200],
                            "detail": (
                                f"Flagged fact (confidence={confidence:.2f} < "
                                f"{confidence_flag_threshold}): "
                                f"{candidate.entity} / {candidate.metric} = {candidate.value}"
                            ),
                        })

        except Exception as e:
            logger.error(f"  Unexpected error on batch {batch_idx + 1}: {e!r}")
            for page in batch:
                result.issues.append({
                    "page_number": page.page_number,
                    "issue_type": "llm_refused",
                    "raw_text_snippet": page.text[:200] if page.text else None,
                    "detail": f"Gemini API error: {str(e)}",
                })

    logger.info(
        f"Extraction complete: {len(result.facts)} facts, "
        f"{len(result.issues)} issues, "
        f"{result.total_tokens_used} tokens used"
    )
    return result