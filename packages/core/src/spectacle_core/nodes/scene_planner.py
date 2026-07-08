from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneGraph, SceneGraphEntry, Script
from spectacle_core.renderer_routing import choose_renderer


def run_scene_planner(script: Script) -> SceneGraph:
    entries = [
        SceneGraphEntry(
            scene_id=s.scene_id,
            renderer=choose_renderer(s.render_hint),
            narration_text=s.narration_text,
            on_screen_text=s.on_screen_text,
            target_duration_s=s.target_duration_s,
            verify=s.verify,
            expression=s.expression,
            stated_answer=s.stated_answer,
            render_params=s.render_params,
        )
        for s in script.scenes
    ]
    script_hash = content_hash(script.model_dump(mode="json"))
    return SceneGraph(script_hash=script_hash, scenes=entries)
