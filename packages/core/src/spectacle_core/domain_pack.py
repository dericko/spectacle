from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from spectacle_core.hashing import content_hash


class SafetyProfile(BaseModel):
    disallowed_topics: list[str]
    age_rating: str


class SceneStub(BaseModel):
    scene_id: str
    render_hint: Literal["layout", "equation_morph"]
    content_hint: str
    target_duration_s: float
    verify: bool
    expression: str | None = None


class ContentTree(BaseModel):
    spec_hash: str
    scenes: list[SceneStub]
    schema_version: str = "1"

    def compute_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


class VerificationOutcome(BaseModel):
    passed: bool
    detail: str


class VerificationGate(Protocol):
    def __call__(self, scene: "SceneGraphEntry") -> VerificationOutcome: ...


@runtime_checkable
class IntakeResultLike(Protocol):
    """Structural shape of a domain pack's intake() return value.

    Defined here (rather than importing the education domain's concrete
    IntakeResult) so packages/core never imports from domains/ -- any object
    with a matching `.plan` / `.clarifying_questions` shape satisfies this
    duck-typed protocol.
    """

    plan: BaseModel | None
    clarifying_questions: list[str]


class DomainPack(Protocol):
    spec_schema: type[BaseModel]

    def structure(self, spec: BaseModel) -> ContentTree: ...

    def intake(self, raw_input: str, prior_chat: list[dict]) -> IntakeResultLike: ...

    def verification_gates(self, scene: "SceneGraphEntry") -> list[VerificationGate]: ...

    safety_profile: SafetyProfile


# Imported here only for the type hint above; avoids a circular import at
# module load time since models.py does not import domain_pack.py.
from spectacle_core.models import SceneGraphEntry  # noqa: E402
