import json
import os
import subprocess
from pathlib import Path
from typing import Literal

_SCENE_FILE = Path(__file__).with_name("manim_scene.py")


def render_manim(
    expression: str,
    stated_answer: str,
    duration_s: float,
    output_path: Path,
    quality: Literal["preview", "final"],
) -> None:
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
