"""Canonical UTF-8 SHA-256 signatures; sequence order remains meaningful."""
import hashlib
import json
import unicodedata
from .codec import to_data


def _normalize(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = _normalize(key)
            if key in result:
                raise ValueError("Normalization produced duplicate keys")
            result[key] = _normalize(item)
        return result
    return value


def signature(inputs) -> str:
    payload = json.dumps(_normalize(to_data(inputs)), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dependency_signature(stage: str, revision: str, inputs, dependencies=None) -> str:
    return signature({"stage": stage, "revision": revision, "inputs": inputs,
                      "dependencies": dependencies or {}})
