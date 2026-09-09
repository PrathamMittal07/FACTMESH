# FactMesh Demo Cases

These four cases have been extracted directly from the live database following the final ingestion run. They demonstrate FactMesh's ability to cross-reference unstructured PDFs, align similar metrics, and gracefully handle extraction pipeline limits.

## Case 1: Cross-Document Corroboration

**Scenario**: The system finds the same metric reported across two different documents and confirms they match despite minor reporting format differences, strengthening the reliability of the fact.

*   **Document A**: India Economic Survey 2024-25 (`01-india-economic-survey-2024-25-excerpt.pdf`)
*   **Document B**: IMF Article IV 2025 (`03-imf-india-2025-article-iv-excerpt.pdf`)
*   **Fact A**: `India / Foreign exchange reserves` = **704.9 USD Billion**
    *   *Evidence*: "As a result of stable capital flows, India's foreign exchange reserves increased from USD 616.7 billion at the end of January 2024 to USD 704.9 billion in September 2024 before moderating to USD 634.6 billion as on 3 January 2025."
*   **Fact B**: `Reserve Bank of India / Foreign Exchange Reserves` = **$706Bn**
    *   *Evidence*: "foreign exchange (FX) reserves declined to $668 billion in March 2025, from $706 billion in September 2024 on significant currency intervention."
*   **Relationship**: `corroborates`
*   **LLM Reasoning**: Both Fact A and Fact B refer to India's foreign exchange reserves for the same time period of September 2024. Fact A states a value of 704.9 USD Billion, while Fact B states $706Bn. These minor numerical discrepancies are standard rounding differences in macroeconomic reporting for the same underlying metric and time period, thus corroborating the general figure.

---

## Case 2: Cross-Document Contradiction (The "Gotcha")

**Scenario**: Two highly credible institutions report differing figures for the exact same metric, scope, and time period. The LLM flags this discrepancy so an analyst can investigate.

*   **Document A**: India Economic Survey 2024-25 (`01-india-economic-survey-2024-25-excerpt.pdf`)
*   **Document B**: RBI Annual Report 2024-25 (`02-rbi-annual-report-2024-25-excerpt.pdf`)
*   **Fact A**: `Global Economy / GDP Growth Rate` = **3.3%**
    *   *Evidence*: "The global economy grew by 3.3 per cent in 2023."
*   **Fact B**: `global economy / GDP Growth Rate` = **3.5%**
    *   *Evidence*: "According to the International Monetary Fund (IMF), global growth at 3.3 per cent in 2024 (3.5 per cent a year ago) was below the historical average (2000-19) of 3.7 per cent"
*   **Relationship**: `contradicts`
*   **LLM Reasoning**: Fact A states that the global economy GDP growth rate in 2023 was 3.3% based on the evidence 'The global economy grew by 3.3 per cent in 2023.' In contrast, Fact B states that the global growth a year ago (referring to 2023) was 3.5%. Although both refer to the same global entity, metric, and time period of 2023, their values conflict directly (3.3% versus 3.5%) without any valid contextual explanation for the discrepancy.

---

## Case 3: Contextual Difference (Nuance Detection)

**Scenario**: The vector search pulls two very similar metrics with different values. The LLM understands the nuance (e.g., initial projection vs. final reported figure) and marks it as a contextual difference, avoiding a false-positive contradiction.

*   **Document A**: India Economic Survey 2024-25 (`01-india-economic-survey-2024-25-excerpt.pdf`)
*   **Document B**: IMF Article IV 2025 (`03-imf-india-2025-article-iv-excerpt.pdf`)
*   **Fact A**: `India / Real GDP Growth Rate` = **6.4%**
    *   *Evidence*: "As per the first advance estimates of national accounts, India's real GDP is estimated to grow by 6.4 per cent in FY25."
*   **Fact B**: `India / Real GDP Growth Rate` = **6.5%**
    *   *Evidence*: "Following economic growth of 6.5 percent in FY2024/25, real GDP expanded by 7.8 percent in the first quarter of FY2025/26."
*   **Relationship**: `contextual_difference`
*   **LLM Reasoning**: Fact A from the India Economic Survey states that India's real GDP is estimated to grow by 6.4 per cent in FY25 based on the first advance estimates. On the other hand, Fact B from the IMF Article IV report cites real GDP growth of 6.5 percent for the same time period of FY2024/25. These differing values reflect distinct institutional projections and reporting methodologies for the same fiscal year.

---

## Case 4: Pipeline Failure Logging

**Scenario**: A document fails mid-processing (e.g., due to an API quota exhaustion). The fail-fast mechanism safely aborts, commits any partial extraction progress to the database, and logs a clean extraction issue for operators.

*   **Document**: Delhivery Annual Report FY24 (`02-delhivery-annual-report-fy24-excerpt.pdf`)
*   **Issue Type**: `parse_error`
*   **Status Code Logged**: `failed`
*   **Issue Detail (Extracted from DB)**: `Pipeline failure: 429 You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits.`
*   **Impact**: Even though the pipeline cleanly aborted upon hitting the 429 ResourceExhausted limit and recorded this issue into the `extraction_issues` table, over 1,000 facts from this document were successfully preserved in the `facts` table due to the immediate commit mechanism implemented in the extraction stage.
