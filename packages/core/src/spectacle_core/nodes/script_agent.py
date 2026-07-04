from typing import Callable

from pydantic import BaseModel

from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneNarration, Script


class ScriptLLMResponse(BaseModel):
    narration_text: str
    on_screen_text: str
    stated_answer: str | None = None


ScriptLLMFn = Callable[[SceneStub], ScriptLLMResponse]


def default_script_llm(stub: SceneStub) -> ScriptLLMResponse:
    """Real implementation calls an LLM to write narration/on-screen text
    for this scene, and (for verified scenes) the script's claimed final
    answer -- the claim sympy independently checks downstream."""
    raise NotImplementedError("wire up a real LLM client here")


def run_script_agent(tree: ContentTree, llm_fn: ScriptLLMFn = default_script_llm) -> Script:
    scenes = []
    for stub in tree.scenes:
        resp = llm_fn(stub)
        scenes.append(SceneNarration(
            scene_id=stub.scene_id,
            render_hint=stub.render_hint,
            narration_text=resp.narration_text,
            on_screen_text=resp.on_screen_text,
            target_duration_s=stub.target_duration_s,
            verify=stub.verify,
            expression=stub.expression,
            stated_answer=resp.stated_answer,
        ))
    tree_hash = content_hash(tree.model_dump(mode="json"))
    return Script(tree_hash=tree_hash, scenes=scenes)
