from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.graph import build_graph
from spectacle_core.nodes.plan_gate import PlanConfirmationError
from spectacle_core.nodes.safety_gate import SafetyBlockedError
from spectacle_core.nodes.script_agent import ScriptLLMResponse
from spectacle_education import education_pack


class _FakeTTS:
    def identity(self) -> str:
        return "fake:default"

    def synthesize(self, text, out_path):
        out_path.write_bytes(b"fake audio")
        return 5.0


def _fake_llm(stub):
    if stub.expression is not None:
        return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}",
                                    stated_answer="7/8")
    return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}")


def _ready_plan_dict(scenes=None):
    """A LessonPlan-shaped dict that already meets intake's readiness
    threshold (objectives + audience present, so no clarifying questions).
    scenes=[] lets structure()'s Task-4 menu fallback build them, mirroring
    what the old flat spec dicts implied before intake/structure split."""
    return {
        "objectives": ["add fractions"],
        "audience": "6th grade",
        "total_duration_target_minutes": 1,
        "worked_example_expression_hint": "3/4 + 1/8",
        "scenes": scenes or [],
    }


def _stub_intake_llm(raw_input, prior_chat):
    return {"plan": _ready_plan_dict(), "questions": []}


_stub_intake_llm.fingerprint = "intake@test"


def test_full_run_in_auto_mode_produces_final_manifest(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    checkpointer = MemorySaver()
    recorded: list[tuple[str, str, str | None]] = []
    graph = build_graph(
        domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
        script_llm_fn=_fake_llm,
        intake_llm_fn=_stub_intake_llm,
        safety_llm_fn=lambda text, topics: [],
        metadata_recorder=lambda h, stage, scene_id=None: recorded.append((h, stage, scene_id)),
    )
    config = {"configurable": {"thread_id": "test-run-1"}}

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim, \
         patch("spectacle_core.nodes.render_scene.mux_audio_video") as mock_av_mux, \
         patch("spectacle_core.nodes.finalize.ffmpeg_concat") as mock_concat:

        def fake_remotion(narration_text, on_screen_text, duration_s, output_path, render_params=None):
            output_path.write_bytes(b"v")
        mock_remotion.side_effect = fake_remotion

        def fake_manim(expression, stated_answer, duration_s, output_path, quality, render_params=None):
            output_path.write_bytes(b"v")
        mock_manim.side_effect = fake_manim

        def fake_mux(video_path, audio_path, output_path):
            output_path.write_bytes(b"f")
        mock_av_mux.side_effect = fake_mux

        def fake_concat(inputs, output_path):
            output_path.write_bytes(b"final")
        mock_concat.side_effect = fake_concat

        result = graph.invoke({
            "raw_input": "add fractions lesson for 6th grade",
            "prior_chat": [],
            "run_mode": "auto",
        }, config=config)

    assert result["final_manifest"] is not None
    assert result["final_manifest"]["scene_graph_hash"]
    stages_recorded = {stage for _, stage, _ in recorded}
    assert {"lesson_plan", "content_tree", "script", "scene_graph", "scene_final", "mux"} <= stages_recorded


def test_script_agent_is_cached_across_runs(tmp_path):
    store = LocalFileArtifactStore(tmp_path)

    call_counts = {"script": 0}

    def counting_llm(stub):
        call_counts["script"] += 1
        return _fake_llm(stub)
    counting_llm.fingerprint = "script_agent@test"

    def fake_safety_llm(text, topics):
        return []

    def run_once(thread_id):
        checkpointer = MemorySaver()
        graph = build_graph(
            domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
            script_llm_fn=counting_llm,
            intake_llm_fn=_stub_intake_llm,
            safety_llm_fn=fake_safety_llm,
        )
        config = {"configurable": {"thread_id": thread_id}}
        with patch("spectacle_core.nodes.render_scene.render_remotion"), \
             patch("spectacle_core.nodes.render_scene.render_manim"), \
             patch("spectacle_core.nodes.render_scene.mux_audio_video"), \
             patch("spectacle_core.nodes.finalize.ffmpeg_concat"):
            graph.invoke({
                "raw_input": "add fractions lesson for 6th grade",
                "prior_chat": [],
                "run_mode": "auto",
            }, config=config)

    run_once("run-1")
    first_run_counts = dict(call_counts)
    assert first_run_counts["script"] > 0

    run_once("run-2")
    # Same content_tree + same fingerprint => script_agent is a cache hit,
    # so the LLM stub must not be called again on the second run.
    assert call_counts == first_run_counts


def test_intake_node_is_cached_across_runs(tmp_path):
    store = LocalFileArtifactStore(tmp_path)

    call_counts = {"intake": 0}

    def counting_intake_llm(raw_input, prior_chat):
        call_counts["intake"] += 1
        return {"plan": _ready_plan_dict(), "questions": []}
    counting_intake_llm.fingerprint = "intake@test-counting"

    def run_once(thread_id):
        checkpointer = MemorySaver()
        graph = build_graph(
            domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
            script_llm_fn=_fake_llm,
            intake_llm_fn=counting_intake_llm,
            safety_llm_fn=lambda text, topics: [],
        )
        config = {"configurable": {"thread_id": thread_id}}
        with patch("spectacle_core.nodes.render_scene.render_remotion"), \
             patch("spectacle_core.nodes.render_scene.render_manim"), \
             patch("spectacle_core.nodes.render_scene.mux_audio_video"), \
             patch("spectacle_core.nodes.finalize.ffmpeg_concat"):
            graph.invoke({
                "raw_input": "add fractions lesson for 6th grade",
                "prior_chat": [],
                "run_mode": "auto",
            }, config=config)

    run_once("run-1")
    assert call_counts["intake"] == 1

    run_once("run-2")
    # Same raw_input + prior_chat + fingerprint => intake_node is a cache
    # hit, so the stub intake LLM must not be called again on the second run.
    assert call_counts["intake"] == 1


def test_unconfirmed_verify_scene_blocks_at_plan_gate(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    checkpointer = MemorySaver()

    def intake_llm_with_unconfirmed_verify_scene(raw_input, prior_chat):
        plan = _ready_plan_dict(scenes=[{
            "scene_id": "worked-1",
            "type": "worked_example",
            "render_hint": "equation_morph",
            "content": "solve 3/4 + 1/8",
            "verify": True,
            "expression": "3/4 + 1/8",
            # source defaults to "intake_draft" => confirmed defaults False,
            # so this scene must block at plan_gate.
        }])
        return {"plan": plan, "questions": []}

    graph = build_graph(
        domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
        script_llm_fn=_fake_llm,
        intake_llm_fn=intake_llm_with_unconfirmed_verify_scene,
        safety_llm_fn=lambda text, topics: [],
    )
    config = {"configurable": {"thread_id": "test-plan-gate-blocked"}}

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim:
        with pytest.raises(PlanConfirmationError):
            graph.invoke({
                "raw_input": "add fractions lesson for 6th grade",
                "prior_chat": [],
                "run_mode": "auto",
            }, config=config)

    mock_remotion.assert_not_called()
    mock_manim.assert_not_called()


def test_run_with_disallowed_topic_in_script_is_blocked_before_render(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    checkpointer = MemorySaver()
    graph = build_graph(
        domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
        script_llm_fn=_fake_llm,
        intake_llm_fn=_stub_intake_llm,
        safety_llm_fn=lambda text, topics: ["violence"],
    )
    config = {"configurable": {"thread_id": "test-run-safety-blocked"}}

    with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
         patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim:
        with pytest.raises(SafetyBlockedError):
            graph.invoke({
                "raw_input": "add fractions lesson for 6th grade",
                "prior_chat": [],
                "run_mode": "auto",
            }, config=config)

    mock_remotion.assert_not_called()
    mock_manim.assert_not_called()
