import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

_SCENE_FILE = Path(__file__).with_name("manim_scene.py")


def _render_ffmpeg_placeholder(duration_s: float, output_path: Path) -> None:
    """Fallback when manim is not installed: solid-color MP4 of the right duration."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a2e:size=1920x1080:rate=24",
            "-t", str(duration_s),
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def render_manim(
    expression: str,
    stated_answer: str,
    duration_s: float,
    output_path: Path,
    quality: Literal["preview", "final"],
) -> None:
    if not shutil.which("manim"):
        _render_ffmpeg_placeholder(duration_s, output_path)
        return

    env = os.environ.copy()
    env["SPECTACLE_SCENE_PARAMS"] = json.dumps({
        "expression": expression,
        "stated_answer": stated_answer,
        "duration_s": duration_s,
    })
    quality_flag = "-ql" if quality == "preview" else "-qh"
    cmd = [
        "manim", "render", quality_flag,
        "--output_file", output_path.name,
        str(_SCENE_FILE), "EquationMorphScene",
    ]
    subprocess.run(cmd, env=env, cwd=output_path.parent, check=True)
