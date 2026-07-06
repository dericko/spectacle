import pytest
from pydantic import BaseModel

from spectacle_core.edit_assistant import propose_edit


class Dummy(BaseModel):
    text: str


def test_propose_edit_validates_llm_output_against_schema():
    def fake_llm(artifact_type, current_artifact, chat_message, history):
        return {"text": "edited by chat"}

    result = propose_edit(Dummy, {"text": "original"}, "make it punchier", [], llm_fn=fake_llm)
    assert result == {"text": "edited by chat"}


def test_propose_edit_raises_on_invalid_llm_output():
    def bad_llm(artifact_type, current_artifact, chat_message, history):
        return {"wrong_field": "oops"}

    with pytest.raises(ValueError, match="edit-assistant produced an invalid"):
        propose_edit(Dummy, {"text": "original"}, "make it punchier", [], llm_fn=bad_llm)
