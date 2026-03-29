"""
app/routers/files.py
--------------------
File management endpoints:
  POST /api/upload           — Upload a raw file to GCS
  POST /api/process_gcs_file — Download from GCS, parse to DataFrame, store in adhoc_sessions
"""

import re
import time
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.auth.utils import login_required
from app.core.config import UPLOAD_FOLDER
from app.core.logging import get_logger
from app.db.firestore import save_adhoc_session_metadata
from app.routers.auth import _get_session_user_info
from app.services.gcs import load_dataframe_from_gcs, upload_file_to_gcs

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["Files"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    user: dict = Depends(login_required),
):
    """
    Upload a raw file to GCS under uploads/{user_id}/{timestamp}_{filename}.
    Returns the GCS object name so the client can later call /api/process_gcs_file.
    """
    try:
        timestamp = int(time.time())
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename)
        gcs_object_name = f"uploads/{user_id}/{timestamp}_{safe_name}"

        await upload_file_to_gcs(file.file, gcs_object_name)

        return JSONResponse(
            {
                "status": "success",
                "gcs_object_name": gcs_object_name,
                "filename": file.filename,
            }
        )
    except Exception:
        logger.error("File upload failed", exc_info=True)
        return JSONResponse({"error": "Upload failed — see server logs"}, status_code=500)


@router.post("/process_gcs_file")
async def process_gcs_file(
    request: Request,
    user: dict = Depends(login_required),
):
    """
    Download a previously uploaded file from GCS, parse it into a DataFrame,
    and register it in the in-memory adhoc_sessions store.
    """
    from app.startup import adhoc_sessions  # noqa: PLC0415

    user_info = await _get_session_user_info(request)
    user_id = user_info.get("id")

    data = await request.json()
    gcs_object_name = data.get("gcs_object_name")

    if not gcs_object_name:
        return JSONResponse({"error": "gcs_object_name is required"}, status_code=400)

    if not user_id:
        return JSONResponse({"error": "Could not resolve user ID from session"}, status_code=401)

    try:
        import os  # noqa: PLC0415 — standard lib, kept local for clarity

        original_filename = os.path.basename(gcs_object_name)
        df = await load_dataframe_from_gcs(gcs_object_name)

        adhoc_sessions[user_id] = {
            "display_name": original_filename,
            "gcs_object_name": gcs_object_name,
            "df": df,
            "model_artifacts": {},
        }

        await save_adhoc_session_metadata(
            user_id,
            {
                "display_name": original_filename,
                "gcs_object_name": gcs_object_name,
                "last_upload": datetime.utcnow(),
            },
        )

        logger.info("📄 File processed — user=%s file=%s shape=%s", user_id, original_filename, df.shape)
        return JSONResponse({"status": "success", "filename": original_filename, "shape": df.shape})

    except Exception:
        logger.error("GCS file processing failed", exc_info=True)
        return JSONResponse({"error": "File processing failed — see server logs"}, status_code=500)
