"""SignBridge gloss & pose playground — a Gradio ops/demo UI.

Separate from the Next.js product: an internal tool to eyeball the produce pipeline end to
end — heuristic vs LLM gloss, the resolved sign sequence, and the per-finger handshape
articulation the avatar renders. Handy for demos and for spotting bad gloss/pose quickly.

Run (from the repo root, in a venv that has signbridge + the `tools` extra):
    pip install -e "ml[foundation,tools]"        # add ,llm and set GROQ_API_KEY for the LLM row
    python tools/gloss_demo/app.py               # -> http://127.0.0.1:7860
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running straight from a source checkout without installing signbridge.
_ML = Path(__file__).resolve().parents[2] / "ml"
if _ML.exists() and str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from signbridge.agents.animation import AnimationDirectorAgent  # noqa: E402
from signbridge.agents.base import AgentContext  # noqa: E402
from signbridge.agents.gloss import GlossTranslationAgent  # noqa: E402
from signbridge.agents.llm_gloss import llm_enabled, make_gloss_agent  # noqa: E402
from signbridge.posing import handshape_articulation  # noqa: E402
from signbridge.schema import load_dictionary  # noqa: E402

_DICT = load_dictionary()
_FINGERS = ["thumb", "index", "middle", "ring", "pinky"]


def analyze(text: str, language: str):
    """Return (heuristic gloss, llm gloss, per-sign articulation rows, plan summary)."""
    text = (text or "").strip()
    if not text:
        return "", "", [], "Enter some text."
    ctx = AgentContext(language=language)

    heuristic = GlossTranslationAgent(_DICT).run(text, ctx).gloss_string()

    if llm_enabled():
        llm = make_gloss_agent(_DICT).run(text, ctx).gloss_string()
    else:
        llm = "— set GROQ_API_KEY (and `pip install -e ml[llm]`) to enable —"

    # Build the animation plan from the heuristic gloss (always available) and show the
    # per-finger articulation for each sign — the accuracy model the avatar applies.
    gloss = GlossTranslationAgent(_DICT).run(text, ctx)
    sign_ids = [t.sign_id for t in gloss.tokens if t.sign_id]
    plan = AnimationDirectorAgent(_DICT).run(sign_ids, ctx)

    rows = []
    for step in plan.steps:
        pose = step.pose or {}
        rh = pose.get("right_hand", {})
        shape = rh.get("handshape", "")
        art = handshape_articulation(shape)
        rows.append(
            [step.gloss, shape, *[round(c, 2) for c in art["curl"]], art["spread"], art["thumb_out"]]
        )

    summary = (
        f"{len(plan.steps)} sign(s) · {plan.total_ms} ms · "
        f"face {'active' if plan.has_facial_motion() else 'static'} · "
        f"LLM {'ON' if llm_enabled() else 'off (heuristic)'}"
    )
    return heuristic, llm, rows, summary


def build_demo():
    import gradio as gr

    with gr.Blocks(title="SignBridge — gloss & pose playground") as demo:
        gr.Markdown("## SignBridge — gloss & pose playground\nText → NSL gloss → per-finger handshape articulation.")
        with gr.Row():
            text = gr.Textbox(label="Text", value="hello thank you", lines=2, scale=3)
            language = gr.Radio(["en", "ne"], value="en", label="Source language", scale=1)
        run = gr.Button("Analyze", variant="primary")
        summary = gr.Markdown()
        with gr.Row():
            heuristic = gr.Textbox(label="Gloss — heuristic")
            llm = gr.Textbox(label="Gloss — LLM (Groq/Llama)")
        table = gr.Dataframe(
            headers=["sign", "handshape", *_FINGERS, "spread", "thumb_out"],
            label="Per-finger articulation (0 = extended, 1 = folded into palm)",
            interactive=False,
            wrap=True,
        )
        run.click(analyze, [text, language], [heuristic, llm, table, summary])
        text.submit(analyze, [text, language], [heuristic, llm, table, summary])
    return demo


if __name__ == "__main__":
    build_demo().launch()
