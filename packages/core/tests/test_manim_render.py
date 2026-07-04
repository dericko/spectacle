import json
import os
from pathlib import Path
from unittest.mock import patch

from spectacle_core.renderers.manim_render import render_manim


def test_render_manim_preview_uses_low_quality_flag(tmp_path):
    output_path = tmp_path / "preview.mp4"
    with patch("subprocess.run") as mock_run:
        render_manim("3/4 + 1/8", "7/8", 45.0, output_path, quality="preview")

    cmd = mock_run.call_args.args[0]
    env = mock_run.call_args.kwargs["env"]
    assert "-ql" in cmd
    assert "-qh" not in cmd
    params = json.loads(env["SPECTACLE_SCENE_PARAMS"])
    assert params == {"expression": "3/4 + 1/8", "stated_answer": "7/8", "duration_s": 45.0}


def test_render_manim_final_uses_high_quality_flag(tmp_path):
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        render_manim("3/4 + 1/8", "7/8", 45.0, output_path, quality="final")

    cmd = mock_run.call_args.args[0]
    assert "-qh" in cmd
    assert "-ql" not in cmd
