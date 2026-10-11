"""ID-free runtime proposals. Authoritative identity belongs to the engine."""

from dataclasses import dataclass, field

from ..manifest.visual import *
from ..manifest.visual_validation import DIAGNOSTIC_CODES


class VisualError(ValueError):
    def __init__(self, code="visual_plan_invalid"):
        self.code = code if code in DIAGNOSTIC_CODES else "visual_plan_invalid"
        super().__init__("Visual planning requires attention.")

@dataclass(frozen=True)
class PlannedShotCandidate:
    story_unit_ids: list[str]
    shot_role: ShotRole = ShotRole.UNKNOWN
    shot_scale_preference: ShotScale = ShotScale.UNKNOWN
    camera_motion_preference: CameraMotion = CameraMotion.UNKNOWN
    media_form_preference: MediaFormPreference = MediaFormPreference.UNKNOWN
    requirements: list[VisualRequirement] = field(default_factory=list)
    constraints: list[VisualConstraint] = field(default_factory=list)
    metadata: PlanningMetadata = field(default_factory=PlanningMetadata)

@dataclass(frozen=True)
class VisualUnitCandidate:
    story_unit_ids: list[str]
    visual_purpose: VisualPurpose = VisualPurpose.UNKNOWN
    representation_mode: RepresentationMode = RepresentationMode.UNKNOWN
    depiction_fidelity: DepictionFidelity = DepictionFidelity.UNKNOWN
    requirements: list[VisualRequirement] = field(default_factory=list)
    geography_requirement: GeographyRequirement | None = None
    temporal_requirement: TemporalRequirement | None = None
    continuity_requirements: list[ContinuityRequirement] = field(default_factory=list)
    constraints: list[VisualConstraint] = field(default_factory=list)
    planned_shots: list[PlannedShotCandidate] = field(default_factory=list)
    metadata: PlanningMetadata = field(default_factory=PlanningMetadata)

@dataclass(frozen=True)
class VisualPlanningResult:
    units: list[VisualUnitCandidate]
    diagnostics: list[VisualDiagnostic] = field(default_factory=list)
