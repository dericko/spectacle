import re

import sympy
from sympy import SympifyError

from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry

# sympy.sympify evaluates via Python's eval() under the hood, so passing
# LLM-generated strings straight through is a code-execution risk (e.g.
# "__import__('os').system(...)" or attribute-chain sandbox escapes like
# "().__class__.__bases__[0].__subclasses__()"). Scenes only ever need
# numeric arithmetic, so reject anything outside that character set before
# it ever reaches sympify.
_SAFE_EXPRESSION_RE = re.compile(r"^[0-9+\-*/().\s%^]+$")


def _safe_sympify(expr_str: str) -> sympy.Expr:
    if not _SAFE_EXPRESSION_RE.fullmatch(expr_str):
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

    passed = sympy.simplify(expected - stated) == 0
    detail = "matches" if passed else f"expected {expected}, script stated {stated}"
    return VerificationOutcome(passed=passed, detail=detail)


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
