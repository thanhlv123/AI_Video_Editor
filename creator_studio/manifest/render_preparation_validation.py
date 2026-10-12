"""Pure bounded M73 validation and deterministic historical reconstruction."""
from dataclasses import fields, is_dataclass
from enum import Enum
from math import gcd
from .codec import check_typed
from .render_preparation import *
from .render_timeline import RenderTimelineOutcome

RECORDS = (OutputProfile, RenderPreparationSpec, RenderTimelineBinding, NarrationBinding,
    RenderPreparationEntryAssessment, UncoveredInterval, RenderPreparationPlan,
    RenderPreparationState, RenderTimelineSpec, AudioInspectionEvidence, AcceptanceReceipt)
MEMBERS = {cls: {f.name for f in fields(cls)} for cls in RECORDS}
CHILDREN = {"plans": RenderPreparationPlan, "entries": RenderPreparationEntryAssessment,
    "uncovered_intervals": UncoveredInterval, "output_profile": OutputProfile,
    "timeline_binding": RenderTimelineBinding, "narration_binding": NarrationBinding,
    "inspection": AudioInspectionEvidence, "acceptance_receipt": AcceptanceReceipt}
LIMITS = {"plans": MAX_PLANS, "entries": MAX_ENTRIES_PER_PLAN,
    "requirements": MAX_REQUIREMENTS_PER_ENTRY, "uncovered_intervals": MAX_UNCOVERED_INTERVALS}

def require(condition):
    if not condition:
        raise ValueError("render_preparation_invalid")

def _walk(value, depth, budget, cls=None, raw=False, name=""):
    budget[0] -= 1
    require(budget[0] >= 0 and depth <= MAX_TRAVERSAL_DEPTH)
    if raw and cls in MEMBERS and type(value) is dict:
        # Count known-record members before touching an unknown member's value.
        require(len(value) <= len(MEMBERS[cls]))
    if is_dataclass(value) or type(value) is dict:
        actual = type(value) if is_dataclass(value) else cls
        if actual is RenderPreparationState:
            plans = value.get("plans") if type(value) is dict else value.plans
            if type(plans) in (list, tuple):
                require(len(plans) <= MAX_PLANS)
                total = 0
                for plan in plans:
                    entries = plan.get("entries") if type(plan) is dict else getattr(plan, "entries", None)
                    if type(entries) in (list, tuple):
                        require(len(entries) <= MAX_ENTRIES_PER_PLAN)
                        total += len(entries)
                        require(total <= MAX_TOTAL_ENTRY_ASSESSMENTS)
        if is_dataclass(value):
            items = ((f.name, getattr(value, f.name)) for f in fields(value))
        else:
            require(len(value) <= MAX_TOTAL_ENTRY_ASSESSMENTS)
            items = value.items()
        for key, item in items:
            require(type(key) is str and len(key) <= MAX_GENERAL_SCALAR)
            child = CHILDREN.get(key)
            if key == "spec":
                child = RenderTimelineSpec if actual is RenderTimelineBinding else RenderPreparationSpec
            if type(item) in (list, tuple):
                limit = LIMITS.get(key, MAX_TOTAL_ENTRY_ASSESSMENTS)
                if key == "requirements" and actual is RenderPreparationPlan:
                    limit = MAX_PLAN_REQUIREMENTS
                require(len(item) <= limit)
            _walk(item, depth + 1, budget, child, raw, key)
    elif type(value) in (list, tuple):
        require(len(value) <= MAX_TOTAL_ENTRY_ASSESSMENTS)
        for item in value:
            _walk(item, depth + 1, budget, cls, raw, name)
    elif isinstance(value, Enum):
        require(type(value.value) is str and len(value.value) <= MAX_GENERAL_SCALAR)
    elif type(value) is str:
        require(len(value) <= MAX_GENERAL_SCALAR)
        if "signature" in name or name in ("narration_sha256", "sha256"):
            require(len(value) in (0, SIGNATURE_LENGTH) and all(c in "0123456789abcdef" for c in value))
        elif name.endswith("_id"):
            require(len(value) <= MAX_ID_LENGTH)
    elif type(value) is int:
        require(value.bit_length() <= 63)
    else:
        require(value is None or type(value) is bool)

def bounded_value(value):
    _walk(value, 0, [MAX_TRAVERSAL_NODES])

def preflight_record(record, cls, *, raw=False):
    _walk(record, 0, [MAX_TRAVERSAL_NODES], cls, raw)
    if cls is RenderPreparationState:
        plans = record.get("plans") if raw and type(record) is dict else getattr(record, "plans", None)
        if type(plans) in (list, tuple):
            total = 0
            for plan in plans:
                entries = plan.get("entries") if raw and type(plan) is dict else getattr(plan, "entries", None)
                if type(entries) in (list, tuple):
                    total += len(entries)
                    require(total <= MAX_TOTAL_ENTRY_ASSESSMENTS)

def preflight_history(state):
    preflight_record(state, RenderPreparationState)

def preflight_document(state):
    preflight_record(state, RenderPreparationState, raw=True)

def preflight_upstream_evidence(manifest, *, raw=False):
    """One traversal budget across the retained M68-M73 evidence sweep.

    Existing upstream capacity validators remain authoritative for their domains;
    this extra sweep closes raw-copy and aggregate depth/node windows locally.
    """
    from typing import get_type_hints, get_origin, get_args
    from .acquisition import AcquisitionState
    from .editing import EditingState
    from .voice_timing import VoiceTimingState
    from .placement_timing import PlacementTimingState
    from .render_timeline import RenderTimelineState
    budget = [MAX_TRAVERSAL_NODES]
    schemas = {}
    totals = {}
    # Discover schemas from trusted annotations only, never from malformed values.
    def register(annotation):
        if is_dataclass(annotation):
            if annotation not in schemas:
                schemas[annotation] = get_type_hints(annotation)
                for child in schemas[annotation].values():
                    register(child)
        else:
            for child in get_args(annotation):
                register(child)
    for root in (RenderPreparationState, RenderTimelineState, PlacementTimingState,
            VoiceTimingState, EditingState, AcquisitionState):
        register(root)

    def walk(value, cls, depth=0, name=""):
        budget[0] -= 1
        require(budget[0] >= 0 and depth <= MAX_TRAVERSAL_DEPTH)
        if get_origin(cls) is list:
            cls = get_args(cls)[0]
        if not is_dataclass(cls):
            cls = next((c for c in get_args(cls) if is_dataclass(c)), cls)
        record_cls = next((known for known in schemas if type(value) is known), None)
        actual = record_cls if record_cls is not None else cls
        if type(value) is dict or record_cls is not None:
            hints = schemas.get(actual, {})
            if type(value) is dict:
                # A wrong record shape is not a type error owned by this sweep.
                require(len(value) <= MAX_TOTAL_ENTRY_ASSESSMENTS)
                items = value.items()
            else:
                items = ((f.name, getattr(value, f.name)) for f in fields(value))
            for key, item in items:
                if type(key) is str:
                    require(len(key) <= MAX_GENERAL_SCALAR)
                    field_name = key
                else:
                    # Bound malformed keys without hashing or coercing them.
                    walk(key, None, depth + 1)
                    field_name = ""
                if type(item) in (list, tuple):
                    limits = {"plans": 64, "runs": 64, "revisions": 64, "entries": 4096,
                        "placements": 4096, "shot_acquisitions": 4096, "materializations": 16384,
                        "assets": 64 if actual is VoiceTimingState else 16384,
                        "units": 100000, "omissions": 100000, "source_bindings": 200000}
                    require(len(item) <= limits.get(field_name, 1_000_000))
                    total_key = (actual, field_name)
                    totals[total_key] = totals.get(total_key, 0) + len(item)
                    aggregate = {"units": 500000, "omissions": 500000,
                        "source_bindings": 1000000, "entries": 65536,
                        "placements": 65536, "shot_acquisitions": 65536}
                    require(totals[total_key] <= aggregate.get(field_name, 2_000_000))
                walk(item, hints.get(field_name), depth + 1, field_name)
        elif type(value) in (list, tuple):
            require(len(value) <= 1_000_000)
            for item in value:
                walk(item, cls, depth + 1, name)
        elif type(value) is str:
            require(len(value) <= MAX_GENERAL_SCALAR)
        elif type(value) is int:
            require(value.bit_length() <= 63)
        else:
            # Opaque leaves (including unexpected dataclasses/enums) consume one
            # node. Strict upstream validation owns their type; do not inspect,
            # stringify, hash, copy or invoke any method on them.
            return
    for name, cls in (("render_preparation", RenderPreparationState),
            ("render_timeline", RenderTimelineState), ("placement_timing", PlacementTimingState),
            ("voice_timing", VoiceTimingState), ("editing", EditingState), ("acquisition", AcquisitionState)):
        value = manifest.get(name) if raw else getattr(manifest, name, None)
        walk(value, cls)

def validate_profile(profile):
    preflight_record(profile, OutputProfile)
    check_typed(OutputProfile, profile)
    require(1 <= profile.width_px <= 16384 and 1 <= profile.height_px <= 16384)
    require(profile.width_px * profile.height_px <= 67_108_864)
    num, den = profile.frame_rate_num, profile.frame_rate_den
    require(1 <= num <= 1_000_000 and 1 <= den <= 1_000_000)
    require(gcd(num, den) == 1 and den <= num <= 240 * den)

POLICY_FIELDS = ("pixel_policy", "duration_policy", "coverage_policy", "geometry_policy",
    "narration_policy", "visual_audio_policy", "subtitle_policy")

def validate_spec(spec):
    preflight_record(spec, RenderPreparationSpec)
    check_typed(RenderPreparationSpec, spec)
    require(spec.contract_version == "1" and spec.engine_version == "1")
    require(tuple(getattr(spec, name) for name in POLICY_FIELDS) == tuple(PreparationPolicy))

def frame_aligned(time_us, profile):
    require(type(time_us) is int and time_us >= 0)
    validate_profile(profile)
    return (time_us * profile.frame_rate_num) % (1_000_000 * profile.frame_rate_den) == 0

def conclusion(requirements):
    return (PreparationConclusion.PREPARATION_REQUIREMENTS_OUTSTANDING if requirements else
        PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED)

def resolve_bindings(manifest, timeline):
    from .render_timeline_validation import validate_plan as validate_timeline
    validate_timeline(manifest, timeline)
    timing = next(p for p in manifest.placement_timing.plans
        if p.placement_timing_plan_id == timeline.placement_timing_plan_id)
    run = next(r for r in manifest.voice_timing.runs if r.alignment_run_id == timing.alignment_run_id)
    revision = next(r for r in manifest.voice_timing.revisions
        if r.revision_id == run.narration_revision_id)
    asset = next(a for a in manifest.voice_timing.assets if a.asset_id == revision.asset_id)
    require(timing.narration_duration_us == run.inspection.duration_us)
    return (RenderTimelineBinding(timeline.render_timeline_plan_id, timeline.input_binding_signature,
        timeline.source_usage_signature, timeline.output_signature, timeline.timing_evidence_signature,
        timeline.media_binding_signature, timeline.spec),
        NarrationBinding(timing.placement_timing_plan_id, timing.output_signature,
            run.alignment_run_id, run.output_signature, run.input_signature, run.request_signature,
            run.receipt, revision.revision_id, asset.asset_id, asset.sha256, asset.byte_count,
            run.inspection, run.inspection.duration_us))

def derive_preparation(manifest, timeline, profile):
    """Only supported resolved scheduling evidence covers the narration interval."""
    entries, covered = [], []
    records = {r.materialization_id: r for r in manifest.acquisition.materializations}
    for entry in timeline.entries:
        requirements = []
        start, end = entry.timeline_start_us, entry.timeline_end_us
        if start is None or end is None:
            requirements.append(PreparationRequirement.FRAME_ALIGNMENT_NOT_ESTABLISHED)
        elif not frame_aligned(start, profile) or not frame_aligned(end, profile):
            requirements.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        supported = entry.outcome == RenderTimelineOutcome.READY and entry.source_usage in (
            SourceUsage.STILL_IMAGE, SourceUsage.WHOLE_VIDEO)
        width = height = None
        if not supported:
            requirements.append(PreparationRequirement.SUPPORTED_SOURCE_USE_NOT_ESTABLISHED)
        else:
            record = records[entry.materialization_id]
            width, height = record.inspection.width, record.inspection.height
            covered.append((start, end))
            requirements.append(PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED
                if entry.source_usage == SourceUsage.STILL_IMAGE else
                PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED)
        if width is None or height is None:
            requirements.append(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED)
        elif (width, height) != (profile.width_px, profile.height_px):
            requirements.append(PreparationRequirement.TRANSFORM_POLICY_REQUIRED)
        entries.append(RenderPreparationEntryAssessment(entry.placement_id, start, end,
            entry.source_usage, entry.source_start_us, entry.source_end_us, entry.source_duration_us,
            width, height, requirements, conclusion(requirements)))
    return entries, covered

def project_plan(manifest, timeline, profile, spec):
    from ..render_preparation.engine import preflight
    preflight(manifest)
    validate_profile(profile)
    validate_spec(spec)
    binding, narration = resolve_bindings(manifest, timeline)
    entries, covered = derive_preparation(manifest, timeline, profile)
    duration = narration.narration_duration_us
    uncovered = derive_uncovered_intervals(covered, duration)
    requirements = []
    if not frame_aligned(duration, profile):
        requirements.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
    if uncovered:
        requirements.append(PreparationRequirement.UNCOVERED_VISUAL_INTERVALS)
    for entry in entries:
        for requirement in entry.requirements:
            if requirement not in requirements:
                requirements.append(requirement)
    plan = assign_identity(RenderPreparationPlan("", binding, narration, profile, spec,
        duration, entries, uncovered, requirements, conclusion(requirements)))
    canonical_payload(plan)
    return plan

def derive_uncovered_intervals(covered, duration):
    require(type(duration) is int and duration > 0)
    require(type(covered) is list and len(covered) <= MAX_ENTRIES_PER_PLAN)
    uncovered, cursor, previous_end = [], 0, 0
    for start, end in covered:
        require(type(start) is int and type(end) is int and 0 <= start < end and start >= previous_end)
        previous_end = end
        start, end = min(start, duration), min(end, duration)
        if start > cursor:
            uncovered.append(UncoveredInterval(cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        uncovered.append(UncoveredInterval(cursor, duration))
    require(len(uncovered) <= MAX_UNCOVERED_INTERVALS)
    return uncovered

def validate_plan(manifest, plan):
    from ..render_preparation.engine import preflight
    preflight(manifest)
    preflight_record(plan, RenderPreparationPlan)
    check_typed(RenderPreparationPlan, plan)
    timeline = next(p for p in manifest.render_timeline.plans
        if p.render_timeline_plan_id == plan.timeline_binding.render_timeline_plan_id)
    require(plan == project_plan(manifest, timeline, plan.output_profile, plan.spec))

def validate_history(manifest):
    state = manifest.render_preparation
    preflight_history(state)
    check_typed(RenderPreparationState, state)
    ids = set()
    for plan in state.plans:
        require(plan.render_preparation_plan_id not in ids)
        ids.add(plan.render_preparation_plan_id)
        validate_plan(manifest, plan)
    require(state.active_render_preparation_plan_id is None or state.active_render_preparation_plan_id in ids)

def render_preparation_errors(manifest):
    try:
        validate_history(manifest)
        return []
    except Exception:
        return ["render_preparation_invalid"]
