"""Exact-selection acquisition; objects publish before copied manifest proposals."""
from copy import deepcopy
from dataclasses import fields, replace
from ..manifest.acquisition import *
from ..manifest.acquisition_validation import spec_valid
from ..manifest.selection import (SelectionOutcome, ReviewStatus, effective_reviews,
    effective_output_signature, output_signature as selection_output)
from ..manifest.selection_validation import eligible_active_selection, candidate_eligibility
from ..manifest.retrieval import UsageRestriction, metadata_fingerprint
from ..manifest.rights import Rights
from ..manifest.validation import require_valid
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import AcquisitionError
from .provider import AcquisitionRequest, choose_rendition
from .inspector import UnavailableInspector, inspect_media
from .storage import RunBudget


def boundary_unchanged(before, after):
    return all(getattr(before, f.name) == getattr(after, f.name)
               for f in fields(before) if f.name != "acquisition")


def current_inputs(manifest, spec):
    require_valid(manifest)
    if not spec_valid(spec):
        raise AcquisitionError("acquisition_validation_failed")
    selection = eligible_active_selection(manifest)
    if selection is None:
        raise AcquisitionError("acquisition_selection_stale")
    reviews = effective_reviews(manifest.selection)
    if any(reviews[s.shot_selection_id].status == ReviewStatus.REJECTED
           for s in selection.shot_selections if s.shot_selection_id in reviews):
        raise AcquisitionError("acquisition_review_rejected")
    retrieval = next(r for r in manifest.retrieval.runs if r.retrieval_id == selection.retrieval_id)
    plan = next(p for p in manifest.visual_planning.plans if p.visual_plan_id == retrieval.visual_plan_id)
    candidates = {c.candidate_id: c for c in retrieval.candidates}
    shots = [(u, s) for u in plan.units for s in u.planned_shots]
    resolved = []
    for choice, (unit, shot), result in zip(selection.shot_selections, shots, retrieval.shot_results):
        if choice.outcome == SelectionOutcome.UNRESOLVED:
            resolved.append(None)
            continue
        candidate = candidates[choice.selected_candidate.candidate_id]
        if (choice.selected_candidate.metadata_fingerprint != metadata_fingerprint(candidate)
                or candidate_eligibility(plan, unit, shot, retrieval, result, candidate) is not None):
            raise AcquisitionError("acquisition_validation_failed")
        resolved.append(candidate)
    return selection, retrieval, resolved


def preflight(manifest, selection, candidates, spec):
    state = manifest.acquisition
    distinct = len({c.candidate_id for c in candidates if c is not None})
    if (len(state.runs) >= MAX_ACQUISITION_RUNS
            or len(selection.shot_selections) > MAX_SHOT_ACQUISITIONS_PER_RUN
            or sum(len(r.shot_acquisitions) for r in state.runs) + len(selection.shot_selections)
               > MAX_TOTAL_HISTORICAL_SHOT_ACQUISITIONS
            or distinct > spec.max_acquisition_count
            or len(state.materializations) + distinct > MAX_MATERIALIZATIONS
            or len(state.assets) + distinct > MAX_ASSETS):
        raise AcquisitionError("acquisition_limit_exceeded")


def build_acquisition(manifest, *, storage, providers=(), inspector=None, spec=None, control=None):
    control = control or CancellationToken()
    inspector = inspector or UnavailableInspector()
    spec = deepcopy(spec) if spec is not None else AcquisitionSpec()
    control.check()
    selection, retrieval, candidates = current_inputs(manifest, spec)
    preflight(manifest, selection, candidates, spec)
    registered = {}
    for provider in providers:
        if provider.spec not in spec.providers or (provider.spec.provider_id, provider.spec.catalog_namespace) in registered:
            raise AcquisitionError("acquisition_validation_failed")
        registered[(provider.spec.provider_id, provider.spec.catalog_namespace)] = provider
    proposal = deepcopy(manifest)
    immutable = selection_output(selection)
    effective = effective_output_signature(manifest.selection, selection)
    expected_inputs = exact_signature([selection, retrieval, candidates])
    expected_providers = {key: exact_signature(provider.spec) for key, provider in registered.items()}

    def recheck_authorization():
        # Reuse the authoritative path, then bind it to this operation's snapshot.
        # Signatures avoid aliasing mutable lists exposed to provider callbacks.
        try:
            current, current_retrieval, current_candidates = current_inputs(manifest, spec)
            if (manifest.selection.active_creator_selection_id != selection.selection_id
                    or selection_output(current) != immutable
                    or effective_output_signature(manifest.selection, current) != effective
                    or exact_signature([current, current_retrieval, current_candidates]) != expected_inputs
                    or any(exact_signature(provider.spec) != expected_providers[key]
                           or (provider.spec.provider_id, provider.spec.catalog_namespace) != key
                           for key, provider in registered.items())):
                raise AcquisitionError("acquisition_selection_stale")
        except AcquisitionError:
            raise
        except Exception:
            raise AcquisitionError("acquisition_validation_failed") from None

    state = proposal.acquisition
    budget = RunBudget(spec.max_run_bytes)
    acquired, outcomes = {}, []
    for choice, candidate in zip(selection.shot_selections, candidates):
        control.check()
        if candidate is None:
            outcomes.append(ShotAcquisition(choice.shot_selection_id, AcquisitionOutcome.NOT_SELECTED_UPSTREAM))
            continue
        provider = registered.get((candidate.provider_id, candidate.catalog_namespace))
        if (candidate.usage_restriction == UsageRestriction.REFERENCE_ONLY
                or candidate.provenance_hint.declared_rights == Rights.REFERENCE_ONLY
                or (provider is not None and not provider.spec.permits_acquisition)):
            outcomes.append(ShotAcquisition(choice.shot_selection_id, AcquisitionOutcome.RIGHTS_BLOCKED))
            continue
        if provider is None:
            outcomes.append(ShotAcquisition(choice.shot_selection_id, AcquisitionOutcome.UNSUPPORTED_SOURCE))
            continue
        key = (retrieval.retrieval_id, candidate.candidate_id, candidate.metadata_fingerprint, exact_signature(provider.spec))
        if key not in acquired:
            request = AcquisitionRequest(retrieval.retrieval_id, candidate.candidate_id,
                candidate.metadata_fingerprint, candidate.provider_id, candidate.catalog_namespace,
                candidate.provider_candidate_ref)
            try:
                control.check()
                resolved = provider.resolve(request, control)
                control.check()
                chosen = choose_rendition(resolved, candidate.visual_media_kind)
            except Cancelled:
                raise
            except TimeoutError:
                raise AcquisitionError("acquisition_timeout") from None
            except Exception:
                raise AcquisitionError("acquisition_provider_failed") from None
            control.check()
            recheck_authorization()
            try:
                with storage.staging(control, spec.max_asset_bytes, budget) as (path, sink):
                    recheck_authorization()
                    try:
                        result = provider.acquire(chosen.handle, sink, control)
                        control.check()
                        if sink.failure_code:
                            raise AcquisitionError(sink.failure_code)
                        if result is not None:
                            raise AcquisitionError("acquisition_provider_failed")
                    except Cancelled:
                        raise
                    except TimeoutError:
                        raise AcquisitionError("acquisition_timeout") from None
                    except Exception:
                        # Read only the controlled sink state, never provider exception attributes.
                        raise AcquisitionError(sink.failure_code or "acquisition_provider_failed") from None
                    sink.finish()  # Close all writer handles before inspection or installation on Windows.
                    if sink.count == 0:
                        raise AcquisitionError("acquisition_validation_failed")
                    facts = inspect_media(inspector, path, candidate.visual_media_kind, spec, control)
                    digest, count = storage.hash_file(path, control, spec.max_asset_bytes)
                    # Inspection may mutate bytes. Its post-inspection size also obeys aggregate bounds.
                    inspection_growth = max(0, count - sink.count)
                    if budget.used + inspection_growth > spec.max_run_bytes:
                        raise AcquisitionError("acquisition_limit_exceeded")
                    budget.used += inspection_growth
                    asset = storage.finalize(path, digest, count, control)
            except (Cancelled, AcquisitionError):
                raise
            except Exception:
                raise AcquisitionError("acquisition_storage_failed") from None
            control.check()
            record = MaterializationRecord("", retrieval.retrieval_id, candidate.candidate_id,
                candidate.metadata_fingerprint, provider.spec, chosen.observation, facts, asset.asset_id)
            record = replace(record, materialization_id=materialization_id(record))
            for collection, value, name in ((state.assets, asset, "asset_id"),
                                            (state.materializations, record, "materialization_id")):
                existing = next((r for r in collection if getattr(r, name) == getattr(value, name)), None)
                if existing is not None and existing != value:
                    raise AcquisitionError("acquisition_collision")
                if existing is None:
                    collection.append(value)
            acquired[key] = record
        outcomes.append(ShotAcquisition(choice.shot_selection_id, AcquisitionOutcome.MATERIALIZED,
                                       acquired[key].materialization_id))
    control.check()
    recheck_authorization()
    fingerprint = input_fingerprint(selection.selection_id, immutable, effective)
    run = assign_identity(AcquisitionRun("", selection.selection_id, immutable, effective, spec,
        fingerprint, acquisition_signature(fingerprint, spec), outcomes, ""))
    retained = next((r for r in state.runs if r.acquisition_id == run.acquisition_id), None)
    if retained is not None:
        if retained != run or state.active_creator_acquisition_id != run.acquisition_id:
            raise AcquisitionError("acquisition_collision")
    else:
        state.runs.append(run)
    state.active_creator_acquisition_id = run.acquisition_id
    control.check()
    if not boundary_unchanged(manifest, proposal):
        raise AcquisitionError("acquisition_boundary_invalid")
    require_valid(proposal)
    control.check()
    recheck_authorization()
    return proposal


def current_usability(manifest, *, storage, inspector=None, spec=None, control=None):
    """Observe only the explicit active run; never repair, reactivate or prune."""
    control = control or CancellationToken()
    inspector = inspector or UnavailableInspector()
    spec = spec or AcquisitionSpec()
    try:
        selection, _, _ = current_inputs(manifest, spec)
        run = next((r for r in manifest.acquisition.runs
                    if r.acquisition_id == manifest.acquisition.active_creator_acquisition_id), None)
        if (run is None or run.selection_id != selection.selection_id or run.acquisition_spec != spec
                or run.selection_output_signature != selection_output(selection)
                or run.effective_selection_output_signature != effective_output_signature(manifest.selection, selection)):
            return False
        records = {r.materialization_id: r for r in manifest.acquisition.materializations}
        assets = {a.asset_id: a for a in manifest.acquisition.assets}
        for mid in dict.fromkeys(s.materialization_id for s in run.shot_acquisitions if s.materialization_id):
            record = records[mid]
            asset = assets[record.asset_id]
            path = storage.verify(asset, control)
            facts = inspect_media(inspector, path, record.inspection.media_kind, spec, control)
            if facts != record.inspection:
                return False
            storage.verify(asset, control)  # Also reject mutation by a reuse inspector.
        control.check()
        return True
    except Cancelled:
        raise
    except Exception:
        return False
