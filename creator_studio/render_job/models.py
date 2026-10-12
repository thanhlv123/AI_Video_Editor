"""Immutable transient logical contracts; no execution or persistence authority."""
from dataclasses import dataclass
from enum import Enum
from ..manifest.render_preparation import (
    OutputProfile, RenderPreparationSpec, NarrationBinding, RenderTimelineBinding,
    RenderPreparationEntryAssessment, PreparationRequirement, PreparationConclusion,
    UncoveredInterval)
from ..manifest.render_timeline import RenderTimelineEntry, RenderDiagnostic

MAX_VISUAL_ENTRIES = 4096
MAX_REASONS_PER_ENTRY = 16
MAX_PLAN_REASONS = 32
MAX_ID_LENGTH = 96
SIGNATURE_LENGTH = 64
MAX_GENERAL_SCALAR = 256
MAX_CANONICAL_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_TRAVERSAL_DEPTH = 32
MAX_TRAVERSAL_NODES = 2_000_000
MAX_INTEGER = (1 << 63) - 1

class RenderJobError(ValueError):
    def __init__(self):
        super().__init__("render_job_invalid")

class AssessmentBoundary(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"

class LaneReason(str, Enum):
    EMPTY_VISUAL_LANE = "EMPTY_VISUAL_LANE"
    UNRESOLVED_INTERVAL = "UNRESOLVED_INTERVAL"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    INEXACT_START = "INEXACT_START"
    GAP = "GAP"
    OVERLAP = "OVERLAP"
    EXCESS_COVERAGE = "EXCESS_COVERAGE"
    ENDPOINT_MISMATCH = "ENDPOINT_MISMATCH"
    UNSUPPORTED_SOURCE_USE = "UNSUPPORTED_SOURCE_USE"

@dataclass(frozen=True)
class RenderJobBinding:
    render_preparation_plan_id: str
    input_binding_signature: str
    output_profile_signature: str
    render_policy_signature: str
    preparation_signature: str
    output_signature: str

@dataclass(frozen=True)
class RenderVisualClip(RenderTimelineEntry):
    diagnostics: tuple[RenderDiagnostic, ...] = ()

    def __post_init__(self):
        if type(self.diagnostics) is not tuple:
            raise RenderJobError()

@dataclass(frozen=True)
class RenderEntryAssessment(RenderPreparationEntryAssessment):
    requirements: tuple[PreparationRequirement, ...]

    def __post_init__(self):
        if type(self.requirements) is not tuple:
            raise RenderJobError()

@dataclass(frozen=True)
class RenderNarrationInput:
    binding: NarrationBinding

@dataclass(frozen=True)
class RenderSourceBinding:
    acquisition_id: str
    edit_plan_id: str
    edit_output_signature: str
    placement_timing_plan_id: str

@dataclass(frozen=True)
class RenderJobDraft:
    binding: RenderJobBinding
    output_profile: OutputProfile
    spec: RenderPreparationSpec
    timeline_binding: RenderTimelineBinding
    source_binding: RenderSourceBinding
    narration: RenderNarrationInput
    output_duration_us: int
    visual_clips: tuple[RenderVisualClip, ...]
    entry_assessments: tuple[RenderEntryAssessment, ...]
    uncovered_intervals: tuple[UncoveredInterval, ...]
    requirements: tuple[PreparationRequirement, ...]
    conclusion: PreparationConclusion
    lane_reasons: tuple[LaneReason, ...]

    def __post_init__(self):
        if any(type(getattr(self, name)) is not tuple for name in (
                "visual_clips", "entry_assessments", "uncovered_intervals",
                "requirements", "lane_reasons")):
            raise RenderJobError()

@dataclass(frozen=True)
class RenderJobSpec:
    draft: RenderJobDraft

@dataclass(frozen=True)
class RenderJobAssessment:
    structurally_valid: bool
    current_logically_eligible: bool
    preparation_requirements_satisfied: bool
    logical_job_constructible: bool
    renderer_adapter_compatibility: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    executability: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
