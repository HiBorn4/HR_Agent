"""
app/auth/utils.py
-----------------
Authentication helpers:
  - JWT creation / decoding (app-issued tokens)
  - Mahindra SSO JWT extraction (with optional AES-ECB decryption)
  - User normalisation across Google OAuth and Mahindra SSO payloads
  - FastAPI dependency: get_current_user / login_required
"""

import base64
import logging
from datetime import datetime, timedelta
from typing import Any

from Crypto.Cipher import AES
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import (
    APP_SECRET_KEY,
    REASONING_ENGINE_APP_NAME,
    TOKEN_ALGO,
    TOKEN_EXP_MINUTES,
    TOKEN_SECRET,
)
import app.startup as startup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App-Issued JWT (session token stored in cookie / Authorization header)
# ---------------------------------------------------------------------------

def create_auth_token(user_id: str, session_id: str) -> str:
    """Create a signed JWT containing user_id and session_id."""
    now = datetime.utcnow()
    payload = {
        "uid": user_id,
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXP_MINUTES),
    }
    return jwt.encode(payload, TOKEN_SECRET, algorithm=TOKEN_ALGO)


def decode_auth_token(token: str) -> dict:
    """Decode and validate an app-issued JWT. Raises HTTP 401 on failure."""
    try:
        return jwt.decode(token, TOKEN_SECRET, algorithms=[TOKEN_ALGO])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


# ---------------------------------------------------------------------------
# User Normalisation
# ---------------------------------------------------------------------------

def normalize_user(user_data: dict) -> dict:
    """
    Normalise heterogeneous user payloads (Google OAuth + Mahindra SSO)
    into a single canonical schema.
    """
    # Google OAuth shape
    if "id" in user_data:
        return {
            "uid": user_data["id"],
            "email": user_data.get("email"),
            "name": user_data.get("name"),
            "auth_provider": "google",
            "raw": user_data,
        }

    # Mahindra SSO shape
    if "user" in user_data:
        return {
            "uid": user_data["user"],
            "email": user_data.get("user_mail") or user_data.get("emailaddress"),
            "name": user_data.get("givenname"),
            "auth_provider": "sso",
            "raw": user_data,
        }

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unrecognised user schema")


# ---------------------------------------------------------------------------
# Request Authentication — FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> tuple[dict, str]:
    """
    Resolve the authenticated user from the incoming request.

    Token lookup order:
      1. ``Authorization: Bearer <token>`` header
      2. ``token`` cookie (production path)

    Returns:
        (normalised_user_dict, session_id)
    """

    token: str | None = None

    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]

    if not token:
        token = request.cookies.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")

    payload = decode_auth_token(token)

    session = await startup.session_service.get_session(
        app_name=REASONING_ENGINE_APP_NAME,
        user_id=payload["uid"],
        session_id=payload["sid"],
    )

    if not session or "user_data" not in session.state:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or not found")

    normalised = normalize_user(session.state["user_data"])
    return normalised, payload["sid"]

async def login_required(request: Request):
    logger.info("🔐 login_required invoked")

    session_id = request.cookies.get("session_id")
    user_id = request.cookies.get("user_id")

    logger.info(
        "🍪 Cookies received → session_id=%s | user_id=%s | path=%s",
        session_id,
        user_id,
        request.url.path,
    )

    if not session_id or not user_id:
        logger.warning("❌ Missing cookies — session_id or user_id not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )

    try:
        logger.info(
            "📡 Fetching session from Vertex → app=%s | user_id=%s | session_id=%s",
            REASONING_ENGINE_APP_NAME,
            user_id,
            session_id,
        )

        session = await startup.session_service.get_session(
            app_name=REASONING_ENGINE_APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        if not session:
            logger.error("❌ Vertex returned NO session object")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )

        logger.info("✅ Session fetched successfully")

        if not session.state:
            logger.error("❌ Session exists but state is EMPTY")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session state"
            )

        logger.info(
            "🧠 Session state keys: %s",
            list(session.state.keys())
        )

        user_data = session.state.get("user_data")

        if not user_data:
            logger.error("❌ user_data missing inside session.state")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session payload"
            )

        logger.info(
            "🎉 Authentication successful for user=%s",
            user_data.get("id")
        )

        return user_data

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "💥 Session validation failed: %s",
            str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session validation failed"
        )

# ---------------------------------------------------------------------------
# Mahindra SSO — JWT extraction (raw or AES-encrypted)
# ---------------------------------------------------------------------------

def extract_jwt_payload(jwt_token: str) -> dict[str, Any]:
    """
    Accept either a raw JWT or an AES-128-ECB encrypted JWT string.

    Returns the decoded payload dict (signature NOT verified — SSO tokens
    are verified by the issuing gateway).
    """
    try:
        if jwt_token.count(".") == 2:
            return jwt.decode(jwt_token, "", options={"verify_signature": False})

        decrypted = _decrypt_aes_token(jwt_token)
        if decrypted.count(".") != 2:
            raise ValueError("Decrypted value is not a valid JWT")

        return jwt.decode(decrypted, "", options={"verify_signature": False})

    except Exception as exc:
        logger.exception("JWT extraction failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


def extract_user_id(payload: dict[str, Any]) -> str:
    """Extract the user identifier from a decoded JWT payload."""
    if user_id := payload.get("user"):
        return str(user_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identifier missing in token",
        )


# ---------------------------------------------------------------------------
# AES-128-ECB Decryption (Mahindra Java/PHP compatibility)
# ---------------------------------------------------------------------------

def _decrypt_aes_token(encrypted_token: str) -> str:
    """
    Decrypt an AES-128-ECB token produced by the Mahindra SSO gateway.

    Steps:
      1. Normalise URL-safe Base64 → standard Base64
      2. Decode outer Base64 envelope
      3. Detect and decode inner Base64 layer (double-encoded tokens)
      4. AES-ECB decrypt with the APP_SECRET_KEY
      5. Strip PKCS7 padding
    """
    secret_key = APP_SECRET_KEY.encode("utf-8")

    def _b64_decode(value: str) -> bytes:
        standard = value.replace("-", "+").replace("_", "/")
        standard += "=" * ((4 - len(standard) % 4) % 4)
        return base64.b64decode(standard)

    outer_decoded = _b64_decode(encrypted_token)

    # Detect double-encoding: if the outer-decoded bytes look like printable
    # Base64 characters, treat them as another encoded layer.
    decoded_str = outer_decoded.decode("utf-8", errors="ignore")
    if all(c.isalnum() or c in "+/=_-" for c in decoded_str):
        encrypted_bytes = _b64_decode(decoded_str)
    else:
        encrypted_bytes = outer_decoded

    cipher = AES.new(secret_key, AES.MODE_ECB)
    decrypted_bytes = cipher.decrypt(encrypted_bytes)

    # PKCS7 unpadding
    pad_len = decrypted_bytes[-1]
    if 1 <= pad_len <= AES.block_size:
        decrypted_bytes = decrypted_bytes[:-pad_len]

    return decrypted_bytes.decode("utf-8", errors="strict").strip().strip("\x00").strip()
