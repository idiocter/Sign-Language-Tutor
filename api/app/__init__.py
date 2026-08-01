"""SignBridge API package.

Safety net: if the `signbridge` package (the ml/ foundation) is not installed into this
environment, add the sibling ml/ directory to sys.path so the backend still imports it.
The clean path is `pip install -e ../ml[foundation]`.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:  # pragma: no cover
    import signbridge  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    ml_dir = Path(__file__).resolve().parents[2] / "ml"
    if (ml_dir / "signbridge").is_dir():
        sys.path.insert(0, str(ml_dir))
