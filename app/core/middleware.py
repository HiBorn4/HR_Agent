"""
app/core/middleware.py
----------------------
Registers all FastAPI / Starlette middleware onto the application instance.
Called once inside the app factory (main.py).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import FRONTEND_URL, SESSION_SECRET_KEY


def register_middleware(app: FastAPI) -> None:
    """Attach CORS and session middleware to *app* in the correct order."""

    # --- CORS ---
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    if FRONTEND_URL:
        allowed_origins.append(FRONTEND_URL)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Session (must be added AFTER CORS so it wraps the handler layer) ---
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
