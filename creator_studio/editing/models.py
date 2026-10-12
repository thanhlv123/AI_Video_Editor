"""Closed M69 runtime errors and distinct readiness observations."""
from dataclasses import dataclass
from ..manifest.editing import TimingState

class EditingError(Exception):
    def __init__(self, code="editing_validation_failed"):
        self.code = code if code in {"editing_validation_failed", "editing_stale",
            "editing_unusable", "editing_capacity", "editing_collision", "editing_boundary_invalid"} else "editing_validation_failed"
        super().__init__(self.code)

@dataclass(frozen=True)
class EditEligibility:
    coverage_complete: bool
    timing_state: TimingState = TimingState.UNRESOLVED
    final_use_readiness: str = "NOT ESTABLISHED"
