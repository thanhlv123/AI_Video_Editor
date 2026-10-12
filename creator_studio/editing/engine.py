"""Observation-only editing proposals with callback authorization fences."""
from copy import deepcopy
from dataclasses import fields
from ..manifest.editing import *
from ..manifest.editing_validation import reconstruct
from ..manifest.selection import effective_output_signature
from ..manifest.validation import require_valid
from ..manifest.acquisition import AcquisitionSpec
from ..acquisition.engine import current_inputs as acquisition_inputs, current_usability
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import EditingError, EditEligibility


def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
               for f in fields(before) if f.name != "editing")


def current_inputs(manifest, acquisition_spec):
    try:
        selection, _, _ = acquisition_inputs(manifest, acquisition_spec)
        run = next(r for r in manifest.acquisition.runs
                   if r.acquisition_id == manifest.acquisition.active_creator_acquisition_id)
        if (run.selection_id != selection.selection_id or run.acquisition_spec != acquisition_spec
                or run.selection_output_signature != selection.output_signature
                or run.effective_selection_output_signature != effective_output_signature(manifest.selection, selection)):
            raise EditingError("editing_stale")
        return run
    except Cancelled:
        raise
    except EditingError:
        raise
    except Exception:
        raise EditingError("editing_stale") from None


def authorization(manifest, acquisition_spec, edit_spec):
    run = current_inputs(manifest, acquisition_spec)
    plan = reconstruct(manifest, run, edit_spec)
    # Retained evidence is bound without embedding locators or runtime objects.
    return exact_signature([plan, acquisition_spec, evidence(manifest, run)])


def evidence(manifest, run):
    records = {r.materialization_id: r for r in manifest.acquisition.materializations}
    assets = {a.asset_id: a for a in manifest.acquisition.assets}
    return [[mid, exact_signature(records[mid]), exact_signature(assets[records[mid].asset_id])]
            for mid in dict.fromkeys(s.materialization_id for s in run.shot_acquisitions if s.materialization_id)]


def verify_current(manifest, *, storage, inspector, acquisition_spec, edit_spec, control):
    control.check()
    captured = authorization(manifest, acquisition_spec, edit_spec)
    control.check()
    if not current_usability(manifest, storage=storage, inspector=inspector,
                             spec=acquisition_spec, control=control):
        raise EditingError("editing_unusable")
    control.check()
    if authorization(manifest, acquisition_spec, edit_spec) != captured:
        raise EditingError("editing_stale")
    return captured


def build_edit_plan(manifest, *, storage, inspector=None, acquisition_spec=None, spec=None, control=None, dependencies=()):
    control = control or CancellationToken()
    acquisition_spec = deepcopy(acquisition_spec) if acquisition_spec is not None else AcquisitionSpec()
    spec = deepcopy(spec) if spec is not None else EditSpec()
    control.check()
    run = current_inputs(manifest, acquisition_spec)
    initial_authorization = authorization(manifest, acquisition_spec, spec)
    initial_editing = exact_signature(manifest.editing)
    control.check()
    expected = reconstruct(manifest, run, spec, control)
    control.check()
    active = next((p for p in manifest.editing.plans
                   if p.edit_plan_id == manifest.editing.active_creator_edit_plan_id), None)
    retained = next((p for p in manifest.editing.plans if p.edit_plan_id == expected.edit_plan_id), None)
    if retained is not None and (retained != expected or active != retained):
        raise EditingError("editing_collision")
    if retained is None and (len(manifest.editing.plans) >= MAX_EDIT_PLANS
            or len(expected.placements) > MAX_PLACEMENTS_PER_PLAN
            or sum(len(p.placements) for p in manifest.editing.plans) + len(expected.placements)
               > MAX_TOTAL_HISTORICAL_PLACEMENTS):
        raise EditingError("editing_capacity")
    if retained is not None:
        # Logical equality alone cannot authorize active reuse: execution and artifacts are required.
        from .stage import EditPlanningStage
        stage = EditPlanningStage(storage=storage, inspector=inspector,
            acquisition_spec=acquisition_spec, spec=spec, dependencies=dependencies)
        states = [s for s in manifest.processing if s.stage == stage.stage_id]
        control.check()
        if len(states) != 1 or not stage.validate_reuse(manifest, states[0].execution):
            raise EditingError("editing_stale")
        control.check()
        captured = authorization(manifest, acquisition_spec, spec)
    else:
        captured = verify_current(manifest, storage=storage, inspector=inspector,
            acquisition_spec=acquisition_spec, edit_spec=spec, control=control)
    control.check()
    if captured != initial_authorization or exact_signature(manifest.editing) != initial_editing:
        raise EditingError("editing_stale")
    proposal = deepcopy(manifest)
    if retained is None:
        proposal.editing.plans.append(expected)
    proposal.editing.active_creator_edit_plan_id = expected.edit_plan_id
    control.check()
    if not boundary_unchanged(manifest, proposal):
        raise EditingError("editing_boundary_invalid")
    require_valid(proposal)
    control.check()
    if authorization(manifest, acquisition_spec, spec) != captured:
        raise EditingError("editing_stale")
    if not boundary_unchanged(manifest, proposal):
        raise EditingError("editing_boundary_invalid")
    return proposal


def current_edit_eligibility(manifest, *, storage, inspector=None, acquisition_spec=None, spec=None, control=None):
    control = control or CancellationToken()
    acquisition_spec = acquisition_spec or AcquisitionSpec()
    spec = spec or EditSpec()
    captured = verify_current(manifest, storage=storage, inspector=inspector,
        acquisition_spec=acquisition_spec, edit_spec=spec, control=control)
    run = current_inputs(manifest, acquisition_spec)
    expected = reconstruct(manifest, run, spec, control)
    active = next((p for p in manifest.editing.plans
                   if p.edit_plan_id == manifest.editing.active_creator_edit_plan_id), None)
    control.check()
    if active != expected or authorization(manifest, acquisition_spec, spec) != captured:
        raise EditingError("editing_stale")
    return EditEligibility(complete(active))
