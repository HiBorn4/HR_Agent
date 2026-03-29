import logging
import os

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from .sub_agents import analytics_agent, bigquery_agent
from app.startup import get_prompt_manager

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CREDS = os.path.join(BASE_DIR, "service-account.json")

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "mahindra-datalake-prod-625956")
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDS)
DATASET_ID = os.getenv("BQ_DATASET_ID", "HR_AI_Dataset")


async def call_bigquery_agent(
    question: str,
    tool_context: ToolContext,
):
    """
    Tool to call the BigQuery NL2SQL sub-agent.

    Assembles a rich prompt (JIT schema + business rules) via PromptManager,
    then delegates to the bigquery_agent which will:
      1. Call nl2sql_router_tool  → generate SQL
      2. Call execute_sql         → run SQL and return rows

    Results are stored in:
      state["bigquery_agent_output"]   — full structured JSON from the agent
      state["bigquery_query_result"]   — raw rows list (written by after_tool_callback)
    """
    logger.debug("call_bigquery_agent — question: %s", question)

    final_prompt = question
    try:
        logger.info("🧠 Assembling JIT schema + business rules prompt...")
        pm = get_prompt_manager()
        final_prompt = pm.assemble_prompt(user_query=question)
        logger.info("✅ JIT Prompt assembled successfully.")
    except Exception as exc:
        logger.error("⚠️  JIT prompt assembly failed: %s — using raw question.", exc)
        final_prompt = question

    agent_tool = AgentTool(agent=bigquery_agent)
    bigquery_agent_output = await agent_tool.run_async(
        args={"request": final_prompt}, tool_context=tool_context
    )

    tool_context.state["bigquery_agent_output"] = bigquery_agent_output
    return bigquery_agent_output


async def call_analytics_agent(
    question: str,
    tool_context: ToolContext,
):
    """
    Tool to call the analytics (Python code execution) sub-agent.

    Passes:
      - The natural-language question
      - Raw rows from state["bigquery_query_result"]  (list of dicts from execute_sql)
      - Full BQ agent output from state["bigquery_agent_output"] for extra context

    The analytics agent uses this data to run Python/pandas analysis and
    produce charts or computed metrics.
    """
    logger.debug("call_analytics_agent — question: %s", question)

    # Raw rows stored by BQ agent's after_tool_callback
    raw_rows = tool_context.state.get("bigquery_query_result", "")

    # Full structured BQ output (nl_results, sql, visualization_suggestion, etc.)
    bq_structured = tool_context.state.get("bigquery_agent_output", "")

    question_with_data = f"""
Question to answer: {question}

The following data was retrieved from BigQuery to answer this question.

<RAW_ROWS>
{raw_rows}
</RAW_ROWS>

<BQ_AGENT_CONTEXT>
{bq_structured}
</BQ_AGENT_CONTEXT>
"""

    agent_tool = AgentTool(agent=analytics_agent)
    analytics_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )

    tool_context.state["analytics_agent_output"] = analytics_agent_output
    return analytics_agent_output
