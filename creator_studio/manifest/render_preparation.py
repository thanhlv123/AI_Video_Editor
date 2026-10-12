"""M73 renderer-neutral retained preparation contract; no execution authority."""
from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
from .render_timeline import RenderTimelineSpec, SourceUsage, canonical_chunks
from .voice_timing import AudioInspectionEvidence, AcceptanceReceipt

MAX_PLANS = 64
MAX_ENTRIES_PER_PLAN = 4096
MAX_TOTAL_ENTRY_ASSESSMENTS = 65536
MAX_REQUIREMENTS_PER_ENTRY = 16
MAX_PLAN_REQUIREMENTS = 32
MAX_UNCOVERED_INTERVALS = 4097
ARTIFACT_COUNT = 2
MAX_ID_LENGTH = 96
MAX_GENERAL_SCALAR = 256
SIGNATURE_LENGTH = 64
MAX_CANONICAL_PLAN_BYTES = 64 * 1024 * 1024
MAX_TRAVERSAL_DEPTH = 32
MAX_TRAVERSAL_NODES = 2_000_000

class PreparationPolicy(str, Enum):
    SQUARE_PIXEL_OUTPUT_V1 = "SQUARE_PIXEL_OUTPUT_V1"
    OUTPUT_DURATION_EQUALS_BOUND_M70_NARRATION_V1 = "OUTPUT_DURATION_EQUALS_BOUND_M70_NARRATION_V1"
    REQUIRE_FULL_VISUAL_COVERAGE_V1 = "REQUIRE_FULL_VISUAL_COVERAGE_V1"
    IDENTITY_GEOMETRY_ONLY_V1 = "IDENTITY_GEOMETRY_ONLY_V1"
    BOUND_NARRATION_ONLY_V1 = "BOUND_NARRATION_ONLY_V1"
    MUTE_ALL_VISUAL_SOURCE_AUDIO_V1 = "MUTE_ALL_VISUAL_SOURCE_AUDIO_V1"
    NO_SUBTITLE_OUTPUT_V1 = "NO_SUBTITLE_OUTPUT_V1"

class PreparationRequirement(str, Enum):
    FRAME_ALIGNMENT_REQUIRED = "FRAME_ALIGNMENT_REQUIRED"
    FRAME_ALIGNMENT_NOT_ESTABLISHED = "FRAME_ALIGNMENT_NOT_ESTABLISHED"
    UNCOVERED_VISUAL_INTERVALS = "UNCOVERED_VISUAL_INTERVALS"
    TRANSFORM_POLICY_REQUIRED = "TRANSFORM_POLICY_REQUIRED"
    GEOMETRY_NOT_ESTABLISHED = "GEOMETRY_NOT_ESTABLISHED"
    IMAGE_PRESENTATION_NOT_ESTABLISHED = "IMAGE_PRESENTATION_NOT_ESTABLISHED"
    SOURCE_PRESENTATION_NOT_ESTABLISHED = "SOURCE_PRESENTATION_NOT_ESTABLISHED"
    SUPPORTED_SOURCE_USE_NOT_ESTABLISHED = "SUPPORTED_SOURCE_USE_NOT_ESTABLISHED"

class PreparationConclusion(str, Enum):
    PREPARATION_REQUIREMENTS_SATISFIED = "PREPARATION_REQUIREMENTS_SATISFIED"
    PREPARATION_REQUIREMENTS_OUTSTANDING = "PREPARATION_REQUIREMENTS_OUTSTANDING"

@dataclass(frozen=True)
class OutputProfile:
    width_px: int
    height_px: int
    frame_rate_num: int
    frame_rate_den: int

@dataclass(frozen=True)
class RenderPreparationSpec:
    pixel_policy: PreparationPolicy
    duration_policy: PreparationPolicy
    coverage_policy: PreparationPolicy
    geometry_policy: PreparationPolicy
    narration_policy: PreparationPolicy
    visual_audio_policy: PreparationPolicy
    subtitle_policy: PreparationPolicy
    contract_version: str = "1"
    engine_version: str = "1"

@dataclass(frozen=True)
class RenderTimelineBinding:
    render_timeline_plan_id: str
    input_binding_signature: str
    source_usage_signature: str
    output_signature: str
    timing_evidence_signature: str
    media_binding_signature: str
    spec: RenderTimelineSpec

@dataclass(frozen=True)
class NarrationBinding:
    placement_timing_plan_id: str
    placement_output_signature: str
    alignment_run_id: str
    alignment_output_signature: str
    alignment_input_signature: str
    alignment_request_signature: str
    acceptance_receipt: AcceptanceReceipt
    narration_revision_id: str
    narration_asset_id: str
    narration_sha256: str
    narration_byte_count: int
    inspection: AudioInspectionEvidence
    narration_duration_us: int

@dataclass(frozen=True)
class RenderPreparationEntryAssessment:
    placement_id: str
    timeline_start_us: int | None
    timeline_end_us: int | None
    source_usage: SourceUsage
    source_start_us: int | None
    source_end_us: int | None
    source_duration_us: int | None
    source_width_px: int | None
    source_height_px: int | None
    requirements: list[PreparationRequirement]
    conclusion: PreparationConclusion

@dataclass(frozen=True)
class UncoveredInterval:
    start_us: int
    end_us: int

@dataclass(frozen=True)
class RenderPreparationPlan:
    render_preparation_plan_id: str
    timeline_binding: RenderTimelineBinding
    narration_binding: NarrationBinding
    output_profile: OutputProfile
    spec: RenderPreparationSpec
    output_duration_us: int
    entries: list[RenderPreparationEntryAssessment]
    uncovered_intervals: list[UncoveredInterval]
    requirements: list[PreparationRequirement]
    conclusion: PreparationConclusion
    input_binding_signature: str = ""
    output_profile_signature: str = ""
    render_policy_signature: str = ""
    preparation_signature: str = ""
    output_signature: str = ""

@dataclass
class RenderPreparationState:
    plans: list[RenderPreparationPlan] = field(default_factory=list)
    active_render_preparation_plan_id: str | None = None

def signed(domain, payload):
    from .render_preparation_validation import bounded_value, require
    require(type(domain) is str and 0 < len(domain) <= 64 and
        all(c in "abcdefghijklmnopqrstuvwxyz_0123456789" for c in domain))
    bounded_value(payload)
    digest, size = hashlib.sha256(), 0
    for chunk in canonical_chunks(["M73", domain, "1", payload]):
        size += len(chunk)
        require(size <= MAX_CANONICAL_PLAN_BYTES)
        digest.update(chunk.encode("ascii"))
    return digest.hexdigest()

def canonical_payload(plan, *, max_bytes=MAX_CANONICAL_PLAN_BYTES):
    from .render_preparation_validation import preflight_record, require
    from .codec import check_typed
    require(type(max_bytes) is int and 0 <= max_bytes <= MAX_CANONICAL_PLAN_BYTES)
    preflight_record(plan, RenderPreparationPlan)
    check_typed(RenderPreparationPlan, plan)
    chunks, size = [], 0
    for chunk in canonical_chunks(plan):
        size += len(chunk)
        require(size <= max_bytes)
        chunks.append(chunk)
    return "".join(chunks)

def assign_identity(plan):
    from .render_preparation_validation import preflight_record
    preflight_record(plan, RenderPreparationPlan)
    binding = signed("input_binding", [plan.timeline_binding, plan.narration_binding])
    profile = signed("output_profile", plan.output_profile)
    policy = signed("render_policy", plan.spec)
    preparation = signed("preparation", [binding, profile, policy, plan.output_duration_us,
        plan.entries, plan.uncovered_intervals, plan.requirements, plan.conclusion])
    output = signed("output", [binding, profile, policy, preparation])
    identity = "render_preparation:" + signed("plan_identity", [binding, profile, policy, preparation, output])
    return replace(plan, render_preparation_plan_id=identity, input_binding_signature=binding,
        output_profile_signature=profile, render_policy_signature=policy,
        preparation_signature=preparation, output_signature=output)
