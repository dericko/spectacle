# Lesson Spec Intake — Implementation Plan (Sub-project 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `EducationSpec` with a two-layer SPEC — a free-text/markdown/chat on-ramp that an intake agent compiles into a structured, human-confirmed `LessonPlan` — so authors can start from a rough plan and the system infers scenes and timing, without ever letting unconfirmed or mis-attributed math reach the verification gate.

**Architecture:** A new domain-side `intake` LLM step turns raw input into a `LessonPlan` (or clarifying questions). A new plan-review interrupt confirms the plan and its math. `structure()` becomes a deterministic projection of the `LessonPlan` into the existing `ContentTree` (with the old scene-menu budgeting demoted to a fallback for thin inputs). Everything downstream of `structure` is unchanged.

**Tech Stack:** Python 3.14, LangGraph (interrupt/`Command(resume=...)`), pydantic v2, pytest. Source design: `docs/superpowers/specs/2026-07-15-lesson-spec-intake-design.md`.

## Global Constraints

- **PREREQUISITE — hardening Phase 0–1 must be merged first.** This plan consumes `spectacle_core.versioning.compute_fingerprint`, `spectacle_core.node_cache.node_input_key`, and `spectacle_core.node_cache.cached_or_compute` (built in `docs/superpowers/plans/2026-07-15-spectacle-hardening.md`). Do not start until those modules exist and their tests pass.
- **Do not weaken the sympy verification gate or its hard-gating** (`domains/education/.../verification.py`, `nodes/verification_gate.py`). Assertion A4: `git diff` on `verification.py` is empty except tests.
- **Do not widen `SAFE_EXPRESSION_RE`.** Arithmetic-only stays. Flag if it blocks you.
- **`packages/core` never imports from `domains/`** (Assertion A9). The `intake` seam added to core is a generic protocol method, not education-specific logic.
- **The single-source-of-truth invariant (A1) is inviolable:** a verify scene's `expression` is the one string fed to both the renderer and the sympy gate. `script_agent` must not invent or alter it.
- Work on `main`, commit after every green step, do not push. End commit messages with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Follow existing test idioms: `unittest.mock.patch` on module-level functions, `LocalFileArtifactStore(tmp_path)`, `content_hash`, injectable `*_llm_fn` seams so tests never hit the network.

## Settled decisions (from the design spec — do not re-litigate)

See `docs/superpowers/specs/2026-07-15-lesson-spec-intake-design.md` §"Settled decisions". Summary: plan-driven scenes (menu = fallback), two-layer SPEC (`LessonPlan` is the contract), draft-then-confirm math, structured checkpoints (no anytime-redirect), scene-type vocabulary retained, verification gate untouched.

**Out of scope (this sub-project):** persistent chat-context UI + chat↔run wiring (that's sub-project 2, Assertion A12); anytime-redirect ("opt 3"); widening `SAFE_EXPRESSION_RE`.

## File structure

- Create: `domains/education/src/spectacle_education/lesson_plan.py` — `SceneSpec`, `LessonPlan`, confirmation semantics.
- Create: `domains/education/src/spectacle_education/intake.py` — `intake()`, `IntakeResult`, readiness threshold, `default_intake_llm` (fingerprinted), `lift_legacy_spec()`.
- Create: `domains/education/src/spectacle_education/timing.py` — `infer_durations()`.
- Modify: `domains/education/src/spectacle_education/structure_agent.py` — deterministic `structure(plan)` + menu fallback; drop the LLM enrichment (moves to intake).
- Modify: `domains/education/src/spectacle_education/scene_menu.py` — `budget_scenes` accepts objectives+duration, not only `EducationSpec`.
- Modify: `domains/education/src/spectacle_education/spec.py` — keep `EducationSpec` only as the legacy-shim input shape.
- Modify: `domains/education/src/spectacle_education/__init__.py` — `spec_schema = LessonPlan`, add `intake`.
- Modify: `packages/core/src/spectacle_core/domain_pack.py` — add generic `intake` to the `DomainPack` protocol; `structure` takes the spec type.
- Modify: `packages/core/src/spectacle_core/nodes/interrupts.py` — reuse as-is (no change expected); confirm.
- Create: `packages/core/src/spectacle_core/nodes/plan_gate.py` — `check_plan_confirmed()` + `PlanConfirmationError` (generic; takes a list of (verify, confirmed, expression) tuples so core stays domain-agnostic).
- Modify: `packages/core/src/spectacle_core/graph.py` — add `intake` + `clarify` + `plan_review` + `plan_gate` nodes before `structure`; relocate the node-cache from `structure` to `intake`.
- Modify: `apps/server/src/server/stub_llms.py` — add `stub_intake_llm`.
- Modify: `apps/server/src/server/main.py` / `run_manager.py` — `StartRunRequest` accepts `raw_input`; legacy `spec` dict lifted via `lift_legacy_spec`.
- Modify tests across `domains/education/tests/` and add `packages/core/tests/test_plan_gate.py`, `domains/education/tests/test_lesson_plan.py`, `test_intake.py`, `test_timing.py`.

---

## Task 1: `LessonPlan` + `SceneSpec` schema

**Files:**
- Create: `domains/education/src/spectacle_education/lesson_plan.py`
- Test: `domains/education/tests/test_lesson_plan.py`

**Interfaces:**
- Produces: `SceneSpec` (pydantic) with fields per design §1; `LessonPlan(VersionedArtifact)` with `node_version` (the intake fingerprint), `objectives`, `audience`, `grade_level`, `total_duration_target_minutes`, `constraints`, `scenes: list[SceneSpec]`.
- Consumes: `spectacle_core.models.VersionedArtifact` (gives `compute_hash()`).

- [ ] **Step 1: Write the failing test.**

```python
# domains/education/tests/test_lesson_plan.py
import pytest
from spectacle_education.lesson_plan import SceneSpec, LessonPlan


def _scene(**kw):
    base = dict(scene_id="worked_example_1", type="worked_example",
                render_hint="equation_morph", content="add the fractions",
                verify=True, expression="3/4 + 1/8", target_duration_s=45.0,
                source="author")
    base.update(kw); return SceneSpec(**base)


def test_author_math_is_confirmed_by_default():
    assert _scene(source="author").confirmed is True


def test_draft_math_is_unconfirmed_by_default():
    assert _scene(source="intake_draft").confirmed is False


def test_draft_can_be_explicitly_confirmed():
    assert _scene(source="intake_draft", confirmed=True).confirmed is True


def test_lesson_plan_is_content_addressed():
    plan = LessonPlan(node_version="intake@abc", objectives=["add fractions"],
                      audience="grade 4", scenes=[_scene()])
    assert len(plan.compute_hash()) == 64
    # identical content → identical hash
    plan2 = LessonPlan(node_version="intake@abc", objectives=["add fractions"],
                       audience="grade 4", scenes=[_scene()])
    assert plan.compute_hash() == plan2.compute_hash()
```

- [ ] **Step 2: Run → FAIL.** `pytest domains/education/tests/test_lesson_plan.py -v` (module missing).

- [ ] **Step 3: Implement.**

```python
# domains/education/src/spectacle_education/lesson_plan.py
from typing import Literal
from pydantic import BaseModel, model_validator
from spectacle_core.models import VersionedArtifact


class SceneSpec(BaseModel):
    scene_id: str
    type: str                                   # from the scene-type vocabulary
    render_hint: Literal["layout", "equation_morph"]
    content: str                                # pedagogical brief for the scriptwriter
    verify: bool = False
    expression: str | None = None               # single source of truth (render + gate)
    target_duration_s: float = 30.0
    source: Literal["author", "intake_draft"] = "intake_draft"
    confirmed: bool | None = None               # resolved by the validator below

    @model_validator(mode="after")
    def _default_confirmed(self) -> "SceneSpec":
        # confirmed == (source == "author") or explicitly set true (e.g. human
        # approval at plan-review). Author-supplied math is confirmed by
        # authorship; drafts start unconfirmed.
        if self.confirmed is None:
            self.confirmed = self.source == "author"
        return self


class LessonPlan(VersionedArtifact):
    node_version: str = "intake@0"              # overwritten with the real intake fingerprint
    objectives: list[str]
    audience: str
    grade_level: str | None = None
    total_duration_target_minutes: int | None = None
    constraints: str | None = None
    # Math for the menu-fallback path (thin plan with no explicit scenes): the
    # fallback needs a worked-example expression to build a verifiable scene.
    # Author-supplied, so the fallback marks that scene source="author".
    worked_example_expression_hint: str | None = None
    scenes: list[SceneSpec] = []
```

- [ ] **Step 4: Run → PASS.** Commit.

```bash
git add domains/education/src/spectacle_education/lesson_plan.py domains/education/tests/test_lesson_plan.py
git commit -m "feat: LessonPlan + SceneSpec schema with confirmation semantics"
```

---

## Task 2: Confirmation-integrity gate (`plan_gate`)

Enforces A2/A3: a `verify=True` scene with missing/unconfirmed `expression` blocks the run. Lives in core, kept domain-agnostic by operating on plain tuples.

**Files:**
- Create: `packages/core/src/spectacle_core/nodes/plan_gate.py`
- Test: `packages/core/tests/test_plan_gate.py`

**Interfaces:**
- Produces: `PlanConfirmationError(Exception)`; `check_plan_confirmed(scenes: list[dict]) -> None` where each dict has `scene_id`, `verify`, `confirmed`, `expression`. Raises on any verify scene lacking confirmation or expression.

- [ ] **Step 1: Failing test.**

```python
# packages/core/tests/test_plan_gate.py
import pytest
from spectacle_core.nodes.plan_gate import check_plan_confirmed, PlanConfirmationError


def _s(scene_id, verify, confirmed, expression):
    return {"scene_id": scene_id, "verify": verify, "confirmed": confirmed, "expression": expression}


def test_confirmed_verify_scene_passes():
    check_plan_confirmed([_s("we_1", True, True, "3/4 + 1/8")])  # no raise


def test_unverified_scene_needs_nothing():
    check_plan_confirmed([_s("intro_1", False, False, None)])  # no raise


def test_unconfirmed_verify_scene_blocks():
    with pytest.raises(PlanConfirmationError) as e:
        check_plan_confirmed([_s("we_1", True, False, "3/4 + 1/8")])
    assert "we_1" in str(e.value)


def test_verify_scene_missing_expression_blocks():
    with pytest.raises(PlanConfirmationError):
        check_plan_confirmed([_s("we_1", True, True, None)])
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.**

```python
# packages/core/src/spectacle_core/nodes/plan_gate.py
class PlanConfirmationError(Exception):
    pass


def check_plan_confirmed(scenes: list[dict]) -> None:
    """Provenance/confirmation gate (distinct from the arithmetic sympy gate).
    A verify scene may only proceed if its math is confirmed AND present.
    Enforced in every run mode; in 'auto' mode intake_draft scenes stay
    unconfirmed and therefore block here."""
    bad = []
    for s in scenes:
        if not s.get("verify"):
            continue
        if not s.get("confirmed") or not s.get("expression"):
            bad.append(s.get("scene_id", "?"))
    if bad:
        raise PlanConfirmationError(
            f"verify scenes not confirmed or missing expression: {', '.join(bad)}")
```

- [ ] **Step 4: Run → PASS.** Commit.

```bash
git add packages/core/src/spectacle_core/nodes/plan_gate.py packages/core/tests/test_plan_gate.py
git commit -m "feat: plan confirmation gate (blocks unconfirmed verify scenes)"
```

---

## Task 3: Timing inference

**Files:**
- Create: `domains/education/src/spectacle_education/timing.py`
- Test: `domains/education/tests/test_timing.py`

**Interfaces:**
- Produces: `infer_durations(scenes: list[SceneSpec], total_target_minutes: int | None) -> None` — mutates each `scene.target_duration_s` in place. Content volume proxied by `len(scene.content.split())`.

- [ ] **Step 1: Failing test (Assertion A8).**

```python
# domains/education/tests/test_timing.py
from spectacle_education.lesson_plan import SceneSpec
from spectacle_education.timing import infer_durations


def _mk(n_words):
    return SceneSpec(scene_id="s", type="concept_explanation", render_hint="layout",
                     content=" ".join(["w"] * n_words))


def test_distributes_total_by_content_volume():
    scenes = [_mk(10), _mk(30)]
    infer_durations(scenes, total_target_minutes=4)  # 240s
    assert abs(sum(s.target_duration_s for s in scenes) - 240) < 1.0
    assert scenes[1].target_duration_s > scenes[0].target_duration_s  # more words → longer


def test_positive_durations_without_a_target():
    scenes = [_mk(5), _mk(20)]
    infer_durations(scenes, total_target_minutes=None)
    assert all(s.target_duration_s > 0 for s in scenes)
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.**

```python
# domains/education/src/spectacle_education/timing.py
from spectacle_education.lesson_plan import SceneSpec

_DEFAULT_WORDS_PER_SECOND = 2.5  # rough narration pace for the no-target heuristic


def infer_durations(scenes: list[SceneSpec], total_target_minutes: int | None) -> None:
    weights = [max(len(s.content.split()), 1) for s in scenes]
    if total_target_minutes:
        total_s = total_target_minutes * 60
        wsum = sum(weights)
        for s, w in zip(scenes, weights):
            s.target_duration_s = round(total_s * w / wsum, 1)
    else:
        for s, w in zip(scenes, weights):
            s.target_duration_s = round(w / _DEFAULT_WORDS_PER_SECOND, 1)
```

- [ ] **Step 4: Run → PASS.** Commit.

```bash
git add domains/education/src/spectacle_education/timing.py domains/education/tests/test_timing.py
git commit -m "feat: content-volume timing inference for LessonPlan scenes"
```

---

## Task 4: Plan-driven `structure()` + menu fallback

Makes `structure` deterministic: project the plan's scenes directly, or fall back to the menu for a thin plan. **Removes the structure-stage LLM enrichment** (content hints / guided-practice generation) — those responsibilities move to intake (Task 5).

**Files:**
- Modify: `domains/education/src/spectacle_education/scene_menu.py` (loosen `budget_scenes` signature)
- Modify: `domains/education/src/spectacle_education/structure_agent.py`
- Modify: `domains/education/tests/test_structure_agent.py`, `test_scene_menu.py`

**Interfaces:**
- Produces: `structure(plan: LessonPlan) -> ContentTree` (deterministic, no LLM, no kwargs).
- Consumes: `budget_scenes(objectives, worked_example_expression, target_duration_minutes) -> list[SceneStub]`.

- [ ] **Step 1: Loosen `budget_scenes`.** Change its signature from `budget_scenes(spec: EducationSpec)` to `budget_scenes(objective: str, worked_example_expression: str | None, target_duration_minutes: int)`. Update its body to use those args (it currently reads `spec.target_duration_minutes` and `spec.learning_objective`). Update `test_scene_menu.py` call sites.

- [ ] **Step 2: Failing tests for `structure` (Assertions A6, A7).**

```python
# domains/education/tests/test_structure_agent.py  (replace EducationSpec-based tests)
from spectacle_education.lesson_plan import LessonPlan, SceneSpec
from spectacle_education.structure_agent import structure


def test_explicit_plan_scenes_drive_structure():  # A7
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", scenes=[
            SceneSpec(scene_id="intro_1", type="intro", render_hint="layout", content="hook"),
            SceneSpec(scene_id="worked_example_1", type="worked_example",
                      render_hint="equation_morph", content="solve it", verify=True,
                      expression="3/4 + 1/8", source="author"),
        ])
    tree = structure(plan)
    assert [s.scene_id for s in tree.scenes] == ["intro_1", "worked_example_1"]
    we = next(s for s in tree.scenes if s.scene_id == "worked_example_1")
    assert we.expression == "3/4 + 1/8" and we.verify is True


def test_thin_plan_falls_back_to_menu():  # A6
    plan = LessonPlan(node_version="intake@x", objectives=["add fractions"],
        audience="grade 4", total_duration_target_minutes=3,
        worked_example_expression_hint="3/4 + 1/8", scenes=[])
    tree = structure(plan)
    names = {s.scene_id.rsplit("_", 1)[0] for s in tree.scenes}
    assert {"intro", "worked_example", "recap"} <= names  # menu mandatory scenes present
```

Note: the thin-fallback test relies on `LessonPlan.worked_example_expression_hint` (defined in Task 1) to give the menu fallback math to verify. The fallback marks that generated worked-example scene `source="author"` (the expression came from the author's input).

- [ ] **Step 3: Run → FAIL.**

- [ ] **Step 4: Implement deterministic `structure`.**

```python
# domains/education/src/spectacle_education/structure_agent.py  (new body)
from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_education.lesson_plan import LessonPlan
from spectacle_education.scene_menu import budget_scenes


def structure(plan: LessonPlan) -> ContentTree:
    spec_hash = content_hash(plan.model_dump(mode="json"))
    if plan.scenes:
        stubs = [SceneStub(
            scene_id=s.scene_id, render_hint=s.render_hint, content_hint=s.content,
            target_duration_s=s.target_duration_s, verify=s.verify, expression=s.expression,
        ) for s in plan.scenes]
    else:
        objective = plan.objectives[0] if plan.objectives else ""
        stubs = budget_scenes(objective, plan.worked_example_expression_hint,
                              plan.total_duration_target_minutes or 3)
    return ContentTree(spec_hash=spec_hash, scenes=stubs)
```

(The old LLM helper functions `default_content_hint_llm` / `default_guided_practice_expression_llm` are deleted here — they move to intake. Remove their imports/usages; delete `test_structure_agent` cases that asserted LLM enrichment.)

- [ ] **Step 5: Run → PASS.** Commit.

```bash
git add domains/education/src/spectacle_education/structure_agent.py domains/education/src/spectacle_education/scene_menu.py domains/education/src/spectacle_education/lesson_plan.py domains/education/tests/
git commit -m "feat: deterministic plan-driven structure() with menu fallback"
```

---

## Task 5: Intake agent + readiness threshold + legacy shim

**Files:**
- Create: `domains/education/src/spectacle_education/intake.py`
- Test: `domains/education/tests/test_intake.py`

**Interfaces:**
- Produces: `IntakeResult(BaseModel){plan: LessonPlan | None, clarifying_questions: list[str]}`; `intake(raw_input: str, prior_chat: list[dict], llm_fn=default_intake_llm) -> IntakeResult`; `default_intake_llm(raw_input, prior_chat) -> dict` (fingerprinted with `compute_fingerprint`); `lift_legacy_spec(spec: dict) -> LessonPlan`.
- Consumes: `spectacle_core.versioning.compute_fingerprint`.

- [ ] **Step 1: Failing tests (Assertions A5, A11) with a fake llm_fn.**

```python
# domains/education/tests/test_intake.py
from spectacle_education.intake import intake, IntakeResult, lift_legacy_spec


def test_below_threshold_returns_questions_not_plan():  # A5
    def fake_llm(raw, chat):
        return {"plan": None, "questions": ["What grade level?"]}
    result = intake("teach fractions", [], llm_fn=fake_llm)
    assert result.plan is None
    assert result.clarifying_questions == ["What grade level?"]


def test_ready_input_compiles_a_plan():
    def fake_llm(raw, chat):
        return {"plan": {"objectives": ["add unlike fractions"], "audience": "grade 4",
                         "scenes": [{"scene_id": "worked_example_1", "type": "worked_example",
                                     "render_hint": "equation_morph", "content": "solve",
                                     "verify": True, "expression": "3/4 + 1/8",
                                     "source": "author"}]},
                "questions": []}
    result = intake("...", [], llm_fn=fake_llm)
    assert result.plan is not None
    assert result.plan.scenes[0].confirmed is True  # author-supplied


def test_readiness_enforced_in_code_even_if_llm_returns_a_thin_plan():  # A5 safety net
    # LLM returns a "plan" with no objectives -> intake must downgrade to questions.
    def fake_llm(raw, chat):
        return {"plan": {"objectives": [], "audience": "", "scenes": []}, "questions": []}
    result = intake("...", [], llm_fn=fake_llm)
    assert result.plan is None and result.clarifying_questions


def test_legacy_spec_lifts_to_minimal_plan():
    plan = lift_legacy_spec({"learning_objective": "add fractions",
                             "worked_example_expression": "3/4 + 1/8",
                             "target_duration_minutes": 3, "audience": "grade 4"})
    assert plan.objectives == ["add fractions"]
    assert plan.worked_example_expression_hint == "3/4 + 1/8"
    assert plan.scenes == []  # thin → structure() will use the menu fallback
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement `intake` (readiness enforced in code), `IntakeResult`, `lift_legacy_spec`, and the fingerprinted default LLM.** The default LLM uses one Anthropic tool call returning `{"plan": {...}|null, "questions": [...]}`; keep it out of the test path. `intake()` validates any returned plan to `LessonPlan`, runs `_meets_threshold(plan)` (≥1 objective, non-empty audience, and every verify scene has an `expression`), and if it fails, returns questions (from the LLM or derived from what's missing). Attach `default_intake_llm.fingerprint = compute_fingerprint("intake", model, tool_template, params)` and stamp it into `plan.node_version` before returning.

```python
# sketch of the threshold + stamping (fill LLM body per script_agent.py's pattern)
def intake(raw_input, prior_chat, llm_fn=default_intake_llm):
    out = llm_fn(raw_input, prior_chat)
    fingerprint = getattr(llm_fn, "fingerprint", "intake@stub")
    plan_data = out.get("plan")
    if plan_data:
        plan = LessonPlan.model_validate({**plan_data, "node_version": fingerprint})
        infer_durations(plan.scenes, plan.total_duration_target_minutes)  # Task 3
        ok, missing = _meets_threshold(plan)
        if ok:
            return IntakeResult(plan=plan, clarifying_questions=[])
        return IntakeResult(plan=None, clarifying_questions=out.get("questions") or missing)
    return IntakeResult(plan=None, clarifying_questions=out.get("questions") or ["Please describe the lesson."])
```

- [ ] **Step 4: Run → PASS.** Commit.

```bash
git add domains/education/src/spectacle_education/intake.py domains/education/tests/test_intake.py
git commit -m "feat: intake agent with in-code readiness threshold + legacy shim"
```

---

## Task 6: DomainPack protocol + education pack wiring

**Files:**
- Modify: `packages/core/src/spectacle_core/domain_pack.py`
- Modify: `domains/education/src/spectacle_education/__init__.py`
- Modify: `domains/education/tests/test_domain_pack.py` (if it asserts the old shape) and `packages/core/tests/test_domain_pack.py`

**Interfaces:**
- `DomainPack` protocol gains: `def intake(self, raw_input: str, prior_chat: list[dict]) -> "IntakeResult": ...` (typed loosely as returning an object with `.plan` / `.clarifying_questions` to avoid a core→domain import — use a `Protocol` or `Any`). `structure(self, spec)` stays but now receives the `spec_schema` instance.

- [ ] **Step 1: Failing test** — assert `education_pack.spec_schema is LessonPlan` and `education_pack.intake("x", [])` returns an `IntakeResult`-shaped object (use a monkeypatched stub intake to avoid the network).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** Add `intake` to the protocol (keep core domain-agnostic: annotate the return as a structural `Protocol` with `plan` and `clarifying_questions` attributes, defined in `domain_pack.py`). Wire `_EducationPack`: `spec_schema = LessonPlan`, `structure = staticmethod(structure)`, `intake = staticmethod(intake)`.
- [ ] **Step 4: Run → PASS.** Commit.

---

## Task 7: Graph wiring — intake → clarify-loop → plan_review → plan_gate → structure

Insert the new front end and **relocate the node-cache from `structure` to `intake`** (structure is now deterministic; intake is the LLM node).

**Files:**
- Modify: `packages/core/src/spectacle_core/graph.py`
- Test: `packages/core/tests/test_graph_integration.py` (add intake-path cases)

**Interfaces:**
- `GraphState` gains `raw_input: str`, `lesson_plan: dict | None`, `clarifying_questions: list[str]`.
- New nodes: `intake_node`, `clarify_node` (interrupt to collect answers, loop back to intake), `plan_review_node` (interrupt to confirm plan + flip `confirmed`), `plan_gate_node` (calls `check_plan_confirmed`), then existing `structure`.

- [ ] **Step 1: Failing integration tests (Assertions A2, A10).** Using stub intake/script LLMs and a fresh store:
  - A2: a plan with a `verify=True, confirmed=False` scene reaching `plan_gate` raises `PlanConfirmationError` (run ends in `error`), and no render occurs.
  - A10: running `intake_node` twice with identical `raw_input` + same fingerprint calls the stub intake once (cache hit second time).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement the graph edges.**
  - Entry point → `intake`. `intake_node` computes `input_key = node_input_key(content_hash(raw_input + prior_chat), intake_fingerprint)` and wraps the intake call in `cached_or_compute` (returning a `LessonPlan`; the clarifying-questions branch is *not* cached).
  - Conditional edge after `intake`: if `clarifying_questions` present → `clarify` (interrupt; on resume, append answers to `raw_input`/`prior_chat`, edge back to `intake`); else → `plan_review`.
  - `plan_review_node`: `interrupt_review(plan, LessonPlan, run_mode)` (reuse `nodes/interrupts.py`) — the human-edited plan comes back with `confirmed` flags set; in `auto` mode it passes through unchanged (drafts stay unconfirmed).
  - `plan_review` → `plan_gate` (calls `check_plan_confirmed` over the plan's scenes; raises to block) → `structure`.
  - **Remove** the `cached_or_compute` wrapper from `structure_node` (it's deterministic now) and the `structure` fingerprint plumbing; keep `record(...)` so the ContentTree still shows in the UI.
- [ ] **Step 4: Run → PASS** (full `pytest packages/core -v`). Commit.

**Note for executor:** confirm the hardening plan's Phase 1 left `structure` cached; this task moves that caching. If Phase 1 is not yet merged, STOP — this task depends on `node_cache`/`versioning`.

---

## Task 8: Server + stubs + legacy input path

**Files:**
- Modify: `apps/server/src/server/main.py` (`StartRunRequest`), `run_manager.py`
- Modify: `apps/server/src/server/stub_llms.py` (add `stub_intake_llm`)
- Test: `apps/server/tests/test_main.py`, `test_run_manager.py`

- [ ] **Step 1: Failing test** — `POST /runs` accepts `{"raw_input": "..."}`; and a legacy `{"spec": {4 fields}}` body still starts a run (lifted via `lift_legacy_spec`).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** `StartRunRequest` gains `raw_input: str | None`; if `spec` (legacy 4-field) is present and `raw_input` is absent, `run_manager` calls `lift_legacy_spec` and injects the resulting `LessonPlan` as `state["lesson_plan"]`, skipping intake (edge straight to `plan_review`). Add `stub_intake_llm` returning a deterministic ready plan for stub runs. Thread `intake_llm_fn` through `build_graph` like `script_llm_fn`.
- [ ] **Step 4: Run → PASS.** Commit.

---

## Task 9: Web create-a-video form (minimal)

Swap the four fields for a single textarea feeding `raw_input`; reuse the existing interrupt UI for plan-review (a plan is just another artifact to approve/edit).

**Files:**
- Modify: `apps/web/app/page.tsx` (or the create-run form component), `apps/web/lib/api.ts`

- [ ] **Step 1:** Replace the structured form inputs with a `raw_input` textarea; POST `{ raw_input }`.
- [ ] **Step 2:** Confirm the runs/[id] review panel renders a `LessonPlan` artifact for plan-review (it already renders arbitrary artifact JSON via `ArtifactPreview`/`ReviewPanel`; verify the plan shape displays and edit/approve round-trips). If the review panel special-cases `Script`/`SceneGraph` types, add `LessonPlan` to that set.
- [ ] **Step 3:** Manual smoke check: start a stub run from the textarea, confirm the plan-review interrupt appears and approval proceeds. Commit.

**Note:** full chat UI is sub-project 2 — this task ships only the text box + existing interrupt approval.

---

## Task 10: End-to-end assertion tests (A1, A7 e2e)

**Files:**
- Test: `domains/education/tests/test_intake_e2e.py` (or extend `test_graph_integration.py`)

- [ ] **Step 1: A1 (single source of truth), e2e with stubs.** Drive a full stub run for a verify scene; assert the `expression` on the `SceneGraphEntry` handed to `render_scene` is byte-identical to the `expression` passed to the sympy gate (they already come from the same field — this test *guards* that a future refactor doesn't fork them). Patch renderers/TTS as the existing render tests do.
- [ ] **Step 2: A7 e2e** — a rich stub plan with 4 explicit scenes yields a final scene graph with those 4 scenes in order (not the menu's 3-mandatory shape).
- [ ] **Step 3: Run → PASS.** Commit.

---

## Self-review checklist (run after implementing)

- **A1:** grep that `expression` flows unmodified from `SceneSpec` → `SceneStub` → `SceneNarration` → `SceneGraphEntry` → both the renderer and the gate. No node rewrites it.
- **A2/A3:** `plan_gate` runs before `structure` in the compiled graph, in all run modes; auto-mode drafts block. Covered by Task 2 + Task 7 tests.
- **A4:** `git diff domains/education/src/spectacle_education/verification.py` empty (except tests). `SAFE_EXPRESSION_RE` untouched.
- **A9:** grep `packages/core` for any `spectacle_education` import → none.
- **A10/A11:** intake is fingerprinted and cache-wrapped; `structure` is no longer cache-wrapped (moved). Changing the intake prompt changes the fingerprint (Task 5/7 tests).
- **Type consistency:** `IntakeResult.plan` / `.clarifying_questions`, `SceneSpec.confirmed`/`.source`, `check_plan_confirmed`, `structure(plan)`, `budget_scenes(objective, expr, minutes)` — identical everywhere referenced.
- **Migration:** every old `EducationSpec`/`structure(spec, ...)` caller updated; legacy input still works via `lift_legacy_spec`.

## Follow-ups to flag (out of scope)

- Sub-project 2: persistent chat-context UI + chat↔run wiring (Assertion A12).
- Anytime-redirect co-pilot ("opt 3").
- Richer intake (multi-example lessons, standards alignment) once the base flow is proven.
- Widening `SAFE_EXPRESSION_RE` so verify covers algebra, not just arithmetic.
