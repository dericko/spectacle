import json
from pathlib import Path
from unittest.mock import patch

from spectacle_core.renderers.remotion_render import render_remotion, _REMOTION_PROJECT_DIR


def test_render_remotion_invokes_npx_remotion_render_with_props(tmp_path):
    output_path = tmp_path / "final.mp4"
    with patch("subprocess.run") as mock_run:
        render_remotion("hello", "Hi!", 20.0, output_path)

    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["npx", "remotion", "render"]
    assert "LayoutScene" in cmd
    assert str(output_path) in cmd
    props_index = cmd.index("--props") + 1
    props = json.loads(cmd[props_index])
    assert props["onScreenText"] == "Hi!"
    assert props["durationInSeconds"] == 20.0
    assert mock_run.call_args.kwargs["cwd"] == _REMOTION_PROJECT_DIR
