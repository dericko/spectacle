from typing import Callable

import anthropic
from pydantic import BaseModel

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneNarration, Script


class ScriptStep(BaseModel):
    expr: str
    label: str = ""


class ScriptLLMResponse(BaseModel):
    narration_text: str
    on_screen_text: str
    stated_answer: str | None = None
    items: list[str] = []
    steps: list[ScriptStep] = []
    render_params: dict = {}


ScriptLLMFn = Callable[[SceneStub], ScriptLLMResponse]

_client: anthropic.Anthropic | None = None

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
        "narration_text as exactly one sentence per item, in the same order, describing that item."
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
        steps=[ScriptStep.model_validate(s) for s in (data.get("steps") or [])],
    )


def run_script_agent(tree: ContentTree, llm_fn: ScriptLLMFn = default_script_llm) -> Script:
    scenes = []
    for stub in tree.scenes:
        resp = llm_fn(stub)
        render_params = dict(resp.render_params)
        if resp.items:
            render_params["items"] = resp.items
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
    return Script(tree_hash=tree_hash, scenes=scenes)
