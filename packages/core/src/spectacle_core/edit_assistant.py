from typing import Callable

from pydantic import BaseModel, ValidationError

EditLLMFn = Callable[[type[BaseModel], dict, str, list[dict]], dict]


def default_edit_llm(artifact_type: type[BaseModel], current_artifact: dict, chat_message: str, history: list[dict]) -> dict:
    """Real implementation calls an LLM with the current artifact JSON,
    the user's natural-language edit request, and prior chat turns, asking
    it to return a full replacement artifact of the same shape. Kept as an
    injectable seam so the API layer (and tests) can swap it out. This is
    domain-agnostic: it works for any pydantic artifact_type, not just
    education's Script/SceneGraph."""
    raise NotImplementedError("wire up a real LLM client here")


def propose_edit(
    artifact_type: type[BaseModel],
    current_artifact: dict,
    chat_message: str,
    history: list[dict],
    llm_fn: EditLLMFn = default_edit_llm,
) -> dict:
    proposed = llm_fn(artifact_type, current_artifact, chat_message, history)
    try:
        validated = artifact_type.model_validate(proposed)
    except ValidationError as exc:
        raise ValueError(f"edit-assistant produced an invalid {artifact_type.__name__}: {exc}")
    return validated.model_dump(mode="json")
