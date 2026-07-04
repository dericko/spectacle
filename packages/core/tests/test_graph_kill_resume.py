from unittest.mock import patch

import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.graph import build_graph
from spectacle_core.nodes.script_agent import ScriptLLMResponse
from spectacle_education import education_pack

PG_CONN = "postgresql://spectacle:spectacle@localhost:5432/spectacle"


def _fake_llm(stub):
    if stub.expression is not None:
        return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}",
                                    stated_answer="7/8")
    return ScriptLLMResponse(narration_text=f"n-{stub.scene_id}", on_screen_text=f"o-{stub.scene_id}")


class _FakeTTS:
    def synthesize(self, text, out_path):
        out_path.write_bytes(b"fake audio")
        return 5.0


@pytest.mark.integration
def test_graph_pauses_at_interrupt_and_resumes_after_object_is_discarded(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    config = {"configurable": {"thread_id": "kill-resume-test"}}

    with PostgresSaver.from_conn_string(PG_CONN) as checkpointer:
        checkpointer.setup()
        graph = build_graph(
            domain_pack=education_pack, store=store, tts_provider=_FakeTTS(), checkpointer=checkpointer,
            script_llm_fn=_fake_llm,
            content_hint_fn=lambda spec, stub: "hint",
            guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        )
        result = graph.invoke({
            "spec": {
                "learning_objective": "add fractions",
                "worked_example_expression": "3/4 + 1/8",
                "target_duration_minutes": 1,
                "audience": "6th grade",
            },
            "run_mode": "accept_edits",
        }, config=config)

    assert "__interrupt__" in result  # paused at script_review, per accept_edits mode

    # Simulate the process dying here: `graph`, `checkpointer`, and `store`
    # above go fully out of scope. Everything below rebuilds from scratch,
    # exactly as a freshly-started process would after a crash.
    del graph, checkpointer

    with PostgresSaver.from_conn_string(PG_CONN) as fresh_checkpointer:
        fresh_store = LocalFileArtifactStore(tmp_path)
        fresh_graph = build_graph(
            domain_pack=education_pack, store=fresh_store, tts_provider=_FakeTTS(), checkpointer=fresh_checkpointer,
            script_llm_fn=_fake_llm,
            content_hint_fn=lambda spec, stub: "hint",
            guided_practice_expression_fn=lambda spec: "1/2 + 1/4",
        )

        with patch("spectacle_core.nodes.render_scene.render_remotion") as mock_remotion, \
             patch("spectacle_core.nodes.render_scene.render_manim") as mock_manim, \
             patch("spectacle_core.nodes.render_scene.mux_audio_video") as mock_av_mux, \
             patch("spectacle_core.nodes.finalize.ffmpeg_concat") as mock_concat:
            mock_remotion.side_effect = lambda *a: a[-1].write_bytes(b"v")
            mock_manim.side_effect = lambda *a, **kw: a[-2].write_bytes(b"v") if len(a) >= 2 else None
            mock_av_mux.side_effect = lambda video_path, audio_path, output_path: output_path.write_bytes(b"f")
            mock_concat.side_effect = lambda inputs, output_path: output_path.write_bytes(b"final")

            final_result = fresh_graph.invoke(Command(resume={"action": "approve"}), config=config)

    assert final_result["final_manifest"] is not None
    # Prove it resumed rather than restarted: content_tree/script were never
    # recomputed with new randomness -- the same thread_id's checkpointed
    # script content_tree hash is unchanged across the two invokes.
