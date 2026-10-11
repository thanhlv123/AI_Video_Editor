"""Provider-neutral planning protocol and non-interpretive offline baseline."""
from typing import Protocol
from ..manifest.semantic import SemanticDocument
from ..manifest.visual import PlanningOptions, Purpose
from ..orchestrator.contracts import CancellationToken
from .models import VisualPlanningResult, VisualUnitCandidate, PlannedShotCandidate, VisualError


class VisualPlanner(Protocol):
    planner_id: str
    planner_version: str

    def plan(self, semantic_document: SemanticDocument, options: PlanningOptions,
             control: CancellationToken) -> VisualPlanningResult: ...


class OfflineStructuralPlanner:
    planner_id = "offline_structural"
    planner_version = "1"

    def plan(self, semantic_document, options, control):
        control.check()
        if semantic_document.purpose != Purpose.CREATOR_STORY:
            raise VisualError("visual_purpose_invalid")
        if not semantic_document.story_units:
            raise VisualError("visual_empty_plan")
        units = []
        for u in semantic_document.story_units:
            control.check()
            units.append(VisualUnitCandidate([u.story_unit_id],
                planned_shots=[PlannedShotCandidate([u.story_unit_id])]))
        return VisualPlanningResult(units)
