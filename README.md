# Spectacle

Spec-driven, agent-orchestrated video generation pipeline. Drop in a content spec, get an MP4 — with content-addressed caching at every stage, two human-in-the-loop review windows, and an independent math verification gate before any frames are rendered.

---

## Table of Contents

1. [How it works](#how-it-works)
2. [Architecture](#architecture)
3. [Quick start](#quick-start)
4. [Tutorial](#tutorial)
5. [Creating a domain pack](#creating-a-domain-pack)
6. [Repo layout](#repo-layout)
7. [Extension seams](#extension-seams)

---

## How it works

A run starts with a **content spec** — a small JSON object describing what you want to teach (or pitch, or explain). The spec flows through a LangGraph graph whose nodes produce content-addressed artifacts. Each artifact is hashed from its inputs; re-running the same spec skips every stage whose inputs haven't changed.

**Pipeline stages:**

```
Spec → Structure → Script Agent → [Interrupt A] → Scene Planner → [Interrupt B] → Verify Gate → Render (fan-out) → Mux → MP4
```

- **Structure** — the domain pack turns the spec into an ordered list of scene stubs with render hints
- **Script Agent** — an LLM writes narration and on-screen text for each scene; for verified scenes it also writes a stated answer (e.g. `"7/8"`)
- **Interrupt A** — pauses for human review of the script; the human can approve, edit via chat, or paste raw JSON
- **Scene Planner** — assigns a concrete renderer (`remotion` or `manim`) to each scene based on its render hint
- **Interrupt B** — pauses for human review of the scene graph; renderer tags can be overridden here
- **Verification Gate** — runs domain-supplied checks (e.g. sympy math equivalence) on every flagged scene; a failed check stops the run before rendering
- **Render (fan-out)** — each scene renders independently and in parallel; cached scenes are skipped
- **Mux** — FFmpeg concatenates scene clips to produce the final MP4

**Run modes** control whether interrupts fire:

| Mode | Behavior |
|---|---|
| `accept_edits` (default) | Pauses at Interrupt A and B for human review |
| `auto` | Skips both interrupts; verification gate still always runs |

---

## Architecture

The repo has three layers that depend only downward.

### packages/core — the engine

`spectacle-core` owns the LangGraph graph, artifact store, TTS, renderer routing, and all pipeline nodes. It **never imports from `domains/`**. The only domain-facing surface is the `DomainPack` protocol — four attributes described in [Creating a domain pack](#creating-a-domain-pack).

### Content-addressed artifacts

Every pipeline stage produces a pydantic model that embeds its upstream hash and a `node_version` string. The hash is SHA-256 of canonical JSON (sorted keys, no whitespace). Before running any node, the graph checks whether an artifact with that hash already exists in the store — if it does, the node is skipped.

Per-scene hashing uses only that scene's own fields: narration text, on-screen text, renderer tag, render params, expression, and stated answer. Editing one scene's text invalidates only that scene's render — siblings are reused untouched.

### Human interrupts and kill/resume

LangGraph's `interrupt()` primitive pauses the graph and persists its full state in Postgres. The graph can be killed at any point and resumed later — even after restarting the server — because the checkpointer reconstructs state from the database, not from in-process memory.

Resuming carries an editable artifact back into the graph via `Command(resume={action: "approve"|"edit", artifact: {...}})`. The full artifact payload flows through so downstream nodes always see the human's final version.

### Renderer routing

Scene stubs carry a `render_hint`:

| Hint | Renderer | Use case |
|---|---|---|
| `"layout"` | Remotion | Text, typography, layout scenes |
| `"equation_morph"` | Manim | Animated equation rendering |

The scene planner translates hints to concrete renderer tags. The human can override any tag at Interrupt B.

### domains/education — the first domain pack

The education pack knows about fractions, algebra, and pedagogy. It:

- Validates `EducationSpec` (learning objective, worked-example expression, target duration, audience)
- Runs `budget_scenes()` to deterministically pick a scene sequence — intro → concept explanation(s) → worked example → guided practice → recap — that fits the requested duration
- Fills expressions into worked-example and guided-practice stubs via LLM calls
- Runs `sympy_equivalence_gate` to verify the script's stated answer against the expression; catches LLM math errors before any frames are rendered

### apps/ — the runnable app

Three pieces:

- **FastAPI server** (`apps/server/`) — `POST /runs`, `GET /runs/:id`, `GET /runs/:id/artifacts`, interrupt chat/resume, simulate-crash, resume endpoints
- **Next.js frontend** (`apps/web/`) — Start Run page, live artifact tree view (polling every 2s), chat+JSON review panel, crash/resume controls
- **Remotion renderer** (`apps/renderer-remotion/`) — React compositions for layout scenes

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+, npm
- Docker (for Postgres), or a local Postgres 14+ instance
- FFmpeg on `$PATH`
- macOS `say` command (for TTS) — or implement `TTSProvider` for another platform
- Manim — `pip install manim` plus its system deps ([install guide](https://docs.manim.community/en/stable/installation.html))

### 1. Clone and install Python packages

```bash
git clone https://github.com/dericko/spectacle
cd spectacle
python -m venv .venv && source .venv/bin/activate
pip install -e packages/core -e domains/education -e apps/server pytest
```

### 2. Start Postgres

```bash
docker compose up -d
```

Starts Postgres on port 5432 with credentials `spectacle / spectacle / spectacle`. To use an existing instance, set `SPECTACLE_PG_CONN` before running the server.

### 3. Install frontend dependencies

```bash
cd apps/web && npm install && cd -
cd apps/renderer-remotion && npm install && cd -
```

### 4. Wire up your LLM client

Three functions are left as `NotImplementedError` stubs and need a real LLM before the pipeline can run end-to-end:

| File | Function | Called with |
|---|---|---|
| `domains/education/src/spectacle_education/structure_agent.py` | `default_content_hint_llm` | `(spec: EducationSpec, stub: SceneStub) → str` |
| `domains/education/src/spectacle_education/structure_agent.py` | `default_guided_practice_expression_llm` | `(spec: EducationSpec) → str` |
| `packages/core/src/spectacle_core/nodes/script_agent.py` | `default_script_llm` | `(stub: SceneStub) → ScriptLLMResponse` |

Point these at any LLM API. The test suite injects fakes, so `pytest` passes without a real key — the stubs only block the live pipeline.

### 5. Run the stack

```bash
# Terminal 1 — API server
cd apps/server
uvicorn server.main:app --reload

# Terminal 2 — Next.js dev server
cd apps/web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Tutorial

This walkthrough exercises all six architectural claims. Run it after wiring up your LLM client.

### Start a run

1. Open the Start Run page at `http://localhost:3000`. Fill in the spec:
   ```
   Learning objective: Add fractions with unlike denominators
   Worked example expression: 3/4 + 1/8
   Target duration: 5 minutes
   Audience: 6th grade
   ```
   Set run mode to **accept_edits**. Click Start Run.

2. The run page at `/runs/:id` polls every 2 seconds. Artifacts appear in the tree as stages complete — `content_tree`, then `script`, and so on.

3. **Interrupt A — review the script.** The review panel mounts when the graph pauses. You can:
   - **Approve as-is** — continues without changes
   - **Chat** — type "make the intro shorter"; the AI proposes an updated artifact; click Send then Approve
   - **Edit JSON directly** — modify the raw artifact in the textarea, then Submit

4. **Interrupt B — review the scene graph.** Each scene shows its assigned renderer. To override, chat: *"switch the recap scene to Manim"*. Confirm in the JSON pane, then Approve.

5. After Interrupt B, the verification gate runs (sympy checks the math), then scenes render in parallel. Each `scene_preview` and `scene_final` artifact appears with an inline video player.

6. The final MP4 is written to `artifacts/<hash>/output.mp4`. The `FinalManifest` artifact in the tree contains the path.

### Verifying the six claims

| # | Claim | How to verify |
|---|---|---|
| C1 | Content-addressed selective regeneration | Run the same spec twice — second run logs "cache hit" for every scene. Edit one scene's narration, re-run — only that scene re-renders. |
| C2 | Kill and resume | While paused at Interrupt A, click Simulate Crash. Restart uvicorn. Click Resume — the run continues from the interrupt, not the beginning. |
| C3 | Human interrupt via `Command(resume=…)` | Confirm both Approve and a raw JSON edit round-trip correctly through the graph. |
| C4 | Independent sympy verification | At Interrupt A, edit `worked_example.stated_answer` to `"1/2"` (wrong). Approve. The run halts at the verification gate — rendering never starts. |
| C5 | Renderer routing and override | Confirm `GET /runs/:id/artifacts` shows worked-example/guided-practice tagged `manim`, others `remotion`. Override a tag via chat at Interrupt B. |
| C6 | Selective hash invalidation | After a full run, start a new run, edit one scene's narration at Interrupt A. Only that scene's `scene_input_hash` changes — siblings reuse cached `SceneFinal` artifacts. |

---

## Creating a domain pack

A domain pack is a plain Python object satisfying the `DomainPack` protocol. No plugin registry, no dynamic loading — just an importable instance you pass to `build_graph()`.

### The four things to implement

| Attribute | Type | Purpose |
|---|---|---|
| `spec_schema` | `type[BaseModel]` | Pydantic model that validates the incoming spec JSON |
| `structure(spec)` | `→ ContentTree` | Turns a validated spec into an ordered list of `SceneStub`s with render hints and content hints for the script LLM |
| `verification_gates(scene)` | `→ list[VerificationGate]` | Returns callables that check a `SceneGraphEntry` before rendering; return `[]` for scenes that don't need verification |
| `safety_profile` | `SafetyProfile` | `disallowed_topics` and `age_rating` — used to constrain LLM system prompts |

Gates always run regardless of run mode. A failed gate stops the run before rendering.

### Skeleton

Create a new package at `domains/my_domain/`:

```python
# domains/my_domain/src/my_domain/__init__.py
from pydantic import BaseModel
from spectacle_core.domain_pack import (
    ContentTree, SceneStub, SafetyProfile,
    VerificationOutcome,
)
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneGraphEntry


class MySpec(BaseModel):
    topic: str
    target_duration_minutes: int
    audience: str


def structure(spec: MySpec) -> ContentTree:
    spec_hash = content_hash(spec.model_dump(mode="json"))
    scenes = [
        SceneStub(
            scene_id="intro_1",
            render_hint="layout",          # "layout" → Remotion, "equation_morph" → Manim
            content_hint=f"Introduce {spec.topic} for {spec.audience}",
            target_duration_s=20.0,
            verify=False,
        ),
        # add more stubs to fill spec.target_duration_minutes
    ]
    return ContentTree(spec_hash=spec_hash, scenes=scenes)


def verification_gates(scene: SceneGraphEntry) -> list:
    # Return [] for scenes that don't need checking.
    # For checkable content (math, code, citations), return callables:
    #   def my_gate(scene: SceneGraphEntry) -> VerificationOutcome: ...
    return []


class _MyPack:
    spec_schema = MySpec
    structure = staticmethod(structure)
    verification_gates = staticmethod(verification_gates)
    safety_profile = SafetyProfile(
        disallowed_topics=["violence", "adult content"],
        age_rating="general",
    )


my_pack = _MyPack()
```

### Wiring it into the app

Pass your pack instance to `build_graph()` in `apps/server/src/server/run_manager.py`:

```python
from my_domain import my_pack

graph = build_graph(
    domain_pack=my_pack,
    store=LocalFileArtifactStore(artifact_root),
    tts_provider=MacSayTTSProvider(),
    checkpointer=checkpointer,
    script_llm_fn=your_llm_fn,
)
```

### Custom verification gates

A gate is any callable matching `(scene: SceneGraphEntry) → VerificationOutcome`. The education pack uses sympy for math. Other ideas:

- A code sandbox that executes generated snippets
- A citation verifier that checks URLs are reachable
- An LLM judge that scores content against a rubric
- A static fact-checker for trivia/quiz content

### Core must stay domain-agnostic

`packages/core` must never import from your domain pack. If you find yourself wanting to add a domain-specific branch inside a core node, the right place for that logic is a verification gate or a new field on `SceneStub` / `SceneGraphEntry` — not a conditional in core.

---

## Repo layout

```
spectacle/
├── packages/core/                     # genre-agnostic engine
│   └── src/spectacle_core/
│       ├── hashing.py                 # canonical_json_bytes(), content_hash()
│       ├── artifacts.py               # ArtifactStore protocol, LocalFileArtifactStore
│       ├── domain_pack.py             # DomainPack protocol, SceneStub, ContentTree
│       ├── models.py                  # VersionedArtifact, Script, SceneGraph, FinalManifest, …
│       ├── renderer_routing.py        # render_hint → renderer tag lookup
│       ├── tts.py                     # TTSProvider protocol, MacSayTTSProvider
│       ├── edit_assistant.py          # domain-agnostic propose_edit() for chat review
│       ├── graph.py                   # GraphState, build_graph()
│       ├── nodes/
│       │   ├── script_agent.py        # run_script_agent()
│       │   ├── scene_planner.py       # run_scene_planner()
│       │   ├── interrupts.py          # interrupt_review() — run-mode-aware pause
│       │   ├── verification_gate.py   # run_verification_gate()
│       │   ├── render_scene.py        # fan_out_scenes(), render_scene() — cache-aware
│       │   └── finalize.py            # collect_scenes_node(), mux_final_node()
│       └── renderers/
│           ├── remotion_render.py     # render_remotion()
│           └── manim_render.py        # render_manim()
│
├── domains/education/                 # education domain pack
│   └── src/spectacle_education/
│       ├── __init__.py                # exports education_pack instance
│       ├── spec.py                    # EducationSpec pydantic model
│       ├── scene_menu.py              # SCENE_MENU constants + budget_scenes()
│       ├── structure_agent.py         # structure() — budget_scenes + LLM seams
│       ├── verification.py            # sympy_equivalence_gate()
│       └── safety.py                  # education_safety_profile
│
├── apps//
│   ├── server/                        # FastAPI server
│   ├── web/                           # Next.js frontend
│   └── renderer-remotion/             # Remotion compositions for layout scenes
│
├── artifacts/                         # gitignored — content-addressed render outputs
├── docker-compose.yml                 # local Postgres on port 5432
└── pytest.ini                         # test roots for all three packages
```

---

## Extension seams

Two seams exist for a future GCP deployment without rewriting any existing code.

**ArtifactStore → GCS.** `LocalFileArtifactStore` implements six methods (`put_json`, `get_json`, `exists`, `put_file`, `file_path`, `file_exists`). A `GCSArtifactStore` is a second implementation of the same protocol — swap it in at `build_graph(store=...)` and nothing else changes.

**render_scene → Cloud Tasks.** `render_scene.py` currently dispatches rendering in-process. Cloud Tasks dispatch can reuse the same `interrupt()` / `Command(resume=…)` primitive already used for human review — the resume signal comes from a Cloud Tasks callback instead of a human click. Graph topology stays identical.

GCP deployment (Cloud Run, Cloud SQL, GCS, Cloud Tasks), concurrent multi-user runs, and CI/CD are not implemented in this repo.
