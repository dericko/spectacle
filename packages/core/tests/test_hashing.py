from spectacle_core.hashing import canonical_json_bytes, content_hash

def test_canonical_json_is_key_order_independent():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)

def test_canonical_json_has_no_extra_whitespace():
    assert canonical_json_bytes({"a": 1}) == b'{"a":1}'

def test_content_hash_is_deterministic():
    obj = {"x": [1, 2, 3], "y": "hello"}
    assert content_hash(obj) == content_hash(dict(obj))

def test_content_hash_differs_on_different_content():
    assert content_hash({"a": 1}) != content_hash({"a": 2})

def test_content_hash_is_64_char_hex():
    h = content_hash({"a": 1})
    assert len(h) == 64
    int(h, 16)  # raises if not hex
