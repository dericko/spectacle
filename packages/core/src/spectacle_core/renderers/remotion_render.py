import json
import subprocess
from pathlib import Path

_REMOTION_PROJECT_DIR = Path(__file__).resolve().parents[5] / "apps/renderer-remotion"


def render_remotion(
    narration_text: str,
    on_screen_text: str,
    duration_s: float,
    output_path: Path,
    render_params: dict = {},
) -> None:
    props_dict: dict = {"onScreenText": on_screen_text, "durationInSeconds": duration_s}
    props_dict.update(render_params)
    props = json.dumps(props_dict)
    cmd = [
        "npx", "remotion", "render", "LayoutScene", str(output_path.resolve()),
        "--props", props,
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, cwd=_REMOTION_PROJECT_DIR, check=True)
