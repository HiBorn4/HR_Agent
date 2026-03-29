"""
main.py
-------
Application entry point and factory.

Responsibilities:
  1. Initialise all services (Firestore, Vertex AI, Gemini, ADK Runner)
  2. Register middleware (CORS, Session)
  3. Mount all route routers

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.routers import auth, chat, files, sessions, system
from app.startup import initialise_services


# ---------------------------------------------------------------------------
# Lifespan — replaces deprecated @app.on_event("startup")
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Run service bootstrap before the app starts accepting requests."""
    configure_logging()
    initialise_services()
    yield
    # Teardown hooks can go here if needed in future


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    application = FastAPI(
        title="Mahindra Rise Intelligence Platform",
        version="4.0.0",
        lifespan=lifespan,
    )

    register_middleware(application)

    application.include_router(auth.router)
    application.include_router(system.router)
    application.include_router(files.router)
    application.include_router(sessions.router)
    application.include_router(chat.router)

    return application


app = create_app()
