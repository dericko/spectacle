from unittest.mock import patch

import pytest
from pydantic import BaseModel

from spectacle_core.models import SceneGraph, SceneGraphEntry
from spectacle_core.nodes.interrupts import interrupt_review


class Dummy(BaseModel):
    text: str


def test_auto_mode_never_calls_interrupt_and_returns_artifact_unchanged():
    with patch("spectacle_core.nodes.interrupts.interrupt") as mock_interrupt:
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="auto")
    mock_interrupt.assert_not_called()
    assert result == Dummy(text="hello")


def test_accept_edits_mode_approve_returns_artifact_unchanged():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"action": "approve"}):
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")
    assert result == Dummy(text="hello")


def test_accept_edits_mode_edit_returns_new_validated_artifact():
    edited_payload = {"action": "edit", "artifact": {"text": "goodbye"}}
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value=edited_payload):
        result = interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")
    assert result == Dummy(text="goodbye")


def test_unknown_action_raises():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"action": "nonsense"}):
        with pytest.raises(ValueError, match="unknown interrupt action"):
            interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")


def test_missing_action_key_raises():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"artifact": {"text": "hello"}}):
        with pytest.raises(ValueError, match="missing required 'action' key"):
            interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")


def test_edit_action_missing_artifact_key_raises():
    with patch("spectacle_core.nodes.interrupts.interrupt", return_value={"action": "edit"}):
        with pytest.raises(ValueError, match="missing required 'artifact' key"):
            interrupt_review(Dummy(text="hello"), Dummy, run_mode="accept_edits")


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="three quarters plus one eighth",
                              on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                              verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_editing_one_scenes_renderer_tag_only_changes_that_scenes_hash():
    original = _scene_graph()
    before_hashes = {s.scene_id: s.scene_input_hash() for s in original.scenes}

    edited_payload = original.model_dump(mode="json")
    edited_payload["scenes"][0]["renderer"] = "manim"  # flip intro_1's tag
    decision = {"action": "edit", "artifact": edited_payload}

    with patch("spectacle_core.nodes.interrupts.interrupt", return_value=decision):
        result = interrupt_review(original, SceneGraph, run_mode="accept_edits")

    after_hashes = {s.scene_id: s.scene_input_hash() for s in result.scenes}

    assert after_hashes["intro_1"] != before_hashes["intro_1"]
    assert after_hashes["worked_example_1"] == before_hashes["worked_example_1"]
