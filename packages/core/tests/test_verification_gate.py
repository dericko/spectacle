import pytest

from spectacle_core.domain_pack import VerificationOutcome
from spectacle_core.models import SceneGraph, SceneGraphEntry
from spectacle_core.nodes.verification_gate import VerificationBlockedError, run_verification_gate


class _FakeDomainPack:
    @staticmethod
    def verification_gates(scene):
        if not scene.verify:
            return []

        def gate(s):
            return VerificationOutcome(passed=s.stated_answer == "7/8", detail="fake gate")

        return [gate]


def _scene_graph(stated_answer: str) -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="...", on_screen_text="3/4 + 1/8",
                              target_duration_s=45.0, verify=True,
                              expression="3/4 + 1/8", stated_answer=stated_answer),
        ],
    )


def test_all_gates_passing_returns_results_with_no_error():
    results = run_verification_gate(_scene_graph("7/8"), _FakeDomainPack())
    assert len(results) == 1  # only the verify=True scene produces a result
    assert results[0].passed is True
    assert results[0].scene_id == "worked_example_1"


def test_unverified_scene_produces_no_verification_result():
    results = run_verification_gate(_scene_graph("7/8"), _FakeDomainPack())
    assert all(r.scene_id != "intro_1" for r in results)


def test_failing_gate_raises_verification_blocked_error():
    with pytest.raises(VerificationBlockedError) as exc_info:
        run_verification_gate(_scene_graph("1/2"), _FakeDomainPack())
    assert "worked_example_1" in str(exc_info.value)
