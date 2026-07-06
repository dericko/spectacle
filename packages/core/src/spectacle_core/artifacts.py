import json
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

    def _dir(self, content_hash: str) -> Path:
        d = self.root / content_hash
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put_json(self, content_hash: str, data: dict) -> None:
        (self._dir(content_hash) / "artifact.json").write_text(json.dumps(data, indent=2))

    def get_json(self, content_hash: str) -> dict:
        return json.loads((self.root / content_hash / "artifact.json").read_text())

    def exists(self, content_hash: str) -> bool:
        return (self.root / content_hash / "artifact.json").exists()

    def put_file(self, content_hash: str, filename: str, src_path: Path) -> Path:
        dest = self._dir(content_hash) / filename
        shutil.copyfile(src_path, dest)
        return dest

    def file_path(self, content_hash: str, filename: str) -> Path:
        return self.root / content_hash / filename

    def file_exists(self, content_hash: str, filename: str) -> bool:
        return self.file_path(content_hash, filename).exists()
