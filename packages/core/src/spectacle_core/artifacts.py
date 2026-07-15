import json
import os
import shutil
from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def put_json(self, content_hash: str, data: dict) -> None: ...
    def get_json(self, content_hash: str) -> dict: ...
    def exists(self, content_hash: str) -> bool: ...
    def put_file(self, content_hash: str, filename: str, src_path: Path) -> Path: ...
    def file_path(self, content_hash: str, filename: str) -> Path: ...
    def file_exists(self, content_hash: str, filename: str) -> bool: ...


class LocalFileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, content_hash: str, filename: str = "artifact.json") -> Path:
        """Resolve a content_hash/filename pair and confirm it stays inside
        `root` — content_hash/filename are attacker-controlled when reached
        via an HTTP route, so a naive `root / content_hash / filename` join
        would allow path traversal (e.g. content_hash="..")."""
        root_resolved = self.root.resolve()
        path = (self.root / content_hash / filename).resolve()
        if not str(path).startswith(str(root_resolved) + os.sep):
            raise ValueError(f"path traversal rejected: {content_hash!r}/{filename!r}")
        return self.root / content_hash / filename

    def _dir(self, content_hash: str) -> Path:
        d = self._resolve(content_hash, "artifact.json").parent
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put_json(self, content_hash: str, data: dict) -> None:
        path = self._resolve(content_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def get_json(self, content_hash: str) -> dict:
        return json.loads(self._resolve(content_hash).read_text())

    def exists(self, content_hash: str) -> bool:
        return self._resolve(content_hash).exists()

    def put_file(self, content_hash: str, filename: str, src_path: Path) -> Path:
        dest = self._resolve(content_hash, filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_path, dest)
        return dest

    def file_path(self, content_hash: str, filename: str) -> Path:
        return self._resolve(content_hash, filename)

    def file_exists(self, content_hash: str, filename: str) -> bool:
        return self.file_path(content_hash, filename).exists()
