"""Structured contract, reference, timing and rights validation."""
from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from .codec import check_typed
from .models import ProjectManifest, Rights, MediaKind, TrackKind, SCHEMA_VERSION
from .execution import execution_errors
from .semantic_validation import semantic_errors
from .visual_validation import visual_errors
from .retrieval_validation import retrieval_errors
from .selection_validation import selection_errors
from .content import canonical_eligible, revision_signature, SourceType, ContentProvenance


@dataclass(frozen=True)
class ValidationError:
    path: str
    code: str
    message: str


class ManifestValidationError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("; ".join(f"{e.path}: {e.message}" for e in errors))


def validate(manifest: ProjectManifest) -> list[ValidationError]:
    errors = []

    def error(path, code, message):
        errors.append(ValidationError(path, code, message))

    try:
        check_typed(ProjectManifest, manifest)
    except (ValueError, TypeError, AttributeError) as exc:
        return [ValidationError("manifest", "contract", str(exc))]
    if manifest.schema_version != SCHEMA_VERSION:
        error("schema_version", "schema", "Unsupported schema version")
    seen = set()

    def identity(value, path):
        if not value or value.strip() != value or not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
            error(path, "id", "A nonempty stable identifier is required")
        elif value in seen:
            error(path, "duplicate_id", "Duplicate identifier")
        seen.add(value)

    identity(manifest.project_id, "project_id")
    groups = ("inputs", "scenes", "media", "subtitle_tracks", "audio", "timeline", "processing", "snapshots")
    for group in groups:
        for i, item in enumerate(getattr(manifest, group)):
            identity(item.id, f"{group}[{i}].id")
    for track in manifest.subtitle_tracks:
        for segment in track.segments:
            identity(segment.id, f"subtitle_segments.{segment.id}")

    def timestamp(value, path):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError()
            return parsed
        except ValueError:
            error(path, "timestamp", "Timezone-aware ISO timestamp required")
    created = timestamp(manifest.created_at, "created_at")
    updated = timestamp(manifest.updated_at, "updated_at")
    if created and updated and updated < created:
        error("updated_at", "timestamp", "Update precedes creation")
    if not manifest.project_name.strip():
        error("project_name", "required", "Project name required")
    if manifest.content.revision < 0:
        error("content.revision", "revision", "Revision cannot be negative")
    records = {}
    for record in manifest.content.records:
        path = "content.records"
        identity(record.content_id, path + ".content_id")
        records[record.content_id] = record
        original = record.original_text.removeprefix("\ufeff")
        expected = unicodedata.normalize("NFC", original.replace("\r\n", "\n").replace("\r", "\n")).rstrip("\n")
        if (record.normalization_version != "1" or not record.normalized_text.strip()
                or expected != record.normalized_text
                or any((unicodedata.category(c) == "Cc" and c not in "\t\r\n")
                       or unicodedata.category(c) == "Cs" for c in original)):
            error(path, "content_normalization", "Invalid normalized content")
        if record.language is not None and not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", record.language):
            error(path, "content_language", "Invalid normalized language")
        try:
            valid_signature = record.revision_signature == revision_signature(record)
        except (ValueError, UnicodeError):
            valid_signature = False
        if not valid_signature:
            error(path, "content_signature", "Invalid content revision signature")
        if record.source_type == SourceType.REFERENCE_TEXT and record.provenance != ContentProvenance.REFERENCE_ONLY:
            error(path, "content_provenance", "Reference text must remain reference only")
        for diagnostic in record.diagnostics:
            if diagnostic.code not in {"reference_content_not_canonical"}:
                error(path, "content_diagnostic", "Unsupported ingest diagnostic")
    canonical_id = manifest.content.canonical_content_id
    if canonical_id is not None:
        record = records.get(canonical_id)
        if record is None or not canonical_eligible(record):
            error("content.canonical_content_id", "content_reference", "Eligible canonical record required")
        elif (manifest.content.script != record.normalized_text
              or manifest.content.source_language != (record.language or "und")):
            error("content.script", "content_consistency", "Canonical script and language must match record")
    scenes = {s.id: s for s in manifest.scenes}
    media = {m.id: m for m in manifest.media}
    allowed = {Rights.OWNED, Rights.LICENSED, Rights.PUBLIC_DOMAIN}

    def ref(value, targets, path, optional=False):
        if optional and value is None:
            return
        if value not in targets:
            error(path, "reference", "Reference target does not exist")

    def interval(start, end, path, optional=False):
        if optional and start is None and end is None:
            return
        if start is None or end is None or start < 0 or start >= end:
            error(path, "interval", "Require nonnegative start < end")

    def final_ref(value, path):
        ref(value, media, path)
        if value in media and not media[value].final_eligible:
            error(path, "rights", "Final-project media must be explicitly eligible")

    def scene_interval(item, path):
        scene = scenes.get(item.scene_id)
        if scene and scene.start is not None and scene.end is not None:
            if item.start < scene.start or item.end > scene.end:
                error(path, "scene_containment",
                      f"Record {item.id} interval [{item.start}, {item.end}] must be within "
                      f"scene {scene.id} interval [{scene.start}, {scene.end}]")

    orders = set()
    for s in manifest.scenes:
        path = f"scenes.{s.id}"
        if s.order < 0 or s.order in orders:
            error(path, "order", "Scene order must be unique and nonnegative")
        orders.add(s.order)
        if s.revision < 0:
            error(path, "revision", "Revision cannot be negative")
        interval(s.start, s.end, path, True)
        interval(s.script_start, s.script_end, path + ".script_span", True)
        if s.script_end is not None and s.script_end > len(manifest.content.script):
            error(path, "script_span", "Span exceeds source script")
        for mid in s.media_ids:
            final_ref(mid, path + ".media_ids")
    for item in manifest.inputs:
        ref(item.media_id, media, f"inputs.{item.id}.media_id", True)
        linked = media.get(item.media_id)
        if linked and item.rights in allowed and linked.provenance.rights not in allowed:
            error(f"inputs.{item.id}.rights", "rights_authority",
                  f"Input declaration cannot authorize media {linked.id}; provenance rights are authoritative")
    for m in manifest.media:
        path = f"media.{m.id}"
        if m.final_eligible and m.provenance.rights not in allowed:
            error(path, "rights", "REFERENCE_ONLY and UNKNOWN cannot be final eligible")
        if m.kind == MediaKind.VIRTUAL_SHOT:
            ref(m.source_media_id, media, path + ".source_media_id")
            interval(m.start, m.end, path)
            if not m.reference.strip():
                error(path, "required", "Virtual shot source file/reference required")
            source = media.get(m.source_media_id)
            if source and m.reference != source.reference:
                error(path, "source", "Virtual shot must retain its source reference")
            if source and m.final_eligible and (not source.final_eligible or source.provenance.rights not in allowed):
                error(path, "rights", "Virtual shot cannot bypass source rights")
            if (source and source.kind == MediaKind.VIRTUAL_SHOT
                    and all(v is not None for v in (source.start, source.end, m.start, m.end))
                    and (m.start < source.start or m.end > source.end)):
                error(path, "shot_containment",
                      f"Shot {m.id} interval must be contained within parent {source.id} interval")
            visited = {m.id}
            current = source
            while current:
                if current.id in visited:
                    error(path, "cycle", "Cyclic media source reference")
                    break
                visited.add(current.id)
                current = media.get(current.source_media_id)
        elif m.source_media_id is not None or m.start is not None or m.end is not None:
            error(path, "virtual_shot", "Source ranges require virtual-shot kind")
    originals = {s.id: s for t in manifest.subtitle_tracks if t.kind == TrackKind.ORIGINAL for s in t.segments}
    for t in manifest.subtitle_tracks:
        for s in t.segments:
            path = f"subtitle_tracks.{t.id}.{s.id}"
            ref(s.scene_id, scenes, path + ".scene_id")
            interval(s.start, s.end, path)
            scene_interval(s, path)
            if s.confidence is not None and not 0 <= s.confidence <= 1:
                error(path, "confidence", "Confidence must be between zero and one")
            if t.kind == TrackKind.REVIEW:
                ref(s.source_segment_id, originals, path + ".source_segment_id")
                source = originals.get(s.source_segment_id)
                if source and (s.scene_id, s.start, s.end, s.original_text) != (source.scene_id, source.start, source.end, source.original_text):
                    error(path, "alignment", "Review segment must share source scene, timing and original text")
            elif s.source_segment_id is not None:
                error(path, "reference", "Original segment cannot reference another segment")
    if manifest.voice.speed <= 0:
        error("voice.speed", "range", "Voice speed must be positive")
    if manifest.voice.audio_media_id is not None:
        final_ref(manifest.voice.audio_media_id, "voice.audio_media_id")
    for a in manifest.audio:
        final_ref(a.media_id, f"audio.{a.id}.media_id")
        ref(a.scene_id, scenes, f"audio.{a.id}.scene_id", True)
    for t in manifest.timeline:
        final_ref(t.media_id, f"timeline.{t.id}.media_id")
        ref(t.scene_id, scenes, f"timeline.{t.id}.scene_id")
        interval(t.start, t.end, f"timeline.{t.id}")
        scene_interval(t, f"timeline.{t.id}")
    snapshot_map = {s.id: s for s in manifest.snapshots}
    snapshot_ids = set(snapshot_map)
    for s in manifest.snapshots:
        if s.project_id != manifest.project_id or s.schema_version != SCHEMA_VERSION:
            error("snapshots", "snapshot", "Snapshot project/schema mismatch")
        timestamp(s.created_at, "snapshots.created_at")
        if not re.fullmatch(r"[0-9a-f]{64}", s.content_signature) or not s.manifest_reference.strip():
            error("snapshots", "snapshot", "Snapshot requires digest and recovery reference")
        ref(s.parent_snapshot_id, snapshot_ids, "snapshots.parent_snapshot_id", True)
        visited = {s.id}
        parent = snapshot_map.get(s.parent_snapshot_id)
        while parent:
            if parent.id in visited:
                error("snapshots", "cycle", "Cyclic snapshot ancestry")
                break
            visited.add(parent.id)
            parent = snapshot_map.get(parent.parent_snapshot_id)
    for state in manifest.processing:
        if state.execution is not None:
            for message in execution_errors(state.execution):
                error("processing.execution", "execution", message)
            expected = {"ready": "pending", "blocked": "pending", "skipped": "succeeded"}.get(state.execution.status.value, state.execution.status.value)
            if state.status.value != expected:
                error("processing.execution", "execution_consistency", "Processing/execution status mismatch")
            if state.dependency_signature is not None and state.dependency_signature != state.execution.dependency_signature:
                error("processing.execution", "execution_consistency", "Processing/execution signature mismatch")
            if state.execution.stage_id != state.stage:
                error("processing.execution", "execution", "Stage identity mismatch")
        if state.dependency_signature is not None and not re.fullmatch(r"[0-9a-f]{64}", state.dependency_signature):
            error("processing", "signature", "Expected SHA-256 signature")
        for d in state.diagnostics:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", d.code):
                error("processing.diagnostics", "diagnostic", "Use controlled diagnostic codes, never raw payloads")
    for code in semantic_errors(manifest.semantic):
        error("semantic", code, "Semantic persistent contract is invalid.")
    for code in visual_errors(manifest.visual_planning, manifest.semantic):
        error("visual_planning", code, "Visual persistent contract is invalid.")
    for code in retrieval_errors(manifest.retrieval, manifest.visual_planning, manifest.semantic):
        error("retrieval", code, "Retrieval persistent contract is invalid.")
    for code in selection_errors(manifest.selection, manifest.retrieval, manifest.visual_planning):
        error("selection", code, "Selection persistent contract is invalid.")
    return errors


def require_valid(manifest):
    errors = validate(manifest)
    if errors:
        raise ManifestValidationError(errors)
