from pathlib import Path
from unittest.mock import patch

from spectacle_core.tts import MacSayTTSProvider


def test_synthesize_calls_say_then_ffmpeg_then_ffprobe_and_returns_duration(tmp_path):
    out_path = tmp_path / "narration.wav"
    provider = MacSayTTSProvider()

    ffprobe_result = type("R", (), {"stdout": "12.5\n"})()
    with patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.unlink") as mock_unlink:
        mock_run.side_effect = [None, None, ffprobe_result]
        duration = provider.synthesize("hello world", out_path)

    assert duration == 12.5
    say_call, ffmpeg_call, ffprobe_call = mock_run.call_args_list
    assert say_call.args[0][0] == "say"
    assert "hello world" in say_call.args[0]
    assert ffmpeg_call.args[0][0] == "ffmpeg"
    assert ffprobe_call.args[0][0] == "ffprobe"
    mock_unlink.assert_called_once()
