import subprocess
from pathlib import Path
from typing import Protocol


class TTSProvider(Protocol):
    def synthesize(self, text: str, out_path: Path) -> float: ...
    def identity(self) -> str: ...


class MacSayTTSProvider:
    def identity(self) -> str:
        return "macsay:default"

    def synthesize(self, text: str, out_path: Path) -> float:
        aiff_path = out_path.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff_path), text], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), str(out_path)], check=True)
        aiff_path.unlink(missing_ok=True)
        return self._probe_duration_s(out_path)

    @staticmethod
    def _probe_duration_s(path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
