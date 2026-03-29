"""
app/intelligence/router.py
--------------------------
Intelligent query routing engine.

Analyses the user question against BigQuery table metadata and returns:
  - chosen_tables
  - columns_matched
  - NL2SQL_Model  (BASELINE | CHASE)
  - BQA_Agent     (gemini-2.5-flash | gemini-2.5-pro)
  - Analytics_Agent (gemini-2.5-flash | gemini-2.5-pro)
"""

import datetime
import json
import os
from typing import Any

from google import genai
from google.genai import types

from app.core.config import GEMINI_API_KEY
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Gemini client — router always runs against the public API (vertexai=False)
# ---------------------------------------------------------------------------
_client = genai.Client(api_key=GEMINI_API_KEY, vertexai=False)

# ---------------------------------------------------------------------------
# Table metadata — loaded once at import time
# ---------------------------------------------------------------------------
_METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "hr_tables_metadata.json")

try:
    with open(_METADATA_PATH, "r", encoding="utf-8") as _f:
        _TABLE_METADATA: dict = json.load(_f)
except FileNotFoundError:
    logger.warning("⚠️  hr_tables_metadata.json not found at '%s' — router will use empty metadata", _METADATA_PATH)
    _TABLE_METADATA = {}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_router_prompt(question: str) -> str:
    pretty_meta = json.dumps(_TABLE_METADATA, indent=2)

    return f"""
You are a Senior BigQuery Analytics Architect and Intelligent Query Routing Engine.

You are an expert in:
- BigQuery schema reasoning
- Semantic table selection
- NL2SQL model routing
- LLM capability assessment
- Analytics complexity detection

You MUST analyse the metadata and user query with precision and return STRICT JSON ONLY.
No explanations. No commentary. No markdown. Output must be valid JSON.

### OBJECTIVE
Given:
- Full table metadata catalog
- A user business question

Determine:
1. Which tables are required
2. Which columns matched and why
3. Which NL2SQL model is required
4. Which BigQuery Agent model to use
5. Which Analytics Agent model to use

### TABLE METADATA (FULL CATALOG)
{pretty_meta}

### USER QUESTION
"{question}"

### DECISION FRAMEWORK

**1. TABLE SELECTION**
- Select only the minimum required tables using exact column name matches, semantic similarity, and business entity relevance.
- Semantic hints (HR domain):
  employees / headcount / attrition → successfactors_employee_master
  requisition / vacancy            → dim_job_requisition
  application / interview / funnel → fact_job_application
  maternity                        → employee_maternity_details
  org structure / department       → employee_mapping_with_org
  
  Just provide the table names in the output — do NOT include any explanations or justifications.
  Do not include ProjectID.DatasetID prefix — just the raw table names.
  I want only the table names.
  If there are multiple tables then include multiple table names in the array.

**2. NL2SQL MODEL SELECTION**
- BASELINE → Simple SELECT, single table, basic filters, single metric
- CHASE    → Required if ANY: multiple tables, JOIN, GROUP BY across entities,
             window functions, period-over-period comparison, retention/funnel,
             aggregation across time, multiple metrics

**3. BIGQUERY AGENT (BQA_Agent)**
- gemini-2.5-flash → Simple SQL generation
- gemini-2.5-pro   → Complex SQL; force if NL2SQL_Model = CHASE, multi-table,
                     window functions, trend analysis, retention/funnel

**4. ANALYTICS AGENT**
- gemini-2.5-flash → Descriptive stats, simple aggregation
- gemini-2.5-pro   → Multiple KPIs, time series, cohort/retention, anomaly
                     detection, forecasting, charts/plots, comparative metrics

**5. HARD OVERRIDES — non-negotiable**
If ANY of the following appear in the query:
join / across departments / across business units / trend / over time /
last year vs this year / growth / funnel / retention / conversion /
multiple metrics / rolling average / ranking / top N / period comparison

Then FORCE:
  "NL2SQL_Model": "CHASE"
  "BQA_Agent": "gemini-2.5-pro"

### OUTPUT FORMAT (STRICT)
Return ONLY valid JSON — no explanations, no markdown, no trailing commas.

{{
  "chosen_tables": [],
  "columns_matched": {{
    "table_name": ["column1", "column2"]
  }},
  "NL2SQL_Model": "",
  "BQA_Agent": "",
  "Analytics_Agent": ""
}}

If no table is relevant, return empty arrays but still follow the structure.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_query(question: str) -> dict[str, Any]:
    """
    Route *question* to the appropriate tables and models.

    Returns:
        Parsed routing dict with keys: chosen_tables, columns_matched,
        NL2SQL_Model, BQA_Agent, Analytics_Agent.

    Raises:
        ValueError: If the model returns invalid JSON.
    """
    prompt = _build_router_prompt(question)
    start = datetime.datetime.now()

    response = _client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    latency = (datetime.datetime.now() - start).total_seconds()
    logger.info("🔀 Router latency: %.2fs", latency)

    try:
        return json.loads(response.text)
    except Exception as exc:
        raise ValueError(f"Router returned invalid JSON:\n{response.text}") from exc
