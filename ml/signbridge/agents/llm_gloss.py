"""LLM-backed gloss translation (LangChain + Groq/Llama) with the rule-based agent as an
automatic fallback.

The heuristic ``GlossTranslationAgent`` is a transparent baseline; this wraps it with an LLM
that can handle phrasing the rules miss, while staying inside the project's guardrails:

* **Language-neutral IDs invariant** — the model may only choose ``gloss_code``s from the
  loaded dictionary. Anything else is treated as fingerspelling, never invented as a sign.
* **Always works offline** — if the ``llm`` extra isn't installed, no API key is set, the
  call fails, or the reply doesn't validate, we transparently fall back to the heuristic.
* **Symbolic only** — text in, gloss out. No video/landmarks (respects the agent-loop rule).

Provider: defaults to **Groq** (groq.com), which serves Llama models over an OpenAI-
compatible API. Configurable via env so it retargets (e.g. xAI Grok) without code changes:

    SIGNBRIDGE_LLM_API_KEY / GROQ_API_KEY  API key (its presence enables the LLM path)
    SIGNBRIDGE_LLM_MODEL                   model id (default: llama-3.3-70b-versatile)
    SIGNBRIDGE_LLM_BASE_URL                override the API endpoint (retarget the provider)
"""

from __future__ import annotations

import json
import os
import re

from ..schema import SignDictionary
from .base import AgentContext
from .gloss import GlossResult, GlossToken, GlossTranslationAgent

_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_FS_RE = re.compile(r"^fs\((.+)\)$", re.IGNORECASE)


def _api_key() -> str | None:
    return os.getenv("SIGNBRIDGE_LLM_API_KEY") or os.getenv("GROQ_API_KEY")


def llm_enabled() -> bool:
    """True when an API key is configured (the LLM gloss path can be attempted)."""
    return bool(_api_key())


class LLMGlossTranslationAgent:
    """Drop-in replacement for :class:`GlossTranslationAgent` that tries the LLM first."""

    name = "gloss_translation_llm"
    language_aware = True

    def __init__(
        self,
        dictionary: SignDictionary,
        fallback: GlossTranslationAgent | None = None,
        model: str | None = None,
    ) -> None:
        self.dictionary = dictionary
        self.fallback = fallback or GlossTranslationAgent(dictionary)
        self.model = model or os.getenv("SIGNBRIDGE_LLM_MODEL", _DEFAULT_MODEL)
        self._code_to_sign = {s.gloss_code: s.sign_id for s in dictionary.signs}
        self._menu = [
            {"gloss": s.gloss_code, "en": s.labels.en, "ne": s.labels.ne} for s in dictionary.signs
        ]
        self._llm = self._make_llm()

    def _make_llm(self):
        key = _api_key()
        if not key:
            return None
        try:
            from langchain_groq import ChatGroq
        except Exception:  # extra not installed — stay on the heuristic
            return None
        # langchain-groq reads GROQ_API_KEY from the environment; mirror our alias into it.
        os.environ.setdefault("GROQ_API_KEY", key)
        kwargs: dict[str, object] = {"model": self.model, "temperature": 0}
        base = os.getenv("SIGNBRIDGE_LLM_BASE_URL")
        if base:
            kwargs["base_url"] = base
        try:
            return ChatGroq(**kwargs)
        except Exception:
            return None

    def run(self, text: str, ctx: AgentContext) -> GlossResult:
        if self._llm is None:
            return self.fallback.run(text, ctx)
        try:
            return self._run_llm(text, ctx)
        except Exception:
            # Any failure (network, rate limit, malformed reply) degrades gracefully.
            return self.fallback.run(text, ctx)

    # -- LLM path ---------------------------------------------------------------------------

    def _system_prompt(self, lang: str) -> str:
        menu = "\n".join(f"{m['gloss']}\t{m['en']} / {m['ne']}" for m in self._menu)
        return (
            "You translate a sentence into a Nepali Sign Language (NSL) gloss sequence.\n"
            "NSL is topic-comment ordered; drop function words (articles, copulas).\n"
            f"Source language: {'Nepali' if lang == 'ne' else 'English'}.\n\n"
            "You may ONLY use gloss codes from this dictionary (code<TAB>meaning):\n"
            f"{menu}\n\n"
            "For a word with no matching sign, output \"fs(word)\" to fingerspell it.\n"
            "Respond with ONLY a JSON object, no prose:\n"
            '{"gloss": ["CODE_OR_FS", ...], "eyebrows": "raised|furrowed|none"}\n'
            "Use \"furrowed\" for wh-questions, \"raised\" for yes/no questions, else \"none\"."
        )

    def _run_llm(self, text: str, ctx: AgentContext) -> GlossResult:
        # LangChain chat models accept (role, content) tuples — no message-class import needed.
        resp = self._llm.invoke([("system", self._system_prompt(ctx.language)), ("human", text)])
        content = getattr(resp, "content", resp)
        result = self._parse(content if isinstance(content, str) else str(content))
        if result is None or not result.tokens:
            # Nothing usable — let the heuristic handle it rather than returning empty.
            return self.fallback.run(text, ctx)
        return result

    def _parse(self, content: str) -> GlossResult | None:
        obj = _extract_json(content)
        if not isinstance(obj, dict):
            return None
        raw = obj.get("gloss")
        if not isinstance(raw, list):
            return None

        tokens: list[GlossToken] = []
        for entry in raw:
            if not isinstance(entry, str):
                continue
            code = entry.strip()
            if code in self._code_to_sign:
                tokens.append(GlossToken(gloss=code, sign_id=self._code_to_sign[code]))
                continue
            m = _FS_RE.match(code)
            if m:
                tokens.append(GlossToken(gloss=f"fs({m.group(1).lower()})"))
                continue
            # Unknown token the model invented: fingerspell it instead of trusting it as a sign.
            word = re.sub(r"[^\w]", "", code).lower()
            if word:
                tokens.append(GlossToken(gloss=f"fs({word})"))

        # Collapse a sign repeated back-to-back (mirrors the heuristic's behaviour).
        collapsed: list[GlossToken] = []
        for t in tokens:
            if collapsed and t.sign_id is not None and collapsed[-1].sign_id == t.sign_id:
                continue
            collapsed.append(t)

        sentence_nmm: dict[str, str] = {}
        brows = str(obj.get("eyebrows", "none")).lower()
        if brows in ("raised", "furrowed"):
            sentence_nmm["eyebrows"] = brows
        return GlossResult(tokens=collapsed, sentence_nmm=sentence_nmm)


def _extract_json(content: str) -> object | None:
    """Best-effort: parse the first JSON object in the reply (handles ```json fences)."""
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1)
    else:
        brace = content.find("{")
        if brace != -1:
            content = content[brace : content.rfind("}") + 1]
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def make_gloss_agent(dictionary: SignDictionary):
    """Return the LLM-backed agent when a key is configured, else the rule-based one.

    Either satisfies the same ``.run(text, ctx) -> GlossResult`` contract, so callers (the
    /produce router) don't branch."""
    if llm_enabled():
        return LLMGlossTranslationAgent(dictionary)
    return GlossTranslationAgent(dictionary)
