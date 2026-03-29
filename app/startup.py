"""
app/startup.py
--------------
One-time service bootstrap executed at application startup.
All heavy singletons (Firestore, ADK SessionService, Runner, Gemini) are
initialised here and exposed as module-level singletons that the rest of the
application imports.

Usage
-----
    from app.startup import runner, session_service, firestore_db, ...
"""

import os
import traceback

import google.generativeai as genai
from google.cloud import aiplatform, firestore
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService

from app.core.config import (
    BQ_PROJECT_ID,
    FIRESTORE_DB_NAME,
    GEMINI_API_KEY,
    LOCATION,
    PROJECT_ID,
    REASONING_ENGINE_APP_NAME,
    CREDENTIALS_PATH,
    BQ_DATASET_ID,
)
from app.core.logging import get_logger
from dynamic_prompting.prompt_manager import PromptManager
from dynamic_prompting.schema_profiler import SchemaProfiler

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Public singletons — consumers import these directly
# ---------------------------------------------------------------------------
session_service: VertexAiSessionService | None = None
artifact_service: InMemoryArtifactService | None = None
runner: Runner | None = None
root_agent = None
firestore_db: firestore.AsyncClient | None = None
_prompt_manager: PromptManager | None = None

# Status flags consumed by /system_status and /health endpoints
GOOGLE_IMPORTS_SUCCESS: bool = False
AGENT_LOADED: bool = False
RAG_AVAILABLE: bool = False
RAG_CONFIGURED: bool = False
IMAGE_GEN_AVAILABLE: bool = False


# In-memory session stores (lightweight, no persistence needed for these)
authenticated_users: dict = {}
adhoc_sessions: dict = {}

def _init_prompt_manager() -> None:
    """
    Create PromptManager once at startup.
    Warm schema cache immediately to avoid 9s BigQuery delay on first request.
    """
    global _prompt_manager

    try:
        profiler = SchemaProfiler(project_id=PROJECT_ID, credentials_path=CREDENTIALS_PATH, dataset_id=BQ_DATASET_ID)
        rules_path = os.path.join(
            os.path.dirname(__file__),
            "../dynamic_prompting/domain_rules.yaml"
        )

        _prompt_manager = PromptManager(
            schema_profiler=profiler,
            rules_path=rules_path
        )

        # 🔥 Warm cache immediately
        _prompt_manager._get_schema_cached(
            ["successfactors_employee_master"]
        )

        logger.info("✅ PromptManager singleton initialised & schema cache warmed")

    except Exception:
        logger.exception("❌ PromptManager initialisation failed")
        _prompt_manager = None

def _init_firestore() -> None:
    global firestore_db
    try:
        firestore_db = firestore.AsyncClient(
            project=PROJECT_ID,
            database=FIRESTORE_DB_NAME,
        )
        logger.info("🔥 Firestore initialised: DB='%s'", FIRESTORE_DB_NAME)
    except Exception:
        logger.exception("❌ Firestore initialisation failed")
        firestore_db = None


def _init_vertex_session_service() -> None:
    global session_service
    try:
        session_service = VertexAiSessionService(project=PROJECT_ID, location=LOCATION)
        logger.info("💾 Vertex AI SessionService initialised (%s / %s)", PROJECT_ID, LOCATION)
    except Exception:
        logger.exception("❌ Vertex AI SessionService initialisation failed")
        session_service = None


def _init_vertex_ai_platform() -> None:
    global IMAGE_GEN_AVAILABLE
    try:
        if BQ_PROJECT_ID:
            aiplatform.init(project=BQ_PROJECT_ID, location="us-central1")
            IMAGE_GEN_AVAILABLE = True
            logger.info("🖼️  Vertex AI platform initialised for project: %s", BQ_PROJECT_ID)
        else:
            logger.warning("⚠️  Vertex AI skipped — BQ_PROJECT_ID not set")
    except Exception:
        logger.exception("❌ Vertex AI platform init failed")


def _init_gemini_rag() -> None:
    global RAG_AVAILABLE, RAG_CONFIGURED
    try:
        if not GEMINI_API_KEY:
            raise EnvironmentError("GEMINI_API_KEY is not set")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-pro")
        resp = model.generate_content("System test: respond 'OK'")
        if resp and "OK" in resp.text:
            RAG_AVAILABLE = RAG_CONFIGURED = True
            logger.info("✅ Gemini RAG configured")
        else:
            logger.warning("⚠️  Gemini API responded but could not be verified")
    except Exception:
        logger.exception("❌ Gemini RAG setup failed")
        RAG_AVAILABLE = RAG_CONFIGURED = False


def _init_google_adk() -> None:
    global GOOGLE_IMPORTS_SUCCESS
    try:
        # Validate that ADK packages are importable (they were already imported above)
        GOOGLE_IMPORTS_SUCCESS = True
        logger.info("✅ Google ADK imports verified")
    except ImportError:
        logger.exception("❌ Google ADK import failed")


def _init_root_agent() -> None:
    global root_agent, AGENT_LOADED
    if not GOOGLE_IMPORTS_SUCCESS:
        logger.warning("⚠️  Skipping agent load — Google ADK not ready")
        return
    try:
        from data_science.agent import root_agent as _agent  # noqa: PLC0415
        root_agent = _agent
        AGENT_LOADED = True
        logger.info("✅ Agent loaded: %s (model: %s)", root_agent.name, root_agent.model)
    except Exception:
        logger.exception("❌ Agent import failed")
        root_agent = None
        AGENT_LOADED = False


def _init_adk_runner() -> None:
    global runner, artifact_service
    if not (GOOGLE_IMPORTS_SUCCESS and AGENT_LOADED and session_service):
        logger.warning("⚠️  Skipping Runner init — missing prerequisites")
        return
    try:
        artifact_service = InMemoryArtifactService()
        runner = Runner(
            app_name=REASONING_ENGINE_APP_NAME,
            agent=root_agent,
            artifact_service=artifact_service,
            session_service=session_service,
        )
        logger.info("✅ ADK Runner initialised for app: %s", REASONING_ENGINE_APP_NAME)
    except Exception:
        logger.error("❌ ADK Runner init failed:\n%s", traceback.format_exc())
        runner = None

def get_prompt_manager() -> PromptManager:
    return _prompt_manager

def initialise_services() -> None:
    """
    Run all service bootstrap steps in the correct dependency order.
    Call this once from the FastAPI lifespan or startup event.
    """
    logger.info("🚀 Starting service initialisation...")

    _init_firestore()
    _init_vertex_session_service()
    _init_vertex_ai_platform()
    _init_gemini_rag()
    _init_google_adk()
    _init_root_agent()
    _init_adk_runner()
    _init_prompt_manager()

    logger.info(
        "🏁 Init summary → ADK:%s | RAG:%s | IMG_GEN:%s | Agent:%s"
        " | SessionSvc:%s | Runner:%s | Firestore:%s",
        GOOGLE_IMPORTS_SUCCESS,
        RAG_CONFIGURED,
        IMAGE_GEN_AVAILABLE,
        AGENT_LOADED,
        session_service is not None,
        runner is not None,
        firestore_db is not None,
    )
