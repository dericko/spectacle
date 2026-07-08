#!/usr/bin/env python3
"""
CLI test harness for the Spectacle pipeline.

Usage:
  # Run all stages end-to-end with stub LLMs (no API cost):
  uv run python scripts/test_pipeline.py --stage all

  # Run individual stages:
  uv run python scripts/test_pipeline.py --stage tts
  uv run python scripts/test_pipeline.py --stage manim
  uv run python scripts/test_pipeline.py --stage remotion
  uv run python scripts/test_pipeline.py --stage mux
  uv run python scripts/test_pipeline.py --stage graph

  # Skip LLM calls (use stubs) - default for 'all' and 'graph':
  uv run python scripts/test_pipeline.py --stage graph --stub

  # Use real LLMs:
  uv run python scripts/test_pipeline.py --stage graph --no-stub
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Make sure packages are importable when run from repo root
ROOT = Path(__file__).resolve().parents[1]
for pkg in [
    ROOT / "packages/core/src",
    ROOT / "domains/education/src",
    ROOT / "apps/server/src",
]:
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

ARTIFACT_DIR = ROOT / "artifacts" / "test_pipeline"

SAMPLE_SPEC = {
    "learning_objective": "Simplify a fraction by finding the GCD",
    "worked_example_expression": "12/18",
    "target_duration_minutes": 2,
    "audience": "middle school students",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def ok(msg):
    print(f"  \033[32m✓\033[0m {msg}")

def fail(msg):
    print(f"  \033[31m✗\033[0m {msg}")
    sys.exit(1)

def section(title):
    print(f"\n\033[1m── {title} ──\033[0m")


# ── stage: TTS ───────────────────────────────────────────────────────────────

def test_tts():
    section("TTS (MacSay → WAV)")
    from spectacle_core.tts import MacSayTTSProvider
    out = Path(tempfile.mkdtemp()) / "narration.wav"
    provider = MacSayTTSProvider()
    duration = provider.synthesize("The fraction twelve eighths simplifies to three halves.", out)
    if not out.exists() or out.stat().st_size < 1000:
        fail(f"WAV not written or too small: {out}")
    ok(f"WAV written ({out.stat().st_size} bytes, {duration:.2f}s) → {out}")


# ── stage: Manim render ───────────────────────────────────────────────────────

def test_manim():
    section("Manim render (equation morph)")
    from spectacle_core.renderers.manim_render import render_manim
    out_dir = Path(tempfile.mkdtemp())
    out = out_dir / "manim_test.mp4"
    print(f"  rendering to {out} ...")
    render_manim("12/18", "2/3", duration_s=4.0, output_path=out, quality="preview")
    if not out.exists() or out.stat().st_size < 1000:
        fail(f"MP4 not written or too small: {out}")
    ok(f"Manim MP4 written ({out.stat().st_size} bytes) → {out}")


# ── stage: Remotion render ────────────────────────────────────────────────────

def test_remotion():
    section("Remotion render (layout scene)")
    from spectacle_core.renderers.remotion_render import render_remotion
    out = Path(tempfile.mkdtemp()) / "remotion_test.mp4"
    print(f"  rendering to {out} ...")
    render_remotion(
        narration_text="The greatest common divisor of 12 and 18 is 6.",
        on_screen_text="GCD(12, 18) = 6",
        duration_s=4.0,
        output_path=out,
    )
    if not out.exists() or out.stat().st_size < 1000:
        fail(f"MP4 not written or too small: {out}")
    ok(f"Remotion MP4 written ({out.stat().st_size} bytes) → {out}")


# ── stage: mux ───────────────────────────────────────────────────────────────

def test_mux():
    section("FFmpeg mux (video + audio → scene_final.mp4)")
    from spectacle_core.nodes.render_scene import mux_audio_video
    from spectacle_core.tts import MacSayTTSProvider

    tmp = Path(tempfile.mkdtemp())

    # Generate a silent audio file via TTS
    audio = tmp / "narration.wav"
    MacSayTTSProvider().synthesize("This is a test.", audio)

    # Generate a video via Remotion (or manim if you prefer)
    from spectacle_core.renderers.remotion_render import render_remotion
    video = tmp / "final.mp4"
    render_remotion("This is a test.", "Test Scene", duration_s=3.0, output_path=video)

    out = tmp / "scene_final.mp4"
    mux_audio_video(video, audio, out)

    if not out.exists() or out.stat().st_size < 1000:
        fail(f"Muxed MP4 not written: {out}")
    ok(f"Muxed MP4 written ({out.stat().st_size} bytes) → {out}")


# ── stage: full graph ─────────────────────────────────────────────────────────

def test_graph(stub: bool):
    section(f"Full LangGraph pipeline ({'stub LLMs' if stub else 'real LLMs'})")

    import uuid
    from langgraph.checkpoint.memory import MemorySaver
    from spectacle_core.artifacts import LocalFileArtifactStore
    from spectacle_core.graph import build_graph
    from spectacle_core.nodes.script_agent import default_script_llm
    from spectacle_core.tts import MacSayTTSProvider
    from spectacle_education import education_pack

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    store = LocalFileArtifactStore(ARTIFACT_DIR)
    checkpointer = MemorySaver()

    if stub:
        from server.stub_llms import stub_content_hint, stub_guided_practice_expression, stub_script_llm
        script_fn = stub_script_llm
        content_hint_fn = stub_content_hint
        guided_practice_fn = stub_guided_practice_expression
    else:
        script_fn = default_script_llm
        content_hint_fn = None
        guided_practice_fn = None

    stages_seen = []

    def record(h, stage, scene_id=None):
        label = f"{stage}:{scene_id}" if scene_id else stage
        stages_seen.append(label)
        print(f"    artifact [{stage}] hash={h[:8]}{'  scene='+scene_id if scene_id else ''}")

    graph = build_graph(
        domain_pack=education_pack,
        store=store,
        tts_provider=MacSayTTSProvider(),
        checkpointer=checkpointer,
        script_llm_fn=script_fn,
        content_hint_fn=content_hint_fn,
        guided_practice_expression_fn=guided_practice_fn,
        metadata_recorder=record,
    )

    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}

    print(f"  run_id={run_id}")
    result = graph.invoke(
        {"spec": SAMPLE_SPEC, "run_mode": "auto"},
        config=config,
    )

    if "__interrupt__" in result:
        fail(f"Graph paused at interrupt — expected auto mode to skip reviews. State: {list(result.keys())}")

    manifest = result.get("final_manifest")
    if not manifest:
        fail(f"No final_manifest in result. Keys: {list(result.keys())}")

    out_path = Path(manifest["output_path"])
    if not out_path.exists():
        fail(f"final.mp4 not written at {out_path}")

    ok(f"Pipeline complete → {out_path}  ({out_path.stat().st_size} bytes)")
    ok(f"Stages recorded: {stages_seen}")


# ── main ──────────────────────────────────────────────────────────────────────

STAGES = {
    "tts": test_tts,
    "manim": test_manim,
    "remotion": test_remotion,
    "mux": test_mux,
}


def main():
    parser = argparse.ArgumentParser(description="Test Spectacle pipeline stages from CLI")
    parser.add_argument(
        "--stage",
        choices=[*STAGES.keys(), "graph", "all"],
        default="all",
        help="Which stage to test (default: all)",
    )
    parser.add_argument(
        "--stub",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use stub LLMs instead of real API calls (default: --stub)",
    )
    args = parser.parse_args()

    if args.stage == "all":
        for name, fn in STAGES.items():
            fn()
        test_graph(stub=args.stub)
    elif args.stage == "graph":
        test_graph(stub=args.stub)
    else:
        STAGES[args.stage]()

    print("\n\033[32mAll tests passed.\033[0m\n")


if __name__ == "__main__":
    main()
