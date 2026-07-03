# Spectacle POC — Design Spec

Date: 2026-07-03
Status: approved for planning

## Purpose

A local, small-scale proof-of-concept demonstrating six architectural claims
for an AI Video Generation Architect interview. Not a production system —
scope is deliberately one lesson, one worked example, two rendered scenes.

The six claims this POC must prove, concretely and observably:

1. Every pipeline stage emits a versioned, content-addressed JSON artifact.
   Re-runs skip stages whose input hash hasn't changed.
2. A LangGraph graph with a Postgres checkpointer orchestrates specialist
   agents and can be killed mid-run and resumed from checkpoint without
   losing state.
3. A human-in-the-loop interrupt pauses the graph for manual approval and
   resumes correctly via `Command(resume={...})`.
4. A worked math example is independently verified with sympy before it's
   allowed into the render; the LLM's script and the symbolic check are
   separate, and a mismatch blocks the pipeline.
5. Per-scene renderer routing: an agent tags each scene with the render
   approach it needs (Remotion vs Manim), and the graph dispatches
   accordingly. The routing decision itself, not just the render output,
   is inspectable.
6. Editable artifacts: a reviewer can edit an artifact directly (script
   text, or a scene's renderer tag) and resume the graph with
   `Command(resume={...edited artifact...})`. The edit invalidates the
   content hash of that artifact and everything downstream of it — but an
   untouched sibling scene's cached render is left alone.

## Repo layout (fixed, from CLAUDE.md)

- `packages/core/` — genre-agnostic engine. No domain-specific imports.
- `domains/education/` — spec schema, structure agent, sympy verification
  gate, safety profile.
- `apps/interview-demo/` — Next.js UI + FastAPI backend service wiring core
  to the education domain pack.
- `artifacts/` — gitignored, content-addressed local outputs.

Core calls domain packs only through the fixed interface below. A domain
pack is a plain Python module imported directly by app config — no plugin
registry, no dynamic loading.

## Domain-pack interface

```python
class DomainPack(Protocol):
    spec_schema: type[BaseModel]

    def structure(self, spec: BaseModel) -> ContentTree: ...

    def verification_gates(self, scene: SceneNode) -> list[VerificationGate]: ...

    safety_profile: SafetyProfile
```

- `spec_schema` — pydantic model validating the incoming lesson spec JSON.
- `structure(spec) -> ContentTree` — breaks the spec into an ordered list of
  scene stubs. Each stub carries a domain-chosen `render_hint` (e.g.
  `"equation_morph"` or `"layout"`) — a declarative signal about *what kind*
  of rendering the scene needs. Core never sees education-specific
  vocabulary (no "worked_example" string in core code); it only ever sees
  `render_hint`. This is the seam that lets a second domain pack (e.g.
  documentary) plug in later without touching `packages/core`: it just
  emits scene stubs with whatever `render_hint`s core already understands,
  or core's hint→renderer table grows by one row.
- `verification_gates(scene) -> list[VerificationGate]` — for a scene with
  `render_hint == "equation_morph"`, returns `[sympy_equivalence_gate]`;
  otherwise `[]`. Core calls every gate returned and blocks on any failure.
- `safety_profile` — a `SafetyProfile(disallowed_topics: list[str],
  age_rating: str)` stub. Present to satisfy interface completeness; not
  deeply exercised in this POC.

`domains/education/` is the only implementation: `EducationSpec` (learning
objective, worked example expression, target duration, audience),
`structure()` implemented as an LLM "pedagogy analyst" call, and the sympy
gate comparing the script's stated final answer against
`sympy.simplify(expression)` for equivalence.

## Artifact schema & content-addressing

Every artifact is a pydantic model, serialized to canonical JSON (sorted
keys, no whitespace), hashed with sha256. Each artifact explicitly embeds
its upstream hash(es) and a `node_version` string constant for the node
that produced it — so bumping a node's prompt/logic invalidates its cached
output even if the upstream input didn't change. This is what makes
artifacts *versioned*, not just content-addressed.

Stored at `artifacts/<hash>/artifact.json`, plus any binary outputs
(`.mp4`, `.wav`) alongside in the same directory.

Chain:

1. `LessonSpec` (input) → `H_spec`
2. `ContentTree` (`domain.structure(spec)`) → `H_tree` (embeds `H_spec`)
3. `Script` (core's script agent; per-scene narration + on-screen text) →
   `H_script` (embeds `H_tree`)
4. **Interrupt A** — human approves or edits `Script` → re-hash → `H_script'`
5. `SceneGraph` (per-scene renderer tag + render params) → `H_scenegraph`
   (embeds `H_script`)
6. **Interrupt B** — human approves or edits `SceneGraph`, including
   overriding a scene's renderer tag → re-hash → `H_scenegraph'`
7. `VerificationResult` (sympy gate output, equation_morph scenes only) —
   blocks the run on mismatch, producing a `blocked` status artifact
   instead of proceeding
8. Per scene, a `scene_input_hash = sha256(canonical_json({narration_text,
   on_screen_text, renderer_tag, render_params}))` — computed from *only
   that scene's own fields*, not the whole `SceneGraph`. This is the
   mechanism behind claim #6: editing scene B's renderer tag changes
   `H_scenegraph` (the top-level receipt) and scene B's `scene_input_hash`,
   but scene A's `scene_input_hash` is unchanged.
9. Per scene, in order: `NarrationClip` (TTS audio + duration, keyed by
   `scene_input_hash`) → `RenderManifest` (video rendered to match that
   duration, keyed by `scene_input_hash`) → `SceneFinal` (av-muxed clip,
   keyed by `scene_input_hash`). Each render/mux node checks
   `artifacts/<scene_input_hash>/scene_final.mp4` first and skips work if
   present.
10. `FinalManifest` (concatenation of all `SceneFinal` clips in scene
    order) → `H_final`.

## LangGraph node/edge structure

```
load_spec
  → structure                 (domain.structure(spec))
  → script_agent               (core, LLM; per-scene narration)
  → [INTERRUPT A: review/edit Script]
  → scene_planner               (core; render_hint -> renderer table)
  → [INTERRUPT B: review/edit SceneGraph, incl. renderer override]
  → verification_gate           (domain.verification_gates per scene; blocks on fail)
  → Send() fan-out per scene:
        tts_scene → render_scene (remotion | manim, chosen by renderer tag)
        → scene_av_mux
  → collect_scenes              (fan-in; all Sends complete)
  → mux_final                   (ffmpeg concat of SceneFinal clips)
  → END
```

- The `Send` routing function that chooses `render_remotion` vs
  `render_manim` per scene is a first-class, inspectable function — this is
  claim #5's "the routing decision, not just the render output."
- Both interrupts use LangGraph's `interrupt()` inside the node and resume
  via `Command(resume={"action": "approve"} | {"action": "edit", "artifact":
  {...}})`. An "edit" resume replaces the artifact, re-hashes it, and
  re-enters the graph from that point — everything downstream re-evaluates
  its cache key from the new hash.
- Verification failure does not loop back to the LLM for auto-retry (out of
  scope); it halts the run with a `blocked` status and the mismatch detail
  visible in the `VerificationResult` artifact.

## Backend process

- `apps/interview-demo/server/` — a FastAPI service importing
  `packages.core` (graph builder, checkpointer, artifact store) and
  `domains.education` (the pack instance), building the compiled graph once
  at startup.
- Checkpointer: LangGraph's `PostgresSaver`, backed by a local Postgres
  instance defined in `docker-compose.yml` (`docker compose up -d` before
  running the demo; `PostgresSaver.setup()` run once to create checkpoint
  tables). This reverses CLAUDE.md's current "skip Postgres for local dev"
  note — CLAUDE.md will be updated as part of implementation.
- Artifact metadata (hash → stage, path, upstream hashes, created_at) is
  also stored in Postgres (a plain `artifacts` table) so the Next.js
  artifact-tree view can query staleness/cache state without walking the
  filesystem.
- Endpoints: `POST /runs`, `GET /runs/:id`, `GET /runs/:id/artifacts` (tree
  view data), `POST /runs/:id/simulate-crash` (calls `os._exit(1)` inside
  the process — a real crash, not a clean shutdown), `POST /runs/:id/resume`,
  `POST /runs/:id/interrupt/resume` (submits an approve/edit payload).
- Crash demo: start a run, hit "Simulate Crash" mid-render, restart
  `uvicorn` by hand, hit "Resume" — the graph continues from the last
  Postgres-persisted checkpoint, proving state survived process death.

## TTS

- `TTSProvider` interface with one method, `synthesize(text, out_path) ->
  duration_s`. Default implementation shells out to macOS `say` (aiff
  output) then `ffmpeg`-converts to wav — zero install, zero API key.
  Swappable later for a real API-backed provider without touching core.
- Per-scene, not full-script: `tts_scene` runs before `render_scene` so the
  renderer receives that scene's actual narration duration as a render
  param (Remotion composition duration / Manim `run_time`). Each scene's
  (audio, video) pair is generated to match by construction — final mux is
  a plain concatenation, eliminating drift risk entirely.

## Next.js app (`apps/interview-demo`)

- "Start Run" trigger (POST to FastAPI `/runs`), polling for status.
- Artifact tree view: nodes colored by cached / stale / pending, backed by
  the Postgres `artifacts` metadata table.
- Review/edit panel: zod-validated editable JSON views for `Script` and
  `SceneGraph` artifacts (including the per-scene renderer-tag dropdown),
  approve/reject buttons, wired to `/runs/:id/interrupt/resume`.
- "Simulate Crash" / "Resume" buttons for the claim-#2 demo.

## Explicitly out of scope

- Multi-lesson batches, multi-voice narration, a grader/judge panel,
  cloud deployment.
- Source-document ingestion / RAG-based spec extraction. The interface
  already accommodates this later (`spec_schema` could grow an optional
  `source_documents` field; `structure()` could do retrieval internally)
  entirely inside a domain pack, without changing `packages/core`. Not
  built now — would dilute focus from the six claims.
- pgvector. No component in this design does similarity search or
  retrieval; adding it now would be an unmotivated dependency.
- Auto-retry/regeneration loop on verification failure — a mismatch halts
  the run; it does not feed back into the LLM automatically.
