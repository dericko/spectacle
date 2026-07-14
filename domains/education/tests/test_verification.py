from spectacle_core.models import SceneGraphEntry
from spectacle_education.verification import sympy_equivalence_gate


def _scene(expression: str, stated_answer: str | None, render_params: dict = {}) -> SceneGraphEntry:
    return SceneGraphEntry(
        scene_id="worked_example_1", renderer="manim",
        narration_text="...", on_screen_text="...",
        target_duration_s=45.0, verify=True,
        expression=expression, stated_answer=stated_answer,
        render_params=render_params,
    )


def test_matching_answer_passes():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", "7/8"))
    assert outcome.passed is True


def test_mismatching_answer_fails():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", "1/2"))
    assert outcome.passed is False
    assert "7/8" in outcome.detail


def test_equivalent_but_differently_formatted_answer_passes():
    outcome = sympy_equivalence_gate(_scene("1/2 + 1/2", "1"))
    assert outcome.passed is True


def test_malformed_expression_fails_without_raising():
    outcome = sympy_equivalence_gate(_scene("3/4 + )( garbage", "7/8"))
    assert outcome.passed is False
    assert "could not parse" in outcome.detail


def test_missing_stated_answer_fails_without_raising():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", None))
    assert outcome.passed is False


def test_zero_division_fails_without_raising():
    """Regression test for ZeroDivisionError in modulo with zero divisor."""
    outcome = sympy_equivalence_gate(_scene("100 % 0", "0"))
    assert outcome.passed is False
    assert "could not parse" in outcome.detail


def test_code_injection_attempt_fails_without_executing():
    """sympy.sympify evaluates via eval() internally; an LLM-generated
    expression is untrusted input and must never reach it unsanitized."""
    outcome = sympy_equivalence_gate(
        _scene("__import__('os').system('touch /tmp/spectacle_pwned')", "7/8")
    )
    assert outcome.passed is False
    assert "could not parse" in outcome.detail
    import os
    assert not os.path.exists("/tmp/spectacle_pwned")


def test_attribute_chain_sandbox_escape_fails_without_executing():
    """Guards against eval-based sandbox escapes that don't need any names
    from a restricted globals dict (e.g. () literal + attribute traversal)."""
    outcome = sympy_equivalence_gate(
        _scene("().__class__.__bases__[0].__subclasses__()", "7/8")
    )
    assert outcome.passed is False
    assert "could not parse" in outcome.detail


def test_steps_all_equivalent_to_expression_pass():
    outcome = sympy_equivalence_gate(_scene(
        "3/4 + 1/8", "7/8",
        render_params={"steps": [
            {"expr": "3/4 + 1/8", "label": "Start"},
            {"expr": "6/8 + 1/8", "label": "Common denominator"},
            {"expr": "7/8", "label": "Result"},
        ]},
    ))
    assert outcome.passed is True


def test_step_not_equivalent_to_expression_fails():
    outcome = sympy_equivalence_gate(_scene(
        "3/4 + 1/8", "7/8",
        render_params={"steps": [
            {"expr": "3/4 + 1/8", "label": "Start"},
            {"expr": "6/8 + 2/8", "label": "Wrong intermediate step"},
            {"expr": "7/8", "label": "Result"},
        ]},
    ))
    assert outcome.passed is False
    assert "step 1" in outcome.detail


def test_step_with_malformed_expression_fails_without_raising():
    outcome = sympy_equivalence_gate(_scene(
        "3/4 + 1/8", "7/8",
        render_params={"steps": [{"expr": "3/4 + )( garbage", "label": "Start"}]},
    ))
    assert outcome.passed is False
    assert "step 0" in outcome.detail
    assert "could not parse" in outcome.detail


def test_step_code_injection_attempt_fails_without_executing():
    outcome = sympy_equivalence_gate(_scene(
        "3/4 + 1/8", "7/8",
        render_params={"steps": [
            {"expr": "__import__('os').system('touch /tmp/spectacle_pwned_step')"},
        ]},
    ))
    assert outcome.passed is False
    import os
    assert not os.path.exists("/tmp/spectacle_pwned_step")


def test_no_steps_present_still_passes_on_final_answer_match():
    outcome = sympy_equivalence_gate(_scene("3/4 + 1/8", "7/8", render_params={}))
    assert outcome.passed is True
