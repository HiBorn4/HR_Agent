"""
app/routers/auth.py
-------------------
Authentication routes:
  GET  /auth/login      — Initiate Google OAuth 2.0 flow
  GET  /auth/callback   — Handle Google OAuth 2.0 callback
  GET  /auth/sso        — Handle Mahindra SSO JWT callback
  POST /auth/logout     — Clear session cookies
"""

import os
import secrets
import traceback
import asyncio
from datetime import datetime

import aiohttp
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.utils import extract_jwt_payload, extract_user_id
from app.core.config import (
    FRONTEND_URL,
    GOOGLE_AUTHORIZATION_ENDPOINT,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_OAUTH_SCOPE,
    GOOGLE_TOKEN_ENDPOINT,
    GOOGLE_USERINFO_ENDPOINT,
    REASONING_ENGINE_APP_NAME,
    UPLOAD_FOLDER,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host", "localhost")
    return f"{proto}://{host}"


def _session_cookie_kwargs() -> dict:
    return dict(httponly=False, secure=True, samesite="None", max_age=3600, path="/")


def _set_auth_cookies(response: RedirectResponse, session_id: str, user_id: str) -> None:
    response.set_cookie(key="session_id", value=session_id, **_session_cookie_kwargs())
    response.set_cookie(key="user_id", value=user_id, **_session_cookie_kwargs())


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

async def _get_session_user_info(request: Request) -> dict:
    """Retrieve user data stored in the Vertex AI session (cookie-based)."""
    from app.startup import session_service  # noqa: PLC0415

    session_id = request.cookies.get("session_id")
    user_id = request.cookies.get("user_id")

    if not session_id or not user_id:
        return {}

    try:
        session = await session_service.get_session(
            app_name=REASONING_ENGINE_APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        return session.state.get("user_data", {}) if session and session.state else {}
    except Exception:
        logger.error("Failed to fetch session from Vertex AI", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/login")
async def auth_login(request: Request):
    """Initiate Google OAuth 2.0 login flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logger.error("OAuth client credentials are not configured")
        return JSONResponse({"error": "OAuth not configured"}, status_code=500)

    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    redirect_uri = f"{_build_base_url(request)}/auth/callback"
    logger.info("🔐 OAuth login initiated — redirect_uri=%s", redirect_uri)

    auth_url = (
        f"{GOOGLE_AUTHORIZATION_ENDPOINT}"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&response_type=code"
        f"&scope={GOOGLE_OAUTH_SCOPE}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle Google OAuth 2.0 callback and create an authenticated session."""
    from app.startup import authenticated_users, session_service  # noqa: PLC0415

    # Validate CSRF state
    received_state = request.query_params.get("state")
    expected_state = request.session.get("oauth_state")
    if not received_state or received_state != expected_state:
        logger.error("OAuth state mismatch — possible CSRF attempt")
        return RedirectResponse("/auth/login")
    request.session.pop("oauth_state", None)

    code = request.query_params.get("code")
    if not code:
        logger.error("No authorization code received in callback")
        return RedirectResponse("/auth/login")

    redirect_uri = f"{_build_base_url(request)}/auth/callback"

    try:
        async with aiohttp.ClientSession() as http:
            # Exchange code for tokens
            async with http.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            ) as token_resp:
                tokens = await token_resp.json()
                if "error" in tokens:
                    logger.error("Token exchange failed: %s", tokens)
                    return RedirectResponse("/auth/login")

            access_token = tokens["access_token"]

            # Fetch user info
            async with http.get(
                GOOGLE_USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as info_resp:
                user_info = await info_resp.json()
                if "error" in user_info:
                    logger.error("User info fetch failed: %s", user_info)
                    return RedirectResponse("/auth/login")

        user_data = {
            "id": user_info.get("sub") or user_info.get("id"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "verified_email": user_info.get("email_verified", False),
            "login_time": datetime.now().isoformat(),
            "access_token": access_token,
        }

        os.makedirs(os.path.join(UPLOAD_FOLDER, user_data["id"]), exist_ok=True)

        try:
            session = await session_service.create_session(
            app_name=REASONING_ENGINE_APP_NAME,
            user_id=user_data["id"],
            state={"user_data": user_data}
        )
        except Exception as e:
            logger.error(f"❌ Failed to Create Session: {e}")
            session = None

        authenticated_users[user_data["id"]] = user_data

        logger.info(
            "✅ Google OAuth login — user=%s email=%s session=%s",
            user_data["id"],
            user_data["email"],
            session.id if session else None
        )

        redirect_to = f"{FRONTEND_URL}/dashboard" if FRONTEND_URL else "/dashboard"
        response = RedirectResponse(redirect_to)
        _set_auth_cookies(response, session.id if session else None, user_data["id"])
        return response

    except Exception:
        logger.error("OAuth callback failed:\n%s", traceback.format_exc())
        return RedirectResponse("/auth/login")


@router.get("/sso")
async def auth_sso(request: Request):
    """Handle Mahindra SSO JWT callback."""
    from app.startup import authenticated_users, session_service  # noqa: PLC0415

    jwt_token = request.query_params.get("jwt_token")
    if not jwt_token:
        logger.error("SSO callback missing jwt_token parameter")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=sso_failed")

    try:
        payload = extract_jwt_payload(jwt_token)
        user_id = extract_user_id(payload)

        user_data = {
            "id": user_id,
            "email": payload.get("user_mail") or payload.get("emailaddress"),
            "name": payload.get("givenname"),
            "auth_provider": "sso",
            "login_time": datetime.now().isoformat(),
        }

        os.makedirs(os.path.join(UPLOAD_FOLDER, user_data["id"]), exist_ok=True)

        session = await session_service.create_session(
            app_name=REASONING_ENGINE_APP_NAME,
            user_id=user_data["id"],
            state={"user_data": user_data},
        )
        authenticated_users[user_data["id"]] = user_data

        logger.info("✅ SSO login — user=%s email=%s", user_data["id"], user_data.get("email"))

        redirect_to = f"{FRONTEND_URL}/dashboard" if FRONTEND_URL else "/dashboard"
        response = RedirectResponse(redirect_to)
        _set_auth_cookies(response, session.id, user_data["id"])
        return response

    except Exception:
        logger.error("SSO callback failed:\n%s", traceback.format_exc())
        return RedirectResponse(f"{FRONTEND_URL}/login?error=sso_failed")


@router.post("/logout")
async def auth_logout(request: Request):
    """Invalidate the current session and clear cookies."""
    from app.startup import session_service  # noqa: PLC0415

    if session_id := request.cookies.get("session_id"):
        try:
            session_service.delete_session(
                REASONING_ENGINE_APP_NAME,
                user_id=session_id,
                session_id=session_id,
            )
            logger.info("🧹 Deleted session %s", session_id)
        except Exception:
            logger.warning("Failed to delete Vertex AI session %s", session_id, exc_info=True)

    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("session_id")
    response.delete_cookie("user_id")
    return response
