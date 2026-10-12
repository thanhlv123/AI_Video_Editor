"""Pure retained lineage verification; never consult current pointers or bytes."""
from .codec import check_typed
from .editing import *

def retained_inputs(manifest, acquisition):
    selection = next(s for s in manifest.selection.runs if s.selection_id == acquisition.selection_id)
    retrieval = next(r for r in manifest.retrieval.runs if r.retrieval_id == selection.retrieval_id)
    visual = next(p for p in manifest.visual_planning.plans if p.visual_plan_id == retrieval.visual_plan_id)
    # M66 retains the historical M64/M65 review outputs; current outputs may change.
    binding = exact_signature([retrieval.upstream_binding_signature, retrieval.retrieval_id,
        retrieval.output_signature, selection.selection_id, selection.output_signature,
        acquisition.effective_selection_output_signature])
    return selection, visual, binding

def project_placements(selection, visual, acquisition, control=None):
    shots = [s for u in visual.units for s in u.planned_shots]
    choices, outcomes = selection.shot_selections, acquisition.shot_acquisitions
    if not len(shots) == len(choices) == len(outcomes):
        raise ValueError("editing_coverage_invalid")
    result = []
    for ordinal in range(len(shots)):
        if control is not None:
            control.check()
        shot, choice, outcome = shots[ordinal], choices[ordinal], outcomes[ordinal]
        if shot.planned_shot_id != choice.planned_shot_id or choice.shot_selection_id != outcome.shot_selection_id:
            raise ValueError("editing_lineage_invalid")
        if (outcome.outcome == AcquisitionOutcome.MATERIALIZED) != (outcome.materialization_id is not None):
            raise ValueError("editing_materialization_invalid")
        result.append(EditPlacement("", ordinal, shot.planned_shot_id, choice.shot_selection_id,
            outcome.outcome, outcome.materialization_id))
    return result

def reconstruct(manifest, acquisition, spec, control=None):
    check_typed(EditSpec, spec)
    if spec != EditSpec():
        raise ValueError("editing_spec_invalid")
    if control is not None:
        control.check()
    selection, visual, binding = retained_inputs(manifest, acquisition)
    if control is not None:
        control.check()
    placements = project_placements(selection, visual, acquisition, control)
    if control is not None:
        control.check()
    fingerprint = exact_signature([acquisition.acquisition_id, acquisition.output_signature, binding])
    result = assign_identity(EditPlan("", acquisition.acquisition_id, acquisition.output_signature,
        binding, fingerprint, spec, exact_signature([fingerprint, spec]), TimingState.UNRESOLVED,
        placements, ""))
    if control is not None:
        control.check()
    return result

def editing_errors(manifest):
    try:
        state = manifest.editing
        check_typed(EditingState, state)
        if (len(state.plans) > MAX_EDIT_PLANS
                or sum(len(p.placements) for p in state.plans) > MAX_TOTAL_HISTORICAL_PLACEMENTS
                or any(len(p.placements) > MAX_PLACEMENTS_PER_PLAN for p in state.plans)):
            raise ValueError()
        ids = {p.edit_plan_id for p in state.plans}
        if len(ids) != len(state.plans) or (state.active_creator_edit_plan_id is not None
                and state.active_creator_edit_plan_id not in ids):
            raise ValueError()
        for plan in state.plans:
            acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == plan.acquisition_id)
            if plan != reconstruct(manifest, acquisition, plan.edit_spec):
                raise ValueError()
        return []
    except Exception:
        return ["editing_contract_invalid"]
