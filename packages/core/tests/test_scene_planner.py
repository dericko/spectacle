from spectacle_core.models import SceneNarration, Script
from spectacle_core.nodes.scene_planner import run_scene_planner


def _script() -> Script:
    return Script(
        tree_hash="deadbeef",
        scenes=[
            SceneNarration(scene_id="intro_1", render_hint="layout",
                             narration_text="hi", on_screen_text="Hi!",
                             target_duration_s=20.0, verify=False),
            SceneNarration(scene_id="worked_example_1", render_hint="equation_morph",
                             narration_text="three quarters plus one eighth",
                             on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                             verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_scene_graph_has_one_entry_per_script_scene_in_order():
    graph = run_scene_planner(_script())
    assert [s.scene_id for s in graph.scenes] == ["intro_1", "worked_example_1"]


def test_layout_scene_routed_to_remotion_and_equation_morph_to_manim():
    graph = run_scene_planner(_script())
    intro, worked = graph.scenes
    assert intro.renderer == "remotion"
    assert worked.renderer == "manim"


def test_expression_and_stated_answer_carried_forward():
    graph = run_scene_planner(_script())
    worked = graph.scenes[1]
    assert worked.expression == "3/4 + 1/8"
    assert worked.stated_answer == "7/8"


def test_script_hash_matches_content_hash_of_script():
    from spectacle_core.hashing import content_hash
    script = _script()
    graph = run_scene_planner(script)
    assert graph.script_hash == content_hash(script.model_dump(mode="json"))
