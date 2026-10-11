"""Bounded deterministic discovery on copied state; no media acquisition."""
from copy import deepcopy
from dataclasses import replace
from ..manifest.codec import check_typed
from ..manifest.validation import require_valid, ManifestValidationError
from ..manifest.visual_validation import eligible_active_plan
from ..manifest.retrieval import *
from ..manifest.retrieval_validation import (spec_valid, candidate_valid, candidate_fields_valid, identifier,
    DIAGNOSTIC_CODES)
from ..orchestrator.contracts import CancellationToken, Cancelled
from .models import (RetrievalError, ProviderCapabilities, ProviderRetrievalResult)
from .provider import OfflineEmptyProvider
from .requests import build_request, sufficient_intent


def effective_spec(providers, spec=None):
    """All untrusted metadata access, including copies, is controlled here."""
    try:
        base = deepcopy(spec) if spec is not None else RetrievalSpec()
        check_typed(RetrievalSpec, base)
        if not providers:
            raise RetrievalError("retrieval_provider_unavailable")
        if len(providers) > MAX_PROVIDERS:
            raise RetrievalError("retrieval_limit_exceeded")
        descriptors = []
        for provider in providers:
            try:
                caps = deepcopy(provider.capabilities)
                check_typed(ProviderCapabilities, caps)
                descriptor = ProviderSpec(deepcopy(provider.provider_id),
                    deepcopy(provider.provider_version), deepcopy(provider.catalog_namespace),
                    caps.supported_kinds, caps.supports_structured_intent,
                    deepcopy(provider.source_class), deepcopy(provider.request_limit))
            except Exception:
                # Provider exception types and codes are never trusted.
                raise RetrievalError("retrieval_provider_unavailable") from None
            descriptors.append(descriptor)
        if base.providers and base.providers != descriptors:
            raise RetrievalError("retrieval_spec_invalid")
        effective = replace(base, providers=descriptors)
        if not spec_valid(effective):
            raise RetrievalError("retrieval_spec_invalid")
        return effective
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError("retrieval_provider_unavailable") from None


def current_plan(manifest, required_visual_spec=None, required_semantic_spec=None):
    try:
        require_valid(manifest)
    except Exception:
        raise RetrievalError("retrieval_reference_invalid") from None
    if manifest.visual_planning.active_creator_plan_id is None:
        raise RetrievalError("retrieval_visual_missing")
    plan = eligible_active_plan(manifest, required_visual_spec, required_semantic_spec)
    if plan is None:
        raise RetrievalError("retrieval_visual_stale")
    if sum(len(u.planned_shots) for u in plan.units) > MAX_SHOTS:
        raise RetrievalError("retrieval_limit_exceeded")
    return plan


def normalize_batch(result, provider, request):
    """Validate entire bounded batch before accepting any of its observations."""
    check_typed(ProviderRetrievalResult, result)
    if (len(result.candidates) > min(request.provider_request_limit, provider.request_limit)
            or len(result.assessments) > MAX_EVIDENCE * len(result.candidates)
            or len(result.diagnostics) > MAX_DIAGNOSTICS
            or any(d.code not in DIAGNOSTIC_CODES for d in result.diagnostics)):
        raise RetrievalError("retrieval_candidate_invalid")
    if result.outcome != ProviderOutcomeKind.SUCCESS:
        if result.candidates or result.assessments:
            raise RetrievalError("retrieval_candidate_invalid")
        return [], []
    candidates = []
    seen = {}
    for proposal in result.candidates:
        c = CandidateDescriptor("", provider.provider_id, proposal.provider_candidate_ref,
            provider.catalog_namespace, provider.source_class, proposal.visual_media_kind, proposal.label,
            proposal.technical_metadata, proposal.provenance_hint, proposal.usage_restriction, "")
        # Reject locators/credential material before any signature is computed.
        if not candidate_fields_valid(c):
            raise RetrievalError("retrieval_candidate_invalid")
        c = replace(c, candidate_id=candidate_id(c.provider_id, c.catalog_namespace, c.provider_candidate_ref))
        c = replace(c, metadata_fingerprint=metadata_fingerprint(c))
        if not candidate_valid(c) or c.visual_media_kind not in provider.supported_kinds:
            raise RetrievalError("retrieval_candidate_invalid")
        if c.candidate_id in seen and seen[c.candidate_id] != c:
            raise RetrievalError("retrieval_candidate_invalid")
        seen[c.candidate_id] = c
        candidates.append(c)
    evidence = []
    allowed_refs = {(r.story_unit_id, r.mention_ordinal, r.mention_fingerprint)
        for item in [*request.requirements, *request.constraints, *request.continuity,
                     *([request.geography] if request.geography else []),
                     *([request.temporal] if request.temporal else [])]
        for r in item.evidence.mentions}
    counts = {}
    for assessment in result.assessments:
        pos = assessment.candidate_position
        if type(pos) is not int or not 0 <= pos < len(candidates):
            raise RetrievalError("retrieval_reference_invalid")
        e = replace(assessment.evidence, candidate_id=candidates[pos].candidate_id)
        if not identifier(e.method_id) or not identifier(e.method_version):
            raise RetrievalError("retrieval_candidate_invalid")
        if e.evidence_ref is not None:
            r = e.evidence_ref
            if (r.story_unit_id, r.mention_ordinal, r.mention_fingerprint) not in allowed_refs:
                raise RetrievalError("retrieval_reference_invalid")
        counts[e.candidate_id] = counts.get(e.candidate_id, 0) + 1
        if counts[e.candidate_id] > MAX_EVIDENCE:
            raise RetrievalError("retrieval_limit_exceeded")
        evidence.append(e)
    return candidates, evidence


def build_retrieval(manifest, *, providers=None, spec=None, required_visual_spec=None,
                    required_semantic_spec=None, control=None):
    control = control or CancellationToken()
    control.check()
    providers = (OfflineEmptyProvider(),) if providers is None else providers
    effective = effective_spec(providers, spec)
    try:
        proposal = deepcopy(manifest)
        plan = current_plan(proposal, required_visual_spec, required_semantic_spec)
        binding = upstream_binding(proposal, plan)
        fingerprint = input_fingerprint(plan, binding)
        signature = retrieval_signature(fingerprint, effective)
        all_candidates = {}
        observed = {}
        results = []
        outcomes = []
        any_success = False
        attempted = False
        failed = False
        source_order = {s: i for i, s in enumerate(effective.source_precedence)}
        for unit in plan.units:
            for shot in unit.planned_shots:
                control.check()
                request = build_request(plan, unit, shot, effective)
                rsig = request_signature(signature, request)
                shortlist = {}
                assessments = []
                shot_success = False
                shot_failed = False
                shot_diagnostics = []
                intent = sufficient_intent(request)
                if intent:
                    for index, (provider, descriptor) in enumerate(zip(providers, effective.providers)):
                        control.check()
                        if (not descriptor.supports_structured_intent or
                                not set(request.allowed_media_kinds).intersection(descriptor.supported_kinds)):
                            outcomes.append(ProviderOutcome(descriptor.provider_id, shot.planned_shot_id,
                                                            ProviderOutcomeKind.UNSUPPORTED))
                            continue
                        attempted = True
                        try:
                            provider_request = replace(request, provider_request_limit=min(
                                request.provider_request_limit, descriptor.request_limit))
                            response = provider.retrieve(deepcopy(provider_request), control)
                            control.check()
                            response = deepcopy(response)
                            candidates, evidence = normalize_batch(response, descriptor, request)
                            # Cross-shot metadata conflicts invalidate the complete invocation.
                            if any(c.candidate_id in observed and observed[c.candidate_id] != c
                                   for c in candidates):
                                raise RetrievalError("retrieval_candidate_invalid")
                            kind = response.outcome
                            provider_diagnostics = response.diagnostics
                        except Cancelled:
                            raise
                        except Exception:
                            candidates, evidence = [], []
                            kind = ProviderOutcomeKind.FAILED
                            provider_diagnostics = []
                        control.check()
                        diagnostics = ([RetrievalDiagnostic("retrieval_provider_failed")]
                                       if kind == ProviderOutcomeKind.FAILED else provider_diagnostics)
                        outcomes.append(ProviderOutcome(descriptor.provider_id, shot.planned_shot_id,
                                                        kind, diagnostics))
                        if kind == ProviderOutcomeKind.FAILED:
                            failed = shot_failed = True
                            continue
                        if kind == ProviderOutcomeKind.UNSUPPORTED:
                            continue
                        shot_success = any_success = True
                        for c in candidates:
                            observed[c.candidate_id] = c
                        evidence_map = {}
                        for e in evidence:
                            evidence_map.setdefault(e.candidate_id, []).append(e)
                        for position, c in enumerate(candidates):
                            control.check()
                            # Conservative hard filtering: no known conflict is relaxed.
                            if (c.visual_media_kind not in request.allowed_media_kinds or
                                    any(e.finding == Finding.CONFLICT for e in evidence_map.get(c.candidate_id, []))):
                                continue
                            key = (source_order[c.source_class], index, position, c.candidate_id)
                            if c.candidate_id not in shortlist:
                                shortlist[c.candidate_id] = (key, c)
                        assessments.extend(evidence)
                ordered = sorted(shortlist.values(), key=lambda item: item[0])
                if len(ordered) > effective.candidates_per_shot:
                    shot_diagnostics.append(RetrievalDiagnostic("retrieval_limit_exceeded"))
                ordered = ordered[:effective.candidates_per_shot]
                ids = [c.candidate_id for _, c in ordered]
                for _, c in ordered:
                    all_candidates[c.candidate_id] = c
                if len(all_candidates) > effective.total_unique_candidates:
                    raise RetrievalError("retrieval_limit_exceeded")
                if not intent:
                    outcome = ShotOutcome.INSUFFICIENT_INTENT
                    shot_diagnostics.append(RetrievalDiagnostic("retrieval_intent_insufficient"))
                elif ids:
                    outcome = ShotOutcome.CANDIDATES
                elif shot_success:
                    outcome = ShotOutcome.EMPTY
                    shot_diagnostics.append(RetrievalDiagnostic("retrieval_empty"))
                elif shot_failed:
                    outcome = ShotOutcome.FAILED
                else:
                    outcome = ShotOutcome.UNSUPPORTED
                selected = set(ids)
                results.append(ShotRetrievalResult(unit.visual_unit_id, shot.planned_shot_id,
                    list(shot.story_unit_ids), rsig, outcome, ids,
                    [e for e in assessments if e.candidate_id in selected], shot_diagnostics))
        if attempted and not any_success and failed:
            raise RetrievalError("retrieval_provider_failed")
        diagnostics = [RetrievalDiagnostic("retrieval_provider_partial")] if failed else []
        run = assign_identity(RetrievalRun("", Purpose.CREATOR_STORY, plan.visual_plan_id,
            plan.output_signature, binding, effective, fingerprint, signature,
            [all_candidates[k] for k in sorted(all_candidates)], results, outcomes, diagnostics, ""))
        control.check()
        existing = next((r for r in proposal.retrieval.runs if r.retrieval_id == run.retrieval_id), None)
        if existing is not None and existing != run:
            raise RetrievalError("retrieval_signature_mismatch")
        if existing is None:
            proposal.retrieval.runs.append(run)
        proposal.retrieval.active_creator_retrieval_id = run.retrieval_id
        try:
            require_valid(proposal)
        except ManifestValidationError as exc:
            if any(e.code == "retrieval_limit_exceeded" for e in exc.errors):
                raise RetrievalError("retrieval_limit_exceeded") from None
            raise
        control.check()
        return proposal
    except (RetrievalError, Cancelled):
        raise
    except Exception:
        raise RetrievalError("retrieval_candidate_invalid") from None
