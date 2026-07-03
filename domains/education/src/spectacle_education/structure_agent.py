from typing import Callable

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_education.scene_menu import budget_scenes
from spectacle_education.spec import EducationSpec

ContentHintFn = Callable[[EducationSpec, SceneStub], str]
GuidedPracticeExpressionFn = Callable[[EducationSpec], str]


def default_content_hint_llm(spec: EducationSpec, stub: SceneStub) -> str:
    """Real implementation calls an LLM to write a one-line pedagogical
    angle for this scene, given the lesson's learning objective. Kept as
    an injectable seam so callers (and tests) can swap it out."""
    raise NotImplementedError("wire up a real LLM client here")


def default_guided_practice_expression_llm(spec: EducationSpec) -> str:
    """Real implementation calls an LLM to pick an analogous, easier
    expression exercising the same skill as spec.worked_example_expression."""
    raise NotImplementedError("wire up a real LLM client here")


def structure(
    spec: EducationSpec,
    guided_practice_expression_fn: GuidedPracticeExpressionFn = default_guided_practice_expression_llm,
    content_hint_fn: ContentHintFn = default_content_hint_llm,
) -> ContentTree:
    spec_hash = content_hash(spec.model_dump(mode="json"))
    stubs = budget_scenes(spec)

    guided_practice_expression: str | None = None
    enriched: list[SceneStub] = []
    for stub in stubs:
        name = stub.scene_id.rsplit("_", 1)[0]
        expression = None
        if name == "worked_example":
            expression = spec.worked_example_expression
        elif name == "guided_practice":
            if guided_practice_expression is None:
                guided_practice_expression = guided_practice_expression_fn(spec)
            expression = guided_practice_expression
        enriched.append(stub.model_copy(update={
            "content_hint": content_hint_fn(spec, stub),
            "expression": expression,
        }))

    return ContentTree(spec_hash=spec_hash, scenes=enriched)
