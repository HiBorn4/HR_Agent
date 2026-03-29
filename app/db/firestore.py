"""
app/db/firestore.py
-------------------
All Firestore read/write helpers used across the application.
Consumers import the async functions directly — no class needed.
"""

import hashlib
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers — lazy-import firestore_db to avoid circular deps at module load
# ---------------------------------------------------------------------------

def _get_db():
    from app.startup import firestore_db  # noqa: PLC0415 — intentional lazy import
    return firestore_db


# ---------------------------------------------------------------------------
# Response Cache
# ---------------------------------------------------------------------------

async def get_cached_response(query: str, mode: str, session_id: str) -> dict | None:
    """
    Retrieve a cached response from Firestore.

    Cache is valid only for:
      - The current UTC day
      - The specific session that created it (prevents cross-session leakage)
    """
    db = _get_db()
    if not db:
        return None

    try:
        query_hash = _make_cache_key(session_id, mode, query)
        doc = await db.collection("response_cache").document(query_hash).get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        cached_response = data.get("response")

        if not cached_response or cached_response.get("status") != "Success" or "data" not in cached_response:
            return None

        # Validate date — today-only cache policy
        timestamp = data.get("timestamp")
        if timestamp:
            ts_date = (
                datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
                if isinstance(timestamp, str)
                else timestamp.date()
            )
            if ts_date != datetime.now(timezone.utc).date():
                logger.info("⚠️  Cache expired (date: %s). Fetching fresh data.", ts_date)
                return None

        logger.info("🔥 Cache HIT — query='%s' session='%s'", query[:60], session_id)
        return cached_response

    except Exception:
        logger.warning("⚠️  Cache retrieval failed", exc_info=True)
        return None


async def cache_response(query: str, mode: str, response_data: dict, session_id: str) -> None:
    """Persist a successful response to the Firestore cache."""
    db = _get_db()
    if not db:
        return

    try:
        query_hash = _make_cache_key(session_id, mode, query)
        await db.collection("response_cache").document(query_hash).set(
            {
                "query": query,
                "mode": mode,
                "session_id": session_id,
                "response": response_data,
                "timestamp": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.warning("⚠️  Failed to cache response", exc_info=True)


# ---------------------------------------------------------------------------
# Chat History
# ---------------------------------------------------------------------------

async def log_chat_message(
    session_id: str,
    user_id: str,
    message: str,
    response: dict,
    mode: str,
) -> None:
    """Append a chat turn to the active session's message sub-collection."""
    db = _get_db()
    if not db or not session_id:
        return

    try:
        await (
            db.collection("chat_sessions")
            .document(session_id)
            .collection("messages")
            .add(
                {
                    "user_id": user_id,
                    "user_message": message,
                    "assistant_response": response,
                    "mode": mode,
                    "timestamp": datetime.now(timezone.utc),
                }
            )
        )
    except Exception:
        logger.warning("⚠️  Failed to log chat history", exc_info=True)


# ---------------------------------------------------------------------------
# Adhoc Session Metadata
# ---------------------------------------------------------------------------

async def save_adhoc_session_metadata(user_id: str, metadata: dict) -> None:
    """Merge adhoc session metadata (filename, GCS path) into user_sessions."""
    db = _get_db()
    if not db:
        return

    try:
        await db.collection("user_sessions").document(user_id).set(metadata, merge=True)
    except Exception:
        logger.error("Failed to save adhoc session metadata", exc_info=True)


async def get_adhoc_session_metadata(user_id: str) -> dict | None:
    """Retrieve persisted adhoc session metadata for a user."""
    db = _get_db()
    if not db:
        return None

    try:
        doc = await db.collection("user_sessions").document(user_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception:
        logger.error("Failed to fetch adhoc session metadata", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Session Archive
# ---------------------------------------------------------------------------

async def archive_session(session_id: str) -> int:
    """
    Move all messages from chat_sessions/{session_id}/messages
    to archived_sessions/{session_id}/messages and delete the source.

    Returns the number of messages archived.
    """
    db = _get_db()
    if not db:
        raise RuntimeError("Firestore is not initialised")

    source_ref = db.collection("chat_sessions").document(session_id).collection("messages")
    messages = await source_ref.get()

    if not messages:
        return 0

    target_ref = db.collection("archived_sessions").document(session_id).collection("messages")
    batch = db.batch()
    count = 0

    for msg in messages:
        msg_data = msg.to_dict()
        msg_data["archived_at"] = datetime.now(timezone.utc)
        batch.set(target_ref.document(msg.id), msg_data)
        batch.delete(msg.reference)
        count += 1

    await batch.commit()
    await db.collection("chat_sessions").document(session_id).delete()

    logger.info("📦 Archived %d messages for session '%s'", count, session_id)
    return count


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _make_cache_key(session_id: str, mode: str, query: str) -> str:
    raw = f"{session_id}:{mode}:{query.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()
