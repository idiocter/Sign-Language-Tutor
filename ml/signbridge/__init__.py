"""SignBridge — NSL sign-language tutor foundation package.

Import surface is split so the lightweight foundation (schema, vocabulary,
transliteration, scoring, scheduling) never pulls in torch/mediapipe. Model and capture
modules import their heavy deps only when you import them explicitly.
"""

__version__ = "0.1.0"

from . import config  # noqa: F401
from .schema import Sign, SignDictionary, load_dictionary  # noqa: F401
from .transliterate import to_devanagari  # noqa: F401
from .vocabulary import build_dictionary  # noqa: F401
