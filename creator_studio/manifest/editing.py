"""M69 ordered visual evidence. Timing and final use are not established."""
from dataclasses import dataclass, field, replace
from enum import Enum
from .codec import to_data
from .semantic import exact_signature
from .acquisition import AcquisitionOutcome

MAX_EDIT_PLANS = 64
MAX_PLACEMENTS_PER_PLAN = 4096
MAX_TOTAL_HISTORICAL_PLACEMENTS = 65536

class TimingState(str, Enum):
    UNRESOLVED = "UNRESOLVED"

@dataclass(frozen=True)
class EditSpec:
    contract_version: str = "1"
    engine_version: str = "1"
    placement_policy_id: str = "m65_order_preserve_all"
    placement_policy_version: str = "1"
    timing_policy: str = "UNRESOLVED_ONLY"

@dataclass(frozen=True)
class EditPlacement:
    placement_id: str
    ordinal: int
    planned_shot_id: str
    shot_selection_id: str
    acquisition_outcome: AcquisitionOutcome
    materialization_id: str | None = None

@dataclass(frozen=True)
class EditPlan:
    edit_plan_id: str
    acquisition_id: str
    acquisition_output_signature: str
    upstream_binding_signature: str
    input_fingerprint: str
    edit_spec: EditSpec
    edit_signature: str
    timing_state: TimingState
    placements: list[EditPlacement]
    output_signature: str

@dataclass
class EditingState:
    plans: list[EditPlan] = field(default_factory=list)
    active_creator_edit_plan_id: str | None = None

def placement_id(signature, placement):
    return "edit_placement:" + exact_signature([signature, placement.ordinal,
        placement.planned_shot_id, placement.shot_selection_id,
        placement.acquisition_outcome, placement.materialization_id])

def output_signature(plan):
    data = to_data(plan)
    data.pop("output_signature")
    return exact_signature(data)

def assign_identity(plan):
    placements = [replace(p, placement_id=placement_id(plan.edit_signature, p)) for p in plan.placements]
    plan = replace(plan, placements=placements,
        edit_plan_id="edit:" + exact_signature([plan.edit_signature, placements]))
    return replace(plan, output_signature=output_signature(plan))

def complete(plan):
    return all(p.acquisition_outcome == AcquisitionOutcome.MATERIALIZED for p in plan.placements)
