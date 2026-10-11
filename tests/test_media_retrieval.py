"""M66 offline contract, provider-boundary, atomicity and reuse regressions."""
import ast
from copy import deepcopy
from dataclasses import replace, fields
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, validate, save, load
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.models import Rights as OldRights, MediaReference
from creator_studio.manifest.rights import Rights
from creator_studio.manifest.retrieval import *
from creator_studio.manifest.retrieval_validation import (
    retrieval_errors, candidate_valid, eligible_active_retrieval, spec_valid)
from creator_studio.manifest.visual import (assign_identity as visual_identity,
    output_signature as visual_output, VisualPurpose, MediaFormPreference,
    VisualReview, ReviewStatus)
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.visual.engine import build_visual_plan
from creator_studio.retrieval.engine import build_retrieval, effective_spec, current_plan
from creator_studio.retrieval.models import (CandidateProposal, ProviderRetrievalResult,
    ProviderCapabilities, RetrievalError, ProposalAssessment)
from creator_studio.retrieval.requests import build_request
from creator_studio.retrieval.provider import OfflineEmptyProvider
from creator_studio.retrieval.stage import MediaRetrievalStage
from creator_studio.orchestrator import ProjectOrchestrator, ManifestRepository
from creator_studio.orchestrator.contracts import (CancellationToken, Cancelled,
    StageContext, StageStatus, ReadinessKind)
from tests.test_semantic_story import content


def active_plan(m):
    return next(p for p in m.visual_planning.plans
                if p.visual_plan_id == m.visual_planning.active_creator_plan_id)


def active_run(m):
    return next(r for r in m.retrieval.runs
                if r.retrieval_id == m.retrieval.active_creator_retrieval_id)


def with_intent(m, form=MediaFormPreference.VIDEO_PREFERRED):
    m = deepcopy(m)
    p = active_plan(m)
    p = visual_identity(replace(p, units=[replace(u,
        visual_purpose=VisualPurpose.ENVIRONMENT,
        planned_shots=[replace(s, media_form_preference=form) for s in u.planned_shots])
        for u in p.units]))
    m.visual_planning.plans = [p]
    m.visual_planning.active_creator_plan_id = p.visual_plan_id
    return m


def install_run(m, r, resign=False):
    m = deepcopy(m)
    if resign:
        r = assign_identity(r)
    m.retrieval.runs = [r]
    m.retrieval.active_creator_retrieval_id = r.retrieval_id
    return m


class SyntheticProvider:
    provider_id = "synthetic"
    provider_version = "1"
    catalog_namespace = "public_test"
    source_class = SourceClass.PUBLIC_STOCK
    request_limit = 32
    capabilities = ProviderCapabilities([VisualMediaKind.VIDEO, VisualMediaKind.IMAGE], True)

    def __init__(self, result=None):
        self.result = result if result is not None else ProviderRetrievalResult([
            CandidateProposal("video:123", VisualMediaKind.VIDEO)])
        self.calls = 0

    def retrieve(self, request, control):
        self.calls += 1
        return deepcopy(self.result)


class FailureProvider(SyntheticProvider):
    provider_id = "failure"

    def retrieve(self, request, control):
        raise RuntimeError("PRIVATE_PROVIDER_PAYLOAD")


class MediaRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = build_visual_plan(build_semantic_story(content()))
        cls.intent = with_intent(cls.baseline)

    def test_deterministic_requests_signatures_and_linkage(self):
        m = build_retrieval(self.intent)
        r = active_run(m)
        p = active_plan(m)
        spec = effective_spec((OfflineEmptyProvider(),))
        self.assertFalse(validate(m))
        self.assertEqual(r.upstream_binding_signature, upstream_binding(m, p))
        self.assertEqual(r.retrieval_input_fingerprint, input_fingerprint(p, upstream_binding(m, p)))
        self.assertEqual(r.retrieval_signature, retrieval_signature(r.retrieval_input_fingerprint, spec))
        for (u, s), result in zip([(u, s) for u in p.units for s in u.planned_shots], r.shot_results):
            request = build_request(p, u, s, spec)
            self.assertEqual(request, build_request(p, u, s, spec))
            self.assertEqual(result.request_signature, request_signature(r.retrieval_signature, request))
            self.assertEqual(result.story_unit_ids, s.story_unit_ids)
            self.assertEqual(result.visual_unit_id, u.visual_unit_id)
            self.assertEqual(result.planned_shot_id, s.planned_shot_id)
        self.assertEqual(m.retrieval, build_retrieval(self.intent).retrieval)
        self.assertEqual(m.retrieval, build_retrieval(m).retrieval)
        self.assertEqual(len(m.retrieval.runs), 1)

    def test_unknown_empty_unsupported_and_no_providers(self):
        provider = SyntheticProvider()
        m = build_retrieval(self.baseline, providers=(provider,))
        self.assertEqual(provider.calls, 0)
        self.assertTrue(all(s.outcome == ShotOutcome.INSUFFICIENT_INTENT for s in active_run(m).shot_results))
        empty = active_run(build_retrieval(self.intent))
        self.assertFalse(empty.candidates)
        self.assertTrue(all(s.outcome == ShotOutcome.EMPTY for s in empty.shot_results))
        provider.capabilities = ProviderCapabilities([VisualMediaKind.IMAGE], True)
        unsupported = active_run(build_retrieval(self.intent, providers=(provider,)))
        self.assertTrue(all(s.outcome == ShotOutcome.UNSUPPORTED for s in unsupported.shot_results))
        stage = MediaRetrievalStage(providers=())
        ready = stage.readiness(self.intent)
        self.assertEqual(ready.kind, ReadinessKind.NOT_READY)
        self.assertEqual(ready.diagnostics[0].code, "retrieval_provider_unavailable")

    def test_unknown_geography_is_not_inferred_intent(self):
        from creator_studio.manifest.visual import GeographyRequirement, GeographyFidelity, Evidence
        m = deepcopy(self.baseline)
        p = active_plan(m)
        p = visual_identity(replace(p, units=[replace(u, geography_requirement=GeographyRequirement(
            GeographyFidelity.UNKNOWN, Evidence(u.story_unit_ids))) for u in p.units]))
        m.visual_planning.plans = [p]
        m.visual_planning.active_creator_plan_id = p.visual_plan_id
        provider = SyntheticProvider()
        result = build_retrieval(m, providers=(provider,))
        self.assertEqual(provider.calls, 0)
        self.assertTrue(all(s.outcome == ShotOutcome.INSUFFICIENT_INTENT for s in active_run(result).shot_results))

    def test_missing_and_stale_visual(self):
        for m, code in [(ProjectManifest("empty"), "retrieval_visual_missing"),
                        (content("Changed.", manifest=self.intent), "retrieval_visual_stale")]:
            with self.subTest(code=code), self.assertRaises(RetrievalError) as error:
                build_retrieval(m)
            self.assertEqual(error.exception.code, code)

    def test_review_change_preserves_history_and_stales(self):
        m = build_retrieval(self.intent)
        old = deepcopy(m.retrieval)
        p = active_plan(m)
        p = replace(p, review=VisualReview(ReviewStatus.APPROVED, True))
        p = replace(p, output_signature=visual_output(p))
        m.visual_planning.plans = [p]
        self.assertEqual(p.visual_plan_id, active_plan(self.intent).visual_plan_id)
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_retrieval(m))
        self.assertEqual(m.retrieval, old)
        newer = build_retrieval(m)
        self.assertEqual(len(newer.retrieval.runs), 2)
        self.assertNotEqual(active_run(newer).retrieval_id, old.active_creator_retrieval_id)

    def test_source_changes_stale_without_reactivation(self):
        m = build_retrieval(self.intent)
        for text in ["Different script."]:
            with self.subTest(text=text):
                changed = content(text, manifest=m)
                self.assertIsNone(eligible_active_retrieval(changed))
                self.assertEqual(changed.retrieval, m.retrieval)
        changed = with_intent(self.baseline, MediaFormPreference.IMAGE_PREFERRED)
        changed.visual_planning.plans.insert(0, active_plan(m))
        changed.retrieval = deepcopy(m.retrieval)
        self.assertFalse(validate(changed))
        self.assertIsNone(eligible_active_retrieval(changed))
        changed.retrieval.active_creator_retrieval_id = None
        self.assertIsNone(eligible_active_retrieval(changed))

    def test_source_exact_binding_includes_formatting_and_locator(self):
        m = build_retrieval(self.intent)
        p = active_plan(m)
        old = upstream_binding(m, p)
        source = m.semantic.source_revisions[0]
        for record in [replace(source.content, original_text=source.content.original_text + "\n"),
                       replace(source.content, source_locator="different-public-locator")]:
            changed = deepcopy(m)
            changed.semantic.source_revisions[0] = replace(source, content=record)
            self.assertNotEqual(upstream_binding(changed, p), old)
            self.assertIsNone(eligible_active_retrieval(changed))

    def test_current_source_formatting_and_locator_invalidate_execution_reuse(self):
        stage, m, execution = self._executed()
        record = m.content.records[0]
        for replacement in [replace(record, original_text=record.original_text.replace("\n", "\r\n")),
                            replace(record, source_locator="changed-public-origin")]:
            changed = deepcopy(m)
            changed.content.records[0] = replacement
            self.assertFalse(validate(changed))
            self.assertFalse(stage.validate_reuse(changed, execution))
            self.assertNotEqual(stage.signature_inputs(m), stage.signature_inputs(changed))

    def test_shot_reference_and_coverage_matrix(self):
        m = build_retrieval(self.intent)
        r = active_run(m)
        s = r.shot_results[0]
        variants = [[], r.shot_results[:-1], [s, s], list(reversed(r.shot_results)),
            [replace(s, planned_shot_id="foreign"), *r.shot_results[1:]],
            [replace(s, visual_unit_id="foreign"), *r.shot_results[1:]],
            [replace(s, story_unit_ids=["foreign"]), *r.shot_results[1:]],
            [replace(s, story_unit_ids=[]), *r.shot_results[1:]],
            [replace(s, request_signature="0" * 64), *r.shot_results[1:]]]
        for results in variants:
            with self.subTest(results=results):
                self.assertTrue(validate(install_run(m, replace(r, shot_results=results), True)))

    def test_candidate_identity_metadata_and_cross_shot_dedup(self):
        m = build_retrieval(self.intent, providers=(SyntheticProvider(),))
        r = active_run(m)
        self.assertEqual(len(r.candidates), 1)
        c = r.candidates[0]
        self.assertEqual(c.candidate_id, candidate_id("synthetic", "public_test", "video:123"))
        self.assertNotEqual(c.candidate_id, candidate_id("another", "public_test", "video:123"))
        self.assertNotEqual(c.candidate_id, candidate_id("synthetic", "public_test", "image:123"))
        changed = replace(c, label="New public label")
        self.assertEqual(changed.candidate_id, c.candidate_id)
        self.assertNotEqual(metadata_fingerprint(changed), c.metadata_fingerprint)
        self.assertEqual(metadata_fingerprint(c), c.metadata_fingerprint)
        self.assertTrue(all(s.candidate_ids == [c.candidate_id] for s in r.shot_results))
        self.assertFalse(validate(m))

    def test_candidate_references_and_orphans_rejected(self):
        m = build_retrieval(self.intent, providers=(SyntheticProvider(),))
        r = active_run(m); c = r.candidates[0]; s = r.shot_results[0]
        variants = [replace(r, candidates=[c, c]), replace(r, candidates=[]),
            replace(r, shot_results=[replace(s, candidate_ids=[c.candidate_id, c.candidate_id]), *r.shot_results[1:]]),
            replace(r, candidates=[replace(c, metadata_fingerprint="0" * 64)]),
            replace(r, candidates=[replace(c, candidate_id="candidate:foreign")]),
            replace(r, shot_results=[replace(x, candidate_ids=[], outcome=ShotOutcome.EMPTY) for x in r.shot_results])]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(validate(install_run(m, variant, True)))

    def test_invalid_provider_refs_are_never_persisted(self):
        for ref in ["", "123", "https://host/video/123", "video:token123", "video:123?key=value",
                    "D:\\private.mp4", "video:123\n", "video:" + "x" * 300]:
            provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal(ref, VisualMediaKind.VIDEO)]))
            with self.subTest(ref=ref), self.assertRaises(RetrievalError):
                build_retrieval(self.intent, providers=(provider,))

    def test_unsafe_candidate_material_rejected_before_identity_hashing(self):
        cases = [CandidateProposal("video:sk-example", VisualMediaKind.VIDEO),
                 CandidateProposal("video:123", VisualMediaKind.VIDEO, label="https://invalid.test"),
                 CandidateProposal("video:123", VisualMediaKind.VIDEO,
                     provenance_hint=ProvenanceHint(attribution="Authorization example"))]
        for candidate in cases:
            with self.subTest(candidate=candidate), patch(
                    "creator_studio.retrieval.engine.candidate_id") as identity:
                with self.assertRaises(RetrievalError):
                    build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([candidate])),))
                identity.assert_not_called()

    def test_technical_metadata_matrix(self):
        valid = [CandidateTechnicalMetadata(), CandidateTechnicalMetadata(1920, 1080, 2.0)]
        invalid = [CandidateTechnicalMetadata(True, 1), CandidateTechnicalMetadata(1, False),
            CandidateTechnicalMetadata(0, 2), CandidateTechnicalMetadata(-1, 2),
            CandidateTechnicalMetadata(1, None), CandidateTechnicalMetadata(None, 1),
            CandidateTechnicalMetadata(1.5, 2), CandidateTechnicalMetadata(source_duration_seconds=True),
            CandidateTechnicalMetadata(source_duration_seconds=0.0),
            CandidateTechnicalMetadata(source_duration_seconds=-1.0),
            CandidateTechnicalMetadata(source_duration_seconds=float("nan")),
            CandidateTechnicalMetadata(source_duration_seconds=float("inf"))]
        for metadata in valid + invalid:
            provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal(
                "video:123", VisualMediaKind.VIDEO, technical_metadata=metadata)]))
            with self.subTest(metadata=metadata):
                if metadata in valid:
                    self.assertFalse(validate(build_retrieval(self.intent, providers=(provider,))))
                else:
                    with self.assertRaises(RetrievalError):
                        build_retrieval(self.intent, providers=(provider,))

    def test_media_kind_is_distinct_and_strict(self):
        for kind in ["VIDEO", "AUDIO", VisualMediaKind.UNKNOWN]:
            provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal("video:123", kind)]))
            with self.subTest(kind=kind), self.assertRaises(RetrievalError):
                build_retrieval(self.intent, providers=(provider,))
        image = with_intent(self.baseline, MediaFormPreference.IMAGE_PREFERRED)
        bad = CandidateProposal("image:123", VisualMediaKind.IMAGE,
            technical_metadata=CandidateTechnicalMetadata(source_duration_seconds=1.0))
        with self.assertRaises(RetrievalError):
            build_retrieval(image, providers=(SyntheticProvider(ProviderRetrievalResult([bad])),))

    def test_rights_single_enum_and_non_authority(self):
        self.assertIs(OldRights, Rights)
        self.assertEqual([r.value for r in Rights], ["OWNED", "LICENSED", "PUBLIC_DOMAIN", "REFERENCE_ONLY", "UNKNOWN"])
        for rights in Rights:
            self.assertIs(decode(Rights, to_data(rights)), rights)
            self.assertIs(MediaReference().provenance.rights, Rights.REFERENCE_ONLY)
            proposal = CandidateProposal("video:123", VisualMediaKind.VIDEO,
                provenance_hint=ProvenanceHint(rights, ClaimOrigin.PROVIDER_DECLARATION),
                usage_restriction=UsageRestriction.REFERENCE_ONLY)
            m = build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([proposal])),))
            c = active_run(m).candidates[0]
            self.assertEqual(c.usage_restriction, UsageRestriction.REFERENCE_ONLY)
            self.assertNotIn("final_eligible", to_data(c))
            self.assertEqual(m.media, self.intent.media)

    def test_deterministic_order_truncation_and_source_precedence(self):
        proposals = [CandidateProposal("video:" + str(n), VisualMediaKind.VIDEO) for n in [7, 1, 4, 2]]
        public = SyntheticProvider(ProviderRetrievalResult(proposals))
        owned = SyntheticProvider(ProviderRetrievalResult([CandidateProposal("video:99", VisualMediaKind.VIDEO)]))
        owned.provider_id = "owned_test"
        owned.source_class = SourceClass.PERSONAL_LIBRARY
        spec = RetrievalSpec(candidates_per_shot=3)
        m = build_retrieval(self.intent, providers=(public, owned), spec=spec)
        r = active_run(m)
        expected = [candidate_id("owned_test", "public_test", "video:99"), candidate_id("synthetic", "public_test", "video:7"),
                    candidate_id("synthetic", "public_test", "video:1")]
        self.assertTrue(all(s.candidate_ids == expected for s in r.shot_results))
        self.assertTrue(all(s.diagnostics[0].code == "retrieval_limit_exceeded" for s in r.shot_results))
        self.assertEqual([c.candidate_id for c in r.candidates], sorted(expected))
        self.assertEqual(m.retrieval, build_retrieval(self.intent, providers=(public, owned), spec=spec).retrieval)

    def test_provider_execution_order_cannot_replace_signed_order(self):
        # Discovery positions, not provider-side work/completion bookkeeping, order results.
        first = SyntheticProvider(); second = SyntheticProvider()
        second.provider_id = "second"
        second.completed_first = True
        r = active_run(build_retrieval(self.intent, providers=(first, second)))
        self.assertEqual(r.shot_results[0].candidate_ids,
            [candidate_id("synthetic", "public_test", "video:123"), candidate_id("second", "public_test", "video:123")])
        reverse = active_run(build_retrieval(self.intent, providers=(second, first)))
        self.assertNotEqual(r.retrieval_signature, reverse.retrieval_signature)
        self.assertEqual(reverse.shot_results[0].candidate_ids, list(reversed(r.shot_results[0].candidate_ids)))

    def test_effective_provider_request_limit_and_no_form_substitution(self):
        provider = SyntheticProvider()
        captured = []
        original = provider.retrieve
        def retrieve(request, control):
            captured.append(request.provider_request_limit)
            return original(request, control)
        provider.retrieve = retrieve
        build_retrieval(self.intent, providers=(provider,), spec=RetrievalSpec(provider_candidate_limit=1))
        self.assertEqual(captured, [1, 1])
        image = CandidateProposal("image:123", VisualMediaKind.IMAGE)
        m = build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([image])),))
        self.assertFalse(active_run(m).candidates)
        self.assertTrue(all(s.outcome == ShotOutcome.EMPTY for s in active_run(m).shot_results))

    def test_conflicting_duplicates_rejected_same_batch_and_across_shots(self):
        first = CandidateProposal("video:123", VisualMediaKind.VIDEO, label="A")
        second = replace(first, label="B")
        with self.assertRaises(RetrievalError):
            build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([first, second])),))
        class ChangingProvider(SyntheticProvider):
            def retrieve(self, request, control):
                self.calls += 1
                return ProviderRetrievalResult([first if self.calls == 1 else second])
        m = build_retrieval(self.intent, providers=(ChangingProvider(),))
        r = active_run(m)
        self.assertEqual(r.candidates[0].label, "A")
        self.assertEqual(r.shot_results[1].outcome, ShotOutcome.FAILED)
        self.assertEqual(r.diagnostics[0].code, "retrieval_provider_partial")

    def test_duplicate_observations_dedup_stably(self):
        proposal = CandidateProposal("video:123", VisualMediaKind.VIDEO)
        m = build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([proposal, proposal])),))
        self.assertEqual(len(active_run(m).candidates), 1)
        self.assertTrue(all(len(s.candidate_ids) == 1 for s in active_run(m).shot_results))

    def test_typed_match_evidence_and_conflict_filter(self):
        candidate = CandidateProposal("video:123", VisualMediaKind.VIDEO)
        for finding in Finding:
            evidence = MatchEvidence("untrusted", MatchAspect.SUBJECT, finding, "test_method", "1")
            provider = SyntheticProvider(ProviderRetrievalResult([candidate], [ProposalAssessment(0, evidence)]))
            m = build_retrieval(self.intent, providers=(provider,))
            r = active_run(m)
            if finding == Finding.CONFLICT:
                self.assertFalse(r.candidates)
                self.assertTrue(all(s.outcome == ShotOutcome.EMPTY for s in r.shot_results))
            else:
                e = r.shot_results[0].assessments[0]
                self.assertEqual(e.candidate_id, r.candidates[0].candidate_id)
                self.assertEqual(e.finding, finding)
                self.assertEqual(r.candidates[0].usage_restriction, UsageRestriction.UNVERIFIED)

    def test_assessment_reference_matrix(self):
        candidate = CandidateProposal("video:123", VisualMediaKind.VIDEO)
        base = MatchEvidence("", MatchAspect.SUBJECT, Finding.MATCH, "method", "1")
        from creator_studio.manifest.visual import SemanticMentionRef
        for assessment in [ProposalAssessment(-1, base), ProposalAssessment(True, base),
                ProposalAssessment(1, base), ProposalAssessment(0, replace(base, method_id="https://private")),
                ProposalAssessment(0, replace(base, evidence_ref=SemanticMentionRef("foreign", 0, "0" * 64)))]:
            with self.subTest(assessment=assessment), self.assertRaises(RetrievalError):
                build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([candidate], [assessment])),))

    def test_provider_failure_sanitized_partial_and_atomic(self):
        before = deepcopy(self.intent)
        stage = MediaRetrievalStage(providers=(FailureProvider(),))
        outcome = stage.execute(StageContext(self.intent, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertIsNone(outcome.update)
        self.assertFalse(outcome.result.artifacts)
        self.assertNotIn("PRIVATE_PROVIDER_PAYLOAD", repr(outcome))
        self.assertEqual(self.intent, before)
        m = build_retrieval(self.intent, providers=(FailureProvider(), SyntheticProvider()))
        self.assertFalse(validate(m))
        self.assertEqual(active_run(m).diagnostics[0].code, "retrieval_provider_partial")

    def test_every_provider_metadata_property_is_controlled(self):
        class CustomFailure(Exception):
            pass
        for exception in (RuntimeError, AttributeError, ValueError, CustomFailure):
            for name in ("provider_id", "provider_version", "capabilities", "catalog_namespace", "source_class", "request_limit"):
                def broken(self, exception=exception):
                    raise exception("PRIVATE_PROVIDER_PAYLOAD")
                cls = type("BrokenMetadata", (SyntheticProvider,), {name: property(broken)})
                provider = cls()
                with self.subTest(name=name, exception=exception):
                    with self.assertRaises(RetrievalError) as error:
                        build_retrieval(self.intent, providers=(provider,))
                    self.assertEqual(error.exception.code, "retrieval_provider_unavailable")
                    self.assertNotIn("PRIVATE_PROVIDER_PAYLOAD", str(error.exception))
                    self.assertEqual(MediaRetrievalStage(providers=(provider,)).readiness(self.intent).kind,
                                     ReadinessKind.NOT_READY)
        with self.assertRaises(RetrievalError):
            build_retrieval(self.intent, providers=(object(),))

    def test_provider_result_and_copy_failures_controlled(self):
        class CopyFailure:
            def __deepcopy__(self, memo):
                raise RuntimeError("PRIVATE_PROVIDER_PAYLOAD")
        for response in [object(), CopyFailure(), ProviderRetrievalResult(diagnostics=[RetrievalDiagnostic("raw_payload")])]:
            provider = SyntheticProvider()
            provider.retrieve = lambda *args: response
            with self.subTest(response=type(response)), self.assertRaises(RetrievalError):
                build_retrieval(self.intent, providers=(provider,))

    def test_provider_cannot_mutate_project_through_request(self):
        class MutatingProvider(SyntheticProvider):
            def retrieve(self, request, control):
                request.story_unit_ids.clear()
                request.requirements.clear()
                return super().retrieve(request, control)
        before = deepcopy(self.intent)
        m = build_retrieval(self.intent, providers=(MutatingProvider(),))
        self.assertEqual(before, self.intent)
        self.assertEqual(m.visual_planning, before.visual_planning)
        self.assertFalse(validate(m))

    def test_cancellation_at_all_engine_checkpoints_is_atomic(self):
        class CountingControl:
            def __init__(self, stop=None):
                self.count = 0
                self.stop = stop
            def check(self):
                self.count += 1
                if self.count == self.stop:
                    raise Cancelled()
        probe = CountingControl()
        build_retrieval(self.intent, providers=(SyntheticProvider(),), control=probe)
        before = deepcopy(self.intent)
        for checkpoint in range(1, probe.count + 1):
            with self.subTest(checkpoint=checkpoint), self.assertRaises(Cancelled):
                build_retrieval(self.intent, providers=(SyntheticProvider(),), control=CountingControl(checkpoint))
            self.assertEqual(self.intent, before)

    def test_late_stage_cancellation_after_artifacts(self):
        token = CancellationToken()
        stage = MediaRetrievalStage()
        original = stage.artifacts
        def cancel(*args):
            artifacts = original(*args)
            token.cancel()
            return artifacts
        stage.artifacts = cancel
        before = deepcopy(self.intent)
        with self.assertRaises(Cancelled):
            stage.execute(StageContext(self.intent, token, 1, lambda *a: None))
        self.assertEqual(before, self.intent)

    def test_limits_and_history_ceiling_no_pruning(self):
        provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal(
            "video:" + str(i), VisualMediaKind.VIDEO) for i in range(33)]))
        with self.assertRaises(RetrievalError):
            build_retrieval(self.intent, providers=(provider,))
        for spec in [RetrievalSpec(candidates_per_shot=0), RetrievalSpec(provider_candidate_limit=True),
                     RetrievalSpec(total_unique_candidates=MAX_CANDIDATES + 1)]:
            with self.subTest(spec=spec), self.assertRaises(RetrievalError):
                build_retrieval(self.intent, spec=spec)
        provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal(
            "video:" + str(i), VisualMediaKind.VIDEO) for i in range(3)]))
        with self.assertRaises(RetrievalError) as error:
            build_retrieval(self.intent, providers=(provider,), spec=RetrievalSpec(total_unique_candidates=2))
        self.assertEqual(error.exception.code, "retrieval_limit_exceeded")
        m = build_retrieval(self.intent)
        with patch("creator_studio.manifest.retrieval_validation.MAX_RUNS", 1):
            before = deepcopy(m)
            with self.assertRaises(RetrievalError):
                build_retrieval(m, spec=RetrievalSpec(candidates_per_shot=1))
            self.assertEqual(m, before)

    def test_request_identity_separate_from_result_identity(self):
        first = active_run(build_retrieval(self.intent, providers=(SyntheticProvider(),)))
        second = active_run(build_retrieval(self.intent, providers=(SyntheticProvider(
            ProviderRetrievalResult([CandidateProposal("video:456", VisualMediaKind.VIDEO)])),)))
        self.assertEqual(first.retrieval_signature, second.retrieval_signature)
        self.assertEqual(first.shot_results[0].request_signature, second.shot_results[0].request_signature)
        self.assertNotEqual(first.retrieval_id, second.retrieval_id)

    def test_all_behavior_options_signed(self):
        provider = SyntheticProvider()
        base = effective_spec((provider,))
        alternatives = [replace(base, candidates_per_shot=1), replace(base, total_unique_candidates=5),
            replace(base, provider_candidate_limit=64), replace(base, retriever_version="2"),
            replace(base, source_precedence=list(reversed(base.source_precedence))),
            replace(base, allowed_media_kinds=[VisualMediaKind.VIDEO]),
            replace(base, providers=[replace(base.providers[0], provider_version="2")]),
            replace(base, providers=[replace(base.providers[0], catalog_namespace="another")]),
            replace(base, providers=[replace(base.providers[0], request_limit=1)]),
            replace(base, providers=[replace(base.providers[0], supports_structured_intent=False)])]
        for spec in alternatives:
            with self.subTest(spec=spec):
                self.assertTrue(spec_valid(spec))
                self.assertNotEqual(retrieval_signature("0" * 64, base), retrieval_signature("0" * 64, spec))

    def test_save_load_unicode_and_additive_strict_migration(self):
        m = build_retrieval(self.intent, providers=(SyntheticProvider(ProviderRetrievalResult([
            CandidateProposal("video:123", VisualMediaKind.VIDEO, label="Cảnh thiên nhiên 日本語")])),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Dự án.json"
            save(m, path)
            self.assertEqual(m, load(path))
        data = to_data(m)
        self.assertEqual(data["schema_version"], 2)
        del data["retrieval"]
        self.assertEqual(decode(ProjectManifest, migrate_document(data)).retrieval, RetrievalState())
        for value in [None, {}, {"runs": []}, {"runs": [], "active_creator_retrieval_id": None, "unknown": 1}]:
            data["retrieval"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(data))

    def test_whole_manifest_boundaries_unchanged(self):
        m = deepcopy(self.intent)
        m.voice.style = "Independent voice setting"
        result = build_retrieval(m, providers=(SyntheticProvider(),))
        for f in fields(ProjectManifest):
            if f.name != "retrieval":
                self.assertEqual(getattr(m, f.name), getattr(result, f.name), f.name)
        first = active_run(build_retrieval(self.intent))
        second = active_run(build_retrieval(m))
        self.assertEqual(first.retrieval_signature, second.retrieval_signature)

    def test_no_urls_queries_or_extra_contract_fields(self):
        cfields = {f.name for f in fields(CandidateDescriptor)}
        self.assertEqual(cfields, {"candidate_id", "provider_id", "provider_candidate_ref", "catalog_namespace", "source_class",
            "visual_media_kind", "label", "technical_metadata", "provenance_hint", "usage_restriction", "metadata_fingerprint"})
        forbidden = {"url", "download_path", "search_query", "keywords", "selected", "approved", "locked",
                     "final_eligible", "score", "winner", "timeline", "voice"}
        data = to_data(active_run(build_retrieval(self.intent, providers=(SyntheticProvider(),))))
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertFalse(any(term in key for term in forbidden), key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(data)
        serialized = json.dumps(data)
        self.assertNotIn("First paragraph", serialized)
        self.assertNotIn("://", serialized)

    def _executed(self, stage=None, manifest=None):
        stage = stage or MediaRetrievalStage()
        # Build retained execution exactly as M62 would, without disk dependency.
        from creator_studio.manifest.signatures import dependency_signature
        from creator_studio.manifest.models import ProcessingState, Status
        outcome = stage.execute(StageContext(manifest or self.intent, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m = outcome.update.manifest
        execution = outcome.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing = [ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution)]
        return stage, m, execution

    def test_offline_reuse_and_custom_default_no_reuse(self):
        stage, m, execution = self._executed()
        self.assertTrue(stage.validate_reuse(m, execution))
        stage, m, execution = self._executed(MediaRetrievalStage(providers=(SyntheticProvider(),)))
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_exact_two_artifacts_and_missing_reordered_invalid(self):
        stage, m, execution = self._executed()
        self.assertEqual(len(execution.artifacts), 2)
        self.assertTrue(execution.artifacts[0].reference.startswith("retrieval/"))
        self.assertTrue(execution.artifacts[1].reference.startswith("retrieval_visual/"))
        for artifacts in [execution.artifacts[:1], execution.artifacts[1:], list(reversed(execution.artifacts))]:
            changed = deepcopy(m)
            changed.processing[0].execution.artifacts = artifacts
            self.assertFalse(stage.validate_reuse(changed, changed.processing[0].execution))
        serialized = json.dumps(to_data(execution.artifacts))
        for value in ["://", "First paragraph", "Authorization", "PRIVATE_PROVIDER_PAYLOAD"]:
            self.assertNotIn(value, serialized)

    def test_execution_identity_spec_and_provider_changes_invalidate_reuse(self):
        stage, m, execution = self._executed()
        self.assertFalse(stage.validate_reuse(m, replace(execution, stage_version="2")))
        self.assertFalse(MediaRetrievalStage(spec=RetrievalSpec(candidates_per_shot=1)).validate_reuse(m, execution))
        provider = OfflineEmptyProvider()
        provider.provider_version = "2"
        self.assertFalse(MediaRetrievalStage(providers=(provider,)).validate_reuse(m, execution))
        provider = OfflineEmptyProvider()
        provider.catalog_namespace = "changed"
        self.assertFalse(MediaRetrievalStage(providers=(provider,)).validate_reuse(m, execution))

    def test_self_consistent_baseline_forgery_rejected(self):
        stage, m, execution = self._executed()
        r = active_run(m)
        c = CandidateDescriptor("", "offline_empty", "video:forged", "empty", SourceClass.UNKNOWN,
            VisualMediaKind.VIDEO, None, CandidateTechnicalMetadata(), ProvenanceHint(), UsageRestriction.UNVERIFIED, "")
        c = replace(c, candidate_id=candidate_id(c.provider_id, c.catalog_namespace, c.provider_candidate_ref))
        c = replace(c, metadata_fingerprint=metadata_fingerprint(c))
        r = assign_identity(replace(r, candidates=[c], shot_results=[replace(s,
            outcome=ShotOutcome.CANDIDATES, candidate_ids=[c.candidate_id], diagnostics=[]) for s in r.shot_results]))
        forged = install_run(m, r)
        forged.processing[0].execution.artifacts = stage.artifacts(forged, r, active_plan(forged))
        self.assertFalse(validate(forged))
        self.assertFalse(stage.validate_reuse(forged, forged.processing[0].execution))

    def test_self_consistent_invalid_provider_outcomes_and_evidence_rejected(self):
        m = build_retrieval(self.intent, providers=(SyntheticProvider(),))
        r = active_run(m)
        variants = [replace(r, provider_outcomes=[]),
            replace(r, provider_outcomes=list(reversed(r.provider_outcomes))),
            replace(r, provider_outcomes=[*r.provider_outcomes, r.provider_outcomes[0]]),
            replace(r, shot_results=[replace(s, assessments=[MatchEvidence(s.candidate_ids[0],
                MatchAspect.SUBJECT, Finding.CONFLICT, "method", "1")]) for s in r.shot_results])]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(validate(install_run(m, variant, True)))

    def test_combined_workflow_dependency_and_required_specs(self):
        from creator_studio.visual.stage import VisualDirectorStage
        p = active_plan(self.baseline)
        d = self.baseline.semantic.documents[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "combined.json"
            save(self.baseline, path)
            runner = ProjectOrchestrator(ManifestRepository(path))
            runner.register(VisualDirectorStage())
            runner.register(MediaRetrievalStage(dependencies=("visual_director",),
                required_visual_spec=p.planning_spec, required_semantic_spec=d.analysis_spec))
            self.assertEqual(runner.run().status, StageStatus.SUCCEEDED)
            repeated = runner.run()
            self.assertEqual(repeated.results[-1].status, StageStatus.SKIPPED)
            self.assertIn(repeated.results[0].status, (StageStatus.SUCCEEDED, StageStatus.SKIPPED))
        self.assertEqual(MediaRetrievalStage(required_visual_spec=replace(p.planning_spec,
            planner_version="2")).readiness(self.baseline).kind, ReadinessKind.NOT_READY)

    def test_old_m61_document_defaults_without_later_extensions(self):
        data = to_data(ProjectManifest("M61"))
        for name in ["semantic", "visual_planning", "retrieval"]:
            del data[name]
        del data["content"]["records"]
        del data["content"]["canonical_content_id"]
        loaded = decode(ProjectManifest, migrate_document(data))
        self.assertFalse(validate(loaded))
        self.assertEqual(loaded.schema_version, 2)
        self.assertEqual(loaded.retrieval, RetrievalState())

    def test_orchestrator_reuses_baseline_without_duplicate_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            save(self.intent, path)
            runner = ProjectOrchestrator(ManifestRepository(path))
            runner.register(MediaRetrievalStage())
            self.assertEqual(runner.run().status, StageStatus.SUCCEEDED)
            self.assertEqual(runner.run().results[0].status, StageStatus.SKIPPED)
            self.assertEqual(len(load(path).retrieval.runs), 1)

    def test_long_collection_linear_coverage(self):
        m = build_visual_plan(build_semantic_story(content("\n\n".join(
            "Đoạn văn số " + str(i) + "." for i in range(120)))))
        result = build_retrieval(m)
        r = active_run(result)
        self.assertEqual(len(r.shot_results), sum(len(u.planned_shots) for u in active_plan(m).units))
        self.assertEqual(len(r.shot_results), 120)
        self.assertFalse(validate(result))

    def test_untrusted_exception_codes_never_persist(self):
        from creator_studio.manifest.retrieval_validation import DIAGNOSTIC_CODES
        payloads = ["private_payload_abc123", "api_key_abc123", "bearer_secret_xyz",
                    "https://secret.example/token"]
        before = deepcopy(self.intent)
        names = ("provider_id", "provider_version", "capabilities", "catalog_namespace",
                 "source_class", "request_limit", "retrieve")
        for name in names:
            for payload in payloads:
                def broken(*args, value=payload):
                    raise RetrievalError(value)
                member = broken if name == "retrieve" else property(broken)
                provider = type("UntrustedCode", (SyntheticProvider,), {name: member})()
                stage = MediaRetrievalStage(providers=(provider,))
                with self.subTest(name=name, payload=payload):
                    with self.assertRaises(RetrievalError) as error:
                        build_retrieval(self.intent, providers=(provider,))
                    expected = ("retrieval_provider_failed" if name == "retrieve"
                                else "retrieval_provider_unavailable")
                    self.assertEqual(error.exception.code, expected)
                    outcome = stage.execute(StageContext(self.intent, CancellationToken(), 1, lambda *a: None))
                    self.assertIsNone(outcome.update)
                    self.assertTrue(all(d.code in DIAGNOSTIC_CODES for d in outcome.result.diagnostics))
                    for value in (stage.readiness(self.intent), stage.signature_inputs(self.intent), outcome.result):
                        self.assertNotIn(payload, repr(value))
                    # Exercise actual M62 persistence without modifying M62.
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / "failure.json"
                        save(self.intent, path)
                        runner = ProjectOrchestrator(ManifestRepository(path))
                        runner.register(stage)
                        runner.run()
                        retained = load(path)
                        self.assertNotIn(payload, path.read_text(encoding="utf-8"))
                        self.assertNotIn(payload, json.dumps(to_data(retained)))
                        execution = retained.processing[0].execution
                        self.assertTrue(execution.diagnostics)
                        self.assertTrue(all(d.code in DIAGNOSTIC_CODES for d in execution.diagnostics))
                        for field in fields(self.intent):
                            if field.name not in {"processing", "metadata", "status", "updated_at"}:
                                self.assertEqual(getattr(retained, field.name), getattr(self.intent, field.name))
                    self.assertEqual(self.intent, before)

    def test_stage_defends_against_unexpected_internal_codes(self):
        from creator_studio.manifest.retrieval_validation import DIAGNOSTIC_CODES
        stage = MediaRetrievalStage()
        for code in DIAGNOSTIC_CODES:
            self.assertEqual(stage._diagnostics(code)[0].code, code)
        for code in ("private_payload_abc123", "api_key_abc123", "bearer_secret_xyz",
                     "https://secret.example/token", [], None):
            self.assertEqual(stage._diagnostics(code)[0].code, "retrieval_candidate_invalid")
            with patch.object(stage, "_inputs", side_effect=RetrievalError(code)):
                self.assertEqual(stage.signature_inputs(self.intent), {"unavailable": "retrieval_candidate_invalid"})
                self.assertEqual(stage.readiness(self.intent).diagnostics[0].code, "retrieval_candidate_invalid")
            with patch("creator_studio.retrieval.stage.build_retrieval", side_effect=RetrievalError(code)):
                outcome = stage.execute(StageContext(self.intent, CancellationToken(), 1, lambda *a: None))
                self.assertEqual(outcome.result.diagnostics[0].code, "retrieval_candidate_invalid")

    def test_catalog_identity_and_all_dependent_signatures(self):
        m = build_retrieval(self.intent, providers=(SyntheticProvider(),))
        run = active_run(m)
        c = run.candidates[0]
        self.assertEqual(c.candidate_id, "candidate:" + exact_signature(
            ["2", "synthetic", "public_test", "video:123"]))
        for name, value in (("catalog_namespace", "other_catalog"), ("provider_id", "other_provider")):
            provider = SyntheticProvider()
            setattr(provider, name, value)
            other = active_run(build_retrieval(self.intent, providers=(provider,)))
            self.assertNotEqual(c.candidate_id, other.candidates[0].candidate_id)
            self.assertNotEqual(run.retrieval_signature, other.retrieval_signature)
            self.assertNotEqual(run.retrieval_id, other.retrieval_id)
        provider = SyntheticProvider()
        provider.provider_version = "2"
        newer = active_run(build_retrieval(self.intent, providers=(provider,)))
        self.assertEqual(c.candidate_id, newer.candidates[0].candidate_id)
        self.assertNotEqual(run.retrieval_signature, newer.retrieval_signature)
        changed = replace(c, catalog_namespace="other_catalog")
        self.assertFalse(candidate_valid(changed))
        self.assertNotEqual(metadata_fingerprint(c), metadata_fingerprint(changed))
        altered = replace(run, candidates=[changed])
        self.assertNotEqual(exact_signature(generated_payload(run)), exact_signature(generated_payload(altered)))
        self.assertNotEqual(run_id(run), run_id(altered))
        self.assertNotEqual(output_signature(run), output_signature(altered))
        self.assertNotEqual(MediaRetrievalStage.artifacts(m, run, active_plan(m)),
                            MediaRetrievalStage.artifacts(m, altered, active_plan(m)))
        self.assertTrue(validate(install_run(m, altered, True)))
        # Even a recomputed ID/digest cannot contradict the captured provider catalog.
        changed = replace(changed, candidate_id=candidate_id(changed.provider_id,
            changed.catalog_namespace, changed.provider_candidate_ref))
        changed = replace(changed, metadata_fingerprint=metadata_fingerprint(changed))
        self.assertTrue(validate(install_run(m, replace(run, candidates=[changed]), True)))
        # Today's provider configuration affects eligibility, never historical structure.
        provider = SyntheticProvider()
        provider.catalog_namespace = "today_catalog"
        self.assertIsNone(eligible_active_retrieval(m, effective_spec((provider,))))
        self.assertFalse(validate(m))
        self.assertEqual(decode(ProjectManifest, to_data(m)), m)

    def test_public_reference_grammar_and_persistent_fields(self):
        from creator_studio.manifest.retrieval_validation import (
            logical_ref, catalog_namespace_valid, candidate_fields_valid, MAX_PUBLIC_ASSET_ID_LENGTH)
        accepted = ["video:123", "video:abc_123", "image:abc_123", "image:abc-123",
                    "asset:foo.bar-9", "clip:library-001", "shot:virtual-00042"]
        rejected = ["https://host/item", "https:example.com", "http:foo", "file://x", "file:x",
                    "C:\\foo", "C:foo", "/home/user/x", "../relative", "video:abc?token=x",
                    "video:abc#fragment", "video:user@host", "video:abc%2Fdef",
                    "video:" + "a" * (MAX_PUBLIC_ASSET_ID_LENGTH + 1), "video:bearer_abc123",
                    "video:api_key_abc123", "video:abc def", "video:abc\n", "video:foo:bar",
                    "HTTPS:foo", "s3:bucket", "data:abc", "blob:abc", "javascript:abc"]
        c = active_run(build_retrieval(self.intent, providers=(SyntheticProvider(),))).candidates[0]
        for ref in accepted:
            with self.subTest(accepted=ref):
                self.assertTrue(logical_ref(ref))
                self.assertTrue(candidate_fields_valid(replace(c, provider_candidate_ref=ref)))
        for ref in rejected:
            with self.subTest(rejected=ref):
                self.assertFalse(logical_ref(ref))
                self.assertFalse(candidate_fields_valid(replace(c, provider_candidate_ref=ref)))
                provider = SyntheticProvider(ProviderRetrievalResult([CandidateProposal(ref, VisualMediaKind.VIDEO)]))
                with patch("creator_studio.retrieval.engine.candidate_id") as identity:
                    with self.assertRaises(RetrievalError):
                        build_retrieval(self.intent, providers=(provider,))
                    identity.assert_not_called()
        for namespace in ("public_test", "library-001", "catalog.v2"):
            self.assertTrue(catalog_namespace_valid(namespace))
        for namespace in rejected + ["https", "file", "api_key_abc123", "a" * 49, "1catalog"]:
            with self.subTest(catalog=namespace):
                self.assertFalse(catalog_namespace_valid(namespace))
                self.assertFalse(candidate_fields_valid(replace(c, catalog_namespace=namespace)))
                provider = SyntheticProvider()
                provider.catalog_namespace = namespace
                with self.assertRaises(RetrievalError):
                    effective_spec((provider,))
        # Separate display validation remains intact and permits ordinary prose.
        self.assertTrue(candidate_fields_valid(replace(c, label="A public landscape label",
            provenance_hint=ProvenanceHint(license_identifier="Public license 1", attribution="Creator Example"))))

    def test_imports_are_offline_and_foundation_only(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = {"requests", "httpx", "urllib", "aiohttp", "PyQt6", "stock", "pipeline",
                     "subprocess", "ffmpeg", "openai"}
        for path in (root / "creator_studio" / "retrieval").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [n.name.split(".")[0] for n in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]] if not node.level else []
                else:
                    continue
                self.assertFalse(set(names) & forbidden, path.name)


if __name__ == "__main__":
    unittest.main()
