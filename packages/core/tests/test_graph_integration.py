from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import ScriptLLMResponse
from spectacle_education import education_pack


class _FakeTTS:
    def synthesize(self, text, out_path):
        out_path.write_bytes(b"fake audio")
        return 5.0


def _fake_llm(stub):
    if stub.expression is not None:
        return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}",
                                    stated_answer="7/8")
    return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}")


def test_full_run_in_auto_mode_produces_final_manifest(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    checkpointer = MemorySaver()
    recorded: list[tuple[str, str, str | None]] = []
    graph = build_graph(
        domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
        script_llm_fn=_fake_llm,
        content_hint_fn=lambda spec, stub: "hint",
        guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        metadata_recorder=lambda h, stage, scene_id=None: recorded.append((h, stage, scene_id)),
    )
    config = {"configurable": {"thread_id": "test-run-1"}}

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim, \
         patch("spectacle_core.nodes.render_scene.mux_audio_video") as mock_av_mux, \
         patch("spectacle_core.nodes.finalize.ffmpeg_concat") as mock_concat:

        def fake_remotion(narration_text, on_screen_text, duration_s, output_path):
            output_path.write_bytes(b"v")
        mock_remotion.side_effect = fake_remotion

        def fake_manim(expression, stated_answer, duration_s, output_path, quality):
            output_path.write_bytes(b"v")
        mock_manim.side_effect = fake_manim

        def fake_mux(video_path, audio_path, output_path):
            output_path.write_bytes(b"f")
        mock_av_mux.side_effect = fake_mux

        def fake_concat(inputs, output_path):
            output_path.write_bytes(b"final")
        mock_concat.side_effect = fake_concat

        result = graph.invoke({
            "spec": {
                "learning_objective": "add fractions",
                "worked_example_expression": "3/4 + 1/8",
                "target_duration_minutes": 1,
                "audience": "6th grade",
            },
            "run_mode": "auto",
        }, config=config)

    assert result["final_manifest"] is not None
    assert result["final_manifest"]["scene_graph_hash"]
    stages_recorded = {stage for _, stage, _ in recorded}
    assert {"content_tree", "script", "scene_graph", "scene_final", "mux"} <= stages_recorded


def test_structure_and_script_agent_are_cached_across_runs(tmp_path):
    store = LocalFileArtifactStore(tmp_path)

    call_counts = {"content_hint": 0, "guided_practice": 0, "script": 0}

    def counting_content_hint(spec, stub):
        call_counts["content_hint"] += 1
        return "hint"
    counting_content_hint.fingerprint = "structure_content_hint@test"

    def counting_guided_practice(spec):
        call_counts["guided_practice"] += 1
        return "1/2 + 1/4"
    counting_guided_practice.fingerprint = "structure_guided_practice@test"

    def counting_llm(stub):
        call_counts["script"] += 1
        return _fake_llm(stub)
    counting_llm.fingerprint = "script_agent@test"

    spec = {
        "learning_objective": "add fractions",
        "worked_example_expression": "3/4 + 1/8",
        "target_duration_minutes": 1,
        "audience": "6th grade",
    }

    def run_once(thread_id):
        checkpointer = MemorySaver()
        graph = build_graph(
            domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
            script_llm_fn=counting_llm,
            content_hint_fn=counting_content_hint,
            guided_practice_expression_fn=counting_guided_practice,
        )
        config = {"configurable": {"thread_id": thread_id}}
        with patch("spectacle_core.nodes.render_scene.render_remotion"), \
             patch("spectacle_core.nodes.render_scene.render_manim"), \
             patch("spectacle_core.nodes.render_scene.mux_audio_video"), \
             patch("spectacle_core.nodes.finalize.ffmpeg_concat"):
            graph.invoke({"spec": spec, "run_mode": "auto"}, config=config)

    run_once("run-1")
    first_run_counts = dict(call_counts)
    assert first_run_counts["content_hint"] > 0
    assert first_run_counts["script"] > 0

    run_once("run-2")
    # Same spec + same fingerprints ⇒ structure and script_agent are cache hits,
    # so the LLM stubs must not be called again on the second run.
    assert call_counts == first_run_counts
