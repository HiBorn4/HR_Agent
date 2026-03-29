"""
app/routers/sessions.py
-----------------------
Session management endpoints:
  POST /api/archive_session — Move a session's messages to archived_sessions
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.utils import login_required
from app.core.logging import get_logger
from app.db.firestore import archive_session

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["Sessions"])


@router.post("/archive_session")
async def archive_session_endpoint(
    request: Request,
    user: dict = Depends(login_required),
):
    """
    Archive all messages for the given session_id:
      - Copies from chat_sessions/{session_id}/messages
      - Writes to  archived_sessions/{session_id}/messages
      - Deletes the source documents and parent session doc
    """
    data = await request.json()
    session_id = data.get("session_id")

    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)

    try:
        archived_count = await archive_session(session_id)

        if archived_count == 0:
            return JSONResponse({"message": "No messages found to archive"}, status_code=200)

        return JSONResponse({"status": "Success", "archived_count": archived_count})

    except RuntimeError as exc:
        logger.error("Archive failed — Firestore not initialised: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception:
        logger.error("Archive session failed", exc_info=True)
        return JSONResponse({"error": "Archive operation failed — see server logs"}, status_code=500)
