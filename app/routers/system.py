"""
app/routers/system.py
---------------------
System / housekeeping endpoints:
  GET /user                    — Return authenticated user profile
  GET /system_status           — Agent and RAG readiness flags
  GET /health                  — Full health check
  GET /api/suggested-questions — Dynamic question bank from BigQuery (with fallback)
"""

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.cloud import bigquery

from app.auth.utils import login_required
from app.core.config import PROJECT_ID
from app.core.logging import get_logger
from app.routers.auth import _get_session_user_info
from app.core.config import BQ_DATASET_ID

logger = get_logger(__name__)

router = APIRouter(tags=["System"])

_DEFAULT_SUGGESTED_QUESTIONS = [
    {"question": "How many new joiners this month?", "category": "Hiring"},
    {"question": "Show me the attrition rate for Q1", "category": "Attrition"},
    {"question": "What is the average salary by department?", "category": "Compensation"},
    {"question": "List top performing employees", "category": "Performance"},
    {"question": "Headcount by Region", "category": "Demographics"},
    {"question": "Diversity ratio in Engineering", "category": "DEI"},
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/user")
async def get_current_user(request: Request):
    """Return the authenticated user's profile fields."""
    user_info = await _get_session_user_info(request)
    logger.info(
        "GET /user — session_id=%s user_id=%s",
        request.cookies.get("session_id"),
        user_info.get("id"),
    )

    if not user_info or not user_info.get("id"):
        return JSONResponse({"id": None, "name": None, "email": None, "picture": None})

    return JSONResponse(
        {
            "id": user_info.get("id"),
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "picture": user_info.get("picture"),
            "session_id": request.cookies.get("session_id"),
        }
    )


@router.get("/system_status")
async def get_system_status():
    """Return agent and RAG readiness flags."""
    from app.startup import AGENT_LOADED, IMAGE_GEN_AVAILABLE, RAG_CONFIGURED  # noqa: PLC0415

    return JSONResponse(
        {
            "agent_loaded": AGENT_LOADED,
            "rag_configured": RAG_CONFIGURED,
            "image_gen_available": IMAGE_GEN_AVAILABLE,
        }
    )


@router.get("/health")
async def health_check():
    """Full health check — returns component readiness at a glance."""
    from app.startup import (  # noqa: PLC0415
        AGENT_LOADED,
        RAG_AVAILABLE,
        RAG_CONFIGURED,
        adhoc_sessions,
    )

    return JSONResponse(
        {
            "status": "healthy",
            "service": "Mahindra Rise Intelligence Platform V4.0",
            "agent_loaded": AGENT_LOADED,
            "rag_available": RAG_AVAILABLE,
            "rag_configured": RAG_CONFIGURED,
            "active_dynamic_analysis_sessions": len(adhoc_sessions),
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/api/suggested-questions")
async def get_suggested_questions():
    """
    Dynamically generate 6 random suggested questions
    using real values from HR_AI_Dataset.

    No extra tables required.
    Optimized for speed (small DISTINCT + LIMIT).
    """

    try:
        client = bigquery.Client(project=PROJECT_ID)

        

        queries = {
            "department": f"""
                SELECT department
                FROM `{PROJECT_ID}.{BQ_DATASET_ID}.successfactors_employee_master`
                WHERE department IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """,
            "location": f"""
                SELECT location
                FROM `{PROJECT_ID}.{BQ_DATASET_ID}.successfactors_employee_master`
                WHERE location IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """,
            "source": f"""
                SELECT source
                FROM `{PROJECT_ID}.{BQ_DATASET_ID}.fact_job_application`
                WHERE source IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """,
            "status": f"""
                SELECT appStatusName
                FROM `{PROJECT_ID}.{BQ_DATASET_ID}.fact_job_application`
                WHERE appStatusName IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """,
            "template": f"""
                SELECT templateName
                FROM `{PROJECT_ID}.{BQ_DATASET_ID}.dim_job_requisition`
                WHERE templateName IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """
        }

        results = {}

        for key, query in queries.items():
            row = list(client.query(query).result())
            results[key] = row[0][0] if row else None

        # Build suggestions dynamically
        suggestions = [
            {
                "question": f"What is the total headcount in {results['department']}?",
                "category": "Headcount"
            },
            {
                "question": f"How many active employees are based in {results['location']}?",
                "category": "Demographics"
            },
            {
                "question": f"How many candidates applied through {results['source']}?",
                "category": "Recruitment"
            },
            {
                "question": f"Show me applications currently in '{results['status']}' status.",
                "category": "Recruitment"
            },
            {
                "question": f"How many open requisitions are there for {results['template']}?",
                "category": "Requisitions"
            },
            {
                "question": f"What is the attrition rate for {results['department']}?",
                "category": "Attrition"
            }
        ]

        # Remove any None values safely
        suggestions = [
            s for s in suggestions
            if "None" not in s["question"]
        ]

        return {"data": suggestions[:6]}

    except Exception:
        logger.warning(
            "⚠️ Failed to generate dynamic suggestions — using fallback",
            exc_info=True
        )

        return {
            "data": [
                {"question": "How many new joiners this month?", "category": "Hiring"},
                {"question": "Show attrition rate for last quarter", "category": "Attrition"},
                {"question": "Headcount by department", "category": "Headcount"},
                {"question": "Top hiring sources", "category": "Recruitment"},
                {"question": "Open requisitions by template", "category": "Requisitions"},
                {"question": "Active employees by location", "category": "Demographics"}
            ]
        }
