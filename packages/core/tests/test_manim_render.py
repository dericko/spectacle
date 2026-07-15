import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_render_manim_rejects_unsafe_expression_regardless_of_verify_flag(tmp_path):
    """render_manim has no `verify` parameter at all — this is the point:
    the safety check must run unconditionally, not only when a caller's
    `verify` flag happens to be True (see domains/education/verification.py's
    scene-level verify=false bypass, which skips its own equivalence gate)."""
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="unsafe expression"):
            render_manim(r"\input{/etc/passwd}", "7/8", 45.0, output_path, quality="final")
    mock_run.assert_not_called()


def test_render_manim_rejects_unsafe_stated_answer(tmp_path):
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="unsafe expression"):
            render_manim("3/4 + 1/8", "__import__('os').system('id')", 45.0, output_path, quality="final")
    mock_run.assert_not_called()


def test_render_manim_rejects_unsafe_step_expression(tmp_path):
    output_path = tmp_path / "final.mp4"
    render_params = {"steps": [{"expr": r"\immediate\write18{id}", "label": "Start"}]}
    with patch("subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="unsafe expression"):
            render_manim("3/4 + 1/8", "7/8", 45.0, output_path, quality="final", render_params=render_params)
    mock_run.assert_not_called()
