"""Stub LLM functions for fast/cheap debugging runs.

Replaces all three LLM call sites with deterministic responses so the full
video pipeline can be exercised without incurring API costs or latency.
stated_answer for verify=True scenes is computed via sympy so the
verification gate still passes.
"""

import sympy

from spectacle_core.domain_pack import SceneStub
from spectacle_core.nodes.script_agent import ScriptLLMResponse


def stub_content_hint(spec, stub: SceneStub) -> str:
    return f"Stub hint for {stub.scene_id.replace('_', ' ')} — {spec.learning_objective}"


def stub_guided_practice_expression(spec) -> str:
    return spec.worked_example_expression


def stub_script_llm(stub: SceneStub) -> ScriptLLMResponse:
    stated_answer = None
    if stub.verify and stub.expression:
        try:
            stated_answer = str(sympy.Rational(sympy.sympify(stub.expression)))
        except Exception:
            stated_answer = stub.expression
    label = stub.scene_id.replace("_", " ").title()
    return ScriptLLMResponse(
        narration_text=(
            f"[Stub] {label}. {stub.content_hint} "
            f"This placeholder narration is generated without an LLM call."
        ),
        on_screen_text=label,
        stated_answer=stated_answer,
    )
