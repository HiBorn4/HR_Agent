"""
data_science/sub_agents/bigquery/agent.py
-----------------------------------------
BigQuery sub-agent.

FIXES applied in this version
------------------------------
1.  **ValueError: Function initial_bq_nl2sql not found** (the crash you saw)
    The old prompt instructed the LLM to call `initial_bq_nl2sql` and
    `execute_sql_on_session`, but those tool names were never registered on
    the agent.  The only NL2SQL tool registered is `nl2sql_router_tool`.

    Fix: The prompt (prompts.py) now uses the exact names of the two tools
    that ARE registered:
        • `nl2sql_router_tool`   — generates SQL (CHASE or BASELINE)
        • `execute_sql`          — ADK built-in that runs the SQL

2.  **Clean two-step flow**
    The LLM is now explicitly instructed to:
        Step 1 → call nl2sql_router_tool(question)  → get SQL string
        Step 2 → call execute_sql(sql)              → get rows
    This replaces the old ambiguous "validate/cache/session" pattern that
    required phantom tools.

3.  **store_results_in_context** unchanged — still saves rows to
    state["bigquery_query_result"] so call_analytics_agent can read them.

Router output keys used
-----------------------
  "NL2SQL_Model"  → "CHASE" or "BASELINE"
  "BQA_Agent"     → model string, e.g. "gemini-2.5-pro"
  "chosen_tables" → list of table names
"""

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from google.adk.planners import BuiltInPlanner

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.genai import types

from . import tools
from .chase_sql import chase_db_tools
from .prompts import return_instructions_bigquery

logger = logging.getLogger(__name__)

ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL = "execute_sql"

_bigquery_toolset = BigQueryToolset(
    tool_filter=[ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL],
    bigquery_tool_config=BigQueryToolConfig(
        write_mode=WriteMode.BLOCKED,
        application_name="adk-samples-data-science-agent",
    ),
)


# ===========================================================================
# BEFORE-AGENT CALLBACK
# ===========================================================================

def setup_before_agent_call(callback_context: CallbackContext) -> None:
    """
    Read router_output from state and apply model + NL2SQL method + table selection.

    State key "router_output" is written by the root agent's before_agent_callback
    (data_science/agent.py → load_router_output_into_state).
    """
    router_output: dict = callback_context.state.get("router_output", {})

    bqa_model: str = (
        router_output.get("BQA_Agent")
        or os.getenv("BIGQUERY_AGENT_MODEL", "gemini-2.5-flash")
    )

    # "NL2SQL_Model" value is "CHASE" or "BASELINE"
    nl2sql_method: str = (
        router_output.get("NL2SQL_Model")
        or os.getenv("NL2SQL_METHOD", "BASELINE")
    ).upper()

    chosen_tables: list = (
        router_output.get("chosen_tables")
        or ["successfactors_employee_master"]
    )

    logger.info(
        "🤖 BQ agent setup — model:%s | NL2SQL:%s | tables:%s",
        bqa_model, nl2sql_method, chosen_tables,
    )

    # Dynamically override the agent model for this invocation
    try:
        if (
            hasattr(callback_context, "_invocation_context")
            and hasattr(callback_context._invocation_context, "agent")
        ):
            callback_context._invocation_context.agent.model = bqa_model
            logger.info("✅ BQ agent model set to: %s", bqa_model)
        else:
            logger.warning("⚠️  Could not access invocation_context.agent — model override skipped")
    except Exception as exc:
        logger.warning("⚠️  Failed to override BQ agent model: %s", exc)

    # Persist routing decisions into state so nl2sql_router_tool reads them at call-time
    callback_context.state["nl2sql_method"] = nl2sql_method
    callback_context.state["chosen_tables"] = chosen_tables

    # Load schema / database settings once per session
    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = tools.get_database_settings(
            chosen_tables=chosen_tables
        )
        logger.info("📂 Database settings loaded for tables: %s", chosen_tables)
    else:
        logger.debug("📂 Database settings already in state — skipping reload")


# ===========================================================================
# NL2SQL ROUTER TOOL
# Dispatches to CHASE or BASELINE based on state["nl2sql_method"].
# This is the ONLY NL2SQL tool registered on the agent — the prompt must
# reference it by this exact name: nl2sql_router_tool
# ===========================================================================

def nl2sql_router_tool(question: str, tool_context: ToolContext) -> str:
    """
    Generates a BigQuery SQL query from a natural-language question.

    Reads state["nl2sql_method"] (written by setup_before_agent_call) and
    delegates to the correct implementation:
        "CHASE"    → chase_db_tools.initial_bq_nl2sql()
        "BASELINE" → tools.bigquery_nl2sql()

    Returns the SQL string. The agent must then call execute_sql() with
    project_id and query parameters.
    """
    from app.core.config import BQ_PROJECT_ID as _BQ_PROJECT_ID  # noqa: PLC0415

    method: str = tool_context.state.get("nl2sql_method", "BASELINE").upper()
    logger.info("🔀 nl2sql_router_tool — method: %s | question: %s", method, question[:120])

    # Ensure project_id is always stored in state so the LLM can reference it
    if not tool_context.state.get("bq_project_id"):
        bq_settings = tool_context.state.get("database_settings", {}).get("bigquery", {})
        tool_context.state["bq_project_id"] = (
            bq_settings.get("data_project_id") or _BQ_PROJECT_ID or ""
        )
        logger.info("📌 bq_project_id set in state: %s", tool_context.state["bq_project_id"])

    if method == "CHASE":
        logger.info("🔗 Delegating to CHASE NL2SQL")
        return chase_db_tools.initial_bq_nl2sql(question, tool_context)

    logger.info("🔗 Delegating to BASELINE NL2SQL")
    return tools.bigquery_nl2sql(question, tool_context)


# ===========================================================================
# AFTER-TOOL CALLBACK — captures SQL execution results into state
# ===========================================================================

def _json_serializable(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_json_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    return obj


def store_results_in_context(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict,
) -> Optional[Dict]:
    """
    After execute_sql succeeds, save the rows to state["bigquery_query_result"]
    so call_analytics_agent (in data_science/tools.py) can read them.
    """
    if tool.name != ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL:
        return None
    if tool_response.get("status") != "SUCCESS":
        return None

    rows = _json_serializable(tool_response.get("rows", []))
    tool_response["rows"] = rows
    tool_context.state["bigquery_query_result"] = rows

    logger.info("✅ Stored %d rows in state['bigquery_query_result']", len(rows))

    # Optional side-channel: persist to Firestore for cross-request access
    try:
        session_id = (
            getattr(tool_context, "session_id", None)
            or tool_context.state.get("session_id")
        )
        if session_id and tools.db:
            tools.db.collection("session_interim_results").document(session_id).set({
                "latest_rows": rows,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.info("✅ Cached %d rows for session %s", len(rows), session_id)
    except Exception as exc:
        logger.warning("⚠️  Firestore side-channel write failed: %s", exc)

    return tool_response


# ===========================================================================
# AGENT DEFINITION
# ===========================================================================

bigquery_agent = LlmAgent(
    model=os.getenv("BIGQUERY_AGENT_MODEL", "gemini-2.5-flash"),
    name="bigquery_agent",
    instruction=return_instructions_bigquery(),
    tools=[
        nl2sql_router_tool,   # ONLY NL2SQL entry-point — CHASE or BASELINE
        _bigquery_toolset,    # provides execute_sql
    ],
    before_agent_callback=setup_before_agent_call,
    after_tool_callback=store_results_in_context,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.00,
        
    ),
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=128,  # Lowered from 2048 to 512 tokens
        )
    )
)