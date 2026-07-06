import json
import subprocess
from pathlib import Path

_REMOTION_PROJECT_DIR = Path(__file__).resolve().parents[5] / "apps/renderer-remotion"


def render_remotion(narration_text: str, on_screen_text: str, duration_s: float, output_path: Path) -> None:
    props = json.dumps({"onScreenText": on_screen_text, "durationInSeconds": duration_s})
    cmd = [
        "npx", "remotion", "render", "LayoutScene", str(output_path),
        "--props", props,
    ]
    subprocess.run(cmd, cwd=_REMOTION_PROJECT_DIR, check=True)
