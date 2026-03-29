"""
app/core/config.py
------------------
Central configuration. All environment variables and project-wide constants
are loaded here. Import from this module instead of calling os.getenv() directly.
"""

import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_SCOPE: str = os.getenv("GOOGLE_OAUTH_SCOPE")
GOOGLE_AUTHORIZATION_ENDPOINT: str = os.getenv("GOOGLE_AUTHORIZATION_ENDPOINT")
GOOGLE_TOKEN_ENDPOINT: str = os.getenv("GOOGLE_TOKEN_ENDPOINT")
GOOGLE_USERINFO_ENDPOINT: str = os.getenv("GOOGLE_USERINFO_ENDPOINT")
CREDENTIALS_PATH: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# ---------------------------------------------------------------------------
# GCP / Vertex AI
# ---------------------------------------------------------------------------
PROJECT_ID: str = os.getenv("GCP_PROJECT_ID")
LOCATION: str = os.getenv("GCP_LOCATION")
BQ_PROJECT_ID: str = os.getenv("BQ_PROJECT_ID")
GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME")
BQ_DATASET_ID: str = os.getenv("BQ_DATASET_ID")

# ---------------------------------------------------------------------------
# Firestore
# ---------------------------------------------------------------------------
FIRESTORE_DB_NAME: str = os.getenv("FIRESTORE_DB_NAME")
FIRESTORE_LOCATION: str = os.getenv("FIRESTORE_LOCATION")

# ---------------------------------------------------------------------------
# ADK / Agent
# ---------------------------------------------------------------------------
REASONING_ENGINE_APP_NAME: str = os.getenv("VERTEX_REASONING_ENGINE_APP")

# ---------------------------------------------------------------------------
# Auth / JWT
# ---------------------------------------------------------------------------
APP_SECRET_KEY: str = os.getenv("SSO_SECRET_KEY")
TOKEN_SECRET: str = os.getenv("APP_AUTH_TOKEN_SECRET")
TOKEN_ALGO: str = os.getenv("TOKEN_ALGO")
TOKEN_EXP_MINUTES: int = int(os.getenv("APP_AUTH_TOKEN_EXP_MINUTES"))

# Used by Starlette SessionMiddleware
SESSION_SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))

# ---------------------------------------------------------------------------
# AI Keys
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
FRONTEND_URL: str = os.getenv("FRONTEND_URL").rstrip("/")
UPLOAD_FOLDER: str = "user_uploads"
