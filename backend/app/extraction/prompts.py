"""LLM prompt templates and JSON schemas for Gemini.

All prompts are fully generic - no hardcoded company names, domains, or document types.
Works on any PDF with any content.
"""

# ────────────────────────────────────────────────────────────
# FACT EXTRACTION
# ────────────────────────────────────────────────────────────

FACT_EXTRACTION_SYSTEM_PROMPT = """You are a precision fact-extraction engine. Your job is to identify every ATOMIC, VERIFIABLE fact in the provided PDF page text and return them in structured JSON.

WHAT IS AN ATOMIC FACT:
- A single measurable claim: a number, date, percentage, ranking, name, or categorical statement that can be checked against the source.
- Must reference a specific entity (company, country, person, institution, etc.)
- Must be grounded in the actual text — never inferred or extrapolated.

REQUIRED FIELDS FOR EACH FACT:
- page_number: The page number where this fact appears
- fact_type: Category. Use one of: financial, operational, macroeconomic, regulatory, product, personnel, risk, event, or create a new type if none fit
- entity: The subject (company name, country, index, product, person, etc.)
- metric: What is being measured (Revenue, GDP Growth Rate, EBITDA Margin, etc.)
- value: The raw value as a string (e.g., "7,225", "8.2%", "positive")
- normalized_value: Numeric value if the value is numeric (null if not)
- unit: Unit of measurement (Crore INR, %, USD Billion, bps, etc.) — null if not applicable
- time_period: The reporting period (FY2024, Q4 FY24, CY2023, etc.) — null if not clear
- scope: Reporting scope (Consolidated, Standalone, Segment, etc.) — null if not stated
- evidence_quote: VERBATIM text from the document that contains this fact. Must be a direct quote, not paraphrased. Maximum 300 characters.
- confidence: Your confidence 0.0-1.0 that this is an accurate, well-grounded extraction
- attributes: Any extra structured fields relevant to the fact type (empty dict if none)

QUALITY RULES:
1. If a value is ambiguous or unclear, set confidence < 0.6
2. If you cannot find verbatim evidence for a fact, do NOT include it
3. Do NOT include facts that are pure opinions, projections, or analyst estimates unless labeled as such
4. It is better to extract fewer high-quality facts than many low-quality ones
5. For each page, note in page_notes if it was image-only, a table of contents, or contained no extractable facts

RETURN FORMAT: A JSON object with a "facts" array and optional "page_notes" string."""


# Gemini JSON schema for structured fact extraction output
FACT_EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "fact_type": {"type": "string"},
                    "entity": {"type": "string"},
                    "metric": {"type": "string"},
                    "value": {"type": "string"},
                    "normalized_value": {"type": "number"},
                    "unit": {"type": "string"},
                    "time_period": {"type": "string"},
                    "scope": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "confidence": {"type": "number"},
                    "attributes": {"type": "object"},
                },
                "required": ["page_number", "fact_type", "evidence_quote", "confidence"],
            },
        },
        "page_notes": {"type": "string"},
    },
    "required": ["facts"],
}


# ────────────────────────────────────────────────────────────
# RECONCILIATION
# ────────────────────────────────────────────────────────────

RECONCILIATION_SYSTEM_PROMPT = """You are an expert fact reconciliation engine. You are given two facts from different documents. Your job is to classify the relationship between them.

RELATIONSHIP TYPES:
- corroborates: Both facts refer to the same thing and the values agree (same entity, metric, time period, scope, and compatible values).
- contradicts: Both facts refer to the same thing but values genuinely conflict without a valid contextual explanation.
- contextual_difference: Values differ, but for a legitimate contextual reason such as:
    * Different time periods (FY2024 vs FY2023)
    * Different reporting scope (Standalone vs Consolidated)
    * Different currency or unit basis
    * Different segment vs total company
    * One is a revision or restatement of the other
  Always explain the specific reason in your reasoning.
- unrelated: The two facts are not about the same metric/entity and were a false-positive similarity match.

STRICT RULES:
1. Do NOT classify as "contradicts" if there is a valid contextual explanation. Use "contextual_difference" instead.
2. You MUST cite specific values, units, time periods, and evidence quotes in your reasoning.
3. Confidence should reflect how certain you are about the classification, not about the facts themselves.
4. If the classification is ambiguous, prefer "contextual_difference" over "contradicts".

RETURN: A JSON object with relationship_type, reasoning (minimum 2 sentences), confidence (0.0-1.0), and contextual_factors array."""


RECONCILIATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "relationship_type": {
            "type": "string",
            "enum": ["corroborates", "contradicts", "contextual_difference", "unrelated"],
        },
        "reasoning": {"type": "string"},
        "confidence": {"type": "number"},
        "contextual_factors": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["relationship_type", "reasoning", "confidence"],
}