from typing import Callable

import anthropic

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_education.scene_menu import budget_scenes
from spectacle_education.spec import EducationSpec

ContentHintFn = Callable[[EducationSpec, SceneStub], str]
GuidedPracticeExpressionFn = Callable[[EducationSpec], str]

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def default_content_hint_llm(spec: EducationSpec, stub: SceneStub) -> str:
    scene_name = stub.scene_id.rsplit("_", 1)[0].replace("_", " ")
    msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": (
                f"Write a single concise sentence describing the pedagogical angle for a "
                f"'{scene_name}' scene in a lesson about: {spec.learning_objective}. "
                f"Audience: {spec.audience}. Return only the sentence."
            ),
        }],
    )
    return msg.content[0].text.strip()


def default_guided_practice_expression_llm(spec: EducationSpec) -> str:
    msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=40,
        messages=[{
            "role": "user",
            "content": (
                f"The worked example is: {spec.worked_example_expression}. "
                f"Give one analogous, slightly easier expression that exercises the same skill. "
                f"Return only the expression (e.g. '1/2 + 1/4'), nothing else."
            ),
        }],
    )
    return msg.content[0].text.strip()


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
