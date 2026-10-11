"""Deterministic offline ingest and explicit copy/validate update boundary."""
from copy import deepcopy
from dataclasses import replace
import re
from ..manifest.codec import check_typed
from ..manifest.content import canonical_eligible, revision_signature
from ..manifest.models import InputKind, ProjectManifest
from ..manifest.validation import require_valid, ManifestValidationError
from .models import (IngestRequest, IngestLimits, IngestResult, IngestStatus,
                     IngestDiagnostic, ContentRecord, ContentProvenance, SourceType)
from .normalization import IngestError, normalize_text, normalize_language
from .readers import read_text


def ingest(request: IngestRequest, limits: IngestLimits = IngestLimits()) -> IngestResult:
    if type(request) is not IngestRequest:
        return IngestResult(IngestStatus.FAILURE, diagnostics=[IngestDiagnostic("invalid_request")])
    try:
        if not isinstance(request.source_type, SourceType):
            raise IngestError("unsupported_source_type")
        try:
            check_typed(IngestRequest, request)
            check_typed(IngestLimits, limits)
        except (ValueError, TypeError):
            raise IngestError("invalid_request") from None
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", request.content_id):
            raise IngestError("invalid_content_id")
        try:
            for value in (request.title, request.source_locator):
                if value is not None:
                    value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise IngestError("invalid_metadata") from None
        language = normalize_language(request.language)
        original = read_text(request, limits)
        if len(original) > limits.max_characters:
            raise IngestError("content_too_large")
        normalized = normalize_text(original)
        if len(normalized) > limits.max_characters:
            raise IngestError("content_too_large")
        if not normalized.strip():
            raise IngestError("content_empty")
        provenance = (ContentProvenance.REFERENCE_ONLY if request.source_type == SourceType.REFERENCE_TEXT
                      else request.provenance)
        record = ContentRecord(request.content_id, request.source_type, original, normalized,
                               "", provenance, language, request.title, request.source_locator)
        diagnostics = []
        if not canonical_eligible(record):
            diagnostics.append(IngestDiagnostic("reference_content_not_canonical"))
        record = replace(record, revision_signature=revision_signature(record), diagnostics=diagnostics)
        return IngestResult(IngestStatus.SUCCESS, record, diagnostics,
                            request.source_type, request.source_locator)
    except IngestError as exc:
        return IngestResult(IngestStatus.FAILURE, diagnostics=[IngestDiagnostic(exc.code)],
                            source_type=request.source_type if isinstance(request.source_type, SourceType) else None)


def apply_ingest(manifest: ProjectManifest, result: IngestResult, *, canonical: bool = True) -> ProjectManifest:
    """Return a validated proposal. Failures and ineligible promotions change nothing."""
    if result.status != IngestStatus.SUCCESS or result.content is None:
        raise IngestError("ingest_failed")
    record = result.content
    if canonical and not canonical_eligible(record):
        raise IngestError("reference_content_not_canonical")
    candidate = deepcopy(manifest)
    old = next((r for r in candidate.content.records if r.content_id == record.content_id), None)
    if not canonical and candidate.content.canonical_content_id == record.content_id:
        raise IngestError("canonical_content_conflict")
    if old is None:
        candidate.content.records.append(deepcopy(record))
    else:
        index = candidate.content.records.index(old)
        candidate.content.records[index] = deepcopy(record)
    if canonical:
        changed = (candidate.content.canonical_content_id != record.content_id or old is None
                   or old.revision_signature != record.revision_signature)
        candidate.content.canonical_content_id = record.content_id
        candidate.content.script = record.normalized_text
        candidate.content.script_type = InputKind.TXT if record.source_type == SourceType.TEXT_FILE else InputKind.TEXT
        candidate.content.source_language = record.language or "und"
        candidate.content.revision += int(changed)
    try:
        require_valid(candidate)
    except ManifestValidationError:
        raise IngestError("manifest_update_invalid") from None
    if canonical and manifest.content.script != candidate.content.script:
        for scene in manifest.scenes:
            start, end = scene.script_start, scene.script_end
            if start is not None and end is not None:
                if manifest.content.script[start:end] != candidate.content.script[start:end]:
                    raise IngestError("scene_script_span_changed", scene_id=scene.id,
                                      span_start=start, span_end=end)
    return candidate
