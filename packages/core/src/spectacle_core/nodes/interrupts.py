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

    action = decision.get("action")
    if action is None:
        raise ValueError(f"missing required 'action' key in interrupt decision: {decision!r}")
    if action == "approve":
        return artifact
    if action == "edit":
        artifact_data = decision.get("artifact")
        if artifact_data is None:
            raise ValueError(f"missing required 'artifact' key in interrupt decision with action='edit': {decision!r}")
        return artifact_cls.model_validate(artifact_data)
    raise ValueError(f"unknown interrupt action: {action!r}")
