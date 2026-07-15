import pytest
from pathlib import Path
from spectacle_core.artifacts import LocalFileArtifactStore


def test_put_and_get_json_roundtrip(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    store.put_json("abc123", {"hello": "world"})
    assert store.get_json("abc123") == {"hello": "world"}


def test_exists_false_before_put_true_after(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    assert store.exists("abc123") is False
    store.put_json("abc123", {"x": 1})
    assert store.exists("abc123") is True


def test_put_file_copies_and_file_exists_reports_it(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake video bytes")
    store = LocalFileArtifactStore(tmp_path / "store")
    dest = store.put_file("scenehash1", "scene_final.mp4", src)
    assert dest.exists()
    assert dest.read_bytes() == b"fake video bytes"
    assert store.file_exists("scenehash1", "scene_final.mp4") is True
    assert store.file_exists("scenehash1", "nope.mp4") is False


def test_file_path_returns_expected_location(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    assert store.file_path("h1", "final.mp4") == tmp_path / "h1" / "final.mp4"


def test_file_path_rejects_path_traversal_content_hash(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.file_path("..", "artifact.json")


def test_file_path_rejects_path_traversal_filename(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.file_path("h1", "../../etc/passwd")


def test_exists_rejects_path_traversal_content_hash(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.exists("..")


def test_get_json_rejects_path_traversal_content_hash(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.get_json("..")
