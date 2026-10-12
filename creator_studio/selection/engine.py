"""Pure copied proposals for logical selection and explicit creator transitions."""
from copy import deepcopy
from dataclasses import fields, replace
from ..manifest.codec import check_typed
from ..manifest.selection import *
from ..manifest.selection_validation import (automatic_projection, spec_valid,
    eligible_active_selection)
from ..manifest.retrieval_validation import eligible_active_retrieval
from ..manifest.validation import require_valid
from ..orchestrator.contracts import CancellationToken
from .models import SelectionError


def current_retrieval(manifest, required_retrieval_spec=None, required_visual_spec=None,
                      required_semantic_spec=None):
    require_valid(manifest)
    run = eligible_active_retrieval(manifest, required_retrieval_spec,
                                   required_visual_spec, required_semantic_spec)
    if run is None:
        raise SelectionError("selection_retrieval_stale")
    return run


def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
               for f in fields(before) if f.name != "selection")


def finish(before, proposal, control):
    if not boundary_unchanged(before, proposal):
        raise SelectionError("selection_boundary_invalid")
    require_valid(proposal)
    control.check()
    return proposal


def publish(proposal, run, *, automatic):
    state = proposal.selection
    active = next((r for r in state.runs if r.selection_id == state.active_creator_selection_id), None)
    if automatic and active is not None:
        subjects = {s.shot_selection_id for s in run.shot_selections}
        reviews = effective_reviews(state)
        for old in active.shot_selections:
            review = reviews.get(old.shot_selection_id)
            if (review is not None and (review.locked or review.status != ReviewStatus.REJECTED)
                    and old.shot_selection_id not in subjects):
                raise SelectionError("selection_review_required")
    retained = next((r for r in state.runs if r.selection_id == run.selection_id), None)
    if retained is not None:
        if retained != run or retained.selection_id != state.active_creator_selection_id:
            # No historical reactivation, including self-consistent manual collisions.
            raise SelectionError("selection_review_required")
    else:
        if len(state.runs) >= MAX_SELECTION_RUNS:
            raise SelectionError("selection_limit_exceeded")
        state.runs.append(run)
    state.active_creator_selection_id = run.selection_id


def build_selection(manifest, *, spec=None, required_retrieval_spec=None,
                    required_visual_spec=None, required_semantic_spec=None, control=None):
    control = control or CancellationToken()
    control.check()
    proposal = deepcopy(manifest)
    spec = deepcopy(spec) if spec is not None else SelectionSpec()
    if not spec_valid(spec):
        raise SelectionError("selection_spec_invalid")
    retrieval = current_retrieval(proposal, required_retrieval_spec,
                                 required_visual_spec, required_semantic_spec)
    run = automatic_projection(proposal, retrieval, spec, control)
    control.check()
    publish(proposal, run, automatic=True)
    return finish(manifest, proposal, control)


def append_review(manifest, *, expected_selection_id, expected_choice, expected_predecessor,
                  status, locked, control=None):
    """Explicit transition for an exact active subject; not creator authentication."""
    control = control or CancellationToken()
    control.check()
    proposal = deepcopy(manifest)
    require_valid(proposal)
    run = next((r for r in proposal.selection.runs if r.selection_id == expected_selection_id), None)
    if (run is None or proposal.selection.active_creator_selection_id != expected_selection_id
            or expected_choice not in run.shot_selections):
        raise SelectionError("selection_expected_state_mismatch")
    tip = effective_reviews(proposal.selection).get(expected_choice.shot_selection_id)
    if expected_predecessor != (tip.review_id if tip else None):
        raise SelectionError("selection_expected_state_mismatch")
    review = SelectionReview("", expected_choice.shot_selection_id, expected_predecessor, status, locked)
    check_typed(SelectionReview, review)
    review = replace(review, review_id=review_id(review))
    if len(proposal.selection.reviews) >= MAX_SELECTION_REVIEWS:
        raise SelectionError("selection_limit_exceeded")
    proposal.selection.reviews.append(review)
    return finish(manifest, proposal, control)


def replace_choice(manifest, *, expected_selection_id, expected_effective_output_signature,
                   expected_choice, replacement_choice, control=None):
    """Targeted creator operation; exact previous run, review state and choice required.

    The supplied replacement is a complete identity-bound choice. Historical runs
    and reviews remain intact. No approval/lock transfers to a changed subject.
    """
    control = control or CancellationToken()
    control.check()
    proposal = deepcopy(manifest)
    run = eligible_active_selection(proposal)
    if (run is None or run.selection_id != expected_selection_id
            or expected_effective_output_signature != effective_output_signature(proposal.selection, run)
            or expected_choice not in run.shot_selections
            or replacement_choice.planned_shot_id != expected_choice.planned_shot_id):
        raise SelectionError("selection_expected_state_mismatch")
    check_typed(ShotSelection, replacement_choice)
    if (replacement_choice.source != SelectionSource.CREATOR
            or replacement_choice.shot_selection_id != shot_id(run.retrieval_id, run.selection_spec, replacement_choice)
            or choice_payload(replacement_choice) == choice_payload(expected_choice)):
        raise SelectionError("selection_expected_state_mismatch")
    choices = [replacement_choice if s == expected_choice else s for s in run.shot_selections]
    changed = assign_identity(replace(run, shot_selections=choices))
    control.check()
    publish(proposal, changed, automatic=False)
    return finish(manifest, proposal, control)
