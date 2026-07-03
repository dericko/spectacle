from typing import Literal

from pydantic import BaseModel

from spectacle_core.domain_pack import SceneStub
from spectacle_education.spec import EducationSpec


class SceneTypeDef(BaseModel):
    name: str
    render_hint: Literal["layout", "equation_morph"]
    verify: bool
    duration_s: float
    repeatable: bool


SCENE_MENU: list[SceneTypeDef] = [
    SceneTypeDef(name="intro", render_hint="layout", verify=False,
                 duration_s=20.0, repeatable=False),
    SceneTypeDef(name="concept_explanation", render_hint="layout", verify=False,
                 duration_s=45.0, repeatable=True),
    SceneTypeDef(name="worked_example", render_hint="equation_morph", verify=True,
                 duration_s=45.0, repeatable=False),
    SceneTypeDef(name="guided_practice", render_hint="equation_morph", verify=True,
                 duration_s=40.0, repeatable=True),
    SceneTypeDef(name="recap", render_hint="layout", verify=False,
                 duration_s=20.0, repeatable=False),
]

_TOLERANCE_S = 30.0
_PEDAGOGICAL_ORDER = {
    "intro": 0,
    "concept_explanation": 1,
    "worked_example": 2,
    "guided_practice": 3,
    "recap": 4,
}


def budget_scenes(spec: EducationSpec) -> list[SceneStub]:
    """Deterministic budgeting: pick a sequence and count of scenes from
    SCENE_MENU whose total duration approximates the requested target
    (soft target, +/- _TOLERANCE_S), rather than letting an LLM invent
    open-ended content depth. The three mandatory scenes (intro,
    worked_example, recap) always appear; concept_explanation and
    guided_practice are added alternately to fill remaining budget."""
    menu = {d.name: d for d in SCENE_MENU}
    target_s = spec.target_duration_minutes * 60
    counters: dict[str, int] = {}
    scenes: list[SceneStub] = []

    def add(name: str) -> float:
        defn = menu[name]
        counters[name] = counters.get(name, 0) + 1
        scenes.append(SceneStub(
            scene_id=f"{name}_{counters[name]}",
            render_hint=defn.render_hint,
            content_hint=f"{name} scene for: {spec.learning_objective}",
            target_duration_s=defn.duration_s,
            verify=defn.verify,
        ))
        return defn.duration_s

    used_s = add("intro") + add("worked_example") + add("recap")

    fillers = ["concept_explanation", "guided_practice"]
    filler_idx = 0
    while target_s - used_s > _TOLERANCE_S:
        name = fillers[filler_idx % 2]
        used_s += add(name)
        filler_idx += 1

    scenes.sort(key=lambda s: _PEDAGOGICAL_ORDER[s.scene_id.rsplit("_", 1)[0]])
    return scenes
