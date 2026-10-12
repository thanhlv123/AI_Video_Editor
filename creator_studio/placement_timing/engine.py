"""Atomic M71 proposals and logical binding; never checks source-media bytes."""
from copy import deepcopy
from dataclasses import replace, fields
from ..manifest.codec import to_data, check_typed
from ..manifest.placement_timing import *
from ..manifest.placement_timing_validation import (preflight_record, preflight_history, validate_history,
    validate_plan, validate_receipt, retained_chain, validate_declarations, derive_entries)
from ..manifest.voice_timing_validation import preflight_history as voice_preflight, validate_spec as validate_voice_spec
from ..manifest.voice_timing import AlignmentSpec
from ..manifest.validation import require_valid
from ..manifest.selection import effective_output_signature
from ..manifest.retrieval import output_signature as retrieval_output
from ..manifest.visual_validation import eligible_active_plan
from ..voice_timing.engine import current_timing_eligibility, active_run, active_revision
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import PlacementTimingError, PlacementTimingAcceptanceRequest, PlacementTimingEligibility
from ..manifest.voice_timing_validation import require, identifier

def normalize_dependencies(dependencies):
    """Request one iterator and at most three elements; retain exact order."""
    try:
        iterator = iter(dependencies)
        values = []
        for _ in range(3):
            try:
                value = next(iterator)
            except StopIteration:
                break
            values.append(value)
        normalized_dependencies = tuple(values)
        if normalized_dependencies not in ((), ("edit_planning", "voice_timing")):
            raise PlacementTimingError()
        return normalized_dependencies
    except PlacementTimingError:
        raise
    except Exception:
        raise PlacementTimingError() from None


def preflight(manifest, control=None):
    preflight_history(getattr(manifest, "placement_timing", None), control)
    voice_preflight(getattr(manifest, "voice_timing", None), control)

def active_plan(manifest):
    return next((p for p in manifest.placement_timing.plans if
        p.placement_timing_plan_id == manifest.placement_timing.active_placement_timing_plan_id), None)

def logical_inputs(manifest, control):
    """Separate logical M69 chain, with no acquisition usability dependency."""
    control.check()
    edit = next(p for p in manifest.editing.plans if
        p.edit_plan_id == manifest.editing.active_creator_edit_plan_id)
    alignment, revision = active_run(manifest), active_revision(manifest)
    require(alignment is not None and revision is not None and
        alignment.narration_revision_id == revision.revision_id)
    control.check()
    lineage = retained_chain(manifest, edit, alignment)
    require(lineage.acquisition_id == manifest.acquisition.active_creator_acquisition_id and
        lineage.selection_id == manifest.selection.active_creator_selection_id and
        lineage.retrieval_id == manifest.retrieval.active_creator_retrieval_id and
        lineage.visual_plan_id == manifest.visual_planning.active_creator_plan_id and
        lineage.semantic_document_id == manifest.semantic.active_creator_document_id)
    control.check()
    visual = eligible_active_plan(manifest)
    require(visual is not None and visual.visual_plan_id == lineage.visual_plan_id)
    acquisition = next(r for r in manifest.acquisition.runs if r.acquisition_id == lineage.acquisition_id)
    selection = next(r for r in manifest.selection.runs if r.selection_id == lineage.selection_id)
    retrieval = next(r for r in manifest.retrieval.runs if r.retrieval_id == lineage.retrieval_id)
    require(acquisition.selection_output_signature == selection.output_signature and
        acquisition.effective_selection_output_signature == effective_output_signature(manifest.selection, selection)
        and selection.retrieval_output_signature == retrieval_output(retrieval) and
        retrieval.visual_plan_output_signature == visual.output_signature)
    control.check()
    return edit, alignment, lineage

def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
        for f in fields(before) if f.name != "placement_timing")

def preflight_declarations(allocations, boundaries, control):
    require(type(allocations) in (list, tuple) and type(boundaries) in (list, tuple))
    require(len(allocations) <= MAX_ALLOCATIONS_PER_PLAN and len(boundaries) <= MAX_BOUNDARIES_PER_PLAN)
    counts = {}
    for declarations, cls, limit in ((allocations, PlacementAllocationDeclaration, MAX_ALLOCATIONS_PER_ENTRY),
            (boundaries, PlacementBoundaryDeclaration, MAX_BOUNDARY_DECLARATIONS_PER_ENTRY)):
        counts.clear()
        for d in declarations:
            control.check()
            require(type(d) is cls)
            # Share retained-record field limits before typing/hash/copy operations.
            preflight_record(d, cls, control=control)
            check_typed(cls, d)
            counts[d.placement_id] = counts.get(d.placement_id, 0) + 1
            require(counts[d.placement_id] <= limit)

def runtime_snapshot(spec, allocations, boundaries, policy_id, policy_version,
        dependencies, voice_spec, voice_policy_id, voice_policy_version):
    """Capture bounded scalar tuples before any complete declaration hashing."""
    def scalars(record):
        return tuple(getattr(record, f.name) for f in fields(record))
    return (scalars(spec), tuple(scalars(a) for a in allocations),
        tuple(scalars(b) for b in boundaries), policy_id, policy_version, dependencies,
        None if voice_spec is None else scalars(voice_spec), voice_policy_id, voice_policy_version)

def bounded_payload(plan, reserve=0):
    """Incremental canonical byte accounting before allocating the joined string."""
    preflight_history(PlacementTimingState([plan]))
    return canonical_payload(plan, max_bytes=MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES - reserve)

def request_for(plan):
    preflight_history(PlacementTimingState([plan]))
    payload = canonical_payload(plan, max_bytes=MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES, include_request=True)
    return PlacementTimingAcceptanceRequest("1", plan.edit_plan_id, tuple(plan.placement_ids),
        plan.alignment_run_id, plan.narration_revision_id, payload,
        plan.acceptance_policy_id, plan.acceptance_policy_version,
        plan.declaration_signature, plan.input_signature, plan.output_signature, plan.request_signature)

def current_placement_timing_eligibility(manifest, *, storage, voice_spec=None,
        voice_acceptance_policy_id, voice_acceptance_policy_version, spec=None,
        acceptance_policy_id, acceptance_policy_version, control=None):
    control = control or CancellationToken()
    control.check()
    preflight(manifest, control)
    captured = exact_signature(manifest)
    historical = logical = voice = False
    plan = active_plan(manifest)
    try:
        require_valid(manifest)
        historical = True
        edit, alignment, lineage = logical_inputs(manifest, control)
        logical = plan is not None and ((plan.edit_plan_id, plan.edit_output_signature,
            plan.placement_ids, plan.alignment_run_id, plan.narration_revision_id, plan.lineage) ==
            (edit.edit_plan_id, edit.output_signature, [p.placement_id for p in edit.placements],
            alignment.alignment_run_id, alignment.narration_revision_id, lineage))
        voice = current_timing_eligibility(manifest, storage=storage, spec=voice_spec,
            acceptance_policy_id=voice_acceptance_policy_id,
            acceptance_policy_version=voice_acceptance_policy_version, control=control).eligible
    except Cancelled:
        raise
    except (ValueError, TypeError, AttributeError, StopIteration, KeyError):
        pass
    control.check()
    preflight(manifest, control)
    require(exact_signature(manifest) == captured)
    expected_spec = plan is not None and plan.spec == (spec or PlacementTimingSpec())
    expected_policy = plan is not None and (plan.acceptance_policy_id, plan.acceptance_policy_version) == (
        acceptance_policy_id, acceptance_policy_version)
    eligible = historical and plan is not None and logical and voice and expected_spec and expected_policy
    complete = bool(eligible and plan.placement_ids and plan.receipt is not None and
        all(e.outcome == PlacementTimingOutcome.TIMED for e in plan.entries))
    return PlacementTimingEligibility(historical, plan is not None, logical, voice,
        expected_spec, expected_policy, complete)

def build_placement_timing(manifest, *, storage, allocations=(), explicit_boundaries=(),
        gate=None, spec=None, acceptance_policy_id, acceptance_policy_version,
        voice_spec=None, voice_acceptance_policy_id, voice_acceptance_policy_version,
        control=None, dependencies=(), authorization_recheck=None):
    control = control or CancellationToken()
    normalized_dependencies = normalize_dependencies(dependencies)
    try:
        control.check()
        require(normalized_dependencies in ((), ("edit_planning", "voice_timing")))
        preflight(manifest, control)
        preflight_declarations(allocations, explicit_boundaries, control)
        require_valid(manifest)
        spec = spec if spec is not None else PlacementTimingSpec()
        check_typed(PlacementTimingSpec, spec)
        require(spec == PlacementTimingSpec())
        identifier(acceptance_policy_id)
        identifier(acceptance_policy_version)
        identifier(voice_acceptance_policy_id)
        identifier(voice_acceptance_policy_version)
        validate_voice_spec(voice_spec if voice_spec is not None else AlignmentSpec())
        captured = exact_signature(manifest)
        captured_inputs = runtime_snapshot(spec, allocations, explicit_boundaries,
            acceptance_policy_id, acceptance_policy_version, normalized_dependencies,
            voice_spec, voice_acceptance_policy_id, voice_acceptance_policy_version)
        def recheck():
            control.check()
            preflight(manifest, control)
            preflight_declarations(allocations, explicit_boundaries, control)
            require(exact_signature(manifest) == captured)
            require(captured_inputs == runtime_snapshot(spec, allocations, explicit_boundaries,
                acceptance_policy_id, acceptance_policy_version, normalized_dependencies,
                voice_spec, voice_acceptance_policy_id, voice_acceptance_policy_version))
            logical_inputs(manifest, control)
            if authorization_recheck is not None:
                authorization_recheck()
            # Callback-capable control/authorization checks come first. The last
            # fence is pure and cannot itself introduce a callback mutation window.
            preflight(manifest)
            preflight_declarations(allocations, explicit_boundaries, CancellationToken())
            require(exact_signature(manifest) == captured)
            require(captured_inputs == runtime_snapshot(spec, allocations, explicit_boundaries,
                acceptance_policy_id, acceptance_policy_version, normalized_dependencies,
                voice_spec, voice_acceptance_policy_id, voice_acceptance_policy_version))

        def verify_voice():
            control.check()
            require(current_timing_eligibility(manifest, storage=storage, spec=voice_spec,
                acceptance_policy_id=voice_acceptance_policy_id,
                acceptance_policy_version=voice_acceptance_policy_version, control=control).eligible)
            recheck()

        edit, alignment, lineage = logical_inputs(manifest, control)
        plan = PlacementTimingPlan("", edit.edit_plan_id, edit.output_signature,
            [p.placement_id for p in edit.placements], alignment.alignment_run_id,
            alignment.output_signature, alignment.request_signature, alignment.receipt.receipt_id,
            alignment.narration_revision_id, alignment.inspection.duration_us, lineage,
            spec, list(allocations), list(explicit_boundaries),
            [], [], acceptance_policy_id, acceptance_policy_version)
        text = validate_declarations(manifest, plan, alignment, control)
        entries, unallocated = derive_entries(plan, alignment, text, control)
        plan = replace(plan, entries=entries, unallocated_unit_ids=unallocated)
        preflight_history(PlacementTimingState([plan]), control)
        bounded_plan = replace(plan, declaration_signature="0" * 64,
            input_signature="0" * 64, output_signature="0" * 64,
            request_signature="0" * 64 if allocations or explicit_boundaries else None)
        if allocations or explicit_boundaries:
            request_for(bounded_plan)
        else:
            bounded_payload(bounded_plan)
        plan = replace(plan, spec=deepcopy(spec), allocations=deepcopy(plan.allocations),
            explicit_boundaries=deepcopy(plan.explicit_boundaries))
        plan = replace(plan, declaration_signature=declaration_signature(plan))
        plan = replace(plan, input_signature=input_signature(plan))
        plan = replace(plan, output_signature=output_signature(plan))
        if allocations or explicit_boundaries:
            plan = replace(plan, request_signature=request_signature(plan))
        preflight_history(PlacementTimingState([plan]), control)
        validate_plan(manifest, plan, control, provisional=True)
        request = request_for(plan) if plan.request_signature is not None else None
        captured_plan = exact_signature(plan)
        # Exact ACTIVE-only reuse; processing evidence and artifacts are mandatory.
        active = active_plan(manifest)
        if active is not None and active.input_signature == plan.input_signature:
            require(active.output_signature == plan.output_signature and
                active.declaration_signature == plan.declaration_signature)
            from .stage import PlacementTimingStage
            stage = PlacementTimingStage(storage=storage, allocations=allocations,
                explicit_boundaries=explicit_boundaries, gate=gate, spec=spec,
                acceptance_policy_id=acceptance_policy_id, acceptance_policy_version=acceptance_policy_version,
                voice_spec=voice_spec, voice_acceptance_policy_id=voice_acceptance_policy_id,
                voice_acceptance_policy_version=voice_acceptance_policy_version, dependencies=normalized_dependencies)
            states = [s for s in manifest.processing if s.stage == stage.stage_id]
            require(len(states) == 1 and stage.validate_reuse(manifest, states[0].execution))
            recheck()
            control.check()
            require(exact_signature(manifest) == captured)
            reused = deepcopy(manifest)
            require_valid(reused)
            recheck()
            require(exact_signature(reused) == captured)
            return reused
        # Capacity preflight includes the proposed append, before callback/copy.
        preflight_history(PlacementTimingState(manifest.placement_timing.plans + [plan]), control)
        verify_voice()
        recheck()
        require(exact_signature(plan) == captured_plan)
        if request is not None:
            if gate is None:
                raise PlacementTimingError("placement_timing_gate_required")
            recheck()
            try:
                receipt = gate.accept(request)
            except Cancelled:
                raise
            except Exception:
                raise PlacementTimingError("placement_timing_gate_failed") from None
            control.check()
            plan = replace(plan, receipt=receipt)
            validate_receipt(plan)
            plan = replace(plan, receipt=deepcopy(receipt))
            recheck()
        plan = replace(plan, placement_timing_plan_id=plan_id(plan))
        require(all(p.placement_timing_plan_id != plan.placement_timing_plan_id
            for p in manifest.placement_timing.plans))
        verify_voice()
        proposal = deepcopy(manifest)
        proposal.placement_timing.plans.append(plan)
        proposal.placement_timing.active_placement_timing_plan_id = plan.placement_timing_plan_id
        captured_proposal = exact_signature(proposal)
        control.check()
        validate_history(proposal, control)
        require_valid(proposal)
        require(boundary_unchanged(manifest, proposal))
        recheck()
        verify_voice()
        require(boundary_unchanged(manifest, proposal))
        recheck()
        control.check()
        preflight(manifest)
        preflight_declarations(allocations, explicit_boundaries, CancellationToken())
        require(exact_signature(manifest) == captured)
        require(captured_inputs == runtime_snapshot(spec, allocations, explicit_boundaries,
            acceptance_policy_id, acceptance_policy_version, normalized_dependencies,
            voice_spec, voice_acceptance_policy_id, voice_acceptance_policy_version))
        require(exact_signature(proposal) == captured_proposal)
        return proposal
    except Cancelled:
        raise
    except PlacementTimingError:
        raise
    except Exception:
        raise PlacementTimingError() from None
