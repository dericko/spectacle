from spectacle_core.versioning import compute_fingerprint


def test_fingerprint_starts_with_node_name():
    fp = compute_fingerprint("script_agent", "claude-haiku-4-5", "TEMPLATE", {"max_tokens": 400})
    assert fp.startswith("script_agent@")


def test_fingerprint_changes_when_prompt_changes():
    a = compute_fingerprint("script_agent", "m", "TEMPLATE A", {})
    b = compute_fingerprint("script_agent", "m", "TEMPLATE B", {})
    assert a != b


def test_fingerprint_changes_when_model_changes():
    a = compute_fingerprint("script_agent", "model-1", "T", {})
    b = compute_fingerprint("script_agent", "model-2", "T", {})
    assert a != b


def test_fingerprint_is_stable_for_same_inputs():
    a = compute_fingerprint("n", "m", "T", {"p": 1})
    b = compute_fingerprint("n", "m", "T", {"p": 1})
    assert a == b
