"""Transient observations, never included in Manifest V2."""
from dataclasses import dataclass
from enum import Enum

class AssessmentBoundary(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"

class RenderPreparationError(ValueError):
    def __init__(self):
        super().__init__("render_preparation_invalid")

@dataclass(frozen=True)
class RenderPreparationAssessment:
    current_logically_eligible: bool
    upstream_full_eligibility: bool
    current_narration_usable: bool
    current_visual_media_usable: bool
    deterministic_requirements_satisfied: bool
    renderer_compatibility: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
    executability: AssessmentBoundary = AssessmentBoundary.NOT_ASSESSED
