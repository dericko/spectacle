import json as _json
from typing import Callable

import anthropic
from pydantic import BaseModel

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneNarration, Script
from spectacle_core.versioning import compute_fingerprint


class ScriptStep(BaseModel):
    expr: str
    label: str = ""


class ScriptLLMResponse(BaseModel):
    narration_text: str
    on_screen_text: str
    stated_answer: str | None = None
    items: list[str] = []
    item_icons: list[str] = []
    steps: list[ScriptStep] = []
    render_params: dict = {}


ScriptLLMFn = Callable[[SceneStub], ScriptLLMResponse]

_client: anthropic.Anthropic | None = None

# Must stay in sync with the icon names in apps/renderer-remotion/src/icons.tsx.
# A fixed enum (rather than open-ended image generation) keeps the per-bullet
# visual deterministic and renderable headlessly, while still letting the LLM
# choose which concept fits each bullet.
_ICON_NAMES = [
    "lightbulb", "target", "book", "chart_bar", "chart_line", "check",
    "calculator", "puzzle", "star", "arrow_right", "compare", "clock",
]

_SCRIPT_TOOL = {
    "name": "write_scene_script",
    "description": "Write the script content for a scene.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narration_text": {
                "type": "string",
                "description": (
                    "What the narrator says aloud. Should fill roughly the target duration. "
                    "When 'items' is provided, narration_text must consist of exactly one "
                    "sentence per item, in the same order, so each bullet's on-screen reveal "
                    "can be timed to the sentence describing it."
                ),
            },
            "on_screen_text": {
                "type": "string",
                "description": "Concise text displayed on screen (1-2 lines max).",
            },
            "stated_answer": {
                "type": "string",
                "description": "The final answer to the expression (e.g. '7/8'). Only for verify=true scenes.",
            },
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2-4 short bullet points for a layout scene, each restating one idea "
                    "from narration_text in order. Omit for non-layout scenes."
                ),
            },
            "item_icons": {
                "type": "array",
                "items": {"type": "string", "enum": _ICON_NAMES},
                "description": (
                    "One icon name per entry in 'items', same order and length, picking "
                    "whichever icon best represents that bullet's visual idea. Required "
                    "whenever 'items' is provided."
                ),
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "expr": {
                            "type": "string",
                            "description": (
                                "Plain arithmetic notation only (e.g. '3/4 + 1/8', '6/8 + 1/8', "
                                "'7/8') -- no LaTeX commands. Must be mathematically equivalent "
                                "to Expression; a verification gate rejects steps that aren't."
                            ),
                        },
                        "label": {"type": "string", "description": "Short label, e.g. 'Common denominator'."},
                    },
                    "required": ["expr"],
                },
                "description": (
                    "2-4 sequential algebra steps from Expression to stated_answer, each "
                    "mathematically equivalent to Expression. Only for verify=true scenes with "
                    "an Expression. The first step's expr should restate Expression and the "
                    "last should equal stated_answer. Write narration_text as exactly one "
                    "sentence per step, in the same order, describing that step's move."
                ),
            },
        },
        "required": ["narration_text", "on_screen_text"],
    },
}


_SCRIPT_MODEL = "claude-haiku-4-5-20251001"
# The static template = the tool schema + the fixed instruction skeleton.
# (Per-stub content enters the cache key via the upstream ContentTree hash,
# so it must NOT be part of the fingerprint.)
_SCRIPT_TEMPLATE = _json.dumps(_SCRIPT_TOOL, sort_keys=True)
SCRIPT_AGENT_FINGERPRINT = compute_fingerprint(
    "script_agent", _SCRIPT_MODEL, _SCRIPT_TEMPLATE, {"max_tokens": 400, "tool_choice": "any"}
)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def default_script_llm(stub: SceneStub) -> ScriptLLMResponse:
    scene_name = stub.scene_id.rsplit("_", 1)[0].replace("_", " ")
    expression_line = f"\nExpression: {stub.expression}" if stub.expression else ""
    answer_instruction = "\nInclude stated_answer: the simplified result of the expression." if stub.verify else ""
    items_instruction = (
        "\nInclude 2-4 short 'items' (bullet points) covering the key ideas, and write "
        "narration_text as exactly one sentence per item, in the same order, describing that item. "
        "Also include 'item_icons': one icon name per item (same order/length) picking whichever "
        "icon best matches that bullet's idea."
        if stub.render_hint == "layout" else ""
    )
    steps_instruction = (
        "\nInclude 2-4 'steps' showing the algebra from Expression to stated_answer, and write "
        "narration_text as exactly one sentence per step, in the same order, describing that step."
        if stub.render_hint == "equation_morph" and stub.verify and stub.expression else ""
    )
    prompt = (
        f"Write a script for a '{scene_name}' scene (~{stub.target_duration_s:.0f}s of narration).\n"
        f"Content hint: {stub.content_hint}{expression_line}{answer_instruction}"
        f"{items_instruction}{steps_instruction}\n"
        f"Use the write_scene_script tool."
    )
    msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        tools=[_SCRIPT_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    data = tool_use.input
    return ScriptLLMResponse(
        narration_text=data["narration_text"],
        on_screen_text=data["on_screen_text"],
        stated_answer=data.get("stated_answer"),
        items=data.get("items") or [],
        item_icons=data.get("item_icons") or [],
        steps=[ScriptStep.model_validate(s) for s in (data.get("steps") or [])],
    )


default_script_llm.fingerprint = SCRIPT_AGENT_FINGERPRINT


def run_script_agent(tree: ContentTree, llm_fn: ScriptLLMFn = default_script_llm) -> Script:
    scenes = []
    for stub in tree.scenes:
        resp = llm_fn(stub)
        render_params = dict(resp.render_params)
        if resp.items:
            render_params["items"] = resp.items
            # Only trust item_icons when it lines up 1:1 with items; otherwise
            # the Remotion side falls back to a deterministic icon cycle.
            if resp.item_icons and len(resp.item_icons) == len(resp.items):
                render_params["itemIcons"] = resp.item_icons
        if resp.steps:
            render_params["steps"] = [s.model_dump() for s in resp.steps]
        scenes.append(SceneNarration(
            scene_id=stub.scene_id,
            render_hint=stub.render_hint,
            narration_text=resp.narration_text,
            on_screen_text=resp.on_screen_text,
            target_duration_s=stub.target_duration_s,
            verify=stub.verify,
            expression=stub.expression,
            stated_answer=resp.stated_answer,
            render_params=render_params,
        ))
    tree_hash = content_hash(tree.model_dump(mode="json"))
    fingerprint = getattr(llm_fn, "fingerprint", "script_agent@stub")
    return Script(node_version=fingerprint, tree_hash=tree_hash, scenes=scenes)
