import json as _json
from typing import Callable

import anthropic
from pydantic import BaseModel

from spectacle_core.versioning import compute_fingerprint

from spectacle_education.lesson_plan import LessonPlan
from spectacle_education.timing import infer_durations


class IntakeResult(BaseModel):
    plan: LessonPlan | None = None
    clarifying_questions: list[str] = []


IntakeLLMFn = Callable[[str, list[dict]], dict]

_client: anthropic.Anthropic | None = None

_SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_id": {"type": "string"},
        "type": {"type": "string", "description": "Scene type from the scene-type vocabulary, e.g. 'worked_example', 'intro', 'summary'."},
        "render_hint": {"type": "string", "enum": ["layout", "equation_morph"]},
        "content": {"type": "string", "description": "Pedagogical brief for the scriptwriter."},
        "verify": {"type": "boolean", "description": "Whether this scene's expression must pass the sympy verification gate."},
        "expression": {
            "type": ["string", "null"],
            "description": (
                "Plain arithmetic/algebra notation only (e.g. '3/4 + 1/8'), no LaTeX. "
                "The single source of truth fed to both the renderer and the verification "
                "gate -- required whenever verify is true."
            ),
        },
        "source": {
            "type": "string",
            "enum": ["author", "intake_draft"],
            "description": (
                "'author' only when the expression came directly from the learner's own "
                "input verbatim; otherwise 'intake_draft' (LLM-proposed, needs human confirmation)."
            ),
        },
    },
    "required": ["scene_id", "type", "render_hint", "content", "source"],
}

_INTAKE_TOOL = {
    "name": "compile_lesson_intake",
    "description": (
        "Compile raw learner/teacher input into a structured lesson plan, or -- if the input "
        "doesn't yet contain enough information to build one -- return clarifying questions instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "plan": {
                "type": ["object", "null"],
                "description": (
                    "A draft LessonPlan, or null if the input doesn't meet the readiness "
                    "threshold (at least one objective, a stated audience, and an expression "
                    "for every verify=true scene)."
                ),
                "properties": {
                    "objectives": {"type": "array", "items": {"type": "string"}},
                    "audience": {"type": "string"},
                    "grade_level": {"type": ["string", "null"]},
                    "total_duration_target_minutes": {"type": ["integer", "null"]},
                    "constraints": {"type": ["string", "null"]},
                    "worked_example_expression_hint": {
                        "type": ["string", "null"],
                        "description": "Plain notation math expression to anchor the worked example, if any.",
                    },
                    "scenes": {"type": "array", "items": _SCENE_SCHEMA},
                },
                "required": ["objectives", "audience"],
            },
            "questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Clarifying questions to ask the learner/teacher, when 'plan' is null.",
            },
        },
        "required": ["questions"],
    },
}

_INTAKE_MODEL = "claude-sonnet-4-5-20250929"
_INTAKE_TEMPLATE = _json.dumps(_INTAKE_TOOL, sort_keys=True)
INTAKE_FINGERPRINT = compute_fingerprint(
    "intake", _INTAKE_MODEL, _INTAKE_TEMPLATE, {"max_tokens": 1024, "tool_choice": "any"}
)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def default_intake_llm(raw_input: str, prior_chat: list[dict]) -> dict:
    history = ""
    if prior_chat:
        history = "\nPrior conversation:\n" + "\n".join(
            f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in prior_chat
        )
    prompt = (
        "A learner or teacher is describing a lesson they want made into a short video.\n"
        f"Input: {raw_input}{history}\n\n"
        "If the input gives enough to build a lesson plan (at least one clear learning "
        "objective, a stated audience, and -- for any scene that needs verification -- a "
        "concrete math expression), compile it into 'plan'. Otherwise leave 'plan' null and "
        "ask for what's missing in 'questions'. Use the compile_lesson_intake tool."
    )
    msg = _get_client().messages.create(
        model=_INTAKE_MODEL,
        max_tokens=1024,
        tools=[_INTAKE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    data = tool_use.input
    return {"plan": data.get("plan"), "questions": data.get("questions") or []}


default_intake_llm.fingerprint = INTAKE_FINGERPRINT


def _meets_threshold(plan: LessonPlan) -> tuple[bool, list[str]]:
    missing = []
    if not plan.objectives:
        missing.append("What is the learning objective?")
    if not plan.audience:
        missing.append("Who is the audience (e.g. grade level)?")
    for scene in plan.scenes:
        if scene.verify and not scene.expression:
            missing.append(f"What is the math expression to verify for scene '{scene.scene_id}'?")
    return (not missing, missing)


def intake(raw_input: str, prior_chat: list[dict], llm_fn: IntakeLLMFn = default_intake_llm) -> IntakeResult:
    out = llm_fn(raw_input, prior_chat)
    fingerprint = getattr(llm_fn, "fingerprint", "intake@stub")
    plan_data = out.get("plan")
    if plan_data:
        plan = LessonPlan.model_validate({**plan_data, "node_version": fingerprint})
        infer_durations(plan.scenes, plan.total_duration_target_minutes)
        ok, missing = _meets_threshold(plan)
        if ok:
            return IntakeResult(plan=plan, clarifying_questions=[])
        return IntakeResult(plan=None, clarifying_questions=out.get("questions") or missing)
    return IntakeResult(plan=None, clarifying_questions=out.get("questions") or ["Please describe the lesson."])


def lift_legacy_spec(spec: dict) -> LessonPlan:
    """Lift the old flat EducationSpec-shaped dict into a thin LessonPlan with
    no scenes, so structure()'s menu fallback (Task 4) builds them."""
    return LessonPlan(
        node_version="legacy_shim@0",
        objectives=[spec["learning_objective"]],
        audience=spec.get("audience", ""),
        total_duration_target_minutes=spec.get("target_duration_minutes"),
        worked_example_expression_hint=spec.get("worked_example_expression"),
        scenes=[],
    )
