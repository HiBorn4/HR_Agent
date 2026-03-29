"""
app/services/gcs.py
-------------------
Google Cloud Storage helpers: upload, download, and DataFrame hydration.
All GCS I/O is run in a thread pool to avoid blocking the async event loop.
"""

import contextlib
import os
import tempfile

import pandas as pd
from fastapi.concurrency import run_in_threadpool
from google.cloud import storage

from app.core.config import GCS_BUCKET_NAME
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_bucket():
    client = storage.Client()
    return client.bucket(GCS_BUCKET_NAME)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

async def upload_file_to_gcs(file_obj, gcs_object_name: str) -> None:
    """
    Upload an open file-like object to GCS.
    Runs synchronous GCS I/O in a thread pool.
    """
    blob = _get_bucket().blob(gcs_object_name)
    await run_in_threadpool(blob.upload_from_file, file_obj)
    logger.info("✅ Uploaded to GCS: %s", gcs_object_name)


# ---------------------------------------------------------------------------
# Download → DataFrame
# ---------------------------------------------------------------------------

async def load_dataframe_from_gcs(gcs_object_name: str) -> pd.DataFrame:
    """
    Download a CSV or Excel file from GCS and return a typed DataFrame.
    Automatic type coercion: numeric strings → numeric; date strings → datetime.
    """
    blob = _get_bucket().blob(gcs_object_name)
    original_filename = os.path.basename(gcs_object_name)

    with tempfile.NamedTemporaryFile(delete=False, suffix=original_filename) as tmp:
        tmp_path = tmp.name

    try:
        await run_in_threadpool(blob.download_to_filename, tmp_path)
        df = _read_file_to_df(tmp_path)
        df = _coerce_column_types(df)
        return df
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_file_to_df(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)


def _coerce_column_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each object-typed column, attempt numeric then datetime coercion.
    Non-convertible columns are left as-is.
    """
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            with contextlib.suppress(ValueError, TypeError):
                df[col] = pd.to_datetime(df[col])
    return df
