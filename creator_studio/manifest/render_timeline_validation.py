"""Bounded, pure retained evidence validation. No current observations."""
from dataclasses import fields, is_dataclass
from enum import Enum
from .codec import check_typed
from .render_timeline import *

RECORDS = (RenderTimelineSpec, RenderTimelineEntry, RenderTimelinePlan, RenderTimelineState)
MEMBERS = {cls: {f.name for f in fields(cls)} for cls in RECORDS}

def require(condition):
    if not condition:
        raise ValueError("render_timeline_invalid")

def bounded_value(value, depth=0, remaining=None):
    """Capacity fence only; strict typing/derivation follows separately."""
    remaining = [2_000_000] if remaining is None else remaining
    remaining[0] -= 1
    require(remaining[0] >= 0 and depth <= 32)
    if is_dataclass(value):
        for f in fields(value):
            item = getattr(value, f.name)
            if type(value) in RECORDS and type(item) in (list, tuple):
                limit = {"plans": MAX_PLANS, "entries": MAX_ENTRIES_PER_PLAN,
                    "diagnostics": MAX_DIAGNOSTICS_PER_ENTRY}.get(f.name, MAX_TOTAL_ENTRIES)
                require(len(item) <= limit)
            bounded_value(item, depth + 1, remaining)
    elif isinstance(value, Enum):
        require(type(value.value) is str and len(value.value) <= 256)
    elif type(value) is str:
        require(len(value) <= 256)
    elif type(value) is int:
        require(value.bit_length() <= 63)
    elif type(value) in (list, tuple, dict):
        require(len(value) <= MAX_TOTAL_ENTRIES)
        for item in (value.items() if type(value) is dict else value):
            bounded_value(item, depth + 1, remaining)
    else:
        require(value is None or type(value) in (bool, float))

def preflight_record(record, cls, *, raw=False, control=None):
    if (type(record) is not dict if raw else type(record) is not cls):
        bounded_value(record)
        return
    if raw:
        require(len(record) <= len(MEMBERS[cls]))
        for name, value in record.items():
            if name not in MEMBERS[cls]:
                bounded_value(name)
                bounded_value(value)
    if cls is RenderTimelineState:
        plans = record.get("plans") if raw else record.plans
        if type(plans) in (list, tuple):
            require(len(plans) <= MAX_PLANS)
            total = 0
            for plan in plans:
                entries = plan.get("entries") if raw and type(plan) is dict else getattr(plan, "entries", None)
                if type(entries) in (list, tuple):
                    require(len(entries) <= MAX_ENTRIES_PER_PLAN)
                    total += len(entries)
                    require(total <= MAX_TOTAL_ENTRIES)
    for f in fields(cls):
        if control:
            control.check()
        value = record.get(f.name) if raw else getattr(record, f.name)
        if f.name in ("plans", "entries", "diagnostics") and type(value) in (list, tuple):
            limit = {"plans": MAX_PLANS, "entries": MAX_ENTRIES_PER_PLAN,
                "diagnostics": MAX_DIAGNOSTICS_PER_ENTRY}[f.name]
            require(len(value) <= limit)
            child = {"plans": RenderTimelinePlan, "entries": RenderTimelineEntry}.get(f.name)
            for item in value:
                if child:
                    preflight_record(item, child, raw=raw, control=control)
                else:
                    bounded_value(item)
        elif f.name == "spec":
            preflight_record(value, RenderTimelineSpec, raw=raw, control=control)
        else:
            bounded_value(value)
            if isinstance(value, str):
                if "signature" in f.name:
                    require(len(value) in (0, 64) and all(c in "0123456789abcdef" for c in value))
                elif f.name.endswith("_id"):
                    require(len(value) <= 96)

def preflight_history(state, control=None):
    preflight_record(state, RenderTimelineState, control=control)

def preflight_document(state):
    preflight_record(state, RenderTimelineState, raw=True)

def preflight_upstream(manifest, *, raw=False):
    """Shallow M68/M69 capacities before recursive upstream validation/copy."""
    get = lambda obj, name: obj.get(name) if type(obj) is dict else getattr(obj, name, None)
    acquisition, editing = get(manifest, "acquisition"), get(manifest, "editing")
    for state, name, limit in ((acquisition, "runs", 64),
            (acquisition, "materializations", 16384), (acquisition, "assets", 16384),
            (editing, "plans", 64)):
        values = get(state, name)
        if type(values) in (list, tuple):
            require(len(values) <= limit)
    for state, collection, child in ((acquisition, "runs", "shot_acquisitions"),
            (editing, "plans", "placements")):
        values, total = get(state, collection), 0
        if type(values) in (list, tuple):
            for record in values:
                children = get(record, child)
                if type(children) in (list, tuple):
                    require(len(children) <= 4096)
                    total += len(children)
                    require(total <= 65536)
    bounded_value(acquisition)
    bounded_value(editing)

def retained_inputs(manifest, timing):
    from .placement_timing_validation import validate_plan as validate_timing
    from .acquisition_validation import acquisition_errors
    from .editing_validation import editing_errors
    from .voice_timing_validation import voice_timing_errors, preflight_history as voice_preflight
    preflight_upstream(manifest)
    voice_preflight(manifest.voice_timing)
    # Upstream whole-history validators also check pointer consistency. Remove
    # only pointers in a shallow read-only view; retained evidence is identical.
    historical = replace(manifest,
        acquisition=replace(manifest.acquisition, active_creator_acquisition_id=None),
        editing=replace(manifest.editing, active_creator_edit_plan_id=None),
        voice_timing=replace(manifest.voice_timing, active_narration_revision_id=None,
            active_alignment_run_id=None))
    require(not acquisition_errors(historical) and not editing_errors(historical)
        and not voice_timing_errors(historical))
    validate_timing(manifest, timing)
    edit = next(p for p in manifest.editing.plans if p.edit_plan_id == timing.edit_plan_id)
    acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == edit.acquisition_id)
    require(edit.acquisition_output_signature == acquisition.output_signature)
    require([p.placement_id for p in edit.placements] == [e.placement_id for e in timing.entries])
    return edit, acquisition

def derive_entries(manifest, edit, acquisition, timing, control=None):
    require(len(edit.placements) <= MAX_ENTRIES_PER_PLAN)
    require(len(edit.placements) == len(timing.entries))
    require(len({p.placement_id for p in edit.placements}) == len(edit.placements))
    acquisitions = {s.shot_selection_id: s for s in acquisition.shot_acquisitions}
    records = {r.materialization_id: r for r in manifest.acquisition.materializations}
    assets = {a.asset_id: a for a in manifest.acquisition.assets}
    entries = []
    previous_end = 0
    for placement, timing_entry in zip(edit.placements, timing.entries):
        if control:
            control.check()
            from ..render_timeline.engine import preflight_for_expensive_operation
            preflight_for_expensive_operation(manifest)
        require(placement.placement_id == timing_entry.placement_id)
        shot = acquisitions[placement.shot_selection_id]
        require((shot.outcome, shot.materialization_id) ==
            (placement.acquisition_outcome, placement.materialization_id))
        entry = RenderTimelineEntry(placement.placement_id, placement.ordinal,
            placement.planned_shot_id, placement.shot_selection_id, shot.outcome,
            timing_entry.outcome, materialization_id=shot.materialization_id)
        if shot.outcome == AcquisitionOutcome.MATERIALIZED:
            record = records[shot.materialization_id]
            asset = assets[record.asset_id]
            entry = replace(entry, asset_id=asset.asset_id,
                materialization_evidence_signature=signed("materialization_evidence", record),
                asset_evidence_signature=signed("asset_evidence", [asset.asset_id, asset.sha256, asset.byte_count]),
                media_kind=record.inspection.media_kind)
            if record.inspection.media_kind == VisualMediaKind.VIDEO:
                entry = replace(entry, source_duration_us=normalize_duration(record.inspection.duration_seconds))
        if timing_entry.outcome != PlacementTimingOutcome.TIMED:
            require(timing_entry.start_us is None and timing_entry.end_us is None)
            outcome = RenderTimelineOutcome.UNRESOLVED_TIMING
        else:
            start, end = timing_entry.start_us, timing_entry.end_us
            require(type(start) is int and type(end) is int and 0 <= start < end)
            require(start >= previous_end)
            previous_end = end
            entry = replace(entry, timeline_start_us=start, timeline_end_us=end)
            if shot.outcome != AcquisitionOutcome.MATERIALIZED:
                outcome = RenderTimelineOutcome.NO_MATERIALIZED_MEDIA
            elif entry.media_kind == VisualMediaKind.IMAGE:
                outcome = RenderTimelineOutcome.READY
                entry = replace(entry, source_usage=SourceUsage.STILL_IMAGE)
            elif entry.media_kind != VisualMediaKind.VIDEO:
                outcome = RenderTimelineOutcome.UNSUPPORTED_MEDIA_TYPE
            elif entry.source_duration_us is None:
                outcome = RenderTimelineOutcome.SOURCE_DURATION_UNRESOLVED
            elif entry.source_duration_us > end - start:
                outcome = RenderTimelineOutcome.SOURCE_TRIM_REQUIRED
            elif entry.source_duration_us < end - start:
                outcome = RenderTimelineOutcome.MEDIA_TOO_SHORT
            else:
                outcome = RenderTimelineOutcome.READY
                entry = replace(entry, source_usage=SourceUsage.WHOLE_VIDEO,
                    source_start_us=0, source_end_us=entry.source_duration_us)
        entries.append(replace(entry, outcome=outcome,
            diagnostics=[] if outcome == RenderTimelineOutcome.READY else [RenderDiagnostic(outcome.value)]))
    return entries

def project_plan(manifest, timing, spec=None, control=None):
    from ..render_timeline.engine import preflight_for_expensive_operation
    preflight_for_expensive_operation(manifest)
    spec = spec or RenderTimelineSpec()
    require(spec == RenderTimelineSpec())
    edit, acquisition = retained_inputs(manifest, timing)
    entries = derive_entries(manifest, edit, acquisition, timing, control)
    media = signed("media_binding", [acquisition, edit, [[e.placement_id,
        e.materialization_id, e.asset_id, e.materialization_evidence_signature,
        e.asset_evidence_signature] for e in entries]])
    plan = RenderTimelinePlan("", acquisition.acquisition_id, edit.edit_plan_id,
        edit.output_signature, timing.placement_timing_plan_id,
        signed("timing_evidence", timing), media, spec, entries)
    plan = assign_identity(plan)
    canonical_payload(plan)
    return plan

def validate_plan(manifest, plan, control=None):
    preflight_record(plan, RenderTimelinePlan, control=control)
    from ..render_timeline.engine import preflight_for_expensive_operation
    preflight_for_expensive_operation(manifest)
    preflight_record(plan, RenderTimelinePlan)
    check_typed(RenderTimelinePlan, plan)
    timing = next(p for p in manifest.placement_timing.plans
        if p.placement_timing_plan_id == plan.placement_timing_plan_id)
    require(plan == project_plan(manifest, timing, plan.spec, control))

def validate_history(manifest, control=None):
    state = manifest.render_timeline
    preflight_history(state, control)
    from ..render_timeline.engine import preflight_for_expensive_operation
    preflight_for_expensive_operation(manifest)
    preflight_history(state)
    check_typed(RenderTimelineState, state)
    ids = set()
    for plan in state.plans:
        require(plan.render_timeline_plan_id not in ids)
        ids.add(plan.render_timeline_plan_id)
        validate_plan(manifest, plan, control)
    require(state.active_render_timeline_plan_id is None or state.active_render_timeline_plan_id in ids)

def render_timeline_errors(manifest):
    try:
        validate_history(manifest)
        return []
    except Exception:
        return ["render_timeline_invalid"]

def complete_render_timeline(manifest, plan):
    try:
        validate_plan(manifest, plan)
        return bool(plan.entries and all(e.outcome == RenderTimelineOutcome.READY for e in plan.entries))
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration):
        return False

def uncovered_intervals(manifest, plan):
    validate_plan(manifest, plan)
    timing = next(p for p in manifest.placement_timing.plans
        if p.placement_timing_plan_id == plan.placement_timing_plan_id)
    result, cursor = [], 0
    for entry in plan.entries:
        if entry.outcome != RenderTimelineOutcome.READY:
            continue
        if entry.timeline_start_us > cursor:
            result.append((cursor, entry.timeline_start_us))
        cursor = entry.timeline_end_us
    if cursor < timing.narration_duration_us:
        result.append((cursor, timing.narration_duration_us))
    require(len(result) <= MAX_UNCOVERED_INTERVALS)
    return tuple(result)
