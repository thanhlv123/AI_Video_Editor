"""Transient M72 observations, separate from retained source-use authority."""
from dataclasses import dataclass

class RenderTimelineError(ValueError):
    def __init__(self):
        super().__init__("render_timeline_invalid")

@dataclass(frozen=True)
class RenderTimelineEligibility:
    historical_validity: bool
    current_logical_binding: bool
    current_placement_timing: bool
    expected_spec: bool
    complete_render_timeline: bool

    @property
    def eligible(self):
        return all((self.historical_validity, self.current_logical_binding,
            self.current_placement_timing, self.expected_spec))
