from typing import Literal

from pydantic import BaseModel


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
