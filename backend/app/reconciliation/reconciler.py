"""Reconciliation engine - classifies relationships between candidate fact pairs.

Uses Gemini to compare two facts and their evidence, returning a typed
relationship (corroborates / contradicts / contextual_difference / unrelated)
with detailed reasoning.
"""

import json
import logging

import google.generativeai as genai

from app.config import settings
from app.llm_retry import generate_with_retry
from app.extraction.prompts import (
    RECONCILIATION_SYSTEM_PROMPT,
    RECONCILIATION_JSON_SCHEMA,
)

logger = logging.getLogger(__name__)

# Configure Gemini once
genai.configure(api_key=settings.gemini_api_key)


def _format_fact_for_reconciliation(fact: dict, label: str) -> str:
    """Format a fact dict into a readable string for the LLM."""
    parts = [f"=== {label} ==="]
    parts.append(f"Document: {fact.get('document_filename', 'Unknown')}")
    parts.append(f"Page: {fact.get('page_number', '?')}")
    parts.append(f"Type: {fact.get('fact_type', '?')}")

    if fact.get("entity"):
        parts.append(f"Entity: {fact['entity']}")
    if fact.get("metric"):
        parts.append(f"Metric: {fact['metric']}")
    if fact.get("value"):
        parts.append(f"Value: {fact['value']}")
    if fact.get("unit"):
        parts.append(f"Unit: {fact['unit']}")
    if fact.get("time_period"):
        parts.append(f"Time Period: {fact['time_period']}")
    if fact.get("scope"):
        parts.append(f"Scope: {fact['scope']}")
    if fact.get("evidence_quote"):
        parts.append(f'Evidence: "{fact["evidence_quote"]}"')

    return "\n".join(parts)


def reconcile_fact_pair(
    fact_a: dict,
    fact_b: dict,
) -> dict | None:
    """Classify the relationship between two facts using Gemini.

    Args:
        fact_a: Dict with fact fields (entity, metric, value, unit, time_period,
                scope, evidence_quote, page_number, document_filename, fact_type).
        fact_b: Same structure as fact_a.

    Returns:
        Dict with keys: relationship_type, reasoning, confidence, contextual_factors.
        Returns None if the LLM call fails.

    Raises:
        RuntimeError: If GEMINI_API_KEY is not configured.
    """
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to backend/.env "
            "(see backend/.env.example)."
        )
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=RECONCILIATION_SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=RECONCILIATION_JSON_SCHEMA,
            temperature=0.1,
        ),
    )

    fact_a_text = _format_fact_for_reconciliation(fact_a, "FACT A")
    fact_b_text = _format_fact_for_reconciliation(fact_b, "FACT B")

    user_message = (
        f"{fact_a_text}\n\n"
        f"{fact_b_text}\n\n"
        "Classify the relationship between FACT A and FACT B. "
        "Your reasoning MUST reference specific values, units, time periods, "
        "and evidence from both facts. Return a valid JSON object."
    )

    try:
        response = generate_with_retry(model, user_message)
        result = json.loads(response.text)

        logger.info(
            f"Reconciled: {result.get('relationship_type')} "
            f"(confidence={result.get('confidence', 0):.2f})"
        )
        return {
            "relationship_type": result["relationship_type"],
            "reasoning": result["reasoning"],
            "confidence": result.get("confidence", 0.5),
            "contextual_factors": result.get("contextual_factors", []),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON during reconciliation: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during reconciliation: {e!r}")
        return None