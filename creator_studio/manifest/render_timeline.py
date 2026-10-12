"""M72 retained scheduling projection. No executable rendering authority."""
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
import math
from .acquisition import AcquisitionOutcome
from .retrieval import VisualMediaKind
from .placement_timing import PlacementTimingOutcome

MAX_PLANS = 64
MAX_ENTRIES_PER_PLAN = 4096
MAX_TOTAL_ENTRIES = 65536
MAX_DIAGNOSTICS_PER_ENTRY = 16
MAX_CANONICAL_PLAN_BYTES = 64 * 1024 * 1024
MAX_UNCOVERED_INTERVALS = 4097

class SourceUsage(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    STILL_IMAGE = "STILL_IMAGE"
    WHOLE_VIDEO = "WHOLE_VIDEO"

class RenderTimelineOutcome(str, Enum):
    READY = "READY"
    UNRESOLVED_TIMING = "UNRESOLVED_TIMING"
    NO_MATERIALIZED_MEDIA = "NO_MATERIALIZED_MEDIA"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    SOURCE_DURATION_UNRESOLVED = "SOURCE_DURATION_UNRESOLVED"
    SOURCE_TRIM_REQUIRED = "SOURCE_TRIM_REQUIRED"
    MEDIA_TOO_SHORT = "MEDIA_TOO_SHORT"

class RenderDiagnostic(str, Enum):
    UNRESOLVED_TIMING = "UNRESOLVED_TIMING"
    NO_MATERIALIZED_MEDIA = "NO_MATERIALIZED_MEDIA"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    SOURCE_DURATION_UNRESOLVED = "SOURCE_DURATION_UNRESOLVED"
    SOURCE_TRIM_REQUIRED = "SOURCE_TRIM_REQUIRED"
    MEDIA_TOO_SHORT = "MEDIA_TOO_SHORT"

@dataclass(frozen=True)
class RenderTimelineSpec:
    contract_version: str = "1"
    engine_version: str = "1"
    source_use_policy: str = "DETERMINISTIC_STILL_OR_EXACT_WHOLE_VIDEO_V1"
    duration_policy: str = "M68_RETAINED_BINARY_DURATION_EXACT_US_V1"
    time_unit: str = "INTEGER_MICROSECONDS"
    interval_policy: str = "HALF_OPEN_SINGLE_LANE_V1"

@dataclass(frozen=True)
class RenderTimelineEntry:
    placement_id: str
    ordinal: int
    planned_shot_id: str
    shot_selection_id: str
    acquisition_outcome: AcquisitionOutcome
    timing_outcome: PlacementTimingOutcome
    timeline_start_us: int | None = None
    timeline_end_us: int | None = None
    materialization_id: str | None = None
    asset_id: str | None = None
    materialization_evidence_signature: str | None = None
    asset_evidence_signature: str | None = None
    media_kind: VisualMediaKind | None = None
    source_duration_us: int | None = None
    source_usage: SourceUsage = SourceUsage.UNRESOLVED
    source_start_us: int | None = None
    source_end_us: int | None = None
    outcome: RenderTimelineOutcome = RenderTimelineOutcome.UNRESOLVED_TIMING
    diagnostics: list[RenderDiagnostic] = field(default_factory=list)

@dataclass(frozen=True)
class RenderTimelinePlan:
    render_timeline_plan_id: str
    acquisition_id: str
    edit_plan_id: str
    edit_output_signature: str
    placement_timing_plan_id: str
    timing_evidence_signature: str
    media_binding_signature: str
    spec: RenderTimelineSpec
    entries: list[RenderTimelineEntry]
    input_binding_signature: str = ""
    source_usage_signature: str = ""
    output_signature: str = ""

@dataclass
class RenderTimelineState:
    plans: list[RenderTimelinePlan] = field(default_factory=list)
    active_render_timeline_plan_id: str | None = None

def normalize_duration(duration):
    """Exact relative to retained binary float; makes no frame accuracy claim."""
    if type(duration) is not float or not math.isfinite(duration) or duration <= 0:
        return None
    numerator, denominator = duration.as_integer_ratio()
    value, remainder = divmod(numerator * 1_000_000, denominator)
    return value if remainder == 0 and value.bit_length() <= 63 else None

def canonical_chunks(value):
    if is_dataclass(value):
        yield from canonical_chunks({f.name: getattr(value, f.name) for f in fields(value)})
    elif type(value) is dict:
        yield "{"
        for index, name in enumerate(sorted(value)):
            if index:
                yield ","
            yield json.dumps(name, ensure_ascii=True)
            yield ":"
            yield from canonical_chunks(value[name])
        yield "}"
    elif type(value) in (list, tuple):
        yield "["
        for index, item in enumerate(value):
            if index:
                yield ","
            yield from canonical_chunks(item)
        yield "]"
    else:
        if isinstance(value, Enum):
            value = value.value
        yield json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))

def canonical_payload(plan, *, max_bytes=MAX_CANONICAL_PLAN_BYTES):
    from .render_timeline_validation import preflight_record
    from .codec import check_typed
    if type(max_bytes) is not int or not 0 <= max_bytes <= MAX_CANONICAL_PLAN_BYTES:
        raise ValueError("render_timeline_capacity")
    preflight_record(plan, RenderTimelinePlan)
    check_typed(RenderTimelinePlan, plan)
    size, chunks = 0, []
    for chunk in canonical_chunks(plan):
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("render_timeline_capacity")
        chunks.append(chunk)
    return "".join(chunks)

def signed(domain, payload):
    from .render_timeline_validation import bounded_value
    if type(domain) is not str or not 0 < len(domain) <= 64 or not all(
            c in "abcdefghijklmnopqrstuvwxyz_0123456789" for c in domain):
        raise ValueError("render_timeline_invalid")
    bounded_value(payload)
    digest, size = hashlib.sha256(), 0
    for chunk in canonical_chunks(["M72", domain, "1", payload]):
        size += len(chunk)
        if size > MAX_CANONICAL_PLAN_BYTES:
            raise ValueError("render_timeline_capacity")
        digest.update(chunk.encode("ascii"))
    return digest.hexdigest()

def assign_identity(plan):
    from .render_timeline_validation import preflight_record
    preflight_record(plan, RenderTimelinePlan)
    input_sig = signed("input_binding", [plan.acquisition_id, plan.edit_plan_id,
        plan.edit_output_signature, plan.placement_timing_plan_id,
        plan.timing_evidence_signature, plan.media_binding_signature, plan.spec])
    usage = signed("source_usage", [plan.spec.source_use_policy, plan.spec.duration_policy,
        [[e.placement_id, e.materialization_id, e.materialization_evidence_signature,
          e.asset_id, e.asset_evidence_signature, e.media_kind, e.source_duration_us, e.source_usage,
          e.source_start_us, e.source_end_us, e.outcome] for e in plan.entries]])
    output = signed("output", [input_sig, usage, plan.entries])
    identity = "render_timeline:" + signed("plan_identity", [input_sig, usage, output])
    return replace(plan, render_timeline_plan_id=identity, input_binding_signature=input_sig,
        source_usage_signature=usage, output_signature=output)
