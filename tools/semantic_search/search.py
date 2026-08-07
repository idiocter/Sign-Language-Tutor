"""Semantic sign search over the vocabulary — a minimal LlamaIndex example.

Honesty note: this is included for breadth. For a dictionary of a few hundred signs, a plain
embedding cosine (or even substring match) is enough; LlamaIndex earns its keep only once
there's a larger corpus / RAG need. It's kept small and OPTIONAL — imports are guarded and it
is not wired into the app.

Indexes each sign's English + Nepali + gloss so a natural-language query ("feeling grateful")
retrieves the closest sign (THANK-YOU). Uses a local HuggingFace embedding by default so it
runs offline once the model is cached.

    pip install -e "ml[foundation]" llama-index-core llama-index-embeddings-huggingface
    python tools/semantic_search/search.py "how do I say thank you"
"""

from __future__ import annotations

import sys
from pathlib import Path

_ML = Path(__file__).resolve().parents[2] / "ml"
if _ML.exists() and str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from signbridge.schema import load_dictionary  # noqa: E402

_DEFAULT_EMBED = "sentence-transformers/all-MiniLM-L6-v2"


def _require_llama_index():
    try:
        from llama_index.core import Document, VectorStoreIndex
        from llama_index.core import Settings
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    except ImportError as exc:
        raise SystemExit(
            "Optional deps missing. Install:\n"
            "  pip install llama-index-core llama-index-embeddings-huggingface"
        ) from exc
    return Document, VectorStoreIndex, Settings, HuggingFaceEmbedding


def build_index(embed_model: str = _DEFAULT_EMBED):
    Document, VectorStoreIndex, Settings, HuggingFaceEmbedding = _require_llama_index()
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)
    Settings.llm = None  # retrieval only; no generation needed

    docs = []
    for s in load_dictionary().signs:
        text = f"{s.labels.en}. Nepali: {s.labels.ne}. Gloss: {s.gloss_code}. Category: {s.curriculum.category or ''}."
        docs.append(Document(text=text, metadata={"sign_id": s.sign_id, "gloss": s.gloss_code}))
    return VectorStoreIndex.from_documents(docs)


def search(query: str, top_k: int = 3, embed_model: str = _DEFAULT_EMBED):
    index = build_index(embed_model)
    retriever = index.as_retriever(similarity_top_k=top_k)
    hits = retriever.retrieve(query)
    return [(h.metadata.get("gloss"), h.metadata.get("sign_id"), round(h.score or 0, 3)) for h in hits]


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print('usage: python tools/semantic_search/search.py "<query>"')
        return 2
    for gloss, sign_id, score in search(" ".join(argv)):
        print(f"{score:>6}  {sign_id}  {gloss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
