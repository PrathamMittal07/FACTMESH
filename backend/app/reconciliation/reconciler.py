"""Reconciliation engine — classifies relationships between candidate fact pairs.

Uses Claude to compare two facts and their evidence, returning a typed
relationship (corroborates / contradicts / contextual_difference / unrelated)
with detailed reasoning.
"""

import logging
import uuid

import anthropic

from app.config import settings
from app.extraction.prompts import (
    RECONCILIATION_SYSTEM_PROMPT,
    RECONCILIATION_TOOL_SCHEMA,
)

logger = logging.getLogger(__name__)


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
        parts.append(f"Evidence: \"{fact['evidence_quote']}\"")

    return "\n".join(parts)


def reconcile_fact_pair(
    fact_a: dict,
    fact_b: dict,
) -> dict | None:
    """Classify the relationship between two facts using Claude.

    Args:
        fact_a: Dict with fact fields (entity, metric, value, unit, time_period,
                scope, evidence_quote, page_number, document_filename, fact_type).
        fact_b: Same structure as fact_a.

    Returns:
        Dict with keys: relationship_type, reasoning, confidence, contextual_factors.
        Returns None if the LLM call fails.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    fact_a_text = _format_fact_for_reconciliation(fact_a, "FACT A")
    fact_b_text = _format_fact_for_reconciliation(fact_b, "FACT B")

    user_message = (
        f"{fact_a_text}\n\n"
        f"{fact_b_text}\n\n"
        "Classify the relationship between FACT A and FACT B. "
        "Use the classify_relationship tool. "
        "Your reasoning MUST reference specific values, units, time periods, "
        "and evidence from both facts."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=RECONCILIATION_SYSTEM_PROMPT,
            tools=[RECONCILIATION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "classify_relationship"},
            messages=[{"role": "user", "content": user_message}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "classify_relationship":
                result = block.input
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

        logger.warning("Claude did not return a tool_use block for reconciliation")
        return None

    except anthropic.APIError as e:
        logger.error(f"Claude API error during reconciliation: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during reconciliation: {e}")
        return None
