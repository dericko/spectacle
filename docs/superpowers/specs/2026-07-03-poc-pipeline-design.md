# Spectacle POC — Design Spec

Date: 2026-07-03
Status: approved for planning

## Purpose

Started as a proof-of-concept for an AI Video Generation Architect interview;
now also an ongoing personal project built collaboratively beyond that
interview. Scope stays deliberately small for this first pass — one lesson,
one learning objective, a duration the user picks (1–10 minutes, in 1-minute
increments) — but the architecture is meant to be a sane starting point for
productionizing later, not a throwaway. Concretely: seams (domain-pack
interface, artifact storage, render dispatch) are chosen so that later growth
(more domain packs, more scenes, real cloud deployment) doesn't require
redesigning them, without building out that future capacity now.

The six claims this project must prove, concretely and observably:

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
objective, worked example expression, `target_duration_minutes` (1–10),
audience), `structure()` implemented as an LLM "pedagogy analyst" call, and
the sympy gate comparing a worked-example scene's stated final answer
against `sympy.simplify(expression)` for equivalence.

## Duration & content model

The user picks a target duration, 1–10 minutes in 1-minute increments.
Rather than letting the pedagogy agent freely invent content depth to fill
arbitrary time (which reintroduces multi-topic-curriculum complexity and
risks unnatural padding), `structure()` selects from a **fixed menu of scene
types**, owned entirely by `domains/education` — core never sees these
names, only the `render_hint` each stub carries:

| Scene type            | render_hint       | Verified? | Notes                                    |
|------------------------|-------------------|-----------|-------------------------------------------|
| `intro`                | `layout`          | no        | exactly one per lesson                    |
| `concept_explanation`  | `layout`          | no        | may repeat, different framing/analogy     |
| `worked_example`       | `equation_morph`  | yes       | the example specified in the spec         |
| `guided_practice`      | `equation_morph`  | yes       | same skill, easier numbers — reinforcement, not a new topic |
| `recap`                | `layout`          | no        | exactly one per lesson                    |

`structure()`'s job is a budgeting decision — picking a sequence and
per-scene duration from this menu to approximate the requested total
(treated as a soft target with tolerance, e.g. ±30s; not an exact frame
count) — not an open-ended content-design decision. This keeps "one
learning objective" intact (`guided_practice` reinforces the same skill)
while still growing scene count meaningfully with duration: a 2-minute
lesson might be `intro, worked_example, recap` (3 scenes); a 10-minute
lesson might add several `concept_explanation` variants and a
`guided_practice` pass (8–12 scenes). Longer lessons naturally exercise the
sympy verification gate more than once (`worked_example` **and**
`guided_practice`), reinforcing claim #4 without extra design work.

A second scene-type menu (a different pedagogical style, or an entirely
different domain pack's own vocabulary) is a later, additive change — either
a new field on `EducationSpec` the domain pack branches on internally, or a
new domain pack module entirely. Neither requires touching `packages/core`.

## Artifact schema & content-addressing

Every artifact is a pydantic model, serialized to canonical JSON (sorted
keys, no whitespace), hashed with sha256. Each artifact explicitly embeds
its upstream hash(es) and a `node_version` string constant for the node
that produced it — so bumping a node's prompt/logic invalidates its cached
output even if the upstream input didn't change. This is what makes
artifacts *versioned*, not just content-addressed.

Stored via an `ArtifactStore` interface (`put(hash, artifact)`,
`get(hash)`, `exists(hash)`) at logical path `<hash>/artifact.json`, plus any
binary outputs (`.mp4`, `.wav`) alongside. Local dev implementation writes
to `./artifacts/<hash>/` on disk; the GCP deployment implementation writes
to a GCS bucket at the same relative layout — same interface, config-
selected backend, no node code depends on which one is active.

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
   `scene_input_hash`) → for `equation_morph` scenes only, a `ScenePreview`
   (Manim's low-quality `-ql` render, video-only, no audio — fast, just a
   visual sanity check of the equation-morph animation) → `RenderManifest`
   (full-fidelity video rendered to match that duration, keyed by
   `scene_input_hash`) → `SceneFinal` (av-muxed clip, keyed by
   `scene_input_hash`). Each render/mux node checks
   `artifacts/<scene_input_hash>/scene_final.mp4` first and skips work if
   present. `ScenePreview` is not gated behind an interrupt — it's written
   to the `ArtifactStore` and surfaced to the UI immediately, purely for
   early visibility, not as an approval checkpoint.
10. `FinalManifest` (concatenation of all `SceneFinal` clips in scene
    order) → `H_final`.

Every artifact is written to the `ArtifactStore` and its metadata row
inserted the moment it's produced — not batched until the run finishes.
This is what makes progressive visibility (below) possible: the UI is
reading state that's already there, not waiting on a final node.

## LangGraph node/edge structure

```
load_spec
  → structure                 (domain.structure(spec))
  → script_agent               (core, LLM; per-scene narration)
  → [INTERRUPT A: review/edit Script]
  → scene_planner               (core; render_hint -> renderer table)
  → [INTERRUPT B: review/edit SceneGraph, incl. renderer override]
  → verification_gate           (domain.verification_gates per scene; blocks on fail)
  → Send() fan-out per scene (N scenes, not fixed to 2 — driven by
    however many scenes structure() picked for the requested duration):
        tts_scene → render_scene (remotion | manim, chosen by renderer tag;
          for manim scenes, emits a fast low-quality ScenePreview first,
          then the full-fidelity render — see artifact chain above)
        → scene_av_mux
  → collect_scenes              (fan-in; all Sends complete)
  → mux_final                   (ffmpeg concat of SceneFinal clips)
  → END
```

- The `Send` routing function that chooses `render_remotion` vs
  `render_manim` per scene is a first-class, inspectable function — this is
  claim #5's "the routing decision, not just the render output." It's also
  the render-dispatch seam: see "Deployment (GCP)" below for how the same
  per-scene payload is dispatched differently (in-process vs. queued)
  depending on environment, without changing this graph.
- Both interrupts use LangGraph's `interrupt()` inside the node and resume
  via `Command(resume={"action": "approve"} | {"action": "edit", "artifact":
  {...}})`. An "edit" resume replaces the artifact, re-hashes it, and
  re-enters the graph from that point — everything downstream re-evaluates
  its cache key from the new hash.
- Verification failure does not loop back to the LLM for auto-retry (out of
  scope); it halts the run with a `blocked` status and the mismatch detail
  visible in the `VerificationResult` artifact.
- **Run modes** — a per-run setting, chosen at `POST /runs`, that governs
  only Interrupt A and Interrupt B: `accept_edits` pauses at both and
  requires an explicit approve/edit before continuing (the default);
  `auto` auto-approves both without pausing, for a hands-off run once
  you trust the spec. The `verification_gate` node is **exempt from this
  toggle** — a sympy mismatch halts the run in either mode, since it's a
  correctness check, not a review checkpoint.

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
- Endpoints: `POST /runs` (accepts the spec and a `run_mode`:
  `accept_edits` | `auto`), `GET /runs/:id`, `GET /runs/:id/artifacts` (tree
  view data, polled/streamed for progressive updates), `POST
  /runs/:id/simulate-crash` (calls `os._exit(1)` inside the process — a
  real crash, not a clean shutdown), `POST /runs/:id/resume`, `POST
  /runs/:id/interrupt/chat` (takes a chat message, returns a proposed
  edited artifact via the edit-assistant call — does not itself resume the
  graph), `POST /runs/:id/interrupt/resume` (submits the final
  approve/edit payload, whether it came from the chat flow or a direct
  JSON edit).
- Crash demo: start a run, hit "Simulate Crash" mid-render, restart
  `uvicorn` by hand, hit "Resume" — the graph continues from the last
  Postgres-persisted checkpoint, proving state survived process death.

## Deployment (GCP)

Private/personal use for now, but built on infrastructure that's a
reasonable starting point for real deployment later — serverless, not a
managed VM:

- **Cloud Run** — two services, `api` (FastAPI + compiled graph) and `web`
  (Next.js), mirroring the local FastAPI/Next.js split.
- **Cloud SQL for Postgres** — same `PostgresSaver` checkpointer and
  `artifacts` metadata table as local dev; only the connection target
  changes.
- **GCS bucket** — the `ArtifactStore` implementation described above;
  same `<hash>/...` layout as local disk.
- **Cloud Tasks** — per-scene render dispatch in place of in-process
  `Send()`. Locally, the fan-out step calls `render_scene` directly and
  blocks in-process until it returns. On Cloud Run this can't work the same
  way — Manim/FFmpeg renders can run long enough that blocking a request
  thread on them doesn't scale — so the async path reuses the same
  pause/resume primitive already built for the human interrupts (claims #3
  and #6), just machine-triggered instead of human-triggered: `render_scene`
  enqueues a Cloud Task carrying the scene payload (scene id, renderer tag,
  render params, `scene_input_hash`) and the node pauses via
  LangGraph's `interrupt()`, checkpointed to Postgres like any other pause.
  The Cloud Task calls `POST /render-scene` on the `api` service, which runs
  the actual render synchronously within that request, writes the
  `RenderManifest` to the `ArtifactStore`, then calls
  `POST /runs/:id/scene-complete`, which resumes the paused node via
  `Command(resume={"scene_id": ..., "render_manifest_hash": ...})`. One
  `RenderDispatcher` interface (`dispatch(scene_payload) -> DispatchMode`,
  where `DispatchMode` is `sync` locally or `pending` on GCP, telling the
  node whether to return immediately or call `interrupt()`) with two
  implementations, chosen by config — the graph node's shape doesn't change
  between environments, only which branch of the `if` it takes.
- Known gap, deliberately deferred: the default `TTSProvider` shells out to
  macOS `say`, which doesn't exist on Cloud Run's Linux containers. Swapping
  to a real API-backed (or open-source local) provider behind the existing
  `TTSProvider` interface is a follow-up, not solved in this pass.

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

Modeled loosely on the Claude Code CLI's own UX: a chat interface sitting
alongside an artifact/state view, plus a run-mode toggle analogous to
`accept-edits` vs `auto` permission modes.

- "Start Run" trigger (POST to FastAPI `/runs`), with a run-mode selector
  (`accept_edits` / `auto`, see above) chosen at start time.
- Progressive artifact stream: the artifact tree view (cached / stale /
  pending, backed by the Postgres `artifacts` metadata table) updates as
  each artifact lands — including per-scene `ScenePreview` and `SceneFinal`
  clips as they complete, not just the final `FinalManifest` — so the user
  can watch scenes arrive individually rather than waiting on the whole run.
- Review/edit interface, at Interrupt A and Interrupt B (in `accept_edits`
  mode): a chat panel alongside the current artifact (`Script` or
  `SceneGraph`, rendered read-only) for "vibe-editing" — the user describes
  a change in natural language ("make scene 3 shorter," "switch the recap
  to Manim") rather than hand-editing JSON. This is backed by one new
  core-level, domain-agnostic call: an edit-assistant that takes
  `(artifact_type, current_artifact, chat_message, history) -> proposed
  artifact`, validated against the same pydantic schema as any other
  artifact of that type before use. Architecturally this changes nothing
  about the interrupt/resume mechanism — the chat turn just constructs the
  edited artifact; submitting it is still the same
  `Command(resume={"action": "edit", "artifact": {...}})` a direct JSON
  edit would produce. A raw JSON view stays available alongside the chat
  for direct edits when that's faster than describing the change.
- "Simulate Crash" / "Resume" buttons for the claim-#2 demo.

## Explicitly out of scope

- Concurrent runs (multiple lessons generating simultaneously). The
  scalability axis this pass targets is scene count per run (up to
  roughly a dozen, driven by the 10-minute duration cap), not concurrent
  run isolation. Revisit if that becomes a real requirement later.
- Multiple learning objectives / multiple independent worked examples per
  lesson, multi-lesson batches, multi-voice narration, a grader/judge
  panel.
- Source-document ingestion / RAG-based spec extraction. The interface
  already accommodates this later (`spec_schema` could grow an optional
  `source_documents` field; `structure()` could do retrieval internally)
  entirely inside a domain pack, without changing `packages/core`. Not
  built now — would dilute focus from the six claims.
- pgvector. No component in this design does similarity search or
  retrieval; adding it now would be an unmotivated dependency.
- Auto-retry/regeneration loop on verification failure — a mismatch halts
  the run; it does not feed back into the LLM automatically.
- Production hardening of the GCP deployment: no CI/CD pipeline,
  Terraform/IaC, multi-user auth, autoscaling tuning, or cost controls.
  The deploy target is a real but manually-run private instance (you're
  the only user); the `ArtifactStore`/`RenderDispatcher` seams are what
  carry this toward production later, not a deploy pipeline built now.
