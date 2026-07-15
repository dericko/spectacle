from pydantic import BaseModel
from spectacle_core.artifacts import LocalFileArtifactStore
from spectacle_core.node_cache import node_input_key, cached_or_compute


class _Art(BaseModel):
    node_version: str = "n@1"
    value: str
    def compute_hash(self) -> str:
        from spectacle_core.hashing import content_hash
        return content_hash(self.model_dump(mode="json"))


def test_input_key_is_deterministic_and_namespaced():
    a = node_input_key("upstreamhash", "script_agent@abc")
    b = node_input_key("upstreamhash", "script_agent@abc")
    assert a == b and len(a) == 64


def test_miss_runs_compute_and_stores_output(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    key = node_input_key("u", "fp")
    calls = []
    def compute():
        calls.append(1)
        return _Art(value="hello")
    result = cached_or_compute(store, key, compute, _Art)
    assert result.value == "hello"
    assert len(calls) == 1
    assert store.exists(key)  # pointer written


def test_hit_skips_compute(tmp_path):
    store = LocalFileArtifactStore(tmp_path)
    key = node_input_key("u", "fp")
    cached_or_compute(store, key, lambda: _Art(value="hello"), _Art)

    def exploding():
        raise AssertionError("compute must not run on a cache hit")
    result = cached_or_compute(store, key, exploding, _Art)
    assert result.value == "hello"
