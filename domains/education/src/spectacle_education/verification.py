import sympy
from sympy import SympifyError

from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry


def sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome:
    if scene.expression is None or scene.stated_answer is None:
        return VerificationOutcome(
            passed=False,
            detail="missing expression or stated_answer for a verified scene",
        )
    try:
        expected = sympy.simplify(sympy.sympify(scene.expression))
        stated = sympy.simplify(sympy.sympify(scene.stated_answer))
    except (SympifyError, TypeError, ZeroDivisionError) as exc:
        return VerificationOutcome(passed=False, detail=f"could not parse expression: {exc}")

    passed = sympy.simplify(expected - stated) == 0
    detail = "matches" if passed else f"expected {expected}, script stated {stated}"
    return VerificationOutcome(passed=passed, detail=detail)


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
