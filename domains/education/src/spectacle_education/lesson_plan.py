from typing import Literal
from pydantic import BaseModel, model_validator
from spectacle_core.models import VersionedArtifact


class SceneSpec(BaseModel):
    scene_id: str
    type: str                                   # from the scene-type vocabulary
    render_hint: Literal["layout", "equation_morph"]
    content: str                                # pedagogical brief for the scriptwriter
    verify: bool = False
    expression: str | None = None               # single source of truth (render + gate)
    target_duration_s: float = 30.0
    source: Literal["author", "intake_draft"] = "intake_draft"
    confirmed: bool | None = None               # resolved by the validator below

    @model_validator(mode="after")
    def _default_confirmed(self) -> "SceneSpec":
        # confirmed == (source == "author") or explicitly set true (e.g. human
        # approval at plan-review). Author-supplied math is confirmed by
        # authorship; drafts start unconfirmed.
        if self.confirmed is None:
            self.confirmed = self.source == "author"
        return self


class LessonPlan(VersionedArtifact):
    node_version: str = "intake@0"              # overwritten with the real intake fingerprint
    objectives: list[str]
    audience: str
    grade_level: str | None = None
    total_duration_target_minutes: int | None = None
    constraints: str | None = None
    # Math for the menu-fallback path (thin plan with no explicit scenes): the
    # fallback needs a worked-example expression to build a verifiable scene.
    # Author-supplied, so the fallback marks that scene source="author".
    worked_example_expression_hint: str | None = None
    scenes: list[SceneSpec] = []
