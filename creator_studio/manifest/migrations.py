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
    result = deepcopy(document)
    result.setdefault("semantic", {"source_revisions": [], "documents": [],
                                   "active_creator_document_id": None})
    result.setdefault("visual_planning", {"plans": [], "active_creator_plan_id": None})
    # M63 additive defaults: preserve all older script and execution data.
    if isinstance(result.get("content"), dict):
        result["content"].setdefault("records", [])
        result["content"].setdefault("canonical_content_id", None)
    # Additive V2 extension: old processing records have no execution metadata.
    for state in result.get("processing", []):
        if isinstance(state, dict):
            state.setdefault("execution", None)
    return result
