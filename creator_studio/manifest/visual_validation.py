"""Pure persistent validation; historical validity is separate from eligibility."""
import math
import re
from .codec import check_typed
from .semantic import Purpose, EntityType, LocationOrigin, exact_signature
from .semantic_validation import eligible_active_document
from .visual import *

DIAGNOSTIC_CODES = frozenset("""visual_semantic_missing visual_semantic_stale
visual_story_unit_missing visual_reference_invalid visual_plan_invalid
visual_signature_mismatch visual_planning_failed visual_review_required
visual_empty_plan visual_constraint_invalid visual_output_stale visual_duplicate_id
visual_purpose_invalid visual_spec_invalid""".split())


def spec_valid(spec):
    try:
        check_typed(PlanningSpec, spec)
        return (spec.visual_contract_version == CONTRACT_VERSION
                and all(re.fullmatch(r"[A-Za-z0-9_.:-]+", x) for x in
                        (spec.engine_version, spec.planner_id, spec.planner_version)))
    except (ValueError, TypeError):
        return False


def visual_errors(state, semantic):
    errors = []
    def fail(code="visual_reference_invalid"):
        errors.append(code)
    try:
        check_typed(VisualState, state)
    except (ValueError, TypeError, AttributeError):
        return ["visual_plan_invalid"]
    documents = {d.semantic_document_id: d for d in semantic.documents}
    seen = set()
    def identity(key):
        if key in seen:
            fail("visual_duplicate_id")
        seen.add(key)
    for plan in state.plans:
        identity(plan.visual_plan_id)
        d = documents.get(plan.semantic_document_id)
        if d is None:
            fail("visual_semantic_missing")
            continue
        if plan.purpose != Purpose.CREATOR_STORY or d.purpose != Purpose.CREATOR_STORY:
            fail("visual_purpose_invalid")
        units = {u.story_unit_id: u for u in d.story_units}
        order = {key: u.ordinal for key, u in units.items()}
        mention_map = {(key, i): m for key, u in units.items()
                       for i, m in enumerate(u.annotations.mentions)}
        def refs(values, allowed, nonempty=True):
            if ((nonempty and not values) or len(values) != len(set(values))
                    or any(v not in allowed or v not in order for v in values)):
                fail("visual_story_unit_missing")
                return False
            ordinals = [order[v] for v in values]
            if any(a >= b for a, b in zip(ordinals, ordinals[1:])):
                fail()
                return False
            return True
        def mention(ref, allowed):
            m = mention_map.get((ref.story_unit_id, ref.mention_ordinal))
            if (ref.story_unit_id not in allowed or m is None
                    or ref.mention_fingerprint != exact_signature(m)):
                fail()
                return None
            return m
        def evidence(e, allowed, required=True):
            refs(e.story_unit_ids, allowed, required)
            evidence_units = set(e.story_unit_ids)
            keys = set()
            for r in e.mentions:
                key = (r.story_unit_id, r.mention_ordinal)
                if key in keys:
                    fail()
                keys.add(key)
                mention(r, evidence_units)
        def metadata(m, explicit=False):
            c = m.confidence
            if c is not None and (type(c) is not float or not math.isfinite(c) or not 0 <= c <= 1):
                fail("visual_plan_invalid")
            if explicit and m.origin == AnnotationOrigin.UNKNOWN:
                fail("visual_constraint_invalid")
        def requirements(values, allowed):
            for r in values:
                evidence(r.evidence, allowed)
                metadata(r.metadata, True)
                if r.identity_fidelity != IdentityFidelity.UNKNOWN and r.aspect != RequirementAspect.SUBJECT:
                    fail("visual_constraint_invalid")
        fidelity_kinds = {ConstraintKind.SHOW_SEMANTIC_TARGET, ConstraintKind.PRESERVE_IDENTITY,
                          ConstraintKind.PRESERVE_LOCATION, ConstraintKind.PRESERVE_TEMPORAL_CONTEXT}
        def constraints(values, allowed, inherited=frozenset()):
            required = set(inherited)
            for c in values:
                evidence(c.evidence, allowed, c.kind in fidelity_kinds)
                metadata(c.metadata, c.kind not in fidelity_kinds)
                if c.kind in fidelity_kinds:
                    if c.polarity != Polarity.REQUIRE:
                        fail("visual_constraint_invalid")
                    if c.target is None:
                        fail("visual_constraint_invalid")
                if c.target is not None:
                    m = mention(c.target, set(c.evidence.story_unit_ids))
                    if m is not None:
                        if c.kind == ConstraintKind.PRESERVE_LOCATION and (m.entity_type != EntityType.PLACE or m.location_origin not in {LocationOrigin.EXPLICIT, LocationOrigin.INFERRED}):
                            fail("visual_constraint_invalid")
                        if c.kind == ConstraintKind.PRESERVE_TEMPORAL_CONTEXT and m.temporal_kind is None:
                            fail("visual_constraint_invalid")
                if c.strength == Strength.REQUIRED:
                    required.add((c.kind, c.polarity))
            if any((k, Polarity.REQUIRE) in required and (k, Polarity.AVOID) in required for k in ConstraintKind):
                fail("visual_constraint_invalid")
            if (ConstraintKind.MOTION, Polarity.REQUIRE) in required and (ConstraintKind.STILLNESS, Polarity.REQUIRE) in required:
                fail("visual_constraint_invalid")
            return required
        if not spec_valid(plan.planning_spec):
            fail("visual_spec_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", plan.semantic_output_signature):
            fail("visual_signature_mismatch")
        if (plan.content_revision_signature != d.content_revision_signature
                or plan.story_unit_ids != list(units)
                or plan.semantic_input_fingerprint != semantic_input_fingerprint(d, captured_output=plan.semantic_output_signature)
                or plan.planning_signature != planning_signature(plan.semantic_input_fingerprint, plan.planning_spec, plan.purpose)):
            fail("visual_signature_mismatch")
        if not plan.units or not units:
            fail("visual_empty_plan")
        covered = set()
        for i, u in enumerate(plan.units):
            identity(u.visual_unit_id)
            refs(u.story_unit_ids, units)
            allowed = set(u.story_unit_ids)
            covered.update(allowed)
            if u.ordinal != i or not u.planned_shots:
                fail("visual_plan_invalid")
            metadata(u.metadata)
            requirements(u.requirements, allowed)
            inherited_constraints = constraints(u.constraints, allowed)
            if u.geography_requirement is not None:
                g = u.geography_requirement
                evidence(g.evidence, allowed)
                if g.fidelity in {GeographyFidelity.EXACT, GeographyFidelity.REGION_COMPATIBLE}:
                    if not g.evidence.mentions:
                        fail()
                    for r in g.evidence.mentions:
                        m = mention(r, allowed)
                        if m is not None and (m.entity_type != EntityType.PLACE or m.location_origin not in {LocationOrigin.EXPLICIT, LocationOrigin.INFERRED}):
                            fail()
            if u.temporal_requirement is not None:
                t = u.temporal_requirement
                evidence(t.evidence, allowed)
                if t.fidelity in {TemporalFidelity.EXACT, TemporalFidelity.APPROXIMATE}:
                    if not t.evidence.mentions:
                        fail()
                    for r in t.evidence.mentions:
                        m = mention(r, allowed)
                        if m is not None and m.temporal_kind is None:
                            fail()
            for c in u.continuity_requirements:
                evidence(c.evidence, units)
                metadata(c.metadata, True)
                if not allowed.intersection(c.evidence.story_unit_ids):
                    fail()
            for j, s in enumerate(u.planned_shots):
                identity(s.planned_shot_id)
                refs(s.story_unit_ids, allowed)
                if s.ordinal != j or s.visual_unit_id != u.visual_unit_id:
                    fail()
                metadata(s.metadata)
                requirements(s.requirements, set(s.story_unit_ids))
                constraints(s.constraints, set(s.story_unit_ids), inherited_constraints)
                if s.planned_shot_id != shot_id(u.visual_unit_id, s):
                    fail("visual_signature_mismatch")
            if u.visual_unit_id != unit_id(plan.visual_plan_id, u):
                fail("visual_signature_mismatch")
        if covered != set(units):
            fail("visual_plan_invalid")
        if any(x.code not in DIAGNOSTIC_CODES for x in plan.diagnostics):
            fail("visual_plan_invalid")
        if plan.visual_plan_id != plan_id(plan) or plan.output_signature != output_signature(plan):
            fail("visual_signature_mismatch")
    selected = state.active_creator_plan_id
    if selected is not None and selected not in {p.visual_plan_id for p in state.plans}:
        fail()
    return errors


def eligible_active_plan(manifest, required_spec=None, required_semantic_spec=None):
    if visual_errors(manifest.visual_planning, manifest.semantic):
        return None
    d = eligible_active_document(manifest, required_semantic_spec)
    p = next((p for p in manifest.visual_planning.plans
              if p.visual_plan_id == manifest.visual_planning.active_creator_plan_id), None)
    if (d is None or p is None or p.purpose != Purpose.CREATOR_STORY
            or p.semantic_document_id != d.semantic_document_id
            or p.semantic_output_signature != d.output_signature
            or p.content_revision_signature != d.content_revision_signature
            or p.semantic_input_fingerprint != semantic_input_fingerprint(d)
            or (required_spec is not None and p.planning_spec != required_spec)):
        return None
    return p
