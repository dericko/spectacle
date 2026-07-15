# Lesson Spec Intake — Design

**Date:** 2026-07-15
**Status:** Approved design; ready for implementation planning (sub-project 1 only).
**Related:** `docs/superpowers/plans/2026-07-15-spectacle-hardening.md` (this feature rides on that plan's Phase 1 cache + versioning).

## Problem

Today "the spec" is a single flat `EducationSpec` (four fields: `learning_objective`, `worked_example_expression`, `target_duration_minutes`, `audience`). It is doing two incompatible jobs at once: it is *both* the human on-ramp *and* the machine contract. That is why the create-a-video surface is trivially narrow — essentially one equation and a duration — and why richer inputs (a curriculum author's worked-out markdown lesson plan) have nowhere to go.

The system needs to accept a flexible, chat-like input a user can start with, infer structure and timing from it, and still preserve the one asset the audit identified as load-bearing: the symbolic verification gate, which is only meaningful when the math it checks is the math shown on screen.

## Settled decisions (do not re-litigate)

Resolved during the design dialogue that produced this doc:

1. **Plan-driven scenes.** A plan's sections drive scene sequence/count/content, replacing the fixed scene-menu budgeting as the *primary* path. The scene menu is **demoted to a fallback**, not retired.
2. **SPEC becomes two layers:** a raw human input, and a compiled, human-confirmed `LessonPlan` artifact. **The `LessonPlan` is "the SPEC"; the text box is the on-ramp.**
3. **Math provenance = draft-then-confirm (subsumes author-supplied).** Intake may *draft* worked-example math, but nothing is verification-eligible until a human confirms it into the `LessonPlan`. Author-supplied math is confirmed trivially.
4. **Interaction = structured checkpoints + persistent chat context.** The chat acts at the review interrupts (not anytime-redirect) but carries full history + a pipeline-state summary forward. Anytime-redirect ("opt 3") is a deferred later version.
5. **Curriculum author is the priority persona;** occasional teachers are served by the low-friction fallback path.
6. **Scene-type vocabulary is retained** (intro / concept_explanation / worked_example / guided_practice / recap, extensible); intake classifies each plan section into a type. The type drives renderer routing and verify-tagging; the plan drives sequence/content.
7. **Verification gate and `SAFE_EXPRESSION_RE` are untouched.** Arithmetic-only remains; widening to algebra is an out-of-scope follow-up.

## The two-layer SPEC model

```
Raw input (free text / markdown / chat)        ← layer 1: the on-ramp (forgiving)
        │
        │  intake agent (domain-side, LLM)
        │  · clarify-to-threshold
        │  · may DRAFT math (unconfirmed)
        ▼
LessonPlan  ← layer 2: "the SPEC" — structured, content-addressed, human-confirmed
        │
        │  plan-review interrupt (confirm plan + math)   ← NEW checkpoint ("interrupt Zero")
        ▼
structure(plan) → ContentTree  ← near-direct projection (plan is already scene-shaped)
        │
        ▼
script_agent → script_review → scene_planner → scene_graph_review
        → verification_gate → render → mux → MP4   (existing pipeline, unchanged downstream)
```

## Architecture fit

Maps onto the existing `DomainPack` protocol without touching `packages/core`:

- `spec_schema` becomes `LessonPlan` (replaces `EducationSpec`).
- **Intake and `LessonPlan` live in `domains/education`** — intake reasons about worked examples and math, so it is a domain concern. Core stays domain-agnostic (CLAUDE.md rule 1 holds).
- `structure(plan) → ContentTree` becomes a near-direct projection because the `LessonPlan` is already scene-shaped. When the plan is *thin* (no explicit scene structure), `structure` uses the existing `budget_scenes` menu to propose one — the fallback.
- Intake is a new LLM node and is fingerprinted + cacheable exactly like `structure`/`script_agent` (hardening plan Phase 1).

## Components

### 1. `LessonPlan` schema (new `spec_schema`)

Content-addressed pydantic artifact.

- **Top level:** `objectives: list[str]`, `audience: str`, `grade_level: str | None`, `total_duration_target_minutes: int | None`, `constraints: str | None`.
- **`scenes: list[SceneSpec]`**, each:
  - `scene_id: str`
  - `type: str` — from the vocabulary; drives `render_hint` and default `verify`
  - `render_hint: Literal["layout", "equation_morph"]` — derived from `type`, overridable
  - `content: str` — pedagogical brief the scriptwriter works from
  - `verify: bool`
  - `expression: str | None` — the confirmed math; **single source of truth** for both render and gate
  - `target_duration_s: float` — timing hint (see §5)
  - `source: Literal["author", "intake_draft"]`
  - `confirmed: bool`

**Confirmation semantics (the integrity core):**
`confirmed == (source == "author") or (human approved it at plan-review)`. Author-supplied math is confirmed by authorship; drafted math needs explicit human approval. In `auto` run mode there is no human, so `intake_draft` math stays `confirmed=false` and therefore cannot render (see §3) — an `auto` run therefore requires author-supplied math to have any verified scenes.

**Consequence for `script_agent`:** it no longer *invents* expressions. For a verify scene it writes narration/steps *around* the confirmed `expression`. This is what preserves "what's shown = what's verified" under plan-driven scenes.

### 2. Intake agent (domain-side)

`intake(raw_input, prior_chat) -> IntakeResult` where `IntakeResult` is either a compiled `LessonPlan` or a set of clarifying questions.

**Readiness threshold** (must hold before intake will compile-and-start):
- at least one objective;
- an audience (or an applied default);
- for every intended verify scene, a concrete `expression` (author-supplied → `source=author`, or drafted → `source=intake_draft, confirmed=false`);
- enough to produce a scene sequence — either explicit plan structure, or enough for the menu fallback.

Below threshold, intake returns **clarifying questions rather than a plan** — this is the "asks before it starts" behavior. Intake is an LLM step with a version fingerprint; identical raw input + same fingerprint returns a cached plan.

### 3. Plan-review interrupt ("interrupt Zero") + integrity enforcement

A new review checkpoint **after intake, before `script_agent`**, reusing the existing `interrupt()` / `Command(resume=...)` machinery. It is where the author confirms the compiled plan and any drafted math (flips `confirmed` to true). It is the earliest of the three human checkpoints (plan → script → scene-graph).

**Hard enforcement:** a `verify=True` scene with a missing or `confirmed=false` `expression` **cannot reach the renderer** — the pipeline blocks, in the same spirit as the sympy gate. This is a distinct, earlier check from `verification_gate` (which checks arithmetic correctness); this one checks *provenance/confirmation*. Both are hard, deterministic, and enforced in every run mode.

### 4. Plan-driven `structure()` with menu fallback

`structure(plan: LessonPlan) -> ContentTree`:
- If the plan has explicit scenes → project them directly to `SceneStub`s (sequence/count/content from the plan).
- If the plan is thin (no scene structure) → call the existing `budget_scenes` to propose a menu-based sequence sized to `total_duration_target_minutes`.
- Either way, every resulting scene has a known `type`, a `render_hint`, a `verify` flag, and (for verify scenes) the confirmed `expression`.

### 5. Timing inference

Intake sets each `SceneSpec.target_duration_s`:
- honor explicit author hints (distribute a stated total across scenes by content volume);
- else a content-volume heuristic scaled to a sane default total.

Downstream is **unchanged**: actual narration (TTS) duration remains the timing master, and `compute_item_start_times` still derives within-scene reveal timing from narration. So "infer timing" is honest — intake proposes hints; real timing emerges at render.

### 6. Chat / interaction (sub-project 2 boundary)

One persistent, pipeline-aware chat thread per run. It summarizes state by **reading what already exists** (artifact metadata store, warnings sidecar from hardening Phase 5, run status) — not new infrastructure. It acts at the three checkpoints (plan-review, script-review, scene-graph-review); interrupt A/plan-review is also the math-confirmation surface. No anytime-redirect. **This component is sub-project 2** (frontend + chat↔run wiring); it depends on but is separable from sub-project 1.

## Assertions (goal-oriented system checks)

Numbered, checkable statements. `[unit]` = unit-testable, `[e2e]` = end-to-end run check, `[static]` = code/structure check. These double as acceptance criteria and as a goal-oriented harness for validating the full system.

**Integrity (highest priority):**
- **A1 `[e2e]`** For every rendered scene with `verify=True`, the expression string handed to the sympy gate is byte-identical to the expression string rendered on screen (single source of truth). *Fail = the gate is verifying something other than what airs.*
- **A2 `[unit][e2e]`** No scene with `verify=True` and (`expression is None` or `confirmed=False`) ever reaches a renderer; the pipeline blocks first.
- **A3 `[unit]`** `confirmed` is true iff `source=="author"` or a human approved the scene at plan-review. In `auto` mode, an `intake_draft` verify scene remains `confirmed=False` and blocks per A2.
- **A4 `[static]`** The sympy verification gate (`verification.py`) and `SAFE_EXPRESSION_RE` are unchanged by this feature (diff-empty except tests). It still raises before render in all run modes.

**Intake behavior:**
- **A5 `[unit]`** Below-threshold raw input yields clarifying questions, never a compiled `LessonPlan`.
- **A6 `[e2e]`** A thin input (objective + duration, no scene structure) still produces a runnable `LessonPlan` via the menu fallback.
- **A7 `[e2e]`** A rich input with N explicit sections produces a `LessonPlan` whose scene count and order follow the input's structure, not the fixed menu.
- **A8 `[unit]`** When `total_duration_target_minutes` is given, the sum of `target_duration_s` approximates it within a stated tolerance; when absent, all `target_duration_s` are positive and derived from content volume.

**Architecture / caching:**
- **A9 `[static]`** `packages/core` imports nothing from `domains/education`; intake and `LessonPlan` live entirely in `domains/education`.
- **A10 `[e2e]`** Re-running intake on identical raw input with an unchanged intake fingerprint returns the cached `LessonPlan` with no new LLM call (rides on hardening Phase 1).
- **A11 `[unit]`** Changing the intake prompt/model changes its fingerprint, which invalidates the cached `LessonPlan` without a manual version bump.

**Interaction (sub-project 2):**
- **A12 `[e2e]`** A chat turn at scene-graph-review has access to the full prior chat history plus a summary reflecting completed stages (plan, script) and any warnings.

## Data flow (end-to-end, happy path)

1. Author types/paste raw input (curriculum markdown or a sentence).
2. Intake compiles → `LessonPlan` (may contain `intake_draft` math) or returns clarifying questions.
3. Plan-review interrupt: author confirms plan + math → `confirmed=true` on approved scenes.
4. `structure(plan)` → `ContentTree` (direct projection, or menu fallback if thin).
5. `script_agent` writes narration/steps around confirmed expressions → script-review.
6. `scene_planner` → scene-graph-review.
7. `verification_gate` (arithmetic) → render fan-out → mux → MP4.
8. Chat thread persists across 3–6, summarizing state read from existing stores.

## Migration surface

- `EducationSpec` → `LessonPlan` is a schema replacement. Existing references: `domains/education/src/spectacle_education/spec.py`, `structure_agent.py`, `scene_menu.py`, the education tests, `apps/server/src/server/stub_llms.py`, and the web create-run form. A compatibility shim (accept the old 4-field shape and lift it into a minimal `LessonPlan`) keeps existing runs/tests working during migration.
- The web create-a-video form changes from four fields to a text box + (later) chat; sub-project 1 can ship with the text box feeding intake and reusing the existing interrupt UI for plan-review.

## Scope & sequencing

- **Sub-project 1 (this spec → implementation plan):** `LessonPlan` schema + migration shim, intake agent + clarify loop, plan-review interrupt + confirmation enforcement (A1–A3), plan-driven `structure()` + menu fallback, timing inference. Self-contained and testable via A1–A11.
- **Sub-project 2 (follow-on spec):** persistent chat-context UI + chat↔run wiring (A12).
- **Sequencing:** hardening plan Phase 0–1 should land first, so intake is a fingerprinted, cacheable node from day one (A10/A11 depend on it).

## Out of scope / follow-ons

- Anytime-redirect co-pilot ("opt 3") — a later version; the checkpoint mechanism is written so opening it up is a widening, not a rewrite.
- Persistent chat UI (sub-project 2).
- Widening `SAFE_EXPRESSION_RE` to algebra/variables so verify covers non-arithmetic math.
- Multilingual / multi-voice narration.
- Auto-generating diagrams from plan sections (decorative layer, hardening Phase 6).
