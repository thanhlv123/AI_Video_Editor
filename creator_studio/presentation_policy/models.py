"""Frozen presentation intent, never physical evidence."""
from dataclasses import dataclass
from enum import Enum
from ..render_job.models import RenderJobDraft
from ..manifest.render_timeline import SourceUsage

MAX_PRESENTATION_OBLIGATIONS = 4096
MAX_TRAVERSAL_DEPTH = 32
MAX_TRAVERSAL_NODES = 2_000_000
MAX_CANONICAL_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_INTEGER = (1 << 63) - 1
MAX_ID_LENGTH = 96
MAX_GENERAL_SCALAR = 256

class PresentationPolicyError(ValueError):
    def __init__(self):
        super().__init__("presentation_policy_invalid")

class PresentationChoice(str, Enum):
    SINGLE_STILL_EXACT_INTERVAL = "SINGLE_STILL_EXACT_INTERVAL"
    EXACT_DISPLAY_GEOMETRY_NO_TRANSFORMATION = "EXACT_DISPLAY_GEOMETRY_NO_TRANSFORMATION"
    SQUARE_PIXELS_NO_CONVERSION = "SQUARE_PIXELS_NO_CONVERSION"
    ZERO_ROTATION = "ZERO_ROTATION"
    OPAQUE = "OPAQUE"
    EXACT_OUTPUT_LATTICE_WHOLE_VIDEO_NO_TRANSFORMATION = "EXACT_OUTPUT_LATTICE_WHOLE_VIDEO_NO_TRANSFORMATION"

class AssessmentBoundary(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"

@dataclass(frozen=True)
class PresentationPolicySpec:
    contract_version: str
    engine_version: str
    still_holding_rule: PresentationChoice
    display_geometry_rule: PresentationChoice
    square_pixel_rule: PresentationChoice
    rotation_rule: PresentationChoice
    opacity_rule: PresentationChoice
    whole_video_frame_lattice_rule: PresentationChoice

@dataclass(frozen=True)
class PresentationObligation:
    ordinal: int
    placement_id: str
    materialization_id: str
    asset_id: str
    materialization_evidence_signature: str
    asset_evidence_signature: str
    source_usage: SourceUsage
    source_width_px: int | None
    source_height_px: int | None
    timeline_start_us: int
    timeline_end_us: int
    required_display_width_px: int
    required_display_height_px: int
    required_square_pixels: PresentationChoice
    required_rotation: PresentationChoice
    required_opacity: PresentationChoice
    required_geometry: PresentationChoice
    required_still_holding: PresentationChoice | None
    required_video_lattice: PresentationChoice | None
    required_frame_rate_num: int | None
    required_frame_rate_den: int | None
    required_source_start_us: int | None
    required_source_end_us: int | None

@dataclass(frozen=True)
class PresentationPolicyProposal:
    draft: RenderJobDraft
    policy: PresentationPolicySpec
    obligations: tuple[PresentationObligation, ...]

@dataclass(frozen=True)
class PresentationPolicyAssessment:
    structurally_valid: bool
    current_logically_bound: bool
    policy_declared: bool
    source_compliance: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    renderer_adapter_compatibility: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    executability: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
