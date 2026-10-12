"""Local bounded, tuple-aware validation with no runtime observations."""
from dataclasses import fields, is_dataclass
from enum import Enum
import re
from types import UnionType
from typing import get_args, get_origin, get_type_hints
from .models import *
from ..manifest.render_timeline import (SourceUsage, RenderTimelineOutcome,
                                        RenderTimelineSpec, canonical_chunks)
from ..manifest.placement_timing import PlacementTimingOutcome
from ..manifest.render_preparation import RenderPreparationPlan, assign_identity
from ..manifest.render_preparation_validation import validate_profile, validate_spec

def require(condition):
    if not condition:
        raise RenderJobError()

def _schemas(root):
    result = {}
    def register(cls):
        if isinstance(cls, type) and is_dataclass(cls):
            if cls not in result:
                result[cls] = get_type_hints(cls)
                for child in result[cls].values():
                    register(child)
        else:
            for child in get_args(cls):
                register(child)
    register(root)
    return result

def preflight(value, cls=RenderJobDraft, *, raw=False, upstream=False):
    """Ancestry detects cycles; each occurrence consumes the shared node budget.

    Only trusted schema classes are inspected. Upstream text has its own bounds,
    rather than the short scalar limit of the logical projection.
    """
    schemas = _schemas(cls)
    budget = [MAX_TRAVERSAL_NODES]
    ancestry = set()
    totals = {}
    def walk(item, expected, depth=0, name="", parent=None):
        budget[0] -= 1
        require(budget[0] >= 0 and depth <= MAX_TRAVERSAL_DEPTH)
        options = get_args(expected) if get_origin(expected) is UnionType else (expected,)
        record = next((c for c in options if c in schemas), None)
        sequence = next((c for c in options if get_origin(c) in (list, tuple)), None)
        known = next((c for c in schemas if type(item) is c), None)
        container = (type(item) is dict or type(item) is list or
            type(item) is tuple or known is not None)
        if container:
            require(id(item) not in ancestry)
            ancestry.add(id(item))
        try:
            if known is not None or type(item) is dict:
                actual = known if known is not None else record
                if not upstream:
                    require(actual in schemas)
                hints = schemas.get(actual, {})
                members = item if type(item) is dict else object.__getattribute__(item, "__dict__")
                # Prove the storage and keys safe before hashing, membership or
                # field access. Exact dict iteration does not invoke key hooks.
                require(type(members) is dict)
                require(len(members) <= (MAX_TRAVERSAL_NODES if upstream else len(hints)))
                for key in members:
                    require(type(key) is str)
                    if upstream:
                        require(len(key) <= MAX_CANONICAL_PAYLOAD_BYTES)
                if not upstream:
                    require(set(members) == set(hints))
                pairs = members.items()
                for key, child in pairs:
                    walk(child, hints.get(key), depth + 1, key, actual)
            elif type(item) is tuple or type(item) is list:
                require(upstream or sequence is not None)
                limit = MAX_TRAVERSAL_NODES if upstream else MAX_VISUAL_ENTRIES
                if upstream:
                    # Retained collection caps are capacity checks, independent
                    # of whether their contents have valid Manifest types.
                    owner = getattr(parent, "__name__", "")
                    limit = {
                        ("RenderPreparationState", "plans"): 64,
                        ("RenderTimelineState", "plans"): 64,
                        ("PlacementTimingState", "plans"): 64,
                        ("EditingState", "plans"): 64,
                        ("VoiceTimingState", "runs"): 64,
                        ("VoiceTimingState", "revisions"): 64,
                        ("VoiceTimingState", "assets"): 64,
                        ("AcquisitionState", "runs"): 64,
                        ("AcquisitionState", "materializations"): 16384,
                        ("AcquisitionState", "assets"): 16384,
                        ("RenderPreparationPlan", "entries"): 4096,
                        ("RenderTimelinePlan", "entries"): 4096,
                        ("PlacementTimingPlan", "entries"): 4096,
                        ("EditPlan", "placements"): 4096,
                        ("AcquisitionRun", "shot_acquisitions"): 4096,
                        ("RenderTimelineEntry", "diagnostics"): 16,
                        ("PlacementTimingEntry", "diagnostics"): 16,
                        ("RenderPreparationEntryAssessment", "requirements"): 16,
                        ("RenderPreparationPlan", "requirements"): 32,
                        ("RenderPreparationPlan", "uncovered_intervals"): 4097,
                        ("AlignmentRun", "units"): 100000,
                        ("AlignmentRun", "omissions"): 100000,
                        ("TimedUnit", "source_bindings"): 8,
                        ("PlacementTimingPlan", "allocations"): 65536,
                        ("PlacementTimingPlan", "explicit_boundaries"): 8192,
                        ("PlacementTimingPlan", "placement_ids"): 4096,
                        ("PlacementTimingPlan", "unallocated_unit_ids"): 100000,
                        ("PlacementTimingEntry", "boundaries"): 2,
                    }.get((owner, name), MAX_TRAVERSAL_NODES)
                    total_key = (parent, name)
                    totals[total_key] = totals.get(total_key, 0) + len(item)
                    aggregate = {"entries": 65536, "placements": 65536,
                        "shot_acquisitions": 65536, "units": 500000,
                        "omissions": 500000, "source_bindings": 1000000}
                    require(totals[total_key] <= aggregate.get(name, MAX_TRAVERSAL_NODES))
                else:
                    if name in ("requirements", "diagnostics"):
                        limit = MAX_PLAN_REASONS if parent is RenderJobDraft else MAX_REASONS_PER_ENTRY
                    elif name == "lane_reasons":
                        limit = MAX_PLAN_REASONS
                    elif name == "uncovered_intervals":
                        limit = MAX_VISUAL_ENTRIES + 1
                require(len(item) <= limit)
                child_cls = get_args(sequence)[0] if sequence is not None else None
                for child in item:
                    walk(child, child_cls, depth + 1, name, parent)
            elif type(item) is str:
                require(len(item) <= (MAX_CANONICAL_PAYLOAD_BYTES if upstream else MAX_GENERAL_SCALAR))
                if not upstream:
                    if "signature" in name or name.endswith("sha256"):
                        require(re.fullmatch(r"[0-9a-f]{64}", item) is not None)
                    elif name.endswith("_id"):
                        require(0 < len(item) <= MAX_ID_LENGTH and
                                re.fullmatch(r"[A-Za-z0-9_.:-]+", item) is not None)
            elif upstream and (type(item) is bytes or type(item) is bytearray):
                require(len(item) <= MAX_CANONICAL_PAYLOAD_BYTES)
            elif type(item) is int:
                require(-MAX_INTEGER <= item <= MAX_INTEGER)
                if not upstream:
                    require(item >= 0)
            elif issubclass(type(item), Enum):
                require(any(type(item) is option for option in options) or upstream)
                enum_value = object.__getattribute__(item, "_value_")
                require(type(enum_value) is str and len(enum_value) <= MAX_GENERAL_SCALAR)
            else:
                require(item is None or type(item) is bool or upstream and type(item) is float)
        finally:
            if container:
                ancestry.remove(id(item))
    walk(value, cls)

def preflight_manifest(manifest):
    from ..manifest import ProjectManifest
    require(type(manifest) is ProjectManifest)
    preflight(manifest, ProjectManifest, upstream=True)

def validate_m72_entry(clip):
    """Reconstruct M72 V1 derive_entries from its retained entry evidence."""
    from ..manifest.acquisition import AcquisitionOutcome
    from ..manifest.placement_timing import PlacementTimingOutcome
    from ..manifest.retrieval import VisualMediaKind
    from ..manifest.render_timeline import RenderDiagnostic

    materialized = clip.acquisition_outcome is AcquisitionOutcome.MATERIALIZED
    evidence = (clip.materialization_id, clip.asset_id,
        clip.materialization_evidence_signature, clip.asset_evidence_signature)
    if materialized:
        require(all(value is not None for value in evidence))
        require(clip.media_kind is not None)
        if clip.media_kind is not VisualMediaKind.VIDEO:
            require(clip.source_duration_us is None)
        elif clip.source_duration_us is not None:
            require(0 < clip.source_duration_us <= MAX_INTEGER)
    else:
        require(all(value is None for value in evidence))
        require(clip.media_kind is None and clip.source_duration_us is None)

    timed = clip.timing_outcome is PlacementTimingOutcome.TIMED
    if timed:
        start, end = clip.timeline_start_us, clip.timeline_end_us
        require(type(start) is int and type(end) is int and 0 <= start < end)
        duration = end - start
        if not materialized:
            outcome = RenderTimelineOutcome.NO_MATERIALIZED_MEDIA
        elif clip.media_kind is VisualMediaKind.IMAGE:
            outcome = RenderTimelineOutcome.READY
        elif clip.media_kind is not VisualMediaKind.VIDEO:
            outcome = RenderTimelineOutcome.UNSUPPORTED_MEDIA_TYPE
        elif clip.source_duration_us is None:
            outcome = RenderTimelineOutcome.SOURCE_DURATION_UNRESOLVED
        elif clip.source_duration_us > duration:
            outcome = RenderTimelineOutcome.SOURCE_TRIM_REQUIRED
        elif clip.source_duration_us < duration:
            outcome = RenderTimelineOutcome.MEDIA_TOO_SHORT
        else:
            outcome = RenderTimelineOutcome.READY
    else:
        require(clip.timeline_start_us is None and clip.timeline_end_us is None)
        outcome = RenderTimelineOutcome.UNRESOLVED_TIMING
    require(clip.outcome is outcome)
    usage = (SourceUsage.STILL_IMAGE if outcome is RenderTimelineOutcome.READY and
        clip.media_kind is VisualMediaKind.IMAGE else
        SourceUsage.WHOLE_VIDEO if outcome is RenderTimelineOutcome.READY else
        SourceUsage.UNRESOLVED)
    require(clip.source_usage is usage)
    require(clip.source_start_us == (0 if usage is SourceUsage.WHOLE_VIDEO else None))
    require(clip.source_end_us == (clip.source_duration_us if usage is SourceUsage.WHOLE_VIDEO else None))
    require(clip.diagnostics == (() if outcome is RenderTimelineOutcome.READY else
        (RenderDiagnostic(outcome.value),)))

def _typed(cls, value, raw=False):
    origin, args = get_origin(cls), get_args(cls)
    if origin is UnionType:
        for option in args:
            try:
                return _typed(option, value, raw)
            except RenderJobError:
                pass
        raise RenderJobError()
    if origin is tuple:
        require(type(value) is tuple or raw and type(value) is list)
        return tuple(_typed(args[0], v, raw) for v in value)
    if is_dataclass(cls):
        hints = get_type_hints(cls)
        if raw:
            require(type(value) is dict and set(value) == set(hints))
            return cls(**{k: _typed(t, value[k], True) for k, t in hints.items()})
        require(type(value) is cls)
        for k, t in hints.items():
            _typed(t, getattr(value, k))
        return value
    if isinstance(cls, type) and issubclass(cls, Enum):
        if raw:
            require(type(value) is str)
            try:
                return cls(value)
            except ValueError:
                raise RenderJobError() from None
        require(type(value) is cls)
        return value
    require(type(value) is cls)
    return value

def canonical_payload(value, cls=RenderJobDraft, *, max_bytes=MAX_CANONICAL_PAYLOAD_BYTES):
    require(type(max_bytes) is int and 0 <= max_bytes <= MAX_CANONICAL_PAYLOAD_BYTES)
    preflight(value, cls)
    _typed(cls, value)
    chunks, size = [], 0
    for chunk in canonical_chunks(value):
        size += len(chunk)
        require(size <= max_bytes)
        chunks.append(chunk)
    return "".join(chunks)

def exact_lane_reasons(clips, output_duration_us):
    """No sorting, clipping, repair or source-use expansion."""
    require(type(clips) is tuple and len(clips) <= MAX_VISUAL_ENTRIES)
    require(type(output_duration_us) is int and 0 < output_duration_us <= MAX_INTEGER)
    reasons = []
    def add(reason):
        if reason not in reasons:
            reasons.append(reason)
    if not clips:
        add(LaneReason.EMPTY_VISUAL_LANE)
    previous = None
    for index, clip in enumerate(clips):
        require(type(clip) is RenderVisualClip)
        start, end = clip.timeline_start_us, clip.timeline_end_us
        if start is None or end is None:
            add(LaneReason.UNRESOLVED_INTERVAL)
        elif (type(start) is not int or type(end) is not int or
              not 0 <= start < end <= MAX_INTEGER):
            add(LaneReason.INVALID_INTERVAL)
        else:
            if index == 0 and start != 0:
                add(LaneReason.INEXACT_START)
                add(LaneReason.GAP)
            if previous is not None:
                if start > previous:
                    add(LaneReason.GAP)
                elif start < previous:
                    add(LaneReason.OVERLAP)
            if end > output_duration_us:
                add(LaneReason.EXCESS_COVERAGE)
        previous = end if type(end) is int else None
        supported = clip.outcome is RenderTimelineOutcome.READY and (
            clip.source_usage is SourceUsage.STILL_IMAGE or
            clip.source_usage is SourceUsage.WHOLE_VIDEO and
            type(clip.source_duration_us) is int and clip.source_duration_us > 0 and
            type(clip.source_start_us) is int and clip.source_start_us == 0 and
            type(clip.source_end_us) is int and clip.source_end_us == clip.source_duration_us and
            type(start) is int and type(end) is int and end - start == clip.source_duration_us)
        if not supported:
            add(LaneReason.UNSUPPORTED_SOURCE_USE)
    if clips and (type(clips[-1].timeline_end_us) is not int or
                  clips[-1].timeline_end_us != output_duration_us):
        add(LaneReason.ENDPOINT_MISMATCH)
    return tuple(reasons)

def validate_binding(binding):
    preflight(binding, RenderJobBinding)
    _typed(RenderJobBinding, binding)

def validate_draft(draft, *, raw=False):
    """Validate a bounded detached projection, not its provenance or authority."""
    preflight(draft, RenderJobDraft, raw=raw)
    draft = _typed(RenderJobDraft, draft, raw)
    # M72 V1 accepts exactly its default policy tuple. Re-signed detached
    # bindings cannot authorize a different timeline contract.
    require(draft.timeline_binding.spec == RenderTimelineSpec())
    validate_profile(draft.output_profile)
    validate_spec(draft.spec)
    require(0 < draft.output_duration_us <= MAX_INTEGER)
    require(draft.output_duration_us == draft.narration.binding.narration_duration_us)
    from ..manifest.voice_timing_validation import validate_inspection, identifier
    from ..manifest.voice_timing import receipt_id
    narration = draft.narration.binding
    validate_inspection(narration.inspection)
    require((narration.narration_asset_id, narration.narration_sha256, narration.narration_byte_count,
             narration.narration_duration_us) == (narration.inspection.asset_id,
             narration.inspection.sha256, narration.inspection.byte_count, narration.inspection.duration_us))
    receipt = narration.acceptance_receipt
    identifier(receipt.acceptance_policy_id)
    identifier(receipt.acceptance_policy_version)
    require(receipt.contract_version == "1" and receipt.receipt_id == receipt_id(receipt))
    require((receipt.request_signature, receipt.input_signature, receipt.output_signature) ==
            (narration.alignment_request_signature, narration.alignment_input_signature,
             narration.alignment_output_signature))
    require(len(draft.visual_clips) == len(draft.entry_assessments))
    previous_end = 0
    placement_ids = set()
    for ordinal, clip in enumerate(draft.visual_clips):
        require(clip.ordinal == ordinal and clip.placement_id not in placement_ids)
        placement_ids.add(clip.placement_id)
        validate_m72_entry(clip)
        if clip.timing_outcome is PlacementTimingOutcome.TIMED:
            require(clip.timeline_start_us >= previous_end)
            previous_end = clip.timeline_end_us
    # The bounded M72 projection includes every signed entry field and only the
    # additional binding scalars needed to reconstruct its retained signatures.
    from ..manifest.render_timeline import (RenderTimelineEntry, RenderTimelinePlan,
        assign_identity as timeline_identity)
    timeline_entries = [RenderTimelineEntry(**{
        f.name: list(e.diagnostics) if f.name == "diagnostics" else getattr(e, f.name)
        for f in fields(RenderTimelineEntry)}) for e in draft.visual_clips]
    source, binding = draft.source_binding, draft.timeline_binding
    timeline = timeline_identity(RenderTimelinePlan("", source.acquisition_id,
        source.edit_plan_id, source.edit_output_signature, source.placement_timing_plan_id,
        binding.timing_evidence_signature, binding.media_binding_signature, binding.spec,
        timeline_entries))
    require(all(getattr(timeline, name) == getattr(binding, name) for name in (
        "render_timeline_plan_id", "input_binding_signature", "source_usage_signature", "output_signature")))
    require(source.placement_timing_plan_id == draft.narration.binding.placement_timing_plan_id)
    from ..manifest.render_preparation_validation import (
        frame_aligned, conclusion, derive_uncovered_intervals)
    covered = []
    expected_requirements = []
    if not frame_aligned(draft.output_duration_us, draft.output_profile):
        expected_requirements.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
    entry_requirements = []
    for clip, assessment in zip(draft.visual_clips, draft.entry_assessments):
        for name in ("placement_id", "timeline_start_us", "timeline_end_us", "source_usage",
                     "source_start_us", "source_end_us", "source_duration_us"):
            require(getattr(clip, name) == getattr(assessment, name))
        requirements = []
        start, end = clip.timeline_start_us, clip.timeline_end_us
        if start is None or end is None:
            requirements.append(PreparationRequirement.FRAME_ALIGNMENT_NOT_ESTABLISHED)
        elif not frame_aligned(start, draft.output_profile) or not frame_aligned(end, draft.output_profile):
            requirements.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        supported = clip.outcome is RenderTimelineOutcome.READY and clip.source_usage in (
            SourceUsage.STILL_IMAGE, SourceUsage.WHOLE_VIDEO)
        width, height = assessment.source_width_px, assessment.source_height_px
        if not supported:
            # M73 retains no dimensions for unsupported or unresolved usage.
            require(width is None and height is None)
            requirements.append(PreparationRequirement.SUPPORTED_SOURCE_USE_NOT_ESTABLISHED)
        else:
            # Retained dimensions are evidence, never presentation authority.
            require(width is None or 0 < width <= MAX_INTEGER)
            require(height is None or 0 < height <= MAX_INTEGER)
            covered.append((start, end))
            requirements.append(PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED
                if clip.source_usage is SourceUsage.STILL_IMAGE else
                PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED)
        if width is None or height is None:
            requirements.append(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED)
        elif (width, height) != (draft.output_profile.width_px, draft.output_profile.height_px):
            requirements.append(PreparationRequirement.TRANSFORM_POLICY_REQUIRED)
        require(assessment.requirements == tuple(requirements))
        require(assessment.conclusion is conclusion(requirements))
        entry_requirements.append(requirements)
    uncovered = tuple(derive_uncovered_intervals(covered, draft.output_duration_us))
    require(draft.uncovered_intervals == uncovered)
    if uncovered:
        expected_requirements.append(PreparationRequirement.UNCOVERED_VISUAL_INTERVALS)
    for requirements in entry_requirements:
        for requirement in requirements:
            if requirement not in expected_requirements:
                expected_requirements.append(requirement)
    require(draft.requirements == tuple(expected_requirements))
    require(draft.conclusion is conclusion(expected_requirements))
    # Reconstruct the retained M73 signature contract, never a new M74 digest.
    entries = [RenderPreparationEntryAssessment(**{
        f.name: list(e.requirements) if f.name == "requirements" else getattr(e, f.name)
        for f in fields(RenderPreparationEntryAssessment)}) for e in draft.entry_assessments]
    plan = assign_identity(RenderPreparationPlan("", draft.timeline_binding,
        draft.narration.binding, draft.output_profile, draft.spec, draft.output_duration_us,
        entries, list(draft.uncovered_intervals), list(draft.requirements), draft.conclusion))
    require(all(getattr(plan, f.name) == getattr(draft.binding, f.name)
                for f in fields(RenderJobBinding)))
    require(draft.lane_reasons == exact_lane_reasons(draft.visual_clips, draft.output_duration_us))
    canonical_payload(draft)
    return draft

def validate_spec_job(job, *, raw=False):
    """Check detached logical completeness; grant no current or runtime authority."""
    preflight(job, RenderJobSpec, raw=raw)
    job = _typed(RenderJobSpec, job, raw)
    draft = validate_draft(job.draft)
    require(not draft.requirements and not draft.lane_reasons and
            all(not e.requirements for e in draft.entry_assessments))
    canonical_payload(job, RenderJobSpec)
    return job
