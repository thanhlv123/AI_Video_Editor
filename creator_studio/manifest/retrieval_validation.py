"""Pure M66 validation; historical structure and current eligibility are separate."""
import math
import re
import unicodedata
from .codec import check_typed
from .retrieval import *
from .visual_validation import eligible_active_plan

DIAGNOSTIC_CODES = frozenset("""retrieval_visual_missing retrieval_visual_stale
retrieval_shot_missing retrieval_spec_invalid retrieval_provider_unavailable
retrieval_provider_failed retrieval_provider_partial retrieval_empty
retrieval_intent_insufficient retrieval_candidate_invalid retrieval_reference_invalid
retrieval_signature_mismatch retrieval_output_stale retrieval_limit_exceeded
retrieval_cancelled""".split())


def public_text(value, limit=256, optional=False):
    if value is None:
        return optional
    if type(value) is not str or not 0 < len(value) <= limit or value.strip() != value:
        return False
    # Public descriptor strings must never carry locators or credential material.
    lowered = value.casefold()
    return (not any(unicodedata.category(c) in {"Cc", "Cs", "Cf"} for c in value)
            and not any(x in lowered for x in ("://", "www.", "authorization", "bearer",
                "cookie", "token", "secret", "api_key", "apikey", "password", "session",
                "signature=", "sk-", "sk_", "ghp_", "github_pat_", "eyj", "akia",
                "?", "&", "=", "\\", "/")))


MAX_ASSET_NAMESPACE_LENGTH = 24
MAX_PUBLIC_ASSET_ID_LENGTH = 48
MAX_CATALOG_NAMESPACE_LENGTH = 48
RESERVED_LOCATOR_SCHEMES = frozenset({
    "http", "https", "file", "ftp", "s3", "gs", "data", "blob", "javascript",
    "ftps", "sftp", "ssh", "smb", "mailto", "urn", "ws", "wss",
})
# Reject explicit credential marker structures, not arbitrary substrings.
_CREDENTIAL_PREFIX = re.compile(
    r"(?:bearer|token|secret|password|api[_-]?key|authorization|session)(?:[_.-]|[0-9])"
    r"|(?:sk|ghp|github_pat|AKIA)[_-]", re.IGNORECASE)


def public_identifier(value, limit):
    return (type(value) is str and 0 < len(value) <= limit
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None
            and _CREDENTIAL_PREFIX.match(value) is None)


def catalog_namespace_valid(value):
    return (public_identifier(value, MAX_CATALOG_NAMESPACE_LENGTH)
            and value[0].isascii() and value[0].isalpha()
            and value.casefold() not in RESERVED_LOCATOR_SCHEMES)


def logical_ref(value):
    if type(value) is not str or value.count(":") != 1:
        return False
    namespace, reference = value.split(":")
    return (0 < len(namespace) <= MAX_ASSET_NAMESPACE_LENGTH
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", namespace) is not None
            and len(namespace) > 1  # Exclude Windows drive prefixes.
            and namespace.casefold() not in RESERVED_LOCATOR_SCHEMES
            and _CREDENTIAL_PREFIX.match(namespace) is None
            and public_identifier(reference, MAX_PUBLIC_ASSET_ID_LENGTH))


def diagnostic_code(code):
    """Only internal allowlisted strings may enter persistent stage state."""
    return code if type(code) is str and code in DIAGNOSTIC_CODES else "retrieval_candidate_invalid"


def identifier(value):
    return public_text(value, 128) and bool(re.fullmatch(r"[A-Za-z0-9_.:-]+", value))


def spec_valid(spec):
    try:
        check_typed(RetrievalSpec, spec)
        if (spec.contract_version != "1" or spec.engine_version != "1"
                or spec.ordering_policy_version != "1"
                or not all(identifier(x) for x in (spec.retriever_id, spec.retriever_version))
                or not 1 <= len(spec.providers) <= MAX_PROVIDERS
                or len({p.provider_id for p in spec.providers}) != len(spec.providers)
                or len(spec.source_precedence) != len(SourceClass)
                or set(spec.source_precedence) != set(SourceClass)
                or not spec.allowed_media_kinds
                or VisualMediaKind.UNKNOWN in spec.allowed_media_kinds
                or len(set(spec.allowed_media_kinds)) != len(spec.allowed_media_kinds)
                or not 1 <= spec.provider_candidate_limit <= MAX_PROVIDER_CANDIDATES
                or not 1 <= spec.candidates_per_shot <= MAX_SHORTLIST
                or not 1 <= spec.total_unique_candidates <= MAX_CANDIDATES):
            return False
        return all(all(identifier(x) for x in (p.provider_id, p.provider_version))
                   and catalog_namespace_valid(p.catalog_namespace)
                   and 1 <= p.request_limit <= MAX_PROVIDER_CANDIDATES
                   and len(set(p.supported_kinds)) == len(p.supported_kinds)
                   and VisualMediaKind.UNKNOWN not in p.supported_kinds
                   for p in spec.providers)
    except Exception:
        return False


def candidate_fields_valid(c):
    try:
        check_typed(CandidateDescriptor, c)
        t = c.technical_metadata
        return (identifier(c.provider_id) and logical_ref(c.provider_candidate_ref)
            and catalog_namespace_valid(c.catalog_namespace)
            and public_text(c.label, optional=True)
            and public_text(c.provenance_hint.license_identifier, optional=True)
            and public_text(c.provenance_hint.attribution, optional=True)
            and ((t.width is None and t.height is None) or
                 (type(t.width) is int and type(t.height) is int and t.width > 0 and t.height > 0))
            and (t.source_duration_seconds is None or
                 (type(t.source_duration_seconds) in (float, int)
                  and math.isfinite(t.source_duration_seconds) and t.source_duration_seconds > 0))
            and (c.visual_media_kind not in (VisualMediaKind.IMAGE, VisualMediaKind.GRAPHIC)
                 or t.source_duration_seconds is None))
    except Exception:
        return False


def candidate_valid(c):
    return (candidate_fields_valid(c)
            and c.candidate_id == candidate_id(c.provider_id, c.catalog_namespace, c.provider_candidate_ref)
            and c.metadata_fingerprint == metadata_fingerprint(c))


def retrieval_errors(state, visual, semantic):
    errors = []
    def fail(code="retrieval_reference_invalid"):
        errors.append(code)
    try:
        check_typed(RetrievalState, state)
        if (len(state.runs) > MAX_RUNS
                or sum(len(r.candidates) for r in state.runs) > MAX_HISTORY_CANDIDATES
                or sum(len(r.shot_results) for r in state.runs) > MAX_HISTORY_SHOTS):
            return ["retrieval_limit_exceeded"]
        plans = {p.visual_plan_id: p for p in visual.plans}
        documents = {d.semantic_document_id: d for d in semantic.documents}
        sources = {s.source_revision_id: s for s in semantic.source_revisions}
        ids = set()
        for run in state.runs:
            if run.retrieval_id in ids:
                fail()
            ids.add(run.retrieval_id)
            plan = plans.get(run.visual_plan_id)
            if plan is None:
                fail("retrieval_visual_missing")
                continue
            spec = run.retrieval_spec
            if not spec_valid(spec):
                fail("retrieval_spec_invalid")
                continue
            # Captured output may precede a review update; historical binding stays valid.
            if not all(re.fullmatch(r"[0-9a-f]{64}", x) for x in (
                    run.visual_plan_output_signature, run.upstream_binding_signature,
                    run.retrieval_input_fingerprint)):
                fail("retrieval_signature_mismatch")
            if (run.purpose != Purpose.CREATOR_STORY or
                    run.retrieval_signature != retrieval_signature(run.retrieval_input_fingerprint, spec)):
                fail("retrieval_signature_mismatch")
            document = documents.get(plan.semantic_document_id)
            source = sources.get(document.source_revision_id) if document else None
            if document is None or source is None:
                fail()
                continue
            binding = exact_signature([plan.visual_plan_id, run.visual_plan_output_signature,
                document.semantic_document_id, plan.semantic_output_signature,
                document.analysis_signature, document.content_revision_signature,
                source.source_revision_id, exact_signature(source.content)])
            captured = replace(plan, output_signature=run.visual_plan_output_signature)
            if (run.upstream_binding_signature != binding or
                    run.retrieval_input_fingerprint != input_fingerprint(captured, binding)):
                fail("retrieval_signature_mismatch")
            if len(run.candidates) > spec.total_unique_candidates or len(run.shot_results) > MAX_SHOTS:
                fail("retrieval_limit_exceeded")
            candidates = {c.candidate_id: c for c in run.candidates}
            providers = {p.provider_id: p for p in spec.providers}
            if list(candidates) != sorted(candidates) or len(candidates) != len(run.candidates):
                fail("retrieval_candidate_invalid")
            for c in run.candidates:
                p = providers.get(c.provider_id)
                if (not candidate_valid(c) or p is None or c.catalog_namespace != p.catalog_namespace
                        or c.source_class != p.source_class
                        or c.visual_media_kind not in p.supported_kinds
                        or c.visual_media_kind not in spec.allowed_media_kinds):
                    fail("retrieval_candidate_invalid")
            shots = [(u, s) for u in plan.units for s in u.planned_shots]
            if len(shots) != len(run.shot_results):
                fail("retrieval_shot_missing")
            used = set()
            evidence_refs = {s.planned_shot_id: {(r.story_unit_id, r.mention_ordinal, r.mention_fingerprint)
                for e in [*u.requirements, *s.requirements,
                    *u.constraints, *s.constraints, *u.continuity_requirements,
                    *([u.geography_requirement] if u.geography_requirement else []),
                    *([u.temporal_requirement] if u.temporal_requirement else [])]
                for r in e.evidence.mentions} for u, s in shots}
            def diagnostics(values):
                if len(values) > MAX_DIAGNOSTICS or any(d.code not in DIAGNOSTIC_CODES for d in values):
                    fail("retrieval_candidate_invalid")
            for (u, s), result in zip(shots, run.shot_results):
                if (result.visual_unit_id != u.visual_unit_id or result.planned_shot_id != s.planned_shot_id
                        or result.story_unit_ids != s.story_unit_ids):
                    fail("retrieval_shot_missing")
                captured = replace(plan, output_signature=run.visual_plan_output_signature)
                if result.request_signature != request_signature(run.retrieval_signature,
                        request_payload(captured, u, s, spec)):
                    fail("retrieval_signature_mismatch")
                refs = result.candidate_ids
                if (len(refs) != len(set(refs)) or any(c not in candidates for c in refs)
                        or len(refs) > spec.candidates_per_shot
                        or (bool(refs) != (result.outcome == ShotOutcome.CANDIDATES))):
                    fail()
                allowed = request_payload(plan, u, s, spec)["allowed_media_kinds"]
                if any(candidates[c].visual_media_kind not in allowed for c in refs if c in candidates):
                    fail("retrieval_candidate_invalid")
                used.update(refs)
                if len(result.assessments) > MAX_EVIDENCE * len(refs):
                    fail("retrieval_limit_exceeded")
                for e in result.assessments:
                    if (e.candidate_id not in refs or not identifier(e.method_id)
                            or not identifier(e.method_version) or e.finding == Finding.CONFLICT):
                        fail()
                    if e.evidence_ref is not None:
                        r = e.evidence_ref
                        if (r.story_unit_id, r.mention_ordinal, r.mention_fingerprint) not in evidence_refs[s.planned_shot_id]:
                            fail()
                counts = {}
                for e in result.assessments:
                    counts[e.candidate_id] = counts.get(e.candidate_id, 0) + 1
                if any(count > MAX_EVIDENCE for count in counts.values()):
                    fail("retrieval_limit_exceeded")
                diagnostics(result.diagnostics)
            if used != set(candidates):
                fail("retrieval_candidate_invalid")
            pairs = set()
            outcome_map = {}
            shot_providers = {}
            expected_pairs = []
            shot_ids = {s.planned_shot_id for _, s in shots}
            for o in run.provider_outcomes:
                pair = (o.provider_id, o.planned_shot_id)
                if o.provider_id not in providers or o.planned_shot_id not in shot_ids or pair in pairs:
                    fail()
                pairs.add(pair)
                outcome_map[pair] = o.outcome
                shot_providers.setdefault(o.planned_shot_id, set()).add(pair)
                diagnostics(o.diagnostics)
            if len(run.provider_outcomes) > len(shots) * len(providers):
                fail("retrieval_limit_exceeded")
            for (u, s), result in zip(shots, run.shot_results):
                payload = request_payload(plan, u, s, spec)
                expected = {(p.provider_id, s.planned_shot_id) for p in spec.providers}
                actual = shot_providers.get(s.planned_shot_id, set())
                if has_intent(payload):
                    expected_pairs.extend((p.provider_id, s.planned_shot_id) for p in spec.providers)
                    if actual != expected:
                        fail()
                elif actual or result.outcome != ShotOutcome.INSUFFICIENT_INTENT:
                    fail()
                values = [outcome_map.get((p.provider_id, s.planned_shot_id)) for p in spec.providers]
                expected_outcome = (ShotOutcome.INSUFFICIENT_INTENT if not has_intent(payload) else
                    ShotOutcome.CANDIDATES if result.candidate_ids else
                    ShotOutcome.EMPTY if ProviderOutcomeKind.SUCCESS in values else
                    ShotOutcome.FAILED if ProviderOutcomeKind.FAILED in values else ShotOutcome.UNSUPPORTED)
                if result.outcome != expected_outcome:
                    fail()
                for cid in result.candidate_ids:
                    if cid in candidates and outcome_map.get((candidates[cid].provider_id,
                            s.planned_shot_id)) != ProviderOutcomeKind.SUCCESS:
                        fail()
            if [(o.provider_id, o.planned_shot_id) for o in run.provider_outcomes] != expected_pairs:
                fail()
            if pairs and not any(o.outcome == ProviderOutcomeKind.SUCCESS for o in run.provider_outcomes):
                if any(o.outcome == ProviderOutcomeKind.FAILED for o in run.provider_outcomes):
                    fail("retrieval_provider_failed")
            diagnostics(run.diagnostics)
            if run.retrieval_id != run_id(run) or run.output_signature != output_signature(run):
                fail("retrieval_signature_mismatch")
        if state.active_creator_retrieval_id is not None and state.active_creator_retrieval_id not in ids:
            fail()
    except Exception:
        fail("retrieval_candidate_invalid")
    return errors


def eligible_active_retrieval(manifest, required_spec=None, required_visual_spec=None,
                              required_semantic_spec=None):
    if retrieval_errors(manifest.retrieval, manifest.visual_planning, manifest.semantic):
        return None
    p = eligible_active_plan(manifest, required_visual_spec, required_semantic_spec)
    r = next((r for r in manifest.retrieval.runs
              if r.retrieval_id == manifest.retrieval.active_creator_retrieval_id), None)
    if (p is None or r is None or r.visual_plan_id != p.visual_plan_id
            or r.visual_plan_output_signature != p.output_signature
            or r.upstream_binding_signature != upstream_binding(manifest, p)
            or r.retrieval_input_fingerprint != input_fingerprint(p, upstream_binding(manifest, p))
            or (required_spec is not None and r.retrieval_spec != required_spec)):
        return None
    return r
