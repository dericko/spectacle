from typing import Callable
from pydantic import BaseModel
from spectacle_core.artifacts import ArtifactStore
from spectacle_core.hashing import content_hash


def node_input_key(upstream_hash: str, fingerprint: str) -> str:
    """Input identity for a node: upstream artifact hash + code/model
    fingerprint. The 'kind' field namespaces these away from real content
    artifacts stored in the same root."""
    return content_hash({"kind": "node_input", "upstream": upstream_hash, "fp": fingerprint})


def cached_or_compute(store: ArtifactStore, input_key: str, compute: Callable[[], BaseModel],
                      model_cls: type[BaseModel]) -> BaseModel:
    if store.exists(input_key):
        output_hash = store.get_json(input_key)["output_hash"]
        return model_cls.model_validate(store.get_json(output_hash))
    artifact = compute()
    output_hash = artifact.compute_hash()
    store.put_json(output_hash, artifact.model_dump(mode="json"))
    store.put_json(input_key, {"output_hash": output_hash})
    return artifact
