"""
app/routers/chat.py
-------------------
Core chat endpoint:
  POST /chat — Routes a user message through the BigQuery agent or adhoc analysis pipeline.

HOW ROUTER OUTPUT REACHES THE AGENTS
--------------------------------------
Neither Runner.run(state=...) nor VertexAiSessionService.update_session()
exist in the ADK SDK.  The correct pattern is:

  1.  route_query()  →  get router_output dict
  2.  router_store.set_router_output(user_id, session_id, router_output)
  3.  runner.run(user_id, session_id, new_message)   ← no state= arg
  4.  Root agent's before_agent_callback calls
      router_store.get_and_clear_router_output() and writes the result into
      callback_context.state["router_output"]
  5.  Sub-agent callbacks read callback_context.state["router_output"] normally

This is fully thread-safe: runner.run() is synchronous and there is at most
one call per (user_id, session_id) at a time.
"""

import asyncio
import io
import re
import secrets
import time
import traceback

import google.generativeai as genai
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from google.genai import types

from app.auth.utils import login_required
from app.core.logging import get_logger
from app.db.firestore import cache_response, get_cached_response, log_chat_message
from app.intelligence.router import route_query
from app.intelligence.router_store import set_router_output   # ← NEW
from app.routers.auth import _get_session_user_info
from app.services.gcs import load_dataframe_from_gcs
from app.services.text_processing import (
    filter_llm_response,
    generate_smart_suggestions,
    parse_markdown_tables,
)

logger = get_logger(__name__)

router = APIRouter(tags=["Chat"])

_ROUTER_FALLBACK: dict = {
    "chosen_tables": ["successfactors_employee_master"],
    "columns_matched": {},
    "NL2SQL_Model": "CHASE",
    "BQA_Agent": "gemini-2.5-pro",
    "Analytics_Agent": "gemini-2.5-pro",
}


# ===========================================================================
# PRIMARY ENDPOINT
# ===========================================================================

@router.post("/chat")
async def mahindra_chat(
    request: Request,
    user: dict = Depends(login_required),
):
    try:
        data = await request.json()

        if not data or "message" not in data:
            return JSONResponse(
                {"error": "Missing 'message' in request body"}, status_code=400
            )

        user_message: str = data["message"]
        session_id: str | None = data.get("session_id")
        mode: str = data.get("mode", "bigquery")
        cleaning_instructions: dict = data.get("cleaning_instructions", {})

        user_info = await _get_session_user_info(request)
        user_id = user_info.get("id")

        if not user_id:
            return JSONResponse(
                {"error": "Authentication error: user ID not found"}, status_code=401
            )

        current_session_id = session_id or f"{mode}_{secrets.token_hex(8)}"

        # ------------------------------------------------------------------
        # 1. MODEL ROUTING
        # ------------------------------------------------------------------
        try:
            router_output = route_query(user_message)
            logger.info(
                "🔀 Router decision — NL2SQL:%s | BQA:%s | Analytics:%s | tables:%s",
                router_output.get("NL2SQL_Model"),
                router_output.get("BQA_Agent"),
                router_output.get("Analytics_Agent"),
                router_output.get("chosen_tables"),
            )
        except Exception as exc:
            logger.warning("Model router failed — using fallback defaults: %s", exc)
            router_output = _ROUTER_FALLBACK

        # ------------------------------------------------------------------
        # 2. CACHE CHECK
        # ------------------------------------------------------------------
        cached = await get_cached_response(user_message, mode, current_session_id)
        if cached:
            await log_chat_message(current_session_id, user_id, user_message, cached, mode)
            return JSONResponse(cached, status_code=200)

        # ------------------------------------------------------------------
        # 3. DISPATCH
        # ------------------------------------------------------------------
        if mode in {"adhoc", "dynamic"}:
            return await _handle_adhoc_mode(
                user_message=user_message,
                mode=mode,
                user_id=user_id,
                current_session_id=current_session_id,
                cleaning_instructions=cleaning_instructions,
                router_output=router_output,
            )

        return await _handle_bigquery_mode(
            user_message=user_message,
            user_id=user_id,
            current_session_id=current_session_id,
            mode=mode,
            router_output=router_output,
        )

    except Exception:
        logger.error("Unhandled chat error:\n%s", traceback.format_exc())
        return JSONResponse({"error": "An unexpected error occurred"}, status_code=500)


# ===========================================================================
# BIGQUERY MODE
# ===========================================================================

async def _handle_bigquery_mode(
    user_message: str,
    user_id: str,
    current_session_id: str,
    mode: str,
    router_output: dict,
) -> JSONResponse:
    from app.startup import runner  # noqa: PLC0415
    from intelligence.orchestrator import MahindraInsightOrchestrator  # noqa: PLC0415

    if not runner:
        return JSONResponse({"error": "Agent is not available"}, status_code=503)

    # ------------------------------------------------------------------
    # KEY FIX: store router_output in the process-level store BEFORE
    # runner.run().  The root agent's before_agent_callback will read it
    # out and write it into callback_context.state["router_output"].
    #
    # DO NOT pass state= to runner.run() — that parameter does not exist.
    # DO NOT call session_service.update_session() — that method does not exist.
    # ------------------------------------------------------------------
    set_router_output(router_output)
    logger.info(
        "📦 router_output stored for (%s, %s) — NL2SQL:%s | BQA:%s | Analytics:%s",
        user_id, current_session_id,
        router_output.get("NL2SQL_Model"),
        router_output.get("BQA_Agent"),
        router_output.get("Analytics_Agent"),
    )
    
    content = types.Content(role="user", parts=[types.Part(text=user_message)])

    try:
        events = await run_in_threadpool(
            lambda: list(
                runner.run(                       # ← no state= argument
                    user_id=str(user_id),
                    session_id=current_session_id,
                    new_message=content,
                )
            )
        )
    except Exception as exc:
        logger.error("ADK agent execution failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse({"error": f"Agent error: {exc}"}, status_code=500)

    raw_response = "".join(
        part.text
        for part in events[-1].content.parts
        if hasattr(part, "text") and part.text is not None
    )

    clean_text, debug_info = filter_llm_response(raw_response)
    clean_text, extracted_tables = parse_markdown_tables(clean_text)

    orchestrator = MahindraInsightOrchestrator()
    insight_data = await orchestrator.generate_insights_from_text(
        text=clean_text,
        ui_card_id=f"card_{int(time.time())}",
        debug_mode=True,
        query=user_message,
        pre_parsed_tables=extracted_tables,
    )

    tables_payload = [extracted_tables] if extracted_tables else []
    if insight_data and "data_points" in insight_data and not extracted_tables:
        tables_payload.append(insight_data["data_points"])

    related_q = None
    if m := re.search(
        r'\{\s*"related_insight_question":\s*"(.*?)"\s*\}', clean_text, re.DOTALL
    ):
        related_q = m[1]
        clean_text = clean_text.replace(m[0], "").strip()

    suggestions = await generate_smart_suggestions(user_message, clean_text)

    if insight_data and (insight_data.get("plotly_html") or insight_data.get("image_base64")):
        clean_text = re.sub(
            r"GRAPH:\s*[\w\s\(\)0-9]*", "", clean_text,
            flags=re.MULTILINE | re.IGNORECASE,
        ).strip()

    if not clean_text.strip() and not tables_payload and not insight_data:
        logger.warning("Agent returned a blank response — injecting safety message")
        clean_text = (
            "I processed your request but no textual response was generated. "
            "This may be due to missing matching data or an internal extraction error. "
            "Try rephrasing your question."
        )
        if debug_info:
            clean_text += f"\n\n**Debug Details:**\n```\n{debug_info[:400]}...\n```"

    structured: dict = {
        "summaryText": clean_text,
        "tables": tables_payload,
        "relatedInsightQuestion": related_q,
        "debugInfo": debug_info,
        "suggestions": suggestions,
        "routerOutput": router_output,
    }

    if insight_data and "plotly_html" in insight_data:
        structured["plotly_html"] = insight_data["plotly_html"]
    elif insight_data and "image_base64" in insight_data:
        structured["image_base64"] = insight_data["image_base64"]

    payload = {
        "status": "Success",
        "data": structured,
        "session_id": current_session_id,
    }
    await _persist(user_message, mode, payload, current_session_id, user_id)
    return JSONResponse(payload, status_code=200)


# ===========================================================================
# ADHOC / DYNAMIC MODE
# ===========================================================================

async def _handle_adhoc_mode(
    user_message: str,
    mode: str,
    user_id: str,
    current_session_id: str,
    cleaning_instructions: dict,
    router_output: dict,
) -> JSONResponse:
    from app.startup import adhoc_sessions  # noqa: PLC0415
    from utils import (  # noqa: PLC0415
        apply_data_transformations,
        generate_image_with_ai,
        get_ml_intent,
        is_image_generation_request,
    )

    if is_image_generation_request(user_message):
        image_b64 = await generate_image_with_ai(user_message)
        if not image_b64:
            return JSONResponse({"error": "Image generation failed"}, status_code=500)
        payload = _build_response_payload(
            summary_text=user_message,
            image_base64=image_b64,
            session_id=current_session_id,
            related_question="Generate another image?",
        )
        await _persist(user_message, mode, payload, current_session_id, user_id)
        return JSONResponse(payload)

    await _restore_adhoc_session_if_needed(user_id, adhoc_sessions)

    if user_id not in adhoc_sessions or "df" not in adhoc_sessions[user_id]:
        return JSONResponse(
            {"error": "No file has been uploaded for this session"}, status_code=400
        )

    session_info = adhoc_sessions[user_id]
    df = apply_data_transformations(session_info["df"], cleaning_instructions)
    ml_intent = await get_ml_intent(user_message)

    if ml_intent:
        return await _handle_ml_intent(
            ml_intent=ml_intent,
            df=df,
            user_message=user_message,
            session_info=session_info,
            current_session_id=current_session_id,
            mode=mode,
            user_id=user_id,
            router_output=router_output,
        )

    analytics_model = router_output.get("Analytics_Agent", "gemini-2.5-pro")
    return await _handle_adhoc_general(
        df=df,
        user_message=user_message,
        session_info=session_info,
        current_session_id=current_session_id,
        mode=mode,
        user_id=user_id,
        analytics_model=analytics_model,
    )


# ===========================================================================
# ML INTENT DISPATCHER
# ===========================================================================

async def _handle_ml_intent(
    ml_intent: str,
    df,
    user_message: str,
    session_info: dict,
    current_session_id: str,
    mode: str,
    user_id: str,
    router_output: dict,
) -> JSONResponse:
    from utils import (  # noqa: PLC0415
        perform_advanced_forecast,
        perform_anomaly_detection,
        perform_eda_dashboard,
        perform_linear_regression_prediction,
        perform_model_testing,
        perform_visual_and_code_gen_analysis,
    )

    try:
        report_text, plot_b64 = "", None
        display_name = session_info["display_name"]

        dispatch = {
            "model_testing": lambda: perform_model_testing(
                df.copy(), user_message, display_name, current_session_id, user_id
            ),
            "advanced_forecast": lambda: perform_advanced_forecast(
                df.copy(), user_message, display_name
            ),
            "linear_regression_prediction": lambda: perform_linear_regression_prediction(
                df.copy(), user_message, display_name
            ),
            "anomaly_detection": lambda: perform_anomaly_detection(
                df.copy(), user_message, display_name
            ),
            "exploratory_data_analysis": lambda: perform_eda_dashboard(
                df.copy(), user_message, display_name
            ),
        }

        if ml_intent in dispatch:
            report_text, plot_b64 = await dispatch[ml_intent]()
        elif ml_intent.endswith(("_plot", "_code_generation")):
            report_text, plot_b64 = await perform_visual_and_code_gen_analysis(
                df.copy(), user_message, ml_intent, display_name
            )
        else:
            report_text = (
                f"The requested analysis '{ml_intent}' is recognised but not yet implemented."
            )

        related_q = None
        if report_text:
            if m := re.search(
                r'\{\s*"related_insight_question":\s*"(.*?)"\s*\}', report_text, re.DOTALL
            ):
                related_q = m[1]
                report_text = report_text.replace(m[0], "").strip()

        payload = _build_response_payload(
            summary_text=report_text,
            image_base64=plot_b64,
            session_id=current_session_id,
            related_question=related_q,
        )
        await _persist(user_message, mode, payload, current_session_id, user_id)
        return JSONResponse(payload)

    except Exception as exc:
        logger.error("ML intent handler failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse({"error": f"ML analysis failed: {exc}"}, status_code=500)


async def _handle_adhoc_general(
    df,
    user_message: str,
    session_info: dict,
    current_session_id: str,
    mode: str,
    user_id: str,
    analytics_model: str = "gemini-2.5-pro",
) -> JSONResponse:
    logger.info("📊 Adhoc general query — model: %s", analytics_model)
    try:
        model = genai.GenerativeModel(analytics_model)
        buf = io.StringIO()
        df.info(buf=buf)
        prompt = (
            f"You are a data analyst assistant. User file: '{session_info['display_name']}'.\n"
            f"Metadata:\n{buf.getvalue()}\n"
            f"Preview:\n{df.head(15).to_string()}\n\n"
            f"Query: \"{user_message}\"\n"
            "Answer clearly in Markdown."
        )
        response = await asyncio.to_thread(model.generate_content, prompt)
        payload = {
            "status": "Success",
            "data": {"summaryText": response.text, "tables": []},
            "session_id": current_session_id,
        }
        await _persist(user_message, mode, payload, current_session_id, user_id)
        return JSONResponse(payload)
    except Exception as exc:
        logger.error("General adhoc query failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse({"error": f"Could not process your query: {exc}"}, status_code=500)


# ===========================================================================
# SESSION RESTORATION
# ===========================================================================

async def _restore_adhoc_session_if_needed(user_id: str, adhoc_sessions: dict) -> bool:
    if user_id in adhoc_sessions:
        return True
    from app.db.firestore import get_adhoc_session_metadata  # noqa: PLC0415
    metadata = await get_adhoc_session_metadata(user_id)
    if not metadata:
        return False
    gcs_object = metadata.get("gcs_object_name")
    display_name = metadata.get("display_name")
    if not gcs_object:
        return False
    try:
        df = await load_dataframe_from_gcs(gcs_object)
        adhoc_sessions[user_id] = {
            "display_name": display_name,
            "gcs_object_name": gcs_object,
            "df": df,
            "model_artifacts": {},
        }
        return True
    except Exception:
        logger.error("Failed to restore adhoc session for user %s", user_id, exc_info=True)
        return False


# ===========================================================================
# HELPERS
# ===========================================================================

def _build_response_payload(
    summary_text: str,
    session_id: str,
    image_base64: str | None = None,
    related_question: str | None = None,
) -> dict:
    return {
        "status": "Success",
        "data": {
            "summaryText": summary_text,
            "image_base64": image_base64,
            "tables": [],
        },
        "session_id": session_id,
        "related_insight_question": related_question,
    }


async def _persist(query: str, mode: str, payload: dict, session_id: str, user_id: str) -> None:
    await cache_response(query, mode, payload, session_id)
    await log_chat_message(session_id, user_id, query, payload, mode)