import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

_SCENE_FILE = Path(__file__).with_name("manim_scene.py")


def _manim_available() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import manim"],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _render_placeholder(expression: str, stated_answer: str, duration_s: float, output_path: Path) -> None:
    """Black-screen MP4 placeholder used when manim is not installed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=30:d={duration_s:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
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
    if not _manim_available():
        _render_placeholder(expression, stated_answer, duration_s, output_path)
        return

    env = os.environ.copy()
    env["SPECTACLE_SCENE_PARAMS"] = json.dumps({
        "expression": expression,
        "stated_answer": stated_answer,
        "duration_s": duration_s,
    })
    quality_flag = "-ql" if quality == "preview" else "-qh"
    cmd = [
        sys.executable, "-m", "manim", "render", quality_flag,
        "--output_file", output_path.name,
        "--media_dir", str(output_path.parent),
        str(_SCENE_FILE), "EquationMorphScene",
    ]
    subprocess.run(cmd, env=env, cwd=output_path.parent, check=True)
