from unittest.mock import patch

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.models import SceneGraph, SceneGraphEntry
from spectacle_core.nodes.render_scene import compute_item_start_times, fan_out_scenes, render_scene


def _scene_graph() -> SceneGraph:
    return SceneGraph(
        script_hash="deadbeef",
        scenes=[
            SceneGraphEntry(scene_id="intro_1", renderer="remotion",
                              narration_text="hi", on_screen_text="Hi!",
                              target_duration_s=20.0, verify=False),
            SceneGraphEntry(scene_id="worked_example_1", renderer="manim",
                              narration_text="three quarters plus one eighth",
                              on_screen_text="3/4 + 1/8", target_duration_s=45.0,
                              verify=True, expression="3/4 + 1/8", stated_answer="7/8"),
        ],
    )


def test_fan_out_produces_one_payload_per_scene():
    payloads = fan_out_scenes(_scene_graph())
    assert [p["scene"]["scene_id"] for p in payloads] == ["intro_1", "worked_example_1"]


def test_render_scene_skips_all_work_on_cache_hit(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]
    scene_hash = entry.scene_input_hash()
    (store._dir(scene_hash) / "scene_final.mp4").write_bytes(b"cached")

    class ExplodingTTS:
        def synthesize(self, *a, **kw):
            raise AssertionError("TTS should not run on a cache hit")

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim:
        result = render_scene({"scene": entry.model_dump(mode="json")}, store, ExplodingTTS())

    mock_remotion.assert_not_called()
    mock_manim.assert_not_called()
    assert result.scene_id == "intro_1"
    assert result.output_path == str(store.file_path(scene_hash, "scene_final.mp4"))


def test_render_scene_layout_path_calls_tts_then_remotion_then_mux(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 21.5

    def fake_render_remotion(narration_text, on_screen_text, duration_s, output_path, render_params=None):
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_remotion", side_effect=fake_render_remotion), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux) as mock_mux:
        result = render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert mock_mux.called
    assert result.scene_id == "intro_1"
    scene_hash = entry.scene_input_hash()
    assert store.file_exists(scene_hash, "scene_final.mp4")


def test_render_scene_manim_path_writes_preview_before_final(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[1]
    calls = []

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 44.0

    def fake_render_manim(expression, stated_answer, duration_s, output_path, quality, render_params=None):
        calls.append(quality)
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_manim", side_effect=fake_render_manim), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert calls == ["preview", "final"]
    scene_hash = entry.scene_input_hash()
    assert store.file_exists(scene_hash, "preview.mp4")


def test_render_scene_calls_on_artifact_for_preview_and_final(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[1]  # the manim scene, so both stages fire
    recorded: list[tuple[str, str]] = []

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 44.0

    def fake_render_manim(expression, stated_answer, duration_s, output_path, quality, render_params=None):
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_manim", side_effect=fake_render_manim), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene(
            {"scene": entry.model_dump(mode="json")}, store, FakeTTS(),
            on_artifact=lambda h, stage: recorded.append((h, stage)),
        )

    scene_hash = entry.scene_input_hash()
    assert (scene_hash, "scene_preview") in recorded
    assert (scene_hash, "scene_final") in recorded


def test_render_scene_calls_on_artifact_even_on_cache_hit(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = _scene_graph().scenes[0]
    scene_hash = entry.scene_input_hash()
    (store._dir(scene_hash) / "scene_final.mp4").write_bytes(b"cached")
    recorded: list[tuple[str, str]] = []

    class ExplodingTTS:
        def synthesize(self, *a, **kw):
            raise AssertionError("TTS should not run on a cache hit")

    render_scene(
        {"scene": entry.model_dump(mode="json")}, store, ExplodingTTS(),
        on_artifact=lambda h, stage: recorded.append((h, stage)),
    )

    assert (scene_hash, "scene_final") in recorded


def test_compute_item_start_times_uses_sentence_boundaries_when_counts_match():
    text = "First idea here. Second idea is longer than the first one. Third."
    starts = compute_item_start_times(text, item_count=3, duration_s=30.0)
    assert len(starts) == 3
    assert starts[0] == 0.0
    assert starts[0] < starts[1] < starts[2]
    assert all(0.0 <= s <= 30.0 for s in starts)


def test_compute_item_start_times_falls_back_to_word_split_on_mismatch():
    # Only one sentence but three items requested -> even word-count split.
    text = "one two three four five six"
    starts = compute_item_start_times(text, item_count=3, duration_s=9.0)
    assert len(starts) == 3
    assert starts[0] == 0.0
    assert starts == sorted(starts)


def test_compute_item_start_times_empty_for_zero_items():
    assert compute_item_start_times("hello", item_count=0, duration_s=10.0) == []


def test_render_scene_layout_path_computes_item_start_times_for_bullets(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = SceneGraphEntry(
        scene_id="concept_explanation_1", renderer="remotion",
        narration_text="First point explained. Second point explained here.",
        on_screen_text="Key Ideas", target_duration_s=20.0, verify=False,
        render_params={"items": ["First point", "Second point"]},
    )

    captured = {}

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 10.0

    def fake_render_remotion(narration_text, on_screen_text, duration_s, output_path, render_params=None):
        captured["render_params"] = render_params
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_remotion", side_effect=fake_render_remotion), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert captured["render_params"]["sceneType"] == "concept_explanation_1"
    item_starts = captured["render_params"]["itemStartTimesS"]
    assert len(item_starts) == 2
    assert item_starts[0] == 0.0
    assert 0.0 < item_starts[1] < 10.0


def test_render_scene_manim_path_computes_step_start_times_for_steps(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    entry = SceneGraphEntry(
        scene_id="worked_example_1", renderer="manim",
        narration_text="First we find a common denominator. Then we add the numerators.",
        on_screen_text="3/4 + 1/8", target_duration_s=45.0, verify=True,
        expression="3/4 + 1/8", stated_answer="7/8",
        render_params={"steps": [
            {"expr": "3/4 + 1/8", "label": "Start"},
            {"expr": "7/8", "label": "Result"},
        ]},
    )

    captured = []

    class FakeTTS:
        def synthesize(self, text, out_path):
            out_path.write_bytes(b"fake audio")
            return 20.0

    def fake_render_manim(expression, stated_answer, duration_s, output_path, quality, render_params=None):
        captured.append(render_params)
        output_path.write_bytes(b"fake video")

    def fake_mux(video_path, audio_path, output_path):
        output_path.write_bytes(b"fake final")

    with patch("spectacle_core.nodes.render_scene.render_manim", side_effect=fake_render_manim), \
         patch("spectacle_core.nodes.render_scene.mux_audio_video", side_effect=fake_mux):
        render_scene({"scene": entry.model_dump(mode="json")}, store, FakeTTS())

    assert len(captured) == 2  # preview + final, both get the computed timing
    for render_params in captured:
        assert render_params["sceneType"] == "worked_example_1"
        step_starts = render_params["stepStartTimesS"]
        assert len(step_starts) == 2
        assert step_starts[0] == 0.0
        assert 0.0 < step_starts[1] < 20.0
