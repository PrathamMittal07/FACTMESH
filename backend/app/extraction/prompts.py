"""Prompts for the Claude fact extraction and reconciliation calls.

These prompts are generic — they contain no document-specific logic,
entity names, or hardcoded metrics. The LLM decides what constitutes a
fact based on what it reads on each page.
"""

FACT_EXTRACTION_SYSTEM_PROMPT = """You are a precise fact-extraction engine. Your job is to read a page of text from a PDF document and identify every atomic, verifiable fact on that page.

RULES:
1. Extract ONLY facts that are explicitly stated on the page — do not infer, calculate, or speculate.
2. Each fact must be atomic: one claim, one value, one entity. Do NOT merge multiple data points into one fact.
3. For every fact, you MUST provide an evidence_quote: a short verbatim span (under 250 characters) copied exactly from the page text. Do NOT paraphrase or reword. If you cannot find a clean verbatim span for a candidate fact, skip that fact entirely.
4. Assign a confidence score (0.0–1.0) reflecting how certain you are that:
   - The fact is correctly extracted (value, unit, entity are right)
   - The evidence_quote is a true verbatim match
   - The fact type classification is correct
5. For numeric facts, always capture the unit as stated (e.g. "INR crore", "₹ lakh", "%", "million USD"). Do NOT convert units.
6. Capture the scope when stated or clearly implied (e.g. "standalone", "consolidated", "India", "global").
7. Capture the time_period as stated (e.g. "FY24", "Q4 FY24", "2024-25", "March 2024").
8. Use the attributes field for any additional context that doesn't fit the standard fields but is important for understanding the fact.
9. If a table has multiple rows, extract each row's data as a separate fact.
10. For non-numeric facts (status changes, appointments, descriptions), use fact_type "semantic" or "status" as appropriate.

FACT TYPES (use these, or propose a more specific one if none fits):
- "numeric": A quantitative measurement or statistic
- "semantic": A qualitative statement or description
- "status": A state or status of an entity (e.g. "resigned", "active", "approved")
- "date": A specific date or date range associated with an event
- "comparison": A relative comparison between entities or time periods
"""

FACT_EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_facts",
    "description": "Extract atomic facts from a page of PDF text. Call this tool once with ALL facts found on the page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "description": "List of atomic facts extracted from this page",
                "items": {
                    "type": "object",
                    "properties": {
                        "fact_type": {
                            "type": "string",
                            "description": "Type of fact: 'numeric', 'semantic', 'status', 'date', 'comparison', or a more specific type",
                        },
                        "entity": {
                            "type": "string",
                            "description": "The entity this fact is about (company name, country, person, etc.)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "What is being measured or described (e.g. 'Revenue from Operations', 'GDP growth rate', 'Board member status')",
                        },
                        "value": {
                            "type": "string",
                            "description": "The raw value as stated in the text (e.g. '74,540.82', '6.5%', 'Resigned')",
                        },
                        "normalized_value": {
                            "type": "number",
                            "description": "Parsed numeric value where applicable (e.g. 74540.82, 6.5). null for non-numeric facts.",
                        },
                        "unit": {
                            "type": "string",
                            "description": "Unit as stated (e.g. 'INR lakh', '₹ crore', '%', 'million USD'). null if unitless.",
                        },
                        "time_period": {
                            "type": "string",
                            "description": "Time period as stated (e.g. 'FY24', 'Q4 FY24', '2024-25'). null if not time-bound.",
                        },
                        "scope": {
                            "type": "string",
                            "description": "Scope qualifier (e.g. 'standalone', 'consolidated', 'India', 'global'). null if not stated.",
                        },
                        "evidence_quote": {
                            "type": "string",
                            "description": "Short verbatim span (under 250 chars) from the page text that supports this fact. MUST be an exact copy from the source text.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0.0-1.0 for this extraction",
                        },
                        "attributes": {
                            "type": "object",
                            "description": "Any additional context that doesn't fit standard fields (e.g. {'table_name': 'Statement of Profit and Loss', 'row_label': 'Revenue from operations'})",
                        },
                    },
                    "required": [
                        "fact_type",
                        "entity",
                        "metric",
                        "value",
                        "evidence_quote",
                        "confidence",
                    ],
                },
            },
            "page_notes": {
                "type": "string",
                "description": "Any issues, ambiguities, or observations about this page that might affect fact quality (e.g. 'Table headers are cut off', 'Units not clearly stated'). null if no issues.",
            },
        },
        "required": ["facts"],
    },
}

RECONCILIATION_SYSTEM_PROMPT = """You are a fact-reconciliation engine. You receive two facts extracted from different PDF documents and must determine their relationship.

RELATIONSHIP TYPES:
- "corroborates": The two facts assert the same claim with compatible values, even if expressed differently (e.g. different wording, rounding differences within reasonable tolerance).
- "contradicts": The two facts assert conflicting claims about the same thing that cannot both be true, and the difference is NOT explained by a difference in time period, scope, methodology, or unit.
- "contextual_difference": The two facts APPEAR to contradict but the difference is explained by a specific contextual factor: different time periods, different scopes (standalone vs consolidated), different definitions of the metric, different units, or different data vintages. You MUST identify exactly what contextual factor explains the difference.
- "unrelated": The two facts are about different things and should not be compared.

RULES:
1. Your reasoning MUST be specific — reference the exact values, units, time periods, scopes, and evidence quotes from both facts. Generic reasoning like "these seem related" or "the values are different" is NOT acceptable.
2. For "contextual_difference", you MUST name the specific contextual factor (e.g. "Fact A reports standalone revenue while Fact B reports consolidated revenue" or "Fact A covers FY24 while Fact B covers FY23").
3. For "contradicts", explain why the difference cannot be explained by context.
4. For "corroborates", note if values match exactly or approximately, and flag any minor discrepancies.
5. Assign a confidence score (0.0-1.0) for your classification.
"""

RECONCILIATION_TOOL_SCHEMA = {
    "name": "classify_relationship",
    "description": "Classify the relationship between two facts and provide detailed reasoning.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relationship_type": {
                "type": "string",
                "enum": [
                    "corroborates",
                    "contradicts",
                    "contextual_difference",
                    "unrelated",
                ],
                "description": "The relationship between the two facts",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed explanation referencing specific values, units, time periods, and evidence from both facts. Must be specific, not generic.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in this classification (0.0-1.0)",
            },
            "contextual_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For contextual_difference: list the specific factors (e.g. ['different scope: standalone vs consolidated', 'different time period: FY23 vs FY24']). Empty for other types.",
            },
        },
        "required": ["relationship_type", "reasoning", "confidence"],
    },
}
