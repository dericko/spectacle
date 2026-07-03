import hashlib
import json


def canonical_json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(obj: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
