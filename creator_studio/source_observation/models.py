"""Frozen V1 observation claims; no physical authority."""
from dataclasses import dataclass
from enum import Enum
from ..presentation_policy.models import PresentationPolicyProposal, AssessmentBoundary

MAX_OBSERVATION_BINDINGS = 4096
MAX_OBSERVATION_CLAIMS = 4096
MAX_VISUAL_STREAMS_PER_CLAIM = 16
MAX_FRAME_OBSERVATIONS_PER_CLAIM = 65536
MAX_FRAME_OBSERVATIONS_PER_BUNDLE = 131072
MAX_TRAVERSAL_DEPTH = 32
MAX_TRAVERSAL_NODES = 2_000_000
MAX_STRING_LENGTH = 256
MAX_UPSTREAM_ID_LENGTH = 96
MAX_INTEGER = (1 << 63) - 1
MAX_DIMENSION_AXIS = 16384
MAX_DIMENSION_AREA = 100_000_000
MAX_CANONICAL_PAYLOAD_BYTES = 64 * 1024 * 1024

class SourceObservationError(ValueError):
    def __init__(self):
        super().__init__("source_observation_invalid")

class SourceKind(str, Enum):
    STILL_IMAGE = "STILL_IMAGE"
    WHOLE_VIDEO = "WHOLE_VIDEO"

class ObservationKnowledge(str, Enum):
    UNKNOWN = "UNKNOWN"
    KNOWN = "KNOWN"

class Orientation(str, Enum):
    IDENTITY = "IDENTITY"
    ROTATED_90 = "ROTATED_90"
    ROTATED_180 = "ROTATED_180"
    ROTATED_270 = "ROTATED_270"
    REFLECTED = "REFLECTED"
    ROTATED_REFLECTED = "ROTATED_REFLECTED"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"

class OtherDisplayTransformStatus(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"

class AlphaPresence(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"

class EffectiveOpacity(str, Enum):
    OPAQUE = "OPAQUE"
    NOT_OPAQUE = "NOT_OPAQUE"
    UNKNOWN = "UNKNOWN"

class PresentationMultiplicity(str, Enum):
    SINGLE_STILL = "SINGLE_STILL"
    MULTI_FRAME = "MULTI_FRAME"
    ANIMATED = "ANIMATED"
    UNKNOWN = "UNKNOWN"

class TimestampEnumerationStatus(str, Enum):
    ABSENT = "ABSENT"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"

class TimestampOrigin(str, Enum):
    UNKNOWN = "UNKNOWN"
    STREAM_TIMEBASE = "STREAM_TIMEBASE"
    NORMALIZED_ZERO = "NORMALIZED_ZERO"
    OTHER = "OTHER"

class ObservationReferenceStatus(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"

class ObservationCoverage(str, Enum):
    ABSENT = "ABSENT"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"

@dataclass(frozen=True)
class SourceObservationSpec:
    contract_version: str
    engine_version: str

@dataclass(frozen=True)
class SourceByteIdentity:
    asset_id: str
    sha256: str
    byte_count: int

@dataclass(frozen=True)
class ExactRational:
    numerator: int
    denominator: int

@dataclass(frozen=True)
class FrameObservation:
    ordinal: int
    pts_ticks: int | None
    duration_ticks: int | None
    timestamp_origin: TimestampOrigin

@dataclass(frozen=True)
class VisualStreamObservation:
    stream_index: int
    source_kind: SourceKind
    coded_width_px: int | None
    coded_height_px: int | None
    display_width: ExactRational | None
    display_height: ExactRational | None
    sample_aspect_ratio: ExactRational | None
    reported_display_aspect_ratio: ExactRational | None
    orientation: Orientation
    rotation_degrees: ExactRational | None
    other_display_transform_status: OtherDisplayTransformStatus
    alpha_presence: AlphaPresence
    effective_opacity: EffectiveOpacity
    pixel_format: str | None
    decoded_presentation_count: int | None
    presentation_multiplicity: PresentationMultiplicity
    nominal_frame_rate: ExactRational | None
    average_frame_rate: ExactRational | None
    time_base: ExactRational | None
    stream_start_ticks: int | None
    stream_duration_ticks: int | None
    presentation_start_ticks: int | None
    presentation_end_exclusive_ticks: int | None
    timestamp_enumeration_status: TimestampEnumerationStatus
    frames: tuple[FrameObservation, ...]

@dataclass(frozen=True)
class SourceObservationClaim:
    byte_identity: SourceByteIdentity
    observer_id: str
    observer_version: str
    observation_method_id: str
    observation_method_version: str
    visual_stream_inventory_complete: bool
    visual_streams: tuple[VisualStreamObservation, ...]
    container_duration_us: int | None

@dataclass(frozen=True)
class ObservationBinding:
    ordinal: int
    placement_id: str
    materialization_id: str
    asset_id: str
    materialization_evidence_signature: str
    asset_evidence_signature: str
    observation_status: ObservationReferenceStatus
    observation_index: int | None

@dataclass(frozen=True)
class SourceObservationBundle:
    proposal: PresentationPolicyProposal
    spec: SourceObservationSpec
    claims: tuple[SourceObservationClaim, ...]
    bindings: tuple[ObservationBinding, ...]

@dataclass(frozen=True)
class SourceObservationAssessment:
    structurally_valid: bool
    current_logically_bound: bool
    observation_coverage: ObservationCoverage
    physical_byte_verification: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    physical_observation_authority: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    presentation_compliance: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    renderer_adapter_compatibility: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    executability: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
