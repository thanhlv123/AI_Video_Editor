"""Explicit migration boundary. Legacy formats and future versions are rejected."""
from copy import deepcopy
from .models import SCHEMA_VERSION


class UnsupportedSchemaError(ValueError):
    pass


def migrate_document(document: dict) -> dict:
    if type(document) is not dict or type(document.get("schema_version")) is not int:
        raise UnsupportedSchemaError("Manifest requires an integer schema_version")
    if document["schema_version"] != SCHEMA_VERSION:
        raise UnsupportedSchemaError("Unsupported manifest schema version; no migration registered")
    # Future sequential V2 -> V3 transformations belong here, before strict decoding.
    return deepcopy(document)
