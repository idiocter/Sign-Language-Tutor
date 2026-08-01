"""Puts the api/ directory on sys.path so `import app...` works under pytest, and creates
the DB schema (the lifespan hook that normally does this doesn't run under TestClient)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db import init_db  # noqa: E402

init_db()
