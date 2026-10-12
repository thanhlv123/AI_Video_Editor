"""Closed eligibility and retained M67 validation, independent of runtime providers."""
from .codec import check_typed
from .selection import *
from .retrieval import (ShotOutcome, UsageRestriction, Finding, MatchAspect,
    request_payload, metadata_fingerprint, output_signature as retrieval_output)
from .retrieval_validation import candidate_valid, eligible_active_retrieval
from .rights import Rights


def spec_valid(spec):
    try:
        check_typed(SelectionSpec, spec)
        return spec == SelectionSpec()
    except Exception:
        return False


def candidate_eligibility(plan, unit, shot, retrieval, result, candidate, *, candidate_lookup=None):
    """Return None only for proven logical eligibility; never rights authorization.

    MatchEvidence has no exact-identity, polarity, constraint or continuity proof
    semantics. Those obligations fail closed even if an aspect-level MATCH exists.
    Supported SHOW obligations require a MATCH for every exact semantic mention;
    subject identity must explicitly be CATEGORY, never EXACT or UNKNOWN.
    """
    candidate_lookup = candidate_lookup if candidate_lookup is not None else {
        c.candidate_id: c for c in retrieval.candidates}
    if (result.planned_shot_id != shot.planned_shot_id
            or result.visual_unit_id != unit.visual_unit_id
            or candidate.candidate_id not in result.candidate_ids
            or candidate_lookup.get(candidate.candidate_id) != candidate or not candidate_valid(candidate)
            or candidate.metadata_fingerprint != metadata_fingerprint(candidate)
            or candidate.usage_restriction == UsageRestriction.REFERENCE_ONLY
            or candidate.provenance_hint.declared_rights == Rights.REFERENCE_ONLY
            or candidate.visual_media_kind not in request_payload(
                plan, unit, shot, retrieval.retrieval_spec)["allowed_media_kinds"]):
        return SelectionReason.NO_ELIGIBLE_CANDIDATE
    evidence = [e for e in result.assessments if e.candidate_id == candidate.candidate_id]
    if any(e.finding == Finding.CONFLICT for e in evidence):
        return SelectionReason.NO_ELIGIBLE_CANDIDATE
    hard = SelectionReason.HARD_REQUIREMENT_UNVERIFIED
    if (unit.depiction_fidelity.value == "EXACT_LITERAL"
            or unit.representation_mode.value in ("MAP", "DOCUMENT", "TEXTUAL")
            or any(c.strength.value == "REQUIRED" for c in [*unit.constraints, *shot.constraints])
            or any(c.strength.value == "REQUIRED" for c in unit.continuity_requirements)):
        return hard
    for requirement in (unit.geography_requirement, unit.temporal_requirement):
        if requirement is not None and requirement.fidelity.value not in ("NONE", "GENERIC"):
            # UNKNOWN is not evidence that a persisted requirement is optional.
            return hard
    aspects = {"SUBJECT": MatchAspect.SUBJECT, "ACTION": MatchAspect.ACTION,
               "ENVIRONMENT": MatchAspect.ENVIRONMENT}
    for requirement in [*unit.requirements, *shot.requirements]:
        if requirement.treatment.value != "SHOW":
            # Aspect MATCH does not prove symbolic/textual/illustrative treatment.
            return hard
        aspect = aspects.get(requirement.aspect.value)
        if (aspect is None or requirement.identity_fidelity.value == "EXACT"
                or (aspect == MatchAspect.SUBJECT and requirement.identity_fidelity.value != "CATEGORY")
                or not requirement.evidence.mentions):
            return hard
        if any(not any(e.aspect == aspect and e.finding == Finding.MATCH
                       and e.evidence_ref == mention for e in evidence)
               for mention in requirement.evidence.mentions):
            return hard
    # Literal depiction without a target-bound SHOW obligation cannot be proved.
    requirements = [*unit.requirements, *shot.requirements]
    literal_aspect = {"LITERAL_ACTION": "ACTION", "LITERAL_SUBJECT": "SUBJECT"}.get(unit.visual_purpose.value)
    if literal_aspect is not None and not any(
            r.treatment.value == "SHOW" and r.aspect.value == literal_aspect for r in requirements):
        return hard
    if (unit.representation_mode.value == "LITERAL"
            or unit.visual_purpose.value in ("LITERAL_ACTION", "LITERAL_SUBJECT")) and not any(
                r.treatment.value == "SHOW" for r in requirements):
        return hard
    return None


def baseline_choices(plan, retrieval, spec=SelectionSpec(), control=None):
    candidates = {c.candidate_id: c for c in retrieval.candidates}
    mapped = {ShotOutcome.EMPTY: SelectionReason.RETRIEVAL_EMPTY,
              ShotOutcome.UNSUPPORTED: SelectionReason.RETRIEVAL_UNSUPPORTED,
              ShotOutcome.FAILED: SelectionReason.RETRIEVAL_FAILED,
              ShotOutcome.INSUFFICIENT_INTENT: SelectionReason.INSUFFICIENT_INTENT}
    choices = []
    for (unit, shot), result in zip(
            [(u, s) for u in plan.units for s in u.planned_shots], retrieval.shot_results):
        if control is not None:
            control.check()
        selected = None
        reason = mapped.get(result.outcome, SelectionReason.NO_ELIGIBLE_CANDIDATE)
        for cid in result.candidate_ids:
            if control is not None:
                control.check()
            candidate = candidates[cid]
            failure = candidate_eligibility(plan, unit, shot, retrieval, result, candidate,
                                            candidate_lookup=candidates)
            if failure is None:
                selected = SelectedCandidateRef(cid, candidate.metadata_fingerprint)
                reason = SelectionReason.FIRST_ELIGIBLE
                break
            if failure == SelectionReason.HARD_REQUIREMENT_UNVERIFIED:
                reason = failure
        choice = ShotSelection("", shot.planned_shot_id,
            SelectionOutcome.SELECTED if selected else SelectionOutcome.UNRESOLVED,
            selected, SelectionSource.AUTOMATIC, reason)
        choices.append(replace(choice, shot_selection_id=shot_id(retrieval.retrieval_id, spec, choice)))
    return choices


def automatic_projection(manifest, retrieval, spec, control=None):
    """Retained observations only; no history/pointer mutation or provider use."""
    plan = next(p for p in manifest.visual_planning.plans if p.visual_plan_id == retrieval.visual_plan_id)
    choices = baseline_choices(plan, retrieval, spec, control)
    reviews = effective_reviews(manifest.selection)
    protected = []
    for choice in choices:
        if control is not None:
            control.check()
        review = reviews.get(choice.shot_selection_id)
        if review is not None and review.status == ReviewStatus.REJECTED:
            choice = replace(choice, outcome=SelectionOutcome.UNRESOLVED, selected_candidate=None,
                             reason=SelectionReason.CREATOR_REVIEW_REQUIRED)
            choice = replace(choice, shot_selection_id=shot_id(retrieval.retrieval_id, spec, choice))
        protected.append(choice)
    fingerprint = input_fingerprint(retrieval)
    return assign_identity(SelectionRun("", Purpose.CREATOR_STORY, retrieval.retrieval_id,
        retrieval.output_signature, spec, fingerprint, selection_signature(fingerprint, spec),
        protected, [], ""))


def selection_errors(state, retrieval_state, visual_state):
    try:
        check_typed(SelectionState, state)
        if (len(state.runs) > MAX_SELECTION_RUNS or len(state.reviews) > MAX_SELECTION_REVIEWS
                or sum(len(r.shot_selections) for r in state.runs) > MAX_TOTAL_HISTORICAL_SHOT_SELECTIONS
                or any(len(r.shot_selections) > MAX_SHOT_SELECTIONS_PER_RUN
                       or len(r.diagnostics) > MAX_DIAGNOSTICS_PER_LIST for r in state.runs)):
            return ["selection_limit_exceeded"]
        errors = []
        runs = {r.selection_id: r for r in state.runs}
        if len(runs) != len(state.runs):
            errors.append("selection_duplicate_run")
        retrievals = {r.retrieval_id: r for r in retrieval_state.runs}
        plans = {p.visual_plan_id: p for p in visual_state.plans}
        rejected_subjects = {r.shot_selection_id for r in state.reviews if r.status == ReviewStatus.REJECTED}
        subjects = {}
        for run in state.runs:
            retrieval = retrievals.get(run.retrieval_id)
            plan = plans.get(retrieval.visual_plan_id) if retrieval else None
            if retrieval is None or plan is None:
                errors.append("selection_reference_invalid")
                continue
            if (not spec_valid(run.selection_spec) or run.purpose != Purpose.CREATOR_STORY
                    or run.retrieval_output_signature != retrieval_output(retrieval)
                    or run.selection_input_fingerprint != input_fingerprint(retrieval)
                    or run.selection_signature != selection_signature(run.selection_input_fingerprint, run.selection_spec)
                    or run.selection_id != run_id(run) or run.output_signature != output_signature(run)):
                errors.append("selection_signature_mismatch")
            shots = [(u, s) for u in plan.units for s in u.planned_shots]
            if [s.planned_shot_id for s in run.shot_selections] != [s.planned_shot_id for _, s in shots]:
                errors.append("selection_shot_coverage")
            if len({s.shot_selection_id for s in run.shot_selections}) != len(run.shot_selections):
                errors.append("selection_duplicate_choice")
            candidates = {c.candidate_id: c for c in retrieval.candidates}
            expected = baseline_choices(plan, retrieval, run.selection_spec)
            for (unit, shot), result, choice, baseline in zip(shots, retrieval.shot_results, run.shot_selections, expected):
                if choice.shot_selection_id != shot_id(run.retrieval_id, run.selection_spec, choice):
                    errors.append("selection_signature_mismatch")
                subject = [run.retrieval_id, choice_payload(choice)]
                if choice.shot_selection_id in subjects and subjects[choice.shot_selection_id] != subject:
                    errors.append("selection_reference_invalid")
                subjects[choice.shot_selection_id] = subject
                ref = choice.selected_candidate
                if choice.outcome == SelectionOutcome.SELECTED:
                    candidate = candidates.get(ref.candidate_id) if ref else None
                    if (candidate is None or ref.metadata_fingerprint != candidate.metadata_fingerprint
                            or candidate_eligibility(plan, unit, shot, retrieval, result, candidate,
                                                     candidate_lookup=candidates) is not None
                            or choice.reason not in (SelectionReason.FIRST_ELIGIBLE, SelectionReason.CREATOR_CHOICE)
                            or (choice.source == SelectionSource.AUTOMATIC and choice.reason != SelectionReason.FIRST_ELIGIBLE)
                            or (choice.source == SelectionSource.CREATOR and choice.reason != SelectionReason.CREATOR_CHOICE)):
                        errors.append("selection_candidate_invalid")
                elif ref is not None or choice.reason in (SelectionReason.FIRST_ELIGIBLE, SelectionReason.CREATOR_CHOICE):
                    errors.append("selection_outcome_invalid")
                elif choice.source == SelectionSource.AUTOMATIC:
                    if choice.reason == SelectionReason.CREATOR_REVIEW_REQUIRED:
                        if baseline.shot_selection_id not in rejected_subjects:
                            errors.append("selection_review_invalid")
                    elif (baseline.outcome != SelectionOutcome.UNRESOLVED
                          or choice.reason != baseline.reason):
                        errors.append("selection_outcome_invalid")
                elif choice.reason != SelectionReason.CREATOR_REVIEW_REQUIRED:
                    errors.append("selection_outcome_invalid")
        # A predecessor must be the already-seen tip of this exact subject chain.
        # This rejects forks, cycles, forward references and ambiguous roots.
        tips = {}
        seen = set()
        for review in state.reviews:
            if (review.shot_selection_id not in subjects or review.review_id in seen
                    or review.review_id != review_id(review)
                    or review.predecessor_review_id != tips.get(review.shot_selection_id)):
                errors.append("selection_review_invalid")
            seen.add(review.review_id)
            tips[review.shot_selection_id] = review.review_id
        if state.active_creator_selection_id is not None and state.active_creator_selection_id not in runs:
            errors.append("selection_reference_invalid")
        return errors
    except Exception:
        return ["selection_contract_invalid"]


def eligible_active_selection(manifest, required_spec=None, required_retrieval_spec=None,
                              required_visual_spec=None, required_semantic_spec=None):
    from .validation import validate
    if validate(manifest):
        return None
    retrieval = eligible_active_retrieval(manifest, required_retrieval_spec,
                                         required_visual_spec, required_semantic_spec)
    run = next((r for r in manifest.selection.runs
                if r.selection_id == manifest.selection.active_creator_selection_id), None)
    if (retrieval is None or run is None or not spec_valid(run.selection_spec)
            or run.retrieval_id != retrieval.retrieval_id
            or run.retrieval_output_signature != retrieval_output(retrieval)
            or (required_spec is not None and run.selection_spec != required_spec)):
        return None
    expected = automatic_projection(manifest, retrieval, run.selection_spec)
    # Historical structure is separate: authenticate only current automatic shots.
    if any(choice.source == SelectionSource.AUTOMATIC and choice != baseline
           for choice, baseline in zip(run.shot_selections, expected.shot_selections)):
        return None
    return run
