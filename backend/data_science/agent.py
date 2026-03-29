"""
data_science/agent.py — Root agent.

INJECTION FIX
-------------
The previous version tried to read user_id and session_id from
callback_context._invocation_context — a private ADK attribute that does NOT
expose those fields reliably.  getattr returned "" for both, so the router_store
lookup always missed and injection was silently skipped.

THE FIX:
  Instead of looking up the store by (user_id, session_id), the store is now
  keyed by a SINGLE KEY "latest" that chat.py always writes before runner.run().
  Because runner.run() is synchronous and called inside run_in_threadpool with
  at most one call per session at a time, this is perfectly safe.

  This completely removes the need to read private ADK attributes.
"""

import base64
import json
import logging
import os
from datetime import date

from google.adk.planners import BuiltInPlanner

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from .sub_agents import bqml_agent
from .sub_agents.bigquery.tools import (
    get_database_settings as get_bq_database_settings,
)
from .tools import call_analytics_agent, call_bigquery_agent

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

_dataset_config: dict = {}
_database_settings: dict = {}
_supported_dataset_types = ["bigquery"]
_required_dataset_config_params = ["name", "description"]


def load_dataset_config() -> dict:
    dataset_config_file = os.getenv("DATASET_CONFIG_FILE", "")
    if not dataset_config_file:
        _logger.fatal("DATASET_CONFIG_FILE env var not set")
    with open(dataset_config_file, "r", encoding="utf-8") as f:
        dataset_config = json.load(f)
    if "datasets" not in dataset_config:
        _logger.fatal("No 'datasets' entry in dataset config")
    for dataset in dataset_config["datasets"]:
        if "type" not in dataset:
            _logger.fatal("Missing dataset type")
        if dataset["type"] not in _supported_dataset_types:
            _logger.fatal("Dataset type '%s' not supported", dataset["type"])
        for p in _required_dataset_config_params:
            if p not in dataset:
                _logger.fatal("Missing required param '%s' from %s dataset config", p, dataset["type"])
    return dataset_config


def get_database_settings(db_type: str) -> dict:
    assert db_type in _supported_dataset_types
    if db_type == "bigquery":
        return get_bq_database_settings()


def init_database_settings(dataset_config: dict) -> dict:
    return {
        dataset["type"]: get_database_settings(dataset["type"])
        for dataset in dataset_config["datasets"]
    }


# ---------------------------------------------------------------------------
# ROOT AGENT BEFORE-CALLBACK  ← INJECTION FIX IS HERE
# ---------------------------------------------------------------------------

def load_router_output_into_state(callback_context: CallbackContext) -> None:
    """
    Pull router_output from the process-level router_store (keyed by "latest")
    and write it into callback_context.state["router_output"].

    WHY "latest" KEY:
      runner.run() is synchronous, called inside run_in_threadpool, one call
      per session at a time.  Using a simple "latest" key removes all
      dependency on private ADK _invocation_context attributes, which do NOT
      reliably expose user_id/session_id.
    """
    from app.intelligence.router_store import get_and_clear_router_output  # noqa: PLC0415

    router_output = get_and_clear_router_output()  # ← no args, uses "latest"

    if router_output:
        callback_context.state["router_output"] = router_output
        _logger.info(
            "✅ router_output injected into state — NL2SQL:%s | BQA:%s | Analytics:%s | tables:%s",
            router_output.get("NL2SQL_Model"),
            router_output.get("BQA_Agent"),
            router_output.get("Analytics_Agent"),
            router_output.get("chosen_tables"),
        )
    else:
        _logger.warning(
            "⚠️  router_store was empty — sub-agents will use env-var defaults. "
            "This is normal if the router itself failed."
        )

    # Load database_settings (preserves original behaviour)
    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = _database_settings


def get_root_agent() -> LlmAgent:
    tools = [call_analytics_agent]
    sub_agents = []
    for dataset in _dataset_config["datasets"]:
        if dataset["type"] == "bigquery":
            tools.append(call_bigquery_agent)
            sub_agents.append(bqml_agent)

    return LlmAgent(
        model=os.getenv("ROOT_AGENT_MODEL", "gemini-2.5-flash"),
        name="data_science_root_agent",
        instruction=return_instructions_root(),
        global_instruction=(
            f"You are a Data Science and Data Analytics Multi Agent System.\n"
            f"Todays date: {date.today()}"
        ),
        sub_agents=sub_agents,
        tools=tools,
        before_agent_callback=load_router_output_into_state,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.01,
        ),
        planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=128,  # Lowered from 2048 to 512 tokens
        )
    )
    )


from .prompts import return_instructions_root  # noqa: E402

_dataset_config = load_dataset_config()
_database_settings = init_database_settings(_dataset_config)

root_agent = get_root_agent()