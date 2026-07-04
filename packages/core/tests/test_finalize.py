# packages/core/tests/test_finalize.py
from pathlib import Path
from unittest.mock import patch

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.models import SceneFinal, SceneGraph, SceneGraphEntry
from spectacle_core.nodes.finalize import collect_scenes, mux_final


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="...", on_screen_text="3/4 + 1/8",
                              target_duration_s=45.0, verify=True,
                              expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_collect_scenes_reorders_fan_in_results_to_scene_graph_order():
    scene_graph = _scene_graph()
    # Sends can complete out of order -- simulate worked_example finishing first.
    scene_finals = {
        "worked_example_1": SceneFinal(scene_id="worked_example_1", scene_input_hash="h2",
                                          output_path="/tmp/b.mp4").model_dump(mode="json"),
        "intro_1": SceneFinal(scene_id="intro_1", scene_input_hash="h1",
                                 output_path="/tmp/a.mp4").model_dump(mode="json"),
    }
    ordered = collect_scenes(scene_finals, scene_graph)
    assert [s.scene_id for s in ordered] == ["intro_1", "worked_example_1"]


def test_mux_final_concatenates_in_order_and_writes_manifest(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    ordered = [
        SceneFinal(scene_id="intro_1", scene_input_hash="h1", output_path=str(tmp_path / "a.mp4")),
        SceneFinal(scene_id="worked_example_1", scene_input_hash="h2", output_path=str(tmp_path / "b.mp4")),
    ]
    for s in ordered:
        Path(s.output_path).write_bytes(b"fake clip")

    def fake_concat(inputs, output_path):
        Path(output_path).write_bytes(b"fake final video")

    with patch("spectacle_core.nodes.finalize.ffmpeg_concat", side_effect=fake_concat) as mock_concat:
        manifest = mux_final(ordered, scene_graph_hash="scenegraphhash", store=store)

    concat_inputs = mock_concat.call_args.args[0]
    assert concat_inputs == [s.output_path for s in ordered]
    assert manifest.scene_graph_hash == "scenegraphhash"
    assert Path(manifest.output_path).exists()
