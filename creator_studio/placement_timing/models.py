"""Immutable policy requests and separate current observations."""
from dataclasses import dataclass
from typing import Protocol
from ..manifest.placement_timing import PlacementTimingAcceptanceReceipt

class PlacementTimingError(ValueError):
    CODES = frozenset(("placement_timing_invalid", "placement_timing_stale",
        "placement_timing_gate_required", "placement_timing_gate_failed",
        "placement_timing_capacity", "placement_timing_receipt_invalid"))

    def __init__(self, code="placement_timing_invalid"):
        self.code = code if code in self.CODES else "placement_timing_invalid"
        super().__init__(self.code)

@dataclass(frozen=True)
class PlacementTimingAcceptanceRequest:
    contract_version: str
    edit_plan_id: str
    placement_ids: tuple[str, ...]
    alignment_run_id: str
    narration_revision_id: str
    # Complete primitive canonical projection, encoded into immutable scalar text.
    proposal_json: str
    acceptance_policy_id: str
    acceptance_policy_version: str
    declaration_signature: str
    input_signature: str
    output_signature: str
    request_signature: str

class PlacementTimingAcceptanceGate(Protocol):
    def accept(self, request: PlacementTimingAcceptanceRequest) -> PlacementTimingAcceptanceReceipt: ...

@dataclass(frozen=True)
class PlacementTimingEligibility:
    historical_validity: bool
    active_plan: bool
    current_logical_binding: bool
    current_voice_timing: bool
    expected_spec: bool
    expected_policy: bool
    complete_placement_timing: bool

    @property
    def eligible(self):
        return all((self.historical_validity, self.active_plan,
            self.current_logical_binding, self.current_voice_timing,
            self.expected_spec, self.expected_policy))
