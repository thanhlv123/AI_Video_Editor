"""Explicit migration boundary. Legacy formats and future versions are rejected."""
from copy import deepcopy
from .models import SCHEMA_VERSION
from .placement_timing_validation import preflight_document as placement_preflight_document
from .render_timeline_validation import preflight_document as render_preflight_document, preflight_upstream


class UnsupportedSchemaError(ValueError):
    pass


def migrate_document(document: dict) -> dict:
    if type(document) is not dict or type(document.get("schema_version")) is not int:
        raise UnsupportedSchemaError("Manifest requires an integer schema_version")
    if document["schema_version"] != SCHEMA_VERSION:
        raise UnsupportedSchemaError("Unsupported manifest schema version; no migration registered")
    # Future sequential V2 -> V3 transformations belong here, before strict decoding.
    render_preflight_document(document.get("render_timeline"))
    preflight_upstream(document, raw=True)
    placement_preflight_document(document.get("placement_timing"))
    result = deepcopy(document)
    result.setdefault("render_timeline", {"plans": [], "active_render_timeline_plan_id": None})
    result.setdefault("semantic", {"source_revisions": [], "documents": [],
                                   "active_creator_document_id": None})
    result.setdefault("visual_planning", {"plans": [], "active_creator_plan_id": None})
    result.setdefault("retrieval", {"runs": [], "active_creator_retrieval_id": None})
    result.setdefault("selection", {"runs": [], "reviews": [], "active_creator_selection_id": None})
    result.setdefault("acquisition", {"runs": [], "materializations": [], "assets": [],
                                      "active_creator_acquisition_id": None})
    result.setdefault("editing", {"plans": [], "active_creator_edit_plan_id": None})
    result.setdefault("placement_timing", {"plans": [], "active_placement_timing_plan_id": None})
    result.setdefault("voice_timing", {"assets": [], "revisions": [], "runs": [],
        "active_narration_revision_id": None, "active_alignment_run_id": None})
    # M63 additive defaults: preserve all older script and execution data.
    if isinstance(result.get("content"), dict):
        result["content"].setdefault("records", [])
        result["content"].setdefault("canonical_content_id", None)
    # Additive V2 extension: old processing records have no execution metadata.
    for state in result.get("processing", []):
        if isinstance(state, dict):
            state.setdefault("execution", None)
    return result
