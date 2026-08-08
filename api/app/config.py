"""Backend settings (env-overridable)."""

from __future__ import annotations

import os


class Settings:
    app_name: str = "SignBridge API"
    # SQLite by default so the app runs with no external services. Point at Postgres in
    # production: DATABASE_URL=postgresql+psycopg://user:pass@host/signbridge
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./signbridge.db")
    # Comma-separated list of allowed CORS origins (the Next.js dev server by default).
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    # Shared secret for the flywheel endpoints that approve learner takes into the training
    # set. Unset (the default) means nothing can be approved or promoted at all — data only
    # ever enters training through a deliberate act.
    reviewer_token: str | None = os.getenv("SIGNBRIDGE_REVIEWER_TOKEN") or None


settings = Settings()
