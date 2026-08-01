# Claude Code config for SignBridge

Project-scoped skills and subagents that encode this repo's workflow and guardrails.

## Skills (`.claude/skills/`)

Invoke with `/<name>` in Claude Code, or Claude uses them automatically when the task matches.

| Skill | What it does |
|---|---|
| `add-sign` | Add an `NSL_dddd` sign to `vocabulary.csv` and rebuild the dictionary, enforcing language-neutral IDs and native-signer validation flags. |
| `train-recognition` | Regenerate synthetic data, train the interim model, export ONNX, verify — or run the production Transformer training when real data exists. |
| `add-avatar-clip` | Wire an authored glTF sign clip into the avatar (overrides the procedural pose), or explain the Blender + ARKit authoring workflow. |
| `run-dev` | Start backend + frontend together and verify both are up. |

## Subagents (`.claude/agents/`)

Delegate with the Agent tool (`subagent_type: "<name>"`).

| Agent | Use it to |
|---|---|
| `nsl-data-reviewer` | Audit collected takes and vocabulary rows for quality problems and signer coverage before training. |
| `signbridge-invariant-guard` | Review a diff against the non-negotiables: signer split, language-neutral IDs, feature-layout parity, symbolic-only agents, on-device inference, bilingual strings. |

## Project agents vs. these agents

Don't confuse them:
- **These** (`.claude/agents/`) are *Claude Code* subagents that help you build the repo.
- The **Layer-7 agents** in `ml/signbridge/agents/` (Curriculum, Critique, Gloss
  Translation, Animation Director, Practice Partner, Data Curator) are *product* components
  that run inside the app on symbolic data. See `TECH_STACK.md` Layer 7.
