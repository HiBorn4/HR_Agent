"""
data_science/sub_agents/bigquery/tools.py
-----------------------------------------
BigQuery tools: schema fetching, SQL caching, and NL2SQL generation.

Per-request routing values (NL2SQL_Model, chosen_tables) are available in
tool_context.state, written there by the bigquery agent's
setup_before_agent_call callback, which itself reads from the Vertex AI
session state injected by chat.py.
"""

import datetime
import hashlib
import json
import logging
import os

import numpy as np
import pandas as pd
import yaml

from google.adk.tools import ToolContext
from google.adk.tools.bigquery.client import get_bigquery_client
from google.cloud import bigquery
from google.cloud import firestore
from google.genai import Client
from google.genai.types import HttpOptions

from app.core.config import (
    BQ_PROJECT_ID,
    BQ_DATASET_ID,
    PROJECT_ID,
    LOCATION,
)

from .chase_sql import chase_constants

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment / client setup
# ---------------------------------------------------------------------------
dataset_id = BQ_DATASET_ID
data_project = BQ_PROJECT_ID
compute_project = BQ_PROJECT_ID
vertex_project = PROJECT_ID
location = LOCATION

http_options = HttpOptions(headers={"user-agent": "adk-samples-data-science-agent"})
llm_client = Client(
    vertexai=True,
    project=vertex_project,
    location=location,
    http_options=http_options,
)

# Firestore client for SQL and schema caching
try:
    db = firestore.Client(
        project=vertex_project,
        database=os.getenv("FIRESTORE_DB_NAME"),
    )
except Exception as exc:
    logger.warning("Firestore Client init failed in tools.py: %s", exc)
    db = None

MAX_NUM_ROWS = 10000

# Module-level schema cache (avoids redundant BigQuery calls within a process)
_database_settings_cache: dict | None = None


# ===========================================================================
# SQL CACHE (Firestore)
# ===========================================================================

def get_cached_sql(question: str, domain: str = "default") -> str | None:
    """Return verified SQL from Firestore if it exists, else None."""
    if not db:
        return None
    try:
        q_hash = _hash_question(question)
        doc = db.collection(f"sql_cache_{domain}").document(q_hash).get()
        if doc.exists:
            return doc.to_dict().get("sql_query")
    except Exception as exc:
        logger.warning("SQL cache read error: %s", exc)
    return None


def save_successful_sql(question: str, sql: str, domain: str = "default") -> None:
    """Persist a generated SQL query to Firestore for future requests."""
    if not db:
        return
    try:
        q_hash = _hash_question(question)
        db.collection(f"sql_cache_{domain}").document(q_hash).set(
            {
                "question": question,
                "sql_query": sql,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "verified": False,
            }
        )
    except Exception as exc:
        logger.warning("SQL cache write error: %s", exc)


# ===========================================================================
# SCHEMA CACHE (Firestore)
# ===========================================================================

def get_cached_schema(bq_dataset_id: str, bq_project: str) -> dict | None:
    """Return the schema dict from Firestore if cached, else None."""
    if not db:
        return None
    try:
        doc_key = f"{bq_project}_{bq_dataset_id}"
        doc = db.collection("schema_cache").document(doc_key).get()
        if doc.exists:
            raw = doc.to_dict().get("schema")
            # Schema is stored as a JSON string
            if isinstance(raw, str):
                return json.loads(raw)
            return raw
    except Exception as exc:
        logger.warning("Schema cache read error: %s", exc)
    return None


def save_schema_to_cache(schema: dict, bq_dataset_id: str, bq_project: str) -> None:
    """Persist a schema dict to Firestore as a JSON string."""
    if not db:
        return
    try:
        schema_json = json.dumps(schema, default=str)
        db.collection("schema_cache").document(f"{bq_project}_{bq_dataset_id}").set(
            {
                "schema": schema_json,
                "timestamp": datetime.datetime.utcnow(),
            }
        )
        logger.debug("Schema cached for %s.%s", bq_project, bq_dataset_id)
    except Exception as exc:
        logger.warning("Schema cache write error: %s", exc)


# ===========================================================================
# DATABASE SETTINGS
# ===========================================================================

def get_database_settings(chosen_tables: list | None = None) -> dict:
    """
    Return database settings, using the module-level cache when no specific
    tables are requested.
    """
    global _database_settings_cache

    if chosen_tables is None and _database_settings_cache is not None:
        return _database_settings_cache

    result = _build_database_settings(chosen_tables=chosen_tables)

    if chosen_tables is None:
        _database_settings_cache = result

    return result


def _build_database_settings(chosen_tables: list | None = None) -> dict:
    schema = get_bigquery_schema_and_samples(chosen_tables=chosen_tables)
    return {
        "data_project_id": data_project,
        "dataset_id": dataset_id,
        "schema": schema,
        **chase_constants.chase_sql_constants_dict,
    }


def get_bigquery_schema_and_samples(chosen_tables: list | None = None) -> dict:
    """
    Return table schema dicts from Firestore cache, or fetch from BigQuery.

    chosen_tables: list of table references (project.dataset.table or just
    table_id).  Only tables in this list are included in the returned schema.
    """
    if chosen_tables:
        # Normalise: keep only the table_id portion (last segment after '.')
        table_ids = [t.split(".")[-1] for t in chosen_tables]
    else:
        table_ids = ["successfactors_employee_master"]

    # Try Firestore cache first
    cached = get_cached_schema(dataset_id, data_project)
    if cached:
        logger.info("🚀 Using cached schema from Firestore")
        return cached

    # Fetch from BigQuery
    logger.info("🔄 Fetching schema from BigQuery for tables: %s", table_ids)

    client = get_bigquery_client(project=compute_project, credentials=None)
    dataset_ref = bigquery.DatasetReference(data_project, dataset_id)
    tables_context: dict = {}

    for table in client.list_tables(dataset_ref):
        if table.table_id not in table_ids:
            continue

        logger.debug("Loading table schema: %s", table.table_id)
        table_ref = dataset_ref.table(table.table_id)
        table_info = client.get_table(table_ref)

        sqlglot_schema = [
            [field.name, field.field_type] for field in table_info.schema
        ]
        llm_schema = [
            {
                "column_name": field.name,
                "data_type": field.field_type,
                "description": field.description or "",
            }
            for field in table_info.schema
        ]
        table_description = table_info.description or "No table description available"

        # Sample rows for richer LLM context
        sample_values: dict = {}
        try:
            df = client.query(
                f"SELECT * FROM `{table_ref}` ORDER BY RAND() LIMIT 3"
            ).to_dataframe()
            if not df.empty:
                sample_values = {
                    col: [_serialize_value_for_sql(v) for v in vals]
                    for col, vals in df.to_dict(orient="list").items()
                }
        except Exception as exc:
            logger.warning("Failed to fetch samples for %s: %s", table_ref, exc)

        tables_context[str(table_ref)] = {
            "table_schema": sqlglot_schema,
            "table_description": table_description,
            "columns_metadata": llm_schema,
            "example_values": sample_values,
        }

    save_schema_to_cache(tables_context, dataset_id, data_project)
    return tables_context


# ===========================================================================
# NL2SQL — BASELINE
# ===========================================================================

_NL2SQL_PROMPT = """
You are a BigQuery SQL expert. Generate valid BigQuery SQL for the question below.

Guidelines:
- Use full table names from the schema.
- For person name columns: use LOWER(col) LIKE '%token%' per word, never =.
- Age: DATE_DIFF(CURRENT_DATE(), birth_date, YEAR)
- Tenure: DATE_DIFF(CURRENT_DATE(), joining_date, YEAR)
- Return only the SQL query, no explanation.

Schema:
{SCHEMA}

Question: {QUESTION}
"""


def bigquery_nl2sql(
    question: str,
    tool_context: ToolContext,
    domain: str = "default",
) -> str:
    """
    Generate a SQL query from a natural language question.

    Fast path: Firestore SQL cache (hit → return immediately)
    Slow path: LLM generation → save to cache

    The LLM model used is read from the BASELINE_NL2SQL_MODEL env var.
    The NL2SQL method (BASELINE vs CHASE) is available in
    tool_context.state["nl2sql_method"] if callers need to branch on it.
    """
    logger.debug("bigquery_nl2sql — question: %s", question)

    nl2sql_method = tool_context.state.get("nl2sql_method", "BASELINE")
    logger.info("NL2SQL method in use: %s", nl2sql_method)

    # Fast path
    cached_sql = get_cached_sql(question, domain)
    if cached_sql:
        logger.info("🚀 SQL cache HIT for: %s", question[:80])
        tool_context.state["sql_query"] = cached_sql
        return cached_sql

    # Slow path — LLM generation
    logger.info("🧠 SQL cache MISS — generating via LLM")

    schema = tool_context.state["database_settings"]["bigquery"]["schema"]
    prompt = _NL2SQL_PROMPT.format(
        SCHEMA=schema,
        QUESTION=question,
    )

    response = llm_client.models.generate_content(
        model=os.getenv("BASELINE_NL2SQL_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config={"temperature": 0.1},
    )

    sql: str = response.text or ""
    sql = sql.replace("```sql", "").replace("```", "").strip()

    save_successful_sql(question, sql, domain)
    tool_context.state["sql_query"] = sql

    logger.debug("bigquery_nl2sql — generated SQL:\n%s", sql)
    return sql


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _hash_question(question: str) -> str:
    clean = question.strip().lower().replace("?", "")
    return hashlib.sha256(clean.encode()).hexdigest()


def _serialize_value_for_sql(value) -> str:
    """Convert a pandas/numpy value to a BigQuery SQL literal string."""
    if isinstance(value, (list, np.ndarray)):
        return f"[{', '.join(_serialize_value_for_sql(v) for v in value)}]"
    if pd.isna(value):
        return "NULL"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, bytes):
        decoded = value.decode("utf-8", "replace")
        escaped = decoded.replace("\\", "\\\\").replace("'", "''")
        return f"b'{escaped}'"
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return f"'{value}'"
    if isinstance(value, dict):
        return f"({', '.join(_serialize_value_for_sql(v) for v in value.values())})"
    return str(value)