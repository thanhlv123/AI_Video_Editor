"""M65 persistent visual contracts and exact ID-free identity payloads."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .semantic import Purpose, ReviewStatus, AnnotationOrigin, exact_signature

CONTRACT_VERSION = "1"
ENGINE_VERSION = "1"


class VisualPurpose(str, Enum):
    UNKNOWN = "UNKNOWN"
    LITERAL_ACTION = "LITERAL_ACTION"
    LITERAL_SUBJECT = "LITERAL_SUBJECT"
    ESTABLISHING_CONTEXT = "ESTABLISHING_CONTEXT"
    ENVIRONMENT = "ENVIRONMENT"
    DETAIL = "DETAIL"
    PROCESS = "PROCESS"
    EMOTIONAL_SUPPORT = "EMOTIONAL_SUPPORT"
    CONCEPTUAL = "CONCEPTUAL"
    TRANSITION = "TRANSITION"
    CTA_SUPPORT = "CTA_SUPPORT"
    OTHER = "OTHER"


class RepresentationMode(str, Enum):
    UNKNOWN = "UNKNOWN"
    LITERAL = "LITERAL"
    ILLUSTRATIVE = "ILLUSTRATIVE"
    SYMBOLIC = "SYMBOLIC"
    ABSTRACT = "ABSTRACT"
    TEXTUAL = "TEXTUAL"
    MAP = "MAP"
    DOCUMENT = "DOCUMENT"


class DepictionFidelity(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXACT_LITERAL = "EXACT_LITERAL"
    CONTEXTUAL = "CONTEXTUAL"
    CONCEPTUAL = "CONCEPTUAL"
    ATMOSPHERIC = "ATMOSPHERIC"


class ShotRole(str, Enum):
    UNKNOWN = "UNKNOWN"
    ESTABLISHING = "ESTABLISHING"
    MASTER = "MASTER"
    ACTION = "ACTION"
    REACTION = "REACTION"
    DETAIL = "DETAIL"
    CUTAWAY = "CUTAWAY"
    INSERT = "INSERT"
    ATMOSPHERE = "ATMOSPHERE"
    TRANSITION = "TRANSITION"
    GRAPHIC = "GRAPHIC"
    OTHER = "OTHER"


class ShotScale(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXTREME_WIDE = "EXTREME_WIDE"
    WIDE = "WIDE"
    MEDIUM = "MEDIUM"
    MEDIUM_CLOSE = "MEDIUM_CLOSE"
    CLOSE = "CLOSE"
    EXTREME_CLOSE = "EXTREME_CLOSE"


class CameraMotion(str, Enum):
    UNKNOWN = "UNKNOWN"
    STATIC = "STATIC"
    PAN = "PAN"
    TILT = "TILT"
    TRACK = "TRACK"
    DOLLY = "DOLLY"
    HANDHELD = "HANDHELD"
    AERIAL = "AERIAL"
    OTHER = "OTHER"


class MediaFormPreference(str, Enum):
    UNKNOWN = "UNKNOWN"
    EITHER = "EITHER"
    VIDEO_PREFERRED = "VIDEO_PREFERRED"
    IMAGE_PREFERRED = "IMAGE_PREFERRED"
    GRAPHIC_PREFERRED = "GRAPHIC_PREFERRED"


class GeographyFidelity(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXACT = "EXACT"
    REGION_COMPATIBLE = "REGION_COMPATIBLE"
    GENERIC = "GENERIC"
    NONE = "NONE"


class TemporalFidelity(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    GENERIC = "GENERIC"
    NONE = "NONE"


class TemporalDimension(str, Enum):
    ERA = "ERA"
    SEASON = "SEASON"
    DAY_NIGHT = "DAY_NIGHT"
    RELATIVE_CHRONOLOGY = "RELATIVE_CHRONOLOGY"


class RequirementAspect(str, Enum):
    SUBJECT = "SUBJECT"
    ACTION = "ACTION"
    ENVIRONMENT = "ENVIRONMENT"
    OBJECT = "OBJECT"
    LOCATION = "LOCATION"
    TIME = "TIME"
    MOOD = "MOOD"


class PlanningTreatment(str, Enum):
    SHOW = "SHOW"
    ILLUSTRATE = "ILLUSTRATE"
    SYMBOLIZE = "SYMBOLIZE"
    EVOKE = "EVOKE"
    TEXTUAL = "TEXTUAL"


class IdentityFidelity(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXACT = "EXACT"
    CATEGORY = "CATEGORY"


class ContinuityKind(str, Enum):
    SUBJECT = "SUBJECT"
    LOCATION = "LOCATION"
    APPEARANCE = "APPEARANCE"
    ENVIRONMENT = "ENVIRONMENT"
    TEMPORAL = "TEMPORAL"
    STYLE = "STYLE"


class Strength(str, Enum):
    PREFERRED = "PREFERRED"
    REQUIRED = "REQUIRED"


class ConstraintKind(str, Enum):
    SHOW_SEMANTIC_TARGET = "SHOW_SEMANTIC_TARGET"
    PRESERVE_IDENTITY = "PRESERVE_IDENTITY"
    PRESERVE_LOCATION = "PRESERVE_LOCATION"
    PRESERVE_TEMPORAL_CONTEXT = "PRESERVE_TEMPORAL_CONTEXT"
    TEXT_OVERLAY = "TEXT_OVERLAY"
    FACES = "FACES"
    GRAPHIC_CONTENT = "GRAPHIC_CONTENT"
    MOTION = "MOTION"
    STILLNESS = "STILLNESS"


class Polarity(str, Enum):
    REQUIRE = "REQUIRE"
    AVOID = "AVOID"


@dataclass(frozen=True)
class PlanningOptions:
    pass


@dataclass(frozen=True)
class PlanningSpec:
    visual_contract_version: str = CONTRACT_VERSION
    engine_version: str = ENGINE_VERSION
    planner_id: str = "offline_structural"
    planner_version: str = "1"
    options: PlanningOptions = field(default_factory=PlanningOptions)


@dataclass(frozen=True)
class VisualReview:
    status: ReviewStatus = ReviewStatus.PENDING
    locked: bool = False


@dataclass(frozen=True)
class SemanticMentionRef:
    story_unit_id: str
    mention_ordinal: int
    mention_fingerprint: str


@dataclass(frozen=True)
class Evidence:
    story_unit_ids: list[str]
    mentions: list[SemanticMentionRef] = field(default_factory=list)


@dataclass(frozen=True)
class PlanningMetadata:
    origin: AnnotationOrigin = AnnotationOrigin.UNKNOWN
    confidence: float | None = None


@dataclass(frozen=True)
class VisualRequirement:
    aspect: RequirementAspect
    evidence: Evidence
    treatment: PlanningTreatment
    metadata: PlanningMetadata
    identity_fidelity: IdentityFidelity = IdentityFidelity.UNKNOWN


@dataclass(frozen=True)
class GeographyRequirement:
    fidelity: GeographyFidelity
    evidence: Evidence


@dataclass(frozen=True)
class TemporalRequirement:
    fidelity: TemporalFidelity
    dimension: TemporalDimension
    evidence: Evidence


@dataclass(frozen=True)
class ContinuityRequirement:
    kind: ContinuityKind
    strength: Strength
    evidence: Evidence
    metadata: PlanningMetadata


@dataclass(frozen=True)
class VisualConstraint:
    kind: ConstraintKind
    polarity: Polarity
    strength: Strength
    evidence: Evidence
    metadata: PlanningMetadata
    target: SemanticMentionRef | None = None


@dataclass(frozen=True)
class PlannedShot:
    planned_shot_id: str
    visual_unit_id: str
    ordinal: int
    story_unit_ids: list[str]
    shot_role: ShotRole = ShotRole.UNKNOWN
    shot_scale_preference: ShotScale = ShotScale.UNKNOWN
    camera_motion_preference: CameraMotion = CameraMotion.UNKNOWN
    media_form_preference: MediaFormPreference = MediaFormPreference.UNKNOWN
    requirements: list[VisualRequirement] = field(default_factory=list)
    constraints: list[VisualConstraint] = field(default_factory=list)
    metadata: PlanningMetadata = field(default_factory=PlanningMetadata)
    review: VisualReview = field(default_factory=VisualReview)


@dataclass(frozen=True)
class VisualUnitPlan:
    visual_unit_id: str
    ordinal: int
    story_unit_ids: list[str]
    visual_purpose: VisualPurpose = VisualPurpose.UNKNOWN
    representation_mode: RepresentationMode = RepresentationMode.UNKNOWN
    depiction_fidelity: DepictionFidelity = DepictionFidelity.UNKNOWN
    requirements: list[VisualRequirement] = field(default_factory=list)
    geography_requirement: GeographyRequirement | None = None
    temporal_requirement: TemporalRequirement | None = None
    continuity_requirements: list[ContinuityRequirement] = field(default_factory=list)
    constraints: list[VisualConstraint] = field(default_factory=list)
    planned_shots: list[PlannedShot] = field(default_factory=list)
    metadata: PlanningMetadata = field(default_factory=PlanningMetadata)
    review: VisualReview = field(default_factory=VisualReview)


@dataclass(frozen=True)
class VisualDiagnostic:
    code: str


@dataclass(frozen=True)
class VisualPlan:
    visual_plan_id: str
    semantic_document_id: str
    semantic_output_signature: str
    content_revision_signature: str
    purpose: Purpose
    planning_spec: PlanningSpec
    semantic_input_fingerprint: str
    planning_signature: str
    story_unit_ids: list[str]
    units: list[VisualUnitPlan]
    diagnostics: list[VisualDiagnostic]
    review: VisualReview
    output_signature: str


@dataclass
class VisualState:
    plans: list[VisualPlan] = field(default_factory=list)
    active_creator_plan_id: str | None = None


def semantic_input_fingerprint(document, *, captured_output=None):
    return exact_signature([document.semantic_document_id,
        document.output_signature if captured_output is None else captured_output,
        document.content_revision_signature, document.source_revision_id,
        [u.story_unit_id for u in document.story_units], document.purpose])


def planning_signature(fingerprint, spec, purpose=Purpose.CREATOR_STORY):
    return exact_signature([fingerprint, spec, purpose])


def shot_payload(shot):
    data = to_data(shot)
    for key in ("planned_shot_id", "visual_unit_id", "ordinal", "review"):
        data.pop(key, None)
    return data


def unit_payload(unit):
    data = to_data(unit)
    for key in ("visual_unit_id", "ordinal", "review"):
        data.pop(key, None)
    data["planned_shots"] = [shot_payload(s) for s in unit.planned_shots]
    return data


def generated_payload(plan):
    return {"units": [unit_payload(u) for u in plan.units],
            "diagnostics": to_data(plan.diagnostics)}


def plan_id(plan):
    return "visual_plan:" + exact_signature([plan.planning_signature,
                                            exact_signature(generated_payload(plan))])


def unit_id(parent_id, unit):
    return "visual_unit:" + exact_signature([parent_id, unit.ordinal,
                                            unit.story_unit_ids, unit_payload(unit)])


def shot_id(parent_id, shot):
    return "planned_shot:" + exact_signature([parent_id, shot.ordinal,
                                             shot.story_unit_ids, shot_payload(shot)])


def output_signature(plan):
    data = to_data(plan)
    data.pop("output_signature")
    return exact_signature(data)


def assign_identity(plan):
    """Derive ID-free payload first; never hash a complete plan per child."""
    pid = plan_id(plan)
    units = []
    for unit in plan.units:
        uid = unit_id(pid, unit)
        shots = [replace(s, visual_unit_id=uid, planned_shot_id=shot_id(uid, s))
                 for s in unit.planned_shots]
        units.append(replace(unit, visual_unit_id=uid, planned_shots=shots))
    plan = replace(plan, visual_plan_id=pid, units=units)
    return replace(plan, output_signature=output_signature(plan))
