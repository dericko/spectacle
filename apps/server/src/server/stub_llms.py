"""Stub LLM functions for fast/cheap debugging runs.

Replaces all three LLM call sites with vivid, deterministic responses that
exercise real Manim and Remotion rendering:

- Layout scenes (intro, concept_explanation, recap) → Remotion LayoutScene
  with staggered bullet-point items.
- Equation scenes (worked_example, guided_practice) → Manim MultiStepScene
  with computed fraction-solving steps.

stated_answer for verify=True scenes is computed via sympy so the
verification gate passes.
"""

from __future__ import annotations

import sympy

from spectacle_core.domain_pack import SceneStub
from spectacle_core.nodes.script_agent import ScriptLLMResponse


# ── content_hint / guided_practice stubs ──────────────────────────────────────

def stub_content_hint(spec, stub: SceneStub) -> str:
    scene_type = stub.scene_id.rsplit("_", 1)[0]
    return f"{scene_type.replace('_', ' ').title()} scene for: {spec.learning_objective}"


def stub_safety_llm(text: str, disallowed_topics: list[str]) -> list[str]:
    return []


def stub_guided_practice_expression(spec) -> str:
    # Produce a slightly easier analogous expression so the scene is distinct.
    expr = spec.worked_example_expression.strip()
    if "+" in expr:
        # e.g. "3/4 + 1/8" → "1/2 + 1/4"
        return "1/2 + 1/4"
    elif "/" in expr and "+" not in expr:
        # e.g. "12/18" → "8/12"
        return "8/12"
    return expr


# ── step generation ───────────────────────────────────────────────────────────

def _frac_latex(p: int, q: int) -> str:
    if q == 1:
        return str(p)
    return rf"\frac{{{p}}}{{{q}}}"


def _fraction_addition_steps(expression: str) -> list[dict] | None:
    """Compute labeled LaTeX steps for a fraction addition like '3/4 + 1/8'."""
    parts = [p.strip() for p in expression.split("+")]
    if len(parts) != 2:
        return None
    try:
        a = sympy.Rational(sympy.sympify(parts[0]))
        b = sympy.Rational(sympy.sympify(parts[1]))
    except Exception:
        return None

    lcd = int(sympy.lcm(a.q, b.q))
    a_num = a.p * (lcd // a.q)
    b_num = b.p * (lcd // b.q)
    result = a + b

    steps: list[dict] = [
        {"expr": f"{_frac_latex(a.p, a.q)} + {_frac_latex(b.p, b.q)}", "label": "Original problem"},
    ]
    if lcd != a.q or lcd != b.q:
        steps.append({
            "expr": f"{_frac_latex(a_num, lcd)} + {_frac_latex(b_num, lcd)}",
            "label": f"Common denominator: {lcd}",
        })
    steps.append({
        "expr": _frac_latex(int(result.p), int(result.q)),
        "label": "Result",
    })
    return steps


def _fraction_simplification_steps(expression: str) -> list[dict] | None:
    """Compute labeled LaTeX steps for fraction simplification like '12/18'."""
    if "+" in expression or "-" in expression or "/" not in expression:
        return None
    try:
        num_s, den_s = expression.split("/", 1)
        num, den = int(num_s.strip()), int(den_s.strip())
    except Exception:
        return None

    gcd = int(sympy.gcd(num, den))
    result = sympy.Rational(num, den)
    if gcd == 1:
        return [{"expr": _frac_latex(num, den), "label": "Already in simplest form"}]

    return [
        {"expr": _frac_latex(num, den), "label": "Original fraction"},
        {
            "expr": rf"\frac{{{num} \div {gcd}}}{{{den} \div {gcd}}}",
            "label": f"Divide by GCD = {gcd}",
        },
        {"expr": _frac_latex(int(result.p), int(result.q)), "label": "Simplified!"},
    ]


def _make_steps(expression: str | None) -> list[dict] | None:
    if not expression:
        return None
    if "+" in expression:
        return _fraction_addition_steps(expression)
    return _fraction_simplification_steps(expression)


# ── per-scene-type stubs ──────────────────────────────────────────────────────

def _extract_objective(content_hint: str) -> str:
    for sep in (" — ", " for: "):
        if sep in content_hint:
            return content_hint.split(sep, 1)[1].strip()
    return content_hint.strip()


def _stub_intro(stub: SceneStub, objective: str) -> ScriptLLMResponse:
    items = [
        f"Topic: {objective}",
        "Step-by-step worked examples",
        "Guided practice to build confidence",
    ]
    narration = (
        f"Welcome to today's lesson on {objective}. "
        f"In this video we'll break the concept down step by step, "
        f"work through a detailed example together, "
        f"and finish with some guided practice. "
        f"Let's get started."
    )
    return ScriptLLMResponse(
        narration_text=narration,
        on_screen_text=objective,
        render_params={"items": items, "sceneType": "intro"},
    )


def _stub_concept_explanation(stub: SceneStub, objective: str) -> ScriptLLMResponse:
    obj_lower = objective.lower()

    if "add" in obj_lower and "fraction" in obj_lower:
        concept = "Finding a Common Denominator"
        items = [
            "Fractions need the same denominator to be added",
            "Find the Least Common Multiple (LCM) of the denominators",
            "Multiply each fraction so both share the LCD",
            "Then add the numerators and keep the denominator",
        ]
        narration = (
            "Before we can add fractions with different denominators, "
            "we need to convert them so they share the same denominator. "
            "This shared value is called the Least Common Denominator, or LCD. "
            "To find it, look for the smallest number that both denominators divide into evenly. "
            "Once you've converted the fractions, simply add the numerators "
            "and write the result over the common denominator."
        )
    elif "gcd" in obj_lower or "simplif" in obj_lower or "greatest" in obj_lower:
        concept = "The Greatest Common Divisor"
        items = [
            "The GCD is the largest factor shared by two numbers",
            "Dividing numerator and denominator by the GCD simplifies a fraction",
            "The result is always in its simplest form",
            "Example: GCD(12, 18) = 6, so 12/18 simplifies to 2/3",
        ]
        narration = (
            "To simplify a fraction, we divide the numerator and denominator "
            "by their Greatest Common Divisor, or GCD. "
            "The GCD is the largest number that divides evenly into both values. "
            "For example, the GCD of 12 and 18 is 6, "
            "because 6 is the largest number that divides both without a remainder. "
            "Dividing top and bottom by 6 gives us 2 over 3, which is fully simplified."
        )
    else:
        concept = f"Key Concepts"
        items = [
            f"Understand the core idea: {objective}",
            "Identify the key steps in the process",
            "Watch for common mistakes",
            "Apply the method systematically",
        ]
        narration = (
            f"Let's explore the key concepts behind {objective}. "
            f"Understanding the underlying ideas will help you apply "
            f"the method correctly and catch mistakes before they happen. "
            f"Pay close attention to each step as we walk through the process."
        )

    return ScriptLLMResponse(
        narration_text=narration,
        on_screen_text=concept,
        render_params={"items": items, "sceneType": "concept_explanation"},
    )


def _stub_equation_scene(stub: SceneStub, objective: str) -> ScriptLLMResponse:
    scene_type = stub.scene_id.rsplit("_", 1)[0]
    expr = stub.expression or ""

    # Compute the verified answer via sympy
    stated_answer: str | None = None
    if stub.verify and expr:
        try:
            stated_answer = str(sympy.Rational(sympy.sympify(expr)))
        except Exception:
            stated_answer = expr

    steps = _make_steps(expr)

    if scene_type == "worked_example":
        narration = (
            f"Let's work through {expr} together step by step. "
        )
        if "+" in expr:
            parts = [p.strip() for p in expr.split("+")]
            a = sympy.Rational(sympy.sympify(parts[0]))
            b = sympy.Rational(sympy.sympify(parts[1]))
            lcd = int(sympy.lcm(a.q, b.q))
            result = a + b
            narration += (
                f"First, I identify the denominators: {a.q} and {b.q}. "
                f"The least common denominator is {lcd}. "
                f"I convert each fraction to have denominator {lcd}, "
                f"then add the numerators to get {result.p} over {result.q}. "
                f"That's our answer: {stated_answer}."
            )
        elif "/" in expr:
            num_s, den_s = expr.split("/", 1)
            num, den = int(num_s.strip()), int(den_s.strip())
            gcd = int(sympy.gcd(num, den))
            result = sympy.Rational(num, den)
            narration += (
                f"The GCD of {num} and {den} is {gcd}. "
                f"Dividing both top and bottom by {gcd} gives us "
                f"{result.p} over {result.q}. "
                f"That's the simplified answer: {stated_answer}."
            )
        else:
            narration += f"The answer is {stated_answer}."
    else:  # guided_practice
        narration = (
            f"Now it's your turn to try one. Work through {expr}. "
            f"Pause the video if you'd like to try it yourself first. "
        )
        if "+" in expr:
            narration += (
                f"Start by finding the least common denominator, "
                f"then convert each fraction and add the numerators. "
                f"The answer is {stated_answer}."
            )
        else:
            narration += (
                f"Find the GCD and divide to simplify. "
                f"The answer is {stated_answer}."
            )

    rp: dict = {"steps": steps} if steps else {}
    rp["sceneType"] = scene_type
    return ScriptLLMResponse(
        narration_text=narration,
        on_screen_text=expr,
        stated_answer=stated_answer,
        render_params=rp,
    )


def _stub_recap(stub: SceneStub, objective: str) -> ScriptLLMResponse:
    obj_lower = objective.lower()

    if "add" in obj_lower and "fraction" in obj_lower:
        items = [
            "Find the LCD of the denominators",
            "Convert each fraction to the LCD",
            "Add the numerators, keep the denominator",
            "Simplify the result if possible",
        ]
        narration = (
            "Great work today. Let's recap what we covered. "
            "To add fractions with unlike denominators, "
            "find the least common denominator, "
            "convert both fractions, "
            "then add the numerators. "
            "Don't forget to simplify your answer if you can. "
            "Keep practicing and these steps will become second nature."
        )
    elif "gcd" in obj_lower or "simplif" in obj_lower:
        items = [
            "Find the GCD of numerator and denominator",
            "Divide both by the GCD",
            "The result is in simplest form",
            "GCD = 1 means already simplified",
        ]
        narration = (
            "Let's recap. To simplify a fraction, "
            "find the greatest common divisor of the numerator and denominator, "
            "then divide both by that number. "
            "If the GCD is already 1, the fraction is fully simplified. "
            "With practice, you'll be able to spot the GCD quickly."
        )
    else:
        items = [
            "Identify the key pattern",
            "Apply the method step by step",
            "Check your answer",
            "Practice regularly to build fluency",
        ]
        narration = (
            f"That wraps up today's lesson on {objective}. "
            f"Remember the key steps, work through problems methodically, "
            f"and check your answers. Keep practicing!"
        )

    return ScriptLLMResponse(
        narration_text=narration,
        on_screen_text="Key Takeaways",
        render_params={"items": items, "sceneType": "recap"},
    )


def _stub_fallback(stub: SceneStub, objective: str) -> ScriptLLMResponse:
    label = stub.scene_id.replace("_", " ").title()
    stated_answer = None
    if stub.verify and stub.expression:
        try:
            stated_answer = str(sympy.Rational(sympy.sympify(stub.expression)))
        except Exception:
            stated_answer = stub.expression
    return ScriptLLMResponse(
        narration_text=f"{label}. {objective}.",
        on_screen_text=label,
        stated_answer=stated_answer,
    )


# ── main dispatch ─────────────────────────────────────────────────────────────

_HANDLERS = {
    "intro": _stub_intro,
    "concept_explanation": _stub_concept_explanation,
    "worked_example": _stub_equation_scene,
    "guided_practice": _stub_equation_scene,
    "recap": _stub_recap,
}


def stub_script_llm(stub: SceneStub) -> ScriptLLMResponse:
    scene_type = stub.scene_id.rsplit("_", 1)[0]
    objective = _extract_objective(stub.content_hint)
    handler = _HANDLERS.get(scene_type, _stub_fallback)
    return handler(stub, objective)
