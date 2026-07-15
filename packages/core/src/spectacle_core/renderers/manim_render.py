import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from spectacle_core.safety import is_safe_math_expression_or_latex

_SCENE_FILE = Path(__file__).with_name("manim_scene.py")


def _reject_unsafe_expressions(expression: str, stated_answer: str, render_params: dict) -> None:
    """Enforced unconditionally for every Manim render, regardless of the
    caller's `verify` flag — verify only gates whether the math is checked
    for correctness, not whether the text is safe to compile as LaTeX."""
    candidates = [expression, stated_answer]
    for step in render_params.get("steps") or []:
        if isinstance(step, dict):
            candidates.append(step.get("expr"))
    for candidate in candidates:
        if candidate is not None and not is_safe_math_expression_or_latex(candidate):
            raise ValueError(f"unsafe expression rejected before LaTeX rendering: {candidate!r}")


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
    render_params: dict = {},
) -> None:
    _reject_unsafe_expressions(expression, stated_answer, render_params)

    if not _manim_available():
        _render_placeholder(expression, stated_answer, duration_s, output_path)
        return

    env = os.environ.copy()
    # MacTeX installs to /Library/TeX/texbin which may not be in PATH when
    # launched from a subprocess chain (e.g. LangGraph threads).
    mactex_bin = "/Library/TeX/texbin"
    if mactex_bin not in env.get("PATH", ""):
        env["PATH"] = mactex_bin + ":" + env.get("PATH", "")
    scene_params: dict = {
        "expression": expression,
        "stated_answer": stated_answer,
        "duration_s": duration_s,
    }
    scene_params.update(render_params)
    env["SPECTACLE_SCENE_PARAMS"] = json.dumps(scene_params)

    # Use MultiStepScene when steps are provided, otherwise the simpler morph.
    scene_class = "MultiStepScene" if render_params.get("steps") else "EquationMorphScene"

    # Manim always nests output under {media_dir}/videos/{scene_stem}/{quality}/
    # regardless of --output_file; use a temp media dir then move the result.
    # Use quality-scoped media dirs so preview and final renders never share
    # partial_movie_file_list.txt — concurrent access to that file causes
    # InvalidDataError mid-combine when both renders write to the same dir.
    quality_flag, quality_subdir = (
        ("-ql", "480p15") if quality == "preview" else ("-qh", "1080p60")
    )
    media_dir = output_path.parent / f"_manim_media_{quality}"

    def _run() -> None:
        cmd = [
            sys.executable, "-m", "manim", "render", quality_flag,
            "--output_file", output_path.name,
            "--media_dir", str(media_dir),
            str(_SCENE_FILE), scene_class,
        ]
        subprocess.run(cmd, env=env, cwd=output_path.parent, check=True)

    try:
        _run()
    except subprocess.CalledProcessError:
        # Manim's partial-clip cache can get corrupted (e.g. concurrent renders
        # wrote stale files). Wipe the media dir and retry once from scratch.
        if media_dir.exists():
            shutil.rmtree(media_dir)
        _run()

    rendered = media_dir / "videos" / _SCENE_FILE.stem / quality_subdir / output_path.name
    rendered.rename(output_path)
