from unittest.mock import patch

import pytest
from pydantic import BaseModel

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
