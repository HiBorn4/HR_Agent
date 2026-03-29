"""
data_science/sub_agents/analytics/agent.py
-------------------------------------------
Analytics sub-agent.

The Analytics_Agent model is driven by the router_output dict injected into
the Vertex AI session state by chat.py BEFORE runner.run() is called.

Fallback chain (if a value is missing at any level):
  router_output["Analytics_Agent"]  ->  env var ANALYTICS_AGENT_MODEL  ->  "gemini-2.5-flash"
"""

import logging
import os

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors import VertexAiCodeExecutor

from .prompts import return_instructions_analytics

logger = logging.getLogger(__name__)


# ===========================================================================
# BEFORE-AGENT CALLBACK — applies router_output from session state
# ===========================================================================

def setup_before_analytics_call(callback_context: CallbackContext) -> None:
    """
    Read the Analytics_Agent model from the router_output in session state
    and dynamically override the agent's model for this invocation.

    State key: "router_output"
    Written by: app/routers/chat.py::_inject_router_output_into_session()

    Fallback chain
    --------------
    router_output["Analytics_Agent"]  ->  ANALYTICS_AGENT_MODEL env var  ->  "gemini-2.5-flash"
    """
    router_output: dict = callback_context.state.get("router_output", {})

    analytics_model: str = (
        router_output.get("Analytics_Agent")
        or os.getenv("ANALYTICS_AGENT_MODEL", "gemini-2.5-flash")
    )

    logger.info("📈 Analytics agent setup — model: %s", analytics_model)

    try:
        if (
            hasattr(callback_context, "_invocation_context")
            and hasattr(callback_context._invocation_context, "agent")
        ):
            callback_context._invocation_context.agent.model = analytics_model
            logger.info("✅ Analytics agent model set to: %s", analytics_model)
        else:
            logger.warning(
                "⚠️  Could not access invocation_context.agent — model override skipped"
            )
    except Exception as exc:
        logger.warning("⚠️  Failed to override analytics agent model: %s", exc)


# ===========================================================================
# AGENT DEFINITION
# ===========================================================================

analytics_agent = Agent(
    model=os.getenv("ANALYTICS_AGENT_MODEL", "gemini-2.5-flash"),
    name="analytics_agent",
    instruction=return_instructions_analytics(),
    before_agent_callback=setup_before_analytics_call,
    code_executor=VertexAiCodeExecutor(
        optimize_data_file=True,
        stateful=True,
    ),
)