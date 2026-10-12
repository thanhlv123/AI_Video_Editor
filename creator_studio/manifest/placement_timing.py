"""M71 retained editorial timing evidence, independent of media readiness."""
from dataclasses import dataclass, field, replace, fields, is_dataclass
from enum import Enum
import json
from .codec import to_data, check_typed
from .semantic import exact_signature

MAX_PLANS = 64
MAX_ENTRIES_PER_PLAN = 4096
MAX_TOTAL_ENTRIES = 65536
MAX_ALLOCATIONS_PER_ENTRY = 64
MAX_BOUNDARY_DECLARATIONS_PER_ENTRY = 2
MAX_DIAGNOSTICS_PER_ENTRY = 16
MAX_ALLOCATIONS_PER_PLAN = 65536
MAX_TOTAL_ALLOCATIONS = 1048576
MAX_BOUNDARIES_PER_PLAN = 8192
MAX_TOTAL_BOUNDARIES = 131072
MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES = 64 * 1024 * 1024

class BoundarySide(str, Enum):
    START = "START"
    END = "END"

class BoundaryKind(str, Enum):
    M70_UNIT_START = "M70_UNIT_START"
    M70_UNIT_END = "M70_UNIT_END"
    ACCEPTED_EXPLICIT_TIME = "ACCEPTED_EXPLICIT_TIME"

class PlacementTimingOutcome(str, Enum):
    TIMED = "TIMED"
    UNRESOLVED = "UNRESOLVED"
    NO_SEMANTIC_TIMING = "NO_SEMANTIC_TIMING"
    AMBIGUOUS_BOUNDARY = "AMBIGUOUS_BOUNDARY"
    SOURCE_OMITTED = "SOURCE_OMITTED"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    MISMATCH_BLOCKED = "MISMATCH_BLOCKED"
    UNMAPPED_BLOCKED = "UNMAPPED_BLOCKED"
    ORDER_CONFLICT = "ORDER_CONFLICT"
    CAPACITY_BLOCKED = "CAPACITY_BLOCKED"

class TimingDiagnostic(str, Enum):
    NO_AUTHORITY = "NO_AUTHORITY"
    NO_SUPPORT = "NO_SUPPORT"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    INDIVISIBLE_EDGE = "INDIVISIBLE_EDGE"
    SOURCE_OMITTED = "SOURCE_OMITTED"
    MISMATCH = "MISMATCH"
    UNMAPPED = "UNMAPPED"
    SPEECH_ADDED = "SPEECH_ADDED"
    UNRELATED_UNIT = "UNRELATED_UNIT"
    ORDER_CONFLICT = "ORDER_CONFLICT"

@dataclass(frozen=True)
class PlacementTimingSpec:
    contract_version: str = "1"
    engine_version: str = "1"
    envelope_policy: str = "M70_LEXICAL_ENVELOPE_V1"
    time_unit: str = "INTEGER_MICROSECONDS"
    interval_policy: str = "HALF_OPEN_SINGLE_LANE_V1"

@dataclass(frozen=True)
class PlacementTimingLineage:
    acquisition_id: str
    selection_id: str
    retrieval_id: str
    visual_plan_id: str
    source_revision_id: str
    source_record_fingerprint: str
    semantic_document_id: str
    semantic_generated_binding: str
    semantic_output_binding: str
    content_revision_signature: str
    analysis_signature: str
    retained_chain_signature: str

@dataclass(frozen=True)
class PlacementAllocationDeclaration:
    placement_id: str
    source_revision_id: str
    semantic_document_id: str
    story_unit_id: str
    start_char: int
    end_char: int
    excerpt_signature: str
    declaration_ref: str = ""

@dataclass(frozen=True)
class PlacementBoundaryDeclaration:
    placement_id: str
    side: BoundarySide
    time_us: int
    declaration_ref: str = ""

@dataclass(frozen=True)
class PlacementBoundaryEvidence:
    side: BoundarySide
    kind: BoundaryKind
    declaration_ref: str
    unit_id: str | None = None

@dataclass(frozen=True)
class PlacementTimingEntry:
    placement_id: str
    outcome: PlacementTimingOutcome
    start_us: int | None = None
    end_us: int | None = None
    boundaries: list[PlacementBoundaryEvidence] = field(default_factory=list)
    diagnostics: list[TimingDiagnostic] = field(default_factory=list)

@dataclass(frozen=True)
class PlacementTimingAcceptanceReceipt:
    acceptance_policy_id: str
    acceptance_policy_version: str
    request_signature: str
    input_signature: str
    output_signature: str
    declaration_signature: str
    receipt_id: str = ""
    contract_version: str = "1"

@dataclass(frozen=True)
class PlacementTimingPlan:
    placement_timing_plan_id: str
    edit_plan_id: str
    edit_output_signature: str
    placement_ids: list[str]
    alignment_run_id: str
    alignment_output_signature: str
    alignment_request_signature: str
    alignment_receipt_id: str
    narration_revision_id: str
    narration_duration_us: int
    lineage: PlacementTimingLineage
    spec: PlacementTimingSpec
    allocations: list[PlacementAllocationDeclaration]
    explicit_boundaries: list[PlacementBoundaryDeclaration]
    entries: list[PlacementTimingEntry]
    unallocated_unit_ids: list[str]
    acceptance_policy_id: str
    acceptance_policy_version: str
    declaration_signature: str = ""
    input_signature: str = ""
    output_signature: str = ""
    request_signature: str | None = None
    receipt: PlacementTimingAcceptanceReceipt | None = None

@dataclass
class PlacementTimingState:
    plans: list[PlacementTimingPlan] = field(default_factory=list)
    active_placement_timing_plan_id: str | None = None

def _preflight_value(value):
    # Local import avoids the contract/validator import cycle. All public signing
    # helpers fence retained M71 records before codec projection can be entered.
    from .placement_timing_validation import preflight_record, preflight_history, _RECORDS
    if type(value) is PlacementTimingPlan:
        preflight_history(PlacementTimingState([value]))
    elif type(value) is PlacementTimingState:
        preflight_history(value)
    elif type(value) in _RECORDS:
        preflight_record(value, type(value))
    elif type(value) in (list, tuple):
        if len(value) > MAX_TOTAL_ALLOCATIONS:
            raise ValueError("placement_timing_capacity")
        for item in value:
            _preflight_value(item)
    elif type(value) is dict:
        if len(value) > MAX_TOTAL_ALLOCATIONS:
            raise ValueError("placement_timing_capacity")
        for key, item in value.items():
            _preflight_value(key)
            _preflight_value(item)
    elif type(value) is str and len(value) > 256:
        raise ValueError("placement_timing_capacity")


def signed(domain, payload):
    _preflight_value(payload)
    return exact_signature(["M71", domain, "1", payload])


def _canonical_chunks(value, *, omit=()):
    """Canonical codec-equivalent tokens without a recursive primitive copy.

    Scalars have already passed their field contracts. Escaping therefore creates
    at most a small bounded token, even when the complete request hits its cap.
    """
    if is_dataclass(value):
        names = sorted(f.name for f in fields(value) if f.name not in omit)
        yield "{"
        for index, name in enumerate(names):
            if index:
                yield ","
            yield json.dumps(name, ensure_ascii=True)
            yield ":"
            yield from _canonical_chunks(getattr(value, name))
        yield "}"
    elif type(value) is dict:
        yield "{"
        for index, name in enumerate(sorted(value)):
            if index:
                yield ","
            yield json.dumps(name, ensure_ascii=True)
            yield ":"
            yield from _canonical_chunks(value[name])
        yield "}"
    elif type(value) in (list, tuple):
        yield "["
        for index, item in enumerate(value):
            if index:
                yield ","
            yield from _canonical_chunks(item)
        yield "]"
    else:
        if isinstance(value, Enum):
            value = value.value
        yield json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def canonical_payload(plan, *, max_bytes=MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES, include_request=False):
    """Enforce the byte budget while traversing the bounded original contract."""
    _preflight_value(plan)
    check_typed(PlacementTimingPlan, plan)
    size, chunks = 0, []
    if include_request:
        metadata = {"contract_version": "1", "edit_plan_id": plan.edit_plan_id,
            "placement_ids": plan.placement_ids, "alignment_run_id": plan.alignment_run_id,
            "narration_revision_id": plan.narration_revision_id, "proposal_json": "",
            "acceptance_policy_id": plan.acceptance_policy_id,
            "acceptance_policy_version": plan.acceptance_policy_version,
            "declaration_signature": plan.declaration_signature, "input_signature": plan.input_signature,
            "output_signature": plan.output_signature, "request_signature": plan.request_signature}
        for chunk in _canonical_chunks(metadata):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("placement_timing_capacity")
    for chunk in _canonical_chunks(plan, omit=("receipt", "placement_timing_plan_id")):
        size += len(chunk)
        if include_request:
            size += chunk.count('"') + chunk.count("\\")
        if size > max_bytes:
            raise ValueError("placement_timing_capacity")
        chunks.append(chunk)
    return "".join(chunks)

def declaration_ref(declaration):
    _preflight_value(declaration)
    data = to_data(declaration)
    data.pop("declaration_ref")
    return "placement_declaration:" + signed(type(declaration).__name__, data)

def declaration_signature(plan):
    _preflight_value(plan)
    return signed("declarations", [plan.allocations, plan.explicit_boundaries])

def input_signature(plan):
    _preflight_value(plan)
    return signed("input", [plan.edit_plan_id, plan.edit_output_signature, plan.placement_ids,
        plan.alignment_run_id, plan.alignment_output_signature, plan.alignment_request_signature,
        plan.alignment_receipt_id, plan.narration_revision_id, plan.narration_duration_us,
        plan.lineage, plan.spec, plan.declaration_signature,
        plan.acceptance_policy_id, plan.acceptance_policy_version])

def output_signature(plan):
    _preflight_value(plan)
    return signed("output", [plan.input_signature, plan.entries, plan.unallocated_unit_ids])

def request_signature(plan):
    _preflight_value(plan)
    return signed("request", [plan.input_signature, plan.declaration_signature,
        plan.output_signature, plan.acceptance_policy_id, plan.acceptance_policy_version, "1"])

def receipt_id(receipt):
    _preflight_value(receipt)
    data = to_data(receipt)
    data.pop("receipt_id")
    return "placement_receipt:" + signed("receipt", data)

def plan_id(plan):
    _preflight_value(plan)
    return "placement_timing:" + signed("plan", [plan.input_signature,
        plan.declaration_signature, plan.output_signature, plan.request_signature,
        plan.receipt if plan.receipt is not None else "ALL_UNRESOLVED_NO_RECEIPT_V1"])

def make_receipt(request):
    """Construct a receipt after a policy decision; this utility is not a gate."""
    r = PlacementTimingAcceptanceReceipt(request.acceptance_policy_id,
        request.acceptance_policy_version, request.request_signature,
        request.input_signature, request.output_signature, request.declaration_signature)
    return replace(r, receipt_id=receipt_id(r))
