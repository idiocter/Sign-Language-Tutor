# SignBridge tools & integrations

Optional developer/ops tooling. **None of this is required to run the app**, and each piece
degrades gracefully if its dependencies or credentials are absent.

Install the extras you need (into the `ml` or `api` venv):

```bash
pip install -e "ml[foundation,tools]"   # scraper + Gradio demo
pip install -e "ml[llm]"                # LangChain + Groq LLM gloss
```

## LLM gloss translation — LangChain + Groq (Llama)  ·  `ml/signbridge/agents/llm_gloss.py`
Text → NSL gloss via an LLM, with the rule-based `GlossTranslationAgent` as an **automatic
fallback**. The `/produce` route uses it transparently through `make_gloss_agent()`.

Enable by setting a key (its presence flips the LLM path on):

```bash
export GROQ_API_KEY=...                              # or SIGNBRIDGE_LLM_API_KEY
export SIGNBRIDGE_LLM_MODEL=llama-3.3-70b-versatile  # optional
export SIGNBRIDGE_LLM_BASE_URL=...                   # optional — retarget provider (e.g. xAI Grok)
```

Guardrails: the model may only pick gloss codes from the dictionary (language-neutral IDs);
anything else is fingerspelled. No key / no dep / bad reply → heuristic. Tested in
`ml/tests/test_llm_gloss.py` (with a fake model, no network).

## Gradio playground  ·  `tools/gloss_demo/app.py`
Interactive: text → heuristic vs LLM gloss → per-finger handshape articulation the avatar
renders. `python tools/gloss_demo/app.py` → http://127.0.0.1:7860

## Vocabulary scraper  ·  `tools/scrape_vocabulary/scrape.py`
Extracts candidate entries into a **staging** CSV (never `vocabulary.csv` directly). Scraped
rows carry blank phonology and must be completed + approved by a human and the
`nsl-data-reviewer` before training. Only point it at a source you're permitted to scrape
(`--check-robots` honours robots.txt). Parsing is stdlib-only and tested in
`ml/tests/test_scrape_vocabulary.py`.

## Semantic sign search — LlamaIndex (optional)  ·  `tools/semantic_search/search.py`
Included for breadth; not wired into the app. For a few-hundred-sign dictionary a plain
embedding match suffices — LlamaIndex only pays off at corpus/RAG scale.

## Automation  ·  `automation/`
- `automation/harvest_vocab.sh` — the **idiomatic** path: a plain script (cron/CI can call it).
- `automation/n8n/signbridge-vocab-pipeline.json` — an importable n8n workflow doing the same
  thing, included for breadth. n8n is external infra; for this repo a script + CI is the
  native fit. See `automation/README.md`.
