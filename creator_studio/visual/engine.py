"""Authoritative deterministic identities and failure-atomic copied proposals."""
from copy import deepcopy
from dataclasses import replace, fields
from ..manifest.codec import check_typed
from ..manifest.validation import require_valid
from ..manifest.semantic_validation import eligible_active_document
from ..manifest.visual import *
from ..manifest.visual_validation import spec_valid, visual_errors
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import VisualPlanningResult, VisualError
from .planner import OfflineStructuralPlanner


def effective_spec(planner=None, options=None):
    planner = planner or OfflineStructuralPlanner()
    spec = PlanningSpec(planner_id=planner.planner_id, planner_version=planner.planner_version,
                        options=deepcopy(options) if options is not None else PlanningOptions())
    if not spec_valid(spec):
        raise VisualError("visual_spec_invalid")
    return spec


def current_document(manifest, required_semantic_spec=None):
    try:
        require_valid(manifest)
    except Exception:
        raise VisualError() from None
    if manifest.semantic.active_creator_document_id is None:
        raise VisualError("visual_semantic_missing")
    d = eligible_active_document(manifest, required_semantic_spec)
    if d is None:
        raise VisualError("visual_semantic_stale")
    if not d.story_units:
        raise VisualError("visual_empty_plan")
    return d


def protected(plan):
    return any(r.status == ReviewStatus.APPROVED or r.locked
               for r in [plan.review, *(u.review for u in plan.units),
                         *(s.review for u in plan.units for s in u.planned_shots)])


def _candidate_fields(candidate, exclude=()):
    return {f.name: deepcopy(getattr(candidate, f.name)) for f in fields(candidate)
            if f.name not in exclude}


def build_visual_plan(manifest, *, planner=None, options=None,
                      required_semantic_spec=None, control=None):
    control = control or CancellationToken()
    control.check()
    proposal = deepcopy(manifest)
    d = current_document(proposal, required_semantic_spec)
    planner = planner or OfflineStructuralPlanner()
    spec = effective_spec(planner, options)
    try:
        result = planner.plan(deepcopy(d), deepcopy(spec.options), control)
    except Cancelled:
        raise
    except Exception:
        raise VisualError("visual_planning_failed") from None
    control.check()
    try:
        check_typed(VisualPlanningResult, result)
        units = []
        for i, u in enumerate(result.units):
            control.check()
            shots = [PlannedShot("", "", j, **_candidate_fields(s))
                     for j, s in enumerate(u.planned_shots)]
            units.append(VisualUnitPlan("", i, **_candidate_fields(u, ("planned_shots",)),
                                        planned_shots=shots))
        fingerprint = semantic_input_fingerprint(d)
        plan = VisualPlan("", d.semantic_document_id, d.output_signature,
            d.content_revision_signature, Purpose.CREATOR_STORY, spec, fingerprint,
            planning_signature(fingerprint, spec), [u.story_unit_id for u in d.story_units],
            units, deepcopy(result.diagnostics), VisualReview(), "")
        plan = assign_identity(plan)
        errors = visual_errors(VisualState([plan], plan.visual_plan_id), proposal.semantic)
        if errors:
            raise VisualError(errors[0])
        active = next((p for p in proposal.visual_planning.plans
                       if p.visual_plan_id == proposal.visual_planning.active_creator_plan_id), None)
        if active is not None and active.visual_plan_id != plan.visual_plan_id and protected(active):
            raise VisualError("visual_review_required")
        existing = next((p for p in proposal.visual_planning.plans
                         if p.visual_plan_id == plan.visual_plan_id), None)
        if existing is not None:
            # IDs encode generated content. Preserve all creator reviews on same-ID execution.
            old_units = {u.visual_unit_id: u for u in existing.units}
            reviewed = []
            for u in plan.units:
                old = old_units[u.visual_unit_id]
                old_shots = {s.planned_shot_id: s for s in old.planned_shots}
                reviewed.append(replace(u, review=old.review,
                    planned_shots=[replace(s, review=old_shots[s.planned_shot_id].review)
                                   for s in u.planned_shots]))
            plan = replace(plan, review=existing.review, units=reviewed)
            plan = replace(plan, output_signature=output_signature(plan))
            proposal.visual_planning.plans = [plan if p.visual_plan_id == plan.visual_plan_id else p
                                             for p in proposal.visual_planning.plans]
        else:
            proposal.visual_planning.plans.append(plan)
        proposal.visual_planning.active_creator_plan_id = plan.visual_plan_id
        require_valid(proposal)
        control.check()
        return proposal
    except (VisualError, Cancelled):
        raise
    except Exception:
        raise VisualError() from None
