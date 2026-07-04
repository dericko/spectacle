from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel


def interrupt_review(
    artifact: BaseModel,
    artifact_cls: type[BaseModel],
    run_mode: Literal["accept_edits", "auto"],
) -> BaseModel:
    """Pause for human review unless run_mode == 'auto'. Returns the
    (possibly edited) artifact to continue the graph with."""
    if run_mode == "auto":
        return artifact

    decision = interrupt({"artifact": artifact.model_dump(mode="json")})

    if decision["action"] == "approve":
        return artifact
    if decision["action"] == "edit":
        return artifact_cls.model_validate(decision["artifact"])
    raise ValueError(f"unknown interrupt action: {decision['action']!r}")
