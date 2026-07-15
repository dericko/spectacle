import sympy
from sympy import SympifyError

from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry
from spectacle_core.safety import delatex, is_safe_math_expression

# The script agent writes render_params["steps"][i]["expr"] as LaTeX so
# Manim's MathTex can render it (e.g. r"\frac{3}{4} + \frac{1}{8}"). Normalize
# that to plain arithmetic before it reaches the safety/sympify checks below,
# which only understand digits and operators.


def _safe_sympify(expr_str: str) -> sympy.Expr:
    expr_str = delatex(expr_str)
    if not is_safe_math_expression(expr_str):
        raise ValueError(f"disallowed characters in expression: {expr_str!r}")
    return sympy.sympify(expr_str)


def sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome:
    if scene.expression is None or scene.stated_answer is None:
        return VerificationOutcome(
            passed=False,
            detail="missing expression or stated_answer for a verified scene",
        )
    try:
        expected = sympy.simplify(_safe_sympify(scene.expression))
        stated = sympy.simplify(_safe_sympify(scene.stated_answer))
    except (SympifyError, TypeError, ZeroDivisionError, ValueError) as exc:
        return VerificationOutcome(passed=False, detail=f"could not parse expression: {exc}")

    if sympy.simplify(expected - stated) != 0:
        return VerificationOutcome(passed=False, detail=f"expected {expected}, script stated {stated}")

    # Manim's MultiStepScene shows LLM-authored intermediate algebra steps
    # (render_params["steps"]); each must be mathematically equivalent to the
    # original expression or a wrong step would air unverified on screen.
    steps = scene.render_params.get("steps") or []
    for i, step in enumerate(steps):
        expr_str = step.get("expr", "") if isinstance(step, dict) else ""
        try:
            step_value = sympy.simplify(_safe_sympify(expr_str))
        except (SympifyError, TypeError, ZeroDivisionError, ValueError) as exc:
            return VerificationOutcome(passed=False, detail=f"step {i} could not parse expression {expr_str!r}: {exc}")
        if sympy.simplify(expected - step_value) != 0:
            return VerificationOutcome(passed=False, detail=f"step {i} ({expr_str!r}) is not equivalent to {expected}")

    return VerificationOutcome(passed=True, detail="matches")


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
