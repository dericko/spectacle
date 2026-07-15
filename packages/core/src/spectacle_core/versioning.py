from spectacle_core.hashing import content_hash


def compute_fingerprint(node_name: str, model_id: str, prompt_template: str, params: dict) -> str:
    """A deterministic identity for a node's *code + model config*, distinct
    from its input data. Folded into artifact node_version and the node cache
    key so that changing a prompt/model/params auto-invalidates the cache
    without a human bumping a version string."""
    digest = content_hash({"model": model_id, "template": prompt_template, "params": params})
    return f"{node_name}@{digest[:12]}"
