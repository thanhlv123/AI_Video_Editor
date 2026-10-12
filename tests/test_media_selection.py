"""M67 offline contracts, adversarial integrity, creator protection and regressions."""
import ast
from copy import deepcopy
from dataclasses import fields, replace
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, validate, save, load
from creator_studio.manifest.codec import decode, to_data
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.models import (ProcessingState, Status, Rights as ModelRights,
    MediaReference, Provenance, Scene, Voice, SubtitleTrack, SubtitleSegment,
    AudioReference, TimelineReference)
from creator_studio.manifest.rights import Rights
from creator_studio.manifest.semantic import ReviewStatus
from creator_studio.manifest.selection import *
from creator_studio.manifest.selection_validation import (
    baseline_choices, candidate_eligibility, eligible_active_selection, selection_errors)
from creator_studio.manifest.retrieval import (
    ShotOutcome, CandidateDescriptor, CandidateTechnicalMetadata, ProvenanceHint,
    UsageRestriction, SourceClass, VisualMediaKind, MatchEvidence, MatchAspect, Finding,
    assign_identity as retrieval_identity, candidate_id, metadata_fingerprint)
from creator_studio.manifest.visual import (
    assign_identity as visual_identity, output_signature as visual_output,
    VisualReview, DepictionFidelity, RepresentationMode, VisualRequirement,
    RequirementAspect, Evidence, PlanningMetadata, PlanningTreatment, IdentityFidelity,
    GeographyRequirement, GeographyFidelity, TemporalRequirement, TemporalFidelity,
    TemporalDimension, VisualConstraint, ConstraintKind, Strength, Polarity,
    ContinuityRequirement, ContinuityKind, ShotScale, CameraMotion, MediaFormPreference,
    SemanticMentionRef)
from creator_studio.manifest.visual import VisualPurpose
from creator_studio.manifest.semantic import (AnnotationOrigin, Mention, SourceSpan,
    SemanticAnnotations, Derivation, story_unit_id, document_id,
    output_signature as semantic_output)
from creator_studio.manifest.signatures import dependency_signature
from creator_studio.selection.engine import (
    build_selection, append_review, replace_choice, automatic_projection, boundary_unchanged)
from creator_studio.selection.models import SelectionError, ERROR_CODES
from creator_studio.selection.stage import MediaSelectionStage
from creator_studio.orchestrator.contracts import (
    CancellationToken, Cancelled, StageContext, StageStatus, ReadinessKind)
from creator_studio.orchestrator import ProjectOrchestrator, ManifestRepository
from creator_studio.retrieval.engine import build_retrieval
from creator_studio.retrieval.models import CandidateProposal, ProviderRetrievalResult, ProposalAssessment
from creator_studio.retrieval.stage import MediaRetrievalStage
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.visual.engine import build_visual_plan
from tests.test_semantic_story import content
from tests.test_media_retrieval import SyntheticProvider, active_run as retrieval_run, active_plan, with_intent


def active(m):
    return next(r for r in m.selection.runs if r.selection_id == m.selection.active_creator_selection_id)


def selected_fixture(intent, proposals=None):
    proposals = proposals if proposals is not None else [
        CandidateProposal("video:first", VisualMediaKind.VIDEO),
        CandidateProposal("video:second", VisualMediaKind.VIDEO)]
    return build_selection(build_retrieval(intent, providers=(SyntheticProvider(
        ProviderRetrievalResult(proposals)),)))


def install(m, run, resign=True):
    m = deepcopy(m)
    run = assign_identity(run) if resign else run
    m.selection.runs = [run]
    m.selection.active_creator_selection_id = run.selection_id
    return m


class CountingControl:
    def __init__(self, stop=None):
        self.count = 0
        self.stop = stop

    def check(self):
        self.count += 1
        if self.count == self.stop:
            raise Cancelled()


class MediaSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = build_visual_plan(build_semantic_story(content()))
        cls.intent = with_intent(cls.baseline)
        cls.built = selected_fixture(cls.intent)

    def review(self, m=None, status=ReviewStatus.APPROVED, locked=False, choice=None):
        m = m or self.built
        run = active(m)
        choice = choice or run.shot_selections[0]
        tip = effective_reviews(m.selection).get(choice.shot_selection_id)
        return append_review(m, expected_selection_id=run.selection_id,
            expected_choice=choice, expected_predecessor=tip.review_id if tip else None,
            status=status, locked=locked)

    def replacement(self, m, *, unresolved=False):
        run = active(m)
        old = run.shot_selections[0]
        r = retrieval_run(m)
        candidate = next(c for c in r.candidates if c.candidate_id != old.selected_candidate.candidate_id)
        new = replace(old, source=SelectionSource.CREATOR,
            outcome=SelectionOutcome.UNRESOLVED if unresolved else SelectionOutcome.SELECTED,
            selected_candidate=None if unresolved else SelectedCandidateRef(candidate.candidate_id, candidate.metadata_fingerprint),
            reason=SelectionReason.CREATOR_REVIEW_REQUIRED if unresolved else SelectionReason.CREATOR_CHOICE)
        return replace(new, shot_selection_id=shot_id(run.retrieval_id, run.selection_spec, new))

    def replace(self, m, replacement=None, **overrides):
        run = active(m)
        args = dict(expected_selection_id=run.selection_id,
            expected_effective_output_signature=effective_output_signature(m.selection, run),
            expected_choice=run.shot_selections[0], replacement_choice=replacement or self.replacement(m))
        args.update(overrides)
        return replace_choice(m, **args)

    def executed(self, m=None, stage=None):
        stage = stage or MediaSelectionStage()
        outcome = stage.execute(StageContext(m or self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        proposed = outcome.update.manifest
        execution = outcome.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(proposed), "configuration": {}}, {})
        proposed.processing = [ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution)]
        return stage, proposed, execution

    def assert_invalid_choice(self, choice):
        run = active(self.built)
        self.assertTrue(validate(install(self.built, replace(run,
            shot_selections=[choice, *run.shot_selections[1:]]))))

    def test_additive_empty_default(self):
        m = ProjectManifest("empty")
        self.assertEqual(m.selection, SelectionState())
        self.assertEqual(m.schema_version, 2)
        self.assertFalse(validate(m))

    def test_older_schema2_loads(self):
        data = to_data(ProjectManifest("old"))
        del data["selection"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "older.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load(path).selection, SelectionState())

    def test_malformed_present_selection_rejected(self):
        for value in (None, {}, [], {"runs": []}, {"runs": "bad", "reviews": [], "active_creator_selection_id": None}):
            with self.subTest(value=value):
                data = to_data(ProjectManifest("bad")); data["selection"] = value
                with self.assertRaises(ValueError):
                    decode(ProjectManifest, migrate_document(data))

    def test_first_eligible_deterministic(self):
        m = self.built
        self.assertEqual(m.selection, build_selection(m).selection)
        r = retrieval_run(m)
        self.assertTrue(all(s.selected_candidate.candidate_id == result.candidate_ids[0]
            for s, result in zip(active(m).shot_selections, r.shot_results)))
        self.assertFalse(validate(m))

    def test_second_when_first_ineligible(self):
        m = selected_fixture(self.intent, [
            CandidateProposal("video:first", VisualMediaKind.VIDEO, usage_restriction=UsageRestriction.REFERENCE_ONLY),
            CandidateProposal("video:second", VisualMediaKind.VIDEO)])
        expected = retrieval_run(m).shot_results[0].candidate_ids[1]
        self.assertEqual(active(m).shot_selections[0].selected_candidate.candidate_id, expected)

    def test_no_reranking(self):
        m = selected_fixture(self.intent, [CandidateProposal("video:z", VisualMediaKind.VIDEO),
                                         CandidateProposal("video:a", VisualMediaKind.VIDEO)])
        r = retrieval_run(m)
        c = next(c for c in r.candidates if c.provider_candidate_ref == "video:z")
        self.assertEqual(active(m).shot_selections[0].selected_candidate.candidate_id, c.candidate_id)

    def test_exact_shortlist_membership(self):
        m = deepcopy(self.built); r = retrieval_run(m)
        # Make disjoint valid observations without changing provider semantics.
        results = [replace(s, candidate_ids=[s.candidate_ids[i % 2]]) for i, s in enumerate(r.shot_results)]
        r = retrieval_identity(replace(r, shot_results=results))
        m.selection = SelectionState(); m.retrieval.runs = [r]; m.retrieval.active_creator_retrieval_id = r.retrieval_id
        m = build_selection(m)
        run = active(m); foreign = run.shot_selections[1].selected_candidate
        forged = replace(run.shot_selections[0], selected_candidate=foreign)
        self.assertTrue(validate(install(m, replace(run, shot_selections=[forged, *run.shot_selections[1:]]))))

    def test_cross_shot_replay(self):
        run = active(self.built)
        self.assert_invalid_choice(run.shot_selections[1])

    def test_cross_run_replay(self):
        m = selected_fixture(self.intent, [CandidateProposal("video:elsewhere", VisualMediaKind.VIDEO)])
        self.assert_invalid_choice(active(m).shot_selections[0])

    def test_unknown_candidate(self):
        old = active(self.built).shot_selections[0]
        self.assert_invalid_choice(replace(old, selected_candidate=SelectedCandidateRef("candidate:" + "0" * 64, "0" * 64)))

    def test_exact_fingerprint_required(self):
        old = active(self.built).shot_selections[0]
        self.assert_invalid_choice(replace(old, selected_candidate=replace(old.selected_candidate, metadata_fingerprint="")))

    def test_tampered_fingerprint_rejected(self):
        old = active(self.built).shot_selections[0]
        self.assert_invalid_choice(replace(old, selected_candidate=replace(old.selected_candidate, metadata_fingerprint="f" * 64)))

    def test_usage_reference_only_rejected(self):
        m = selected_fixture(self.intent, [CandidateProposal("video:ref", VisualMediaKind.VIDEO,
            usage_restriction=UsageRestriction.REFERENCE_ONLY)])
        self.assertTrue(all(s.reason == SelectionReason.NO_ELIGIBLE_CANDIDATE for s in active(m).shot_selections))

    def test_declared_rights_reference_only_rejected(self):
        m = selected_fixture(self.intent, [CandidateProposal("video:ref", VisualMediaKind.VIDEO,
            provenance_hint=ProvenanceHint(declared_rights=Rights.REFERENCE_ONLY))])
        self.assertTrue(all(s.outcome == SelectionOutcome.UNRESOLVED for s in active(m).shot_selections))

    def test_permissive_hint_never_authorizes(self):
        for rights in (Rights.OWNED, Rights.LICENSED, Rights.PUBLIC_DOMAIN, Rights.UNKNOWN):
            with self.subTest(rights=rights):
                m = selected_fixture(self.intent, [CandidateProposal("video:hint", VisualMediaKind.VIDEO,
                    provenance_hint=ProvenanceHint(declared_rights=rights))])
                self.assertTrue(complete(active(m)))
                self.assertEqual(m.media, [])
                self.assertNotIn("final_eligible", json.dumps(to_data(m.selection)))

    def test_unresolved_empty(self):
        m = build_selection(build_retrieval(self.intent))
        self.assertTrue(all(s.reason == SelectionReason.RETRIEVAL_EMPTY for s in active(m).shot_selections))
        self.assertFalse(complete(active(m)))
        self.assertFalse(validate(m))

    def test_unresolved_unsupported(self):
        provider = SyntheticProvider(); provider.capabilities = replace(provider.capabilities, supports_structured_intent=False)
        m = build_selection(build_retrieval(self.intent, providers=(provider,)))
        self.assertTrue(all(s.reason == SelectionReason.RETRIEVAL_UNSUPPORTED for s in active(m).shot_selections))

    def test_unresolved_failed_mapping(self):
        # M66 rejects wholly failed runs; mixed retained per-shot failure is valid.
        class Mixed(SyntheticProvider):
            def retrieve(self, request, control):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("synthetic failure")
                return ProviderRetrievalResult([])
        m = build_selection(build_retrieval(self.intent, providers=(Mixed(),)))
        self.assertEqual(active(m).shot_selections[0].reason, SelectionReason.RETRIEVAL_FAILED)
        self.assertFalse(validate(m))

    def test_unresolved_insufficient_intent(self):
        m = build_selection(build_retrieval(self.baseline))
        self.assertTrue(all(s.reason == SelectionReason.INSUFFICIENT_INTENT for s in active(m).shot_selections))

    def test_unresolved_no_eligible(self):
        self.test_usage_reference_only_rejected()

    def hard_fixture(self, **changes):
        m = deepcopy(self.intent); p = active_plan(m)
        p = visual_identity(replace(p, units=[replace(u, **changes) for u in p.units]))
        m.visual_planning.plans = [p]; m.visual_planning.active_creator_plan_id = p.visual_plan_id
        return selected_fixture(m)

    def test_unresolved_hard_literal_fidelity(self):
        m = self.hard_fixture(depiction_fidelity=DepictionFidelity.EXACT_LITERAL)
        self.assertTrue(all(s.reason == SelectionReason.HARD_REQUIREMENT_UNVERIFIED for s in active(m).shot_selections))
        self.assertFalse(validate(m))

    def test_exact_ordered_coverage(self):
        self.assertEqual([s.planned_shot_id for s in active(self.built).shot_selections],
            [s.planned_shot_id for u in active_plan(self.built).units for s in u.planned_shots])

    def test_omitted_shot_rejected(self):
        r = active(self.built)
        self.assertTrue(validate(install(self.built, replace(r, shot_selections=r.shot_selections[1:]))))

    def test_duplicate_shot_rejected(self):
        r = active(self.built)
        self.assertTrue(validate(install(self.built, replace(r, shot_selections=[r.shot_selections[0]] * len(r.shot_selections)))))

    def test_unknown_shot_rejected(self):
        self.assert_invalid_choice(replace(active(self.built).shot_selections[0], planned_shot_id="unknown"))

    def test_duplicate_candidate_allowed(self):
        refs = [s.selected_candidate for s in active(self.built).shot_selections]
        self.assertGreater(len(refs), 1)
        self.assertEqual(len(set(refs)), 1)
        self.assertFalse(validate(self.built))

    def predicate(self, unit=None, shot=None, candidate=None, assessments=None):
        r = retrieval_run(self.built); p = active_plan(self.built)
        u = unit or p.units[0]; s = shot or u.planned_shots[0]
        result = r.shot_results[0]
        if assessments is not None:
            result = replace(result, assessments=assessments)
        c = candidate or next(c for c in r.candidates if c.candidate_id == result.candidate_ids[0])
        return candidate_eligibility(p, u, s, r, result, c)

    def test_media_kind_hard_mismatch(self):
        p = active_plan(self.built); u = p.units[0]
        s = replace(u.planned_shots[0], media_form_preference=MediaFormPreference.IMAGE_PREFERRED)
        self.assertEqual(self.predicate(shot=s), SelectionReason.NO_ELIGIBLE_CANDIDATE)

    def test_unknown_hard_evidence_not_proof(self):
        u = active_plan(self.built).units[0]
        requirement = VisualRequirement(RequirementAspect.SUBJECT, Evidence(u.story_unit_ids),
            PlanningTreatment.SHOW, PlanningMetadata(AnnotationOrigin.CREATOR), IdentityFidelity.CATEGORY)
        c = active(self.built).shot_selections[0].selected_candidate.candidate_id
        self.assertEqual(self.predicate(unit=replace(u, requirements=[requirement]), assessments=[
            MatchEvidence(c, MatchAspect.SUBJECT, Finding.UNKNOWN, "method", "1")]),
            SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_aspect_match_cannot_prove_exact_identity(self):
        u = active_plan(self.built).units[0]
        requirement = VisualRequirement(RequirementAspect.SUBJECT, Evidence(u.story_unit_ids),
            PlanningTreatment.SHOW, PlanningMetadata(AnnotationOrigin.CREATOR), IdentityFidelity.EXACT)
        c = active(self.built).shot_selections[0].selected_candidate.candidate_id
        self.assertEqual(self.predicate(unit=replace(u, requirements=[requirement]), assessments=[
            MatchEvidence(c, MatchAspect.SUBJECT, Finding.MATCH, "method", "1")]),
            SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_category_requires_exact_target_match(self):
        u = active_plan(self.built).units[0]
        ref = SemanticMentionRef(u.story_unit_ids[0], 0, "a" * 64)
        requirement = VisualRequirement(RequirementAspect.SUBJECT, Evidence(u.story_unit_ids, [ref]),
            PlanningTreatment.SHOW, PlanningMetadata(AnnotationOrigin.CREATOR), IdentityFidelity.CATEGORY)
        c = active(self.built).shot_selections[0].selected_candidate.candidate_id
        u = replace(u, requirements=[requirement])
        for finding, evidence_ref in ((Finding.UNKNOWN, ref), (Finding.MATCH, None)):
            self.assertEqual(self.predicate(unit=u, assessments=[MatchEvidence(c, MatchAspect.SUBJECT,
                finding, "method", "1", evidence_ref)]), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)
        self.assertIsNone(self.predicate(unit=u, assessments=[MatchEvidence(c, MatchAspect.SUBJECT,
            Finding.MATCH, "method", "1", ref)]))

    def test_unsupported_geography_hard(self):
        u = active_plan(self.built).units[0]
        for fidelity in (GeographyFidelity.EXACT, GeographyFidelity.REGION_COMPATIBLE, GeographyFidelity.UNKNOWN):
            self.assertEqual(self.predicate(unit=replace(u, geography_requirement=GeographyRequirement(
                fidelity, Evidence(u.story_unit_ids)))), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_unsupported_temporal_hard(self):
        u = active_plan(self.built).units[0]
        for fidelity in (TemporalFidelity.EXACT, TemporalFidelity.APPROXIMATE, TemporalFidelity.UNKNOWN):
            self.assertEqual(self.predicate(unit=replace(u, temporal_requirement=TemporalRequirement(
                fidelity, TemporalDimension.ERA, Evidence(u.story_unit_ids)))), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_required_constraints_both_polarities(self):
        u = active_plan(self.built).units[0]
        for polarity in Polarity:
            constraint = VisualConstraint(ConstraintKind.FACES, polarity, Strength.REQUIRED,
                Evidence(u.story_unit_ids), PlanningMetadata(AnnotationOrigin.CREATOR))
            self.assertEqual(self.predicate(unit=replace(u, constraints=[constraint])), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_required_continuity_unverified(self):
        u = active_plan(self.built).units[0]
        continuity = ContinuityRequirement(ContinuityKind.SUBJECT, Strength.REQUIRED,
            Evidence(u.story_unit_ids), PlanningMetadata(AnnotationOrigin.CREATOR))
        self.assertEqual(self.predicate(unit=replace(u, continuity_requirements=[continuity])), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_soft_camera_preferences_no_hard_requirement(self):
        u = active_plan(self.built).units[0]
        s = replace(u.planned_shots[0], shot_scale_preference=ShotScale.CLOSE, camera_motion_preference=CameraMotion.PAN)
        self.assertIsNone(self.predicate(shot=s))

    def test_nonshow_identity_obligation_unverified(self):
        u = active_plan(self.built).units[0]
        for treatment in (PlanningTreatment.ILLUSTRATE, PlanningTreatment.SYMBOLIZE,
                          PlanningTreatment.EVOKE, PlanningTreatment.TEXTUAL):
            requirement = VisualRequirement(RequirementAspect.SUBJECT, Evidence(u.story_unit_ids),
                treatment, PlanningMetadata(AnnotationOrigin.CREATOR), IdentityFidelity.CATEGORY)
            self.assertEqual(self.predicate(unit=replace(u, requirements=[requirement])),
                             SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_unproven_representation_unresolved(self):
        for mode in (RepresentationMode.MAP, RepresentationMode.DOCUMENT, RepresentationMode.TEXTUAL):
            m = self.hard_fixture(representation_mode=mode)
            self.assertTrue(all(s.reason == SelectionReason.HARD_REQUIREMENT_UNVERIFIED for s in active(m).shot_selections))

    def evidence_fixture(self, aspect=RequirementAspect.SUBJECT, finding=Finding.MATCH,
                         identity=IdentityFidelity.CATEGORY, omit_target=False):
        m = build_semantic_story(content("Paris Paris.")); d = m.semantic.documents[0]
        u = d.story_units[0]
        mention = Mention(SourceSpan(0, 5), "Paris")
        u = replace(u, derivation=Derivation.ANALYZER, annotations=SemanticAnnotations(mentions=[mention]))
        u = replace(u, story_unit_id=story_unit_id(d.analysis_signature, u.source_excerpts, u.derivation))
        d = replace(d, story_units=[u]); d = replace(d, semantic_document_id=document_id(d))
        d = replace(d, output_signature=semantic_output(d))
        m.semantic.documents = [d]; m.semantic.active_creator_document_id = d.semantic_document_id
        m = with_intent(build_visual_plan(m)); p = active_plan(m)
        ref = SemanticMentionRef(u.story_unit_id, 0, exact_signature(mention))
        requirement = VisualRequirement(aspect, Evidence([u.story_unit_id], [ref]),
            PlanningTreatment.SHOW, PlanningMetadata(AnnotationOrigin.CREATOR), identity)
        p = visual_identity(replace(p, units=[replace(p.units[0], requirements=[requirement])]))
        m.visual_planning.plans = [p]; m.visual_planning.active_creator_plan_id = p.visual_plan_id
        match_aspect = {RequirementAspect.SUBJECT: MatchAspect.SUBJECT,
                        RequirementAspect.ACTION: MatchAspect.ACTION,
                        RequirementAspect.ENVIRONMENT: MatchAspect.ENVIRONMENT}[aspect]
        response = ProviderRetrievalResult([CandidateProposal("video:evidence", VisualMediaKind.VIDEO)],
            [ProposalAssessment(0, MatchEvidence("", match_aspect, finding, "synthetic", "1",
                                                None if omit_target else ref))])
        return build_selection(build_retrieval(m, providers=(SyntheticProvider(response),)))

    def test_persisted_category_evidence_chain(self):
        m = self.evidence_fixture()
        self.assertFalse(validate(m))
        self.assertTrue(complete(active(m)))
        self.assertEqual(active(m).shot_selections[0].selected_candidate.candidate_id,
                         retrieval_run(m).shot_results[0].candidate_ids[0])

    def test_persisted_unknown_target_evidence_unresolved(self):
        for args in (dict(finding=Finding.UNKNOWN), dict(omit_target=True), dict(identity=IdentityFidelity.EXACT)):
            m = self.evidence_fixture(**args)
            self.assertFalse(validate(m))
            self.assertEqual(active(m).shot_selections[0].reason, SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_persisted_action_environment_proof(self):
        for aspect in (RequirementAspect.ACTION, RequirementAspect.ENVIRONMENT):
            m = self.evidence_fixture(aspect=aspect, identity=IdentityFidelity.UNKNOWN)
            self.assertFalse(validate(m))
            self.assertTrue(complete(active(m)))

    def test_literal_action_needs_action_target(self):
        m = self.evidence_fixture(); p = active_plan(m); u = p.units[0]
        self.assertEqual(self.predicate(unit=replace(active_plan(self.built).units[0],
            visual_purpose=VisualPurpose.LITERAL_ACTION)), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)
        r = retrieval_run(m); result = r.shot_results[0]
        c = r.candidates[0]
        self.assertEqual(candidate_eligibility(p, replace(u, visual_purpose=VisualPurpose.LITERAL_ACTION),
            u.planned_shots[0], r, result, c), SelectionReason.HARD_REQUIREMENT_UNVERIFIED)

    def test_persisted_evidence_reference_tamper_rejected(self):
        m = self.evidence_fixture(); r = retrieval_run(m); result = r.shot_results[0]
        evidence = result.assessments[0]
        result = replace(result, assessments=[replace(evidence, evidence_ref=replace(
            evidence.evidence_ref, mention_fingerprint="f" * 64))])
        r = retrieval_identity(replace(r, shot_results=[result]))
        m.retrieval.runs = [r]; m.retrieval.active_creator_retrieval_id = r.retrieval_id
        self.assertTrue(validate(m))
        with self.assertRaises(ValueError):
            build_selection(m)

    def test_deterministic_shot_id(self):
        r = active(self.built)
        for s in r.shot_selections:
            self.assertEqual(s.shot_selection_id, shot_id(r.retrieval_id, r.selection_spec, s))

    def test_deterministic_selection_id(self):
        r = active(self.built)
        self.assertEqual(r.selection_id, run_id(r))

    def test_deterministic_signature_chain(self):
        r = active(self.built)
        self.assertEqual(r.selection_input_fingerprint, input_fingerprint(retrieval_run(self.built)))
        self.assertEqual(r.selection_signature, selection_signature(r.selection_input_fingerprint, r.selection_spec))
        self.assertEqual(r.output_signature, output_signature(r))

    def test_review_does_not_change_logical_identity(self):
        m = self.review()
        self.assertEqual(m.selection.runs, self.built.selection.runs)
        self.assertNotEqual(effective_output_signature(m.selection, active(m)),
                            effective_output_signature(self.built.selection, active(self.built)))

    def test_source_does_not_change_logical_identity(self):
        r = active(self.built); s = r.shot_selections[0]
        modified = assign_identity(replace(r, shot_selections=[replace(s, source=SelectionSource.CREATOR,
            reason=SelectionReason.CREATOR_CHOICE), *r.shot_selections[1:]]))
        self.assertEqual(modified.selection_id, r.selection_id)
        self.assertEqual(modified.shot_selections[0].shot_selection_id, s.shot_selection_id)
        self.assertNotEqual(modified.output_signature, r.output_signature)

    def test_same_choice_preserves_review(self):
        m = self.review()
        result = build_selection(m)
        self.assertEqual(result.selection, m.selection)

    def test_approved_candidate_replacement_automatic_blocked(self):
        m = self.replace(self.review())
        m = self.review(m)
        with self.assertRaises(SelectionError):
            build_selection(m)

    def test_locked_candidate_replacement_automatic_blocked(self):
        m = self.replace(self.built)
        m = self.review(m, status=ReviewStatus.PENDING, locked=True)
        with self.assertRaises(SelectionError):
            build_selection(m)

    def test_explicit_pending_review_replacement_blocked(self):
        m = self.replace(self.built)
        m = self.review(m, status=ReviewStatus.PENDING)
        with self.assertRaises(SelectionError):
            build_selection(m)

    def changed_upstream(self, m):
        p = active_plan(m)
        changed = deepcopy(m)
        p = replace(p, review=VisualReview(ReviewStatus.APPROVED))
        p = replace(p, output_signature=visual_output(p))
        changed.visual_planning.plans = [p]
        return build_retrieval(changed, providers=(SyntheticProvider(),))

    def test_approved_selected_to_unresolved_blocked(self):
        m = self.review()
        changed = deepcopy(m)
        p = active_plan(changed)
        p = replace(p, review=VisualReview(ReviewStatus.APPROVED))
        p = replace(p, output_signature=visual_output(p))
        changed.visual_planning.plans = [p]
        changed = build_retrieval(changed)
        with self.assertRaises(SelectionError):
            build_selection(changed)

    def test_rejected_choice_not_selected_again(self):
        m = self.review(status=ReviewStatus.REJECTED)
        result = build_selection(m)
        choice = active(result).shot_selections[0]
        self.assertEqual(choice.reason, SelectionReason.CREATOR_REVIEW_REQUIRED)
        self.assertIsNone(choice.selected_candidate)
        self.assertEqual(result.selection.reviews, m.selection.reviews)
        self.assertEqual(build_selection(result).selection, result.selection)

    def test_targeted_expected_state_replacement(self):
        m = self.review(locked=True)
        result = self.replace(m)
        self.assertEqual(len(result.selection.runs), 2)
        self.assertEqual(result.selection.runs[0], active(m))
        self.assertEqual(result.selection.reviews, m.selection.reviews)
        self.assertNotIn(active(result).shot_selections[0].shot_selection_id, effective_reviews(result.selection))
        self.assertFalse(validate(result))

    def test_replacement_exact_previous_required(self):
        for overrides in (dict(expected_selection_id="unknown"),
                          dict(expected_effective_output_signature="a" * 64),
                          dict(expected_choice=active(self.built).shot_selections[1])):
            with self.subTest(overrides=overrides), self.assertRaises(SelectionError):
                self.replace(self.built, **overrides)

    def test_no_generic_bypass(self):
        for function in (replace_choice, build_selection, append_review):
            self.assertNotIn("force", inspect.signature(function).parameters)
            self.assertNotIn("ignore_lock", inspect.signature(function).parameters)
            self.assertFalse(any(p.kind == p.VAR_KEYWORD for p in inspect.signature(function).parameters.values()))

    def test_review_predecessor_resolves(self):
        with self.assertRaises(SelectionError):
            append_review(self.built, expected_selection_id=active(self.built).selection_id,
                expected_choice=active(self.built).shot_selections[0], expected_predecessor="unknown",
                status=ReviewStatus.APPROVED, locked=False)

    def test_review_fork_rejected(self):
        m = self.review(); first = m.selection.reviews[0]
        fork = replace(first, review_id="", status=ReviewStatus.REJECTED)
        fork = replace(fork, review_id=review_id(fork)); m.selection.reviews.append(fork)
        self.assertTrue(validate(m))

    def test_review_cycle_rejected(self):
        m = self.review(); first = m.selection.reviews[0]
        cycle = replace(first, predecessor_review_id=first.review_id)
        m.selection.reviews = [cycle]
        self.assertTrue(validate(m))

    def test_review_unknown_subject_rejected(self):
        m = self.review(); review = replace(m.selection.reviews[0], shot_selection_id="unknown")
        m.selection.reviews = [replace(review, review_id=review_id(review))]
        self.assertTrue(validate(m))

    def test_review_fingerprint_change_no_transfer(self):
        m = self.review(); old = active(m).shot_selections[0]
        new = replace(old, selected_candidate=replace(old.selected_candidate, metadata_fingerprint="b" * 64))
        self.assertNotEqual(shot_id(active(m).retrieval_id, SelectionSpec(), new), old.shot_selection_id)
        self.assertNotIn(shot_id(active(m).retrieval_id, SelectionSpec(), new), effective_reviews(m.selection))

    def test_valid_review_transition_chain(self):
        m = self.review(status=ReviewStatus.PENDING, locked=True)
        m = self.review(m, status=ReviewStatus.APPROVED, locked=False)
        self.assertFalse(validate(m))
        self.assertEqual(m.selection.reviews[1].predecessor_review_id, m.selection.reviews[0].review_id)

    def test_retrieval_change_stales_selection(self):
        changed = self.changed_upstream(self.built)
        self.assertIsNone(eligible_active_selection(changed))

    def test_shortlist_reordering_stales_with_valid_history(self):
        m = deepcopy(self.built); old = retrieval_run(m)
        newer = retrieval_identity(replace(old, shot_results=[replace(s,
            candidate_ids=list(reversed(s.candidate_ids))) for s in old.shot_results]))
        m.retrieval.runs.append(newer); m.retrieval.active_creator_retrieval_id = newer.retrieval_id
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_selection(m))
        result = build_selection(m)
        self.assertEqual(result.selection.runs[0], active(self.built))
        self.assertEqual(active(result).shot_selections[0].selected_candidate.candidate_id,
                         newer.shot_results[0].candidate_ids[0])

    def test_metadata_change_stales_with_valid_history(self):
        m = deepcopy(self.built); old = retrieval_run(m)
        candidates = [replace(c, label="Updated observation") for c in old.candidates]
        candidates = [replace(c, metadata_fingerprint=metadata_fingerprint(c)) for c in candidates]
        newer = retrieval_identity(replace(old, candidates=candidates))
        m.retrieval.runs.append(newer); m.retrieval.active_creator_retrieval_id = newer.retrieval_id
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_selection(m))

    def test_current_provider_spec_does_not_invalidate_history(self):
        r = retrieval_run(self.built)
        spec = replace(r.retrieval_spec, providers=[replace(p, provider_version="2") for p in r.retrieval_spec.providers])
        self.assertIsNone(eligible_active_selection(self.built, required_retrieval_spec=spec))
        self.assertFalse(validate(self.built))

    def test_output_change_stales_selection(self):
        changed = deepcopy(self.built)
        r = retrieval_run(changed)
        changed.retrieval.runs = [replace(r, output_signature="0" * 64)]
        self.assertIsNone(eligible_active_selection(changed))

    def test_visual_change_stales_through_m66(self):
        m = deepcopy(self.built); p = active_plan(m)
        p = replace(p, review=VisualReview(ReviewStatus.APPROVED))
        m.visual_planning.plans = [replace(p, output_signature=visual_output(p))]
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_selection(m))

    def test_historical_valid_after_retrieval_change(self):
        changed = self.changed_upstream(self.built)
        self.assertFalse(validate(changed))
        self.assertEqual(changed.selection, self.built.selection)

    def test_historical_and_current_separate(self):
        m = deepcopy(self.built); m.retrieval.active_creator_retrieval_id = None
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_selection(m))

    def test_no_historical_auto_reactivation(self):
        m = deepcopy(self.built); m.selection.active_creator_selection_id = None
        before = deepcopy(m)
        self.assertIsNone(eligible_active_selection(m))
        with self.assertRaises(SelectionError):
            build_selection(m)
        self.assertEqual(m, before)

    def test_automatic_reuse_reconstructs(self):
        stage, m, previous = self.executed()
        self.assertTrue(stage.validate_reuse(m, previous))
        with patch("creator_studio.selection.stage.automatic_projection", side_effect=SelectionError("selection_contract_invalid")):
            self.assertFalse(stage.validate_reuse(m, previous))

    def test_self_consistent_nonbaseline_forgery_reuse_rejected(self):
        stage, m, execution = self.executed(); r = active(m)
        replacement = self.replacement(m)
        forged_choice = replace(replacement, source=SelectionSource.AUTOMATIC, reason=SelectionReason.FIRST_ELIGIBLE)
        forged = assign_identity(replace(r, shot_selections=[forged_choice, *r.shot_selections[1:]]))
        m.selection.runs = [forged]; m.selection.active_creator_selection_id = forged.selection_id
        execution.artifacts = stage.artifacts(m, forged, retrieval_run(m))
        self.assertFalse(validate(m))
        before = deepcopy(m)
        original = deepcopy(self.built)
        shortlist = retrieval_run(m).shot_results[0].candidate_ids
        self.assertEqual(r.shot_selections[0].selected_candidate.candidate_id, shortlist[0])
        self.assertEqual(forged.shot_selections[0].selected_candidate.candidate_id, shortlist[1])
        self.assertIsNone(eligible_active_selection(m))
        with self.assertRaises(SelectionError):
            self.replace(m)
        self.assertFalse(stage.validate_reuse(m, execution))
        self.assertEqual(m, before)
        self.assertEqual(self.built, original)

    def test_forged_automatic_unresolved_current_rejected(self):
        # Historical rejection supports retained structure, while the later
        # approval requires a selected baseline in the current projection.
        m = build_selection(self.review(status=ReviewStatus.REJECTED))
        baseline = m.selection.runs[0]
        review = SelectionReview("", baseline.shot_selections[0].shot_selection_id,
            m.selection.reviews[0].review_id, ReviewStatus.APPROVED, False)
        m.selection.reviews.append(replace(review, review_id=review_id(review)))
        forged = assign_identity(active(m))
        m.selection.runs[-1] = forged
        m.selection.active_creator_selection_id = forged.selection_id
        artifacts = MediaSelectionStage.artifacts(m, forged, retrieval_run(m))
        self.assertTrue(artifacts)
        before = deepcopy(m)
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_selection(m))
        self.assertEqual(m, before)

    def test_historical_selected_survives_review_and_pointer_changes(self):
        old = deepcopy(active(self.built))
        m = self.review(status=ReviewStatus.REJECTED)
        self.assertFalse(validate(m))
        self.assertEqual(active(m), old)
        self.assertIsNone(eligible_active_selection(m))
        projected = automatic_projection(m, retrieval_run(m), SelectionSpec())
        self.assertEqual(projected.shot_selections[0].reason,
                         SelectionReason.CREATOR_REVIEW_REQUIRED)
        self.assertIsNone(projected.shot_selections[0].selected_candidate)
        m = build_selection(m)
        self.assertIsNotNone(eligible_active_selection(m))
        self.assertEqual(m.selection.runs[0], old)
        m.retrieval.active_creator_retrieval_id = None
        self.assertFalse(validate(m))
        self.assertEqual(m.selection.runs[0], old)
        self.assertIsNone(eligible_active_selection(m))

    def test_stale_self_consistent_binding_reuse_rejected(self):
        stage, m, previous = self.executed()
        changed = self.changed_upstream(m)
        self.assertFalse(validate(changed))
        self.assertFalse(stage.validate_reuse(changed, previous))

    def test_manual_reuse_disabled(self):
        m = self.replace(self.built)
        stage = MediaSelectionStage(); run = active(m)
        execution = __import__("creator_studio.manifest.execution", fromlist=["ExecutionRecord"]).ExecutionRecord(
            stage.stage_id, stage.stage_version, StageStatus.SUCCEEDED,
            dependency_signature=dependency_signature(stage.stage_id, stage.stage_version,
                {"inputs": stage.signature_inputs(m), "configuration": {}}, {}),
            artifacts=stage.artifacts(m, run, retrieval_run(m)))
        m.processing = [ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution)]
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_exact_two_artifacts(self):
        stage, m, previous = self.executed()
        self.assertEqual(len(previous.artifacts), 2)
        self.assertEqual(previous.artifacts[0].reference, "selection/" + active(m).selection_id)
        self.assertEqual(previous.artifacts[1].reference, "selection_retrieval/" + retrieval_run(m).retrieval_id)

    def test_artifact_order_required(self):
        stage, m, previous = self.executed()
        previous.artifacts.reverse()
        self.assertFalse(stage.validate_reuse(m, previous))

    def test_artifact_tampering_rejected(self):
        for mode in ("signature", "reference", "missing", "extra"):
            stage, m, previous = self.executed()
            if mode == "signature":
                previous.artifacts[0].signature = "0" * 64
            elif mode == "reference":
                previous.artifacts[1].reference = "selection_retrieval/unknown"
            elif mode == "missing":
                previous.artifacts.pop()
            else:
                previous.artifacts.append(deepcopy(previous.artifacts[0]))
            self.assertFalse(stage.validate_reuse(m, previous))

    def test_standalone_dependency_convention(self):
        self.assertEqual(MediaSelectionStage().dependencies, ())
        self.assertEqual(MediaSelectionStage.stage_id, "media_selection")
        self.assertEqual(MediaSelectionStage.stage_version, "1")

    def test_combined_dependency_convention(self):
        self.assertEqual(MediaSelectionStage(dependencies=("media_retrieval",)).dependencies, ("media_retrieval",))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "combined.json"
            save(self.intent, path)
            runner = ProjectOrchestrator(ManifestRepository(path))
            runner.register(MediaRetrievalStage())
            runner.register(MediaSelectionStage(dependencies=("media_retrieval",)))
            self.assertEqual(runner.run().status, StageStatus.SUCCEEDED)
            self.assertEqual(runner.run().results[-1].status, StageStatus.SKIPPED)

    def test_cancellation_atomicity(self):
        before = deepcopy(self.built)
        with self.assertRaises(Cancelled):
            build_selection(self.built, control=CountingControl(2))
        self.assertEqual(self.built, before)

    def test_late_cancellation_atomicity(self):
        counter = CountingControl(); build_selection(self.built, control=counter)
        before = deepcopy(self.built)
        with self.assertRaises(Cancelled):
            build_selection(self.built, control=CountingControl(counter.count))
        self.assertEqual(self.built, before)

    def test_stage_late_cancellation_atomicity(self):
        stage = MediaSelectionStage(); counter = CountingControl()
        stage.execute(StageContext(self.built, counter, 1, lambda *a: None))
        before = deepcopy(self.built)
        with self.assertRaises(Cancelled):
            stage.execute(StageContext(self.built, CountingControl(counter.count), 1, lambda *a: None))
        self.assertEqual(self.built, before)

    def test_validation_failure_atomicity(self):
        before = deepcopy(self.built)
        with patch("creator_studio.selection.engine.finish", side_effect=ValueError("synthetic")):
            result = MediaSelectionStage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertIsNone(result.update)
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertEqual(self.built, before)

    def test_input_unchanged(self):
        before = deepcopy(self.built)
        build_selection(self.built)
        self.assertEqual(self.built, before)

    def test_non_selection_domains_unchanged(self):
        result = build_selection(self.built)
        self.assertTrue(boundary_unchanged(self.built, result))
        for f in fields(self.built):
            if f.name != "selection":
                self.assertEqual(getattr(self.built, f.name), getattr(result, f.name))

    def test_mediareference_unchanged(self):
        self.assertEqual(self.built.media, build_selection(self.built).media)
        self.assertEqual(self.built.media, [])

    def test_scenes_unchanged(self):
        self.assertEqual(self.built.scenes, build_selection(self.built).scenes)

    def test_voice_subtitle_audio_timeline_unchanged(self):
        result = self.replace(self.review())
        for domain in ("voice", "subtitle_tracks", "audio", "timeline", "media", "scenes"):
            self.assertEqual(getattr(result, domain), getattr(self.built, domain))

    def test_populated_nonselection_domains_preserved(self):
        m = deepcopy(self.built)
        m.media = [MediaReference(id="owned-media", reference="user-footage",
            provenance=Provenance(rights=Rights.OWNED), final_eligible=True)]
        m.scenes = [Scene(id="existing-scene", start=0.0, end=10.0, narration="Existing",
                          media_ids=["owned-media"])]
        m.voice = Voice(audio_media_id="owned-media")
        m.subtitle_tracks = [SubtitleTrack(id="existing-track", segments=[SubtitleSegment(
            id="existing-subtitle", scene_id="existing-scene", original_text="Existing", start=0.0, end=2.0)])]
        m.audio = [AudioReference(id="existing-audio", media_id="owned-media", scene_id="existing-scene")]
        m.timeline = [TimelineReference(id="existing-timeline", media_id="owned-media",
            scene_id="existing-scene", start=0.0, end=2.0)]
        self.assertFalse(validate(m))
        before = deepcopy(m)
        result = self.replace(self.review(build_selection(m)))
        self.assertTrue(boundary_unchanged(before, result))
        self.assertEqual(m, before)

    def test_boundary_guard_detects_mutation(self):
        m = deepcopy(self.built); m.content.script += "changed"
        self.assertFalse(boundary_unchanged(self.built, m))

    def test_boundary_guard_rejects_publication(self):
        from creator_studio.selection.engine import finish
        m = deepcopy(self.built); m.project_name = "changed"
        with self.assertRaises(SelectionError):
            finish(self.built, m, CancellationToken())

    def test_all_selection_cancellation_checkpoints(self):
        control = CountingControl(); build_selection(self.built, control=control)
        before = deepcopy(self.built)
        for stop in range(1, control.count + 1):
            with self.subTest(stop=stop), self.assertRaises(Cancelled):
                build_selection(self.built, control=CountingControl(stop))
            self.assertEqual(self.built, before)

    def test_review_and_replacement_cancellation_atomicity(self):
        m = self.review(); run = active(m); before = deepcopy(m)
        with self.assertRaises(Cancelled):
            self.replace(m, control=CountingControl(3))
        with self.assertRaises(Cancelled):
            append_review(m, expected_selection_id=run.selection_id,
                expected_choice=run.shot_selections[0], expected_predecessor=m.selection.reviews[-1].review_id,
                status=ReviewStatus.PENDING, locked=False, control=CountingControl(2))
        self.assertEqual(m, before)

    def test_urls_not_persisted(self):
        payload = json.dumps(to_data(self.built.selection))
        self.assertNotIn("://", payload)
        self.assertNotIn("url", payload)

    def test_paths_not_persisted(self):
        payload = json.dumps(to_data(self.built.selection))
        self.assertNotIn("\\", payload)
        self.assertNotIn("path", payload)

    def test_arbitrary_credential_fields_impossible(self):
        data = to_data(self.built.selection)
        for name in ("token", "cookie", "Authorization", "local_path", "raw_response", "download_url"):
            changed = deepcopy(data); changed["runs"][0][name] = "synthetic"
            with self.assertRaises(ValueError):
                decode(SelectionState, changed)

    def test_diagnostics_allowlisted(self):
        run = active(self.built)
        bad = replace(run, diagnostics=["arbitrary"])
        self.assertTrue(selection_errors(SelectionState([bad]), self.built.retrieval, self.built.visual_planning))
        for code in ("arbitrary", "https://example.invalid", None, [], "token=synthetic"):
            self.assertEqual(MediaSelectionStage()._diagnostics(code)[0].code, "selection_contract_invalid")

    def test_run_count_ceiling(self):
        state = deepcopy(self.built.selection); state.runs *= MAX_SELECTION_RUNS + 1
        self.assertEqual(selection_errors(state, self.built.retrieval, self.built.visual_planning), ["selection_limit_exceeded"])

    def test_per_run_shot_ceiling(self):
        run = active(self.built)
        state = SelectionState([replace(run, shot_selections=[run.shot_selections[0]] * (MAX_SHOT_SELECTIONS_PER_RUN + 1))])
        self.assertEqual(selection_errors(state, self.built.retrieval, self.built.visual_planning), ["selection_limit_exceeded"])

    def test_aggregate_shot_ceiling(self):
        run = active(self.built)
        large = replace(run, shot_selections=[run.shot_selections[0]] * MAX_SHOT_SELECTIONS_PER_RUN)
        state = SelectionState([large] * (MAX_TOTAL_HISTORICAL_SHOT_SELECTIONS // MAX_SHOT_SELECTIONS_PER_RUN + 1))
        self.assertEqual(selection_errors(state, self.built.retrieval, self.built.visual_planning), ["selection_limit_exceeded"])

    def test_review_ceiling(self):
        state = self.review().selection
        state.reviews *= MAX_SELECTION_REVIEWS + 1
        self.assertEqual(selection_errors(state, self.built.retrieval, self.built.visual_planning), ["selection_limit_exceeded"])

    def test_diagnostic_ceiling(self):
        run = active(self.built)
        state = SelectionState([replace(run, diagnostics=[SelectionReason.NO_ELIGIBLE_CANDIDATE] * (MAX_DIAGNOSTICS_PER_LIST + 1))])
        self.assertEqual(selection_errors(state, self.built.retrieval, self.built.visual_planning), ["selection_limit_exceeded"])

    def test_no_implicit_pruning(self):
        before = deepcopy(self.built)
        with patch("creator_studio.selection.engine.MAX_SELECTION_RUNS", 1):
            with self.assertRaises(SelectionError):
                self.replace(self.built)
        self.assertEqual(self.built, before)

    def test_provider_neutral(self):
        for source in SourceClass:
            provider = SyntheticProvider(); provider.provider_id = "neutral"; provider.source_class = source
            m = build_selection(build_retrieval(self.intent, providers=(provider,)))
            self.assertTrue(complete(active(m)))

    def test_no_provider_invocation(self):
        with patch.object(SyntheticProvider, "retrieve", side_effect=AssertionError("provider called")), \
                patch("creator_studio.retrieval.engine.build_retrieval", side_effect=AssertionError("retrieval called")):
            self.assertFalse(validate(build_selection(self.built)))

    def test_no_acquisition_behavior(self):
        forbidden = {"requests", "urllib", "httpx", "aiohttp", "ffmpeg", "ffprobe",
            "PyQt6", "PyQt", "stock", "pexels", "pixabay", "pipeline", "subprocess", "socket"}
        root = Path(__file__).resolve().parents[1] / "creator_studio"
        paths = [*(root / "selection").glob("*.py"), root / "manifest/selection.py", root / "manifest/selection_validation.py"]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({a.name.split(".")[0] for a in node.names} & forbidden, path.name)
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    self.assertNotIn((node.module or "").split(".")[0], forbidden, path.name)

    def test_strict_unknown_fields(self):
        for target in (SelectionState, SelectionSpec, SelectionRun, ShotSelection, SelectedCandidateRef, SelectionReview):
            instance = {SelectionState: self.built.selection, SelectionSpec: SelectionSpec(),
                SelectionRun: active(self.built), ShotSelection: active(self.built).shot_selections[0],
                SelectedCandidateRef: active(self.built).shot_selections[0].selected_candidate,
                SelectionReview: self.review().selection.reviews[0]}[target]
            data = to_data(instance); data["unexpected"] = "synthetic"
            with self.assertRaises(ValueError):
                decode(target, data)

    def test_migration_no_fabricated_selections(self):
        data = to_data(self.built); del data["selection"]
        m = decode(ProjectManifest, migrate_document(data))
        self.assertEqual(m.selection, SelectionState())
        self.assertEqual(m.retrieval, self.built.retrieval)

    def test_m66_retained_unchanged(self):
        result = self.replace(self.review())
        self.assertEqual(result.retrieval, self.built.retrieval)

    def test_rights_enum_canonical_unchanged(self):
        self.assertIs(ModelRights, Rights)
        self.assertEqual({r.name for r in Rights}, {"OWNED", "LICENSED", "PUBLIC_DOMAIN", "REFERENCE_ONLY", "UNKNOWN"})
        self.assertEqual(self.built.media, [])

    def test_m65_m66_history_preserved(self):
        m = self.changed_upstream(self.built)
        result = build_selection(m)
        self.assertEqual(result.retrieval, m.retrieval)
        self.assertEqual(result.visual_planning, m.visual_planning)
        self.assertEqual(result.semantic, m.semantic)
        self.assertEqual(result.selection.runs[0], active(self.built))

    def test_spec_current_eligibility(self):
        self.assertIsNotNone(eligible_active_selection(self.built, SelectionSpec()))
        self.assertIsNone(eligible_active_selection(self.built, replace(SelectionSpec(), baseline_policy_version="2")))
        with self.assertRaises(SelectionError):
            build_selection(self.built, spec=replace(SelectionSpec(), baseline_policy_version="2"))

    def test_required_upstream_specs(self):
        r = retrieval_run(self.built); p = active_plan(self.built)
        self.assertIsNone(eligible_active_selection(self.built, required_retrieval_spec=replace(r.retrieval_spec, candidates_per_shot=1)))
        self.assertIsNone(eligible_active_selection(self.built, required_visual_spec=replace(p.planning_spec, planner_version="2")))

    def test_run_signatures_tamper_matrix(self):
        run = active(self.built)
        for field in ("selection_id", "retrieval_id", "retrieval_output_signature", "selection_input_fingerprint",
                      "selection_signature", "output_signature"):
            with self.subTest(field=field):
                self.assertTrue(validate(install(self.built, replace(run, **{field: "tampered"}), False)))

    def test_selected_unresolved_exclusivity(self):
        old = active(self.built).shot_selections[0]
        self.assert_invalid_choice(replace(old, selected_candidate=None))
        self.assert_invalid_choice(replace(old, outcome=SelectionOutcome.UNRESOLVED, reason=SelectionReason.NO_ELIGIBLE_CANDIDATE))

    def test_false_automatic_unresolved_reason_rejected(self):
        old = active(self.built).shot_selections[0]
        for reason in (SelectionReason.RETRIEVAL_EMPTY, SelectionReason.HARD_REQUIREMENT_UNVERIFIED,
                       SelectionReason.CREATOR_REVIEW_REQUIRED):
            choice = replace(old, outcome=SelectionOutcome.UNRESOLVED,
                selected_candidate=None, reason=reason)
            self.assert_invalid_choice(choice)
            run = active(self.built)
            forged = install(self.built, replace(run,
                shot_selections=[choice, *run.shot_selections[1:]]))
            before = deepcopy(forged)
            self.assertIsNone(eligible_active_selection(forged))
            self.assertEqual(forged, before)

    def test_historical_review_required_survives_later_review(self):
        m = build_selection(self.review(status=ReviewStatus.REJECTED))
        # Reviewing the new unresolved subject cannot rewrite the old rejection.
        result = self.review(m)
        self.assertFalse(validate(result))
        self.assertEqual(result.selection.runs, m.selection.runs)

    def test_duplicate_run_rejected(self):
        m = deepcopy(self.built); m.selection.runs.append(active(m))
        self.assertTrue(validate(m))

    def test_active_pointer_unknown_rejected(self):
        m = deepcopy(self.built); m.selection.active_creator_selection_id = "unknown"
        self.assertTrue(validate(m))

    def test_effective_review_invalid_prevents_current(self):
        m = self.review(); m.selection.reviews.append(m.selection.reviews[0])
        self.assertIsNone(eligible_active_selection(m))

    def test_review_invalidates_old_artifact_reuse(self):
        stage, m, previous = self.executed()
        m = self.review(m)
        self.assertFalse(stage.validate_reuse(m, previous))

    def test_pure_reconstruction_preserves_all_history(self):
        m = self.changed_upstream(self.built); before = deepcopy(m)
        automatic_projection(m, retrieval_run(m), SelectionSpec())
        self.assertEqual(m, before)

    def test_stage_readiness_missing_upstream(self):
        self.assertEqual(MediaSelectionStage().readiness(ProjectManifest("missing")).kind, ReadinessKind.NOT_READY)

    def test_roundtrip_selection_and_reviews(self):
        m = self.replace(self.review())
        self.assertEqual(decode(ProjectManifest, to_data(m)), m)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            save(m, path)
            self.assertEqual(load(path), m)


if __name__ == "__main__":
    unittest.main()
