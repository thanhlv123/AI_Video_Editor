"""M68 offline adversarial contracts; providers and inspectors here are synthetic."""
import ast
from copy import deepcopy
from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, validate, save, load
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.acquisition import *
from creator_studio.manifest.acquisition_validation import spec_valid, inspection_valid
from creator_studio.manifest.selection import (SelectionSource, SelectionReason, ReviewStatus,
    effective_output_signature, assign_identity as selection_identity)
from creator_studio.manifest.retrieval import VisualMediaKind
from creator_studio.manifest.models import ProcessingState, Status
from creator_studio.manifest.signatures import dependency_signature
from creator_studio.acquisition.engine import build_acquisition, current_usability, boundary_unchanged
from creator_studio.acquisition.provider import ResolvedRendition, choose_rendition
from creator_studio.acquisition.inspector import UnavailableInspector
from creator_studio.acquisition.storage import ManagedStorage
from creator_studio.acquisition.models import AcquisitionError
from creator_studio.acquisition.stage import MediaAcquisitionStage
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
from creator_studio.selection.engine import append_review, build_selection
from creator_studio.retrieval.engine import build_retrieval
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.visual.engine import build_visual_plan
from tests.test_semantic_story import content
from tests.test_media_retrieval import with_intent
from tests.test_media_selection import selected_fixture, active


class OfflineProvider:
    def __init__(self, data=b"synthetic-media", permitted=True):
        self.spec = AcquisitionProviderSpec("synthetic", "public_test", permits_acquisition=permitted)
        self.data = data
        self.calls = self.transfers = 0
        self.failure = None
        self.cancel_resolve = False

    def resolve(self, request, control):
        self.calls += 1
        self.request = request
        if self.cancel_resolve:
            control.cancel()
        if self.failure:
            raise self.failure
        return [ResolvedRendition(RenditionObservation("original", VisualMediaKind.VIDEO, 640, 480), object())]

    def acquire(self, handle, sink, control):
        self.transfers += 1
        if self.data:
            sink.write(self.data)


class OfflineInspector:
    inspector_id = "synthetic"
    inspector_version = "1"
    policy_id = "objective_media"
    policy_version = "1"

    def __init__(self):
        self.calls = 0
        self.mutate = None
        self.facts = InspectionFacts("synthetic", "1", VisualMediaKind.VIDEO,
            MediaFormat.MP4, MediaCodec.H264, 640, 480, 2.0)

    def inspect(self, path, control):
        self.calls += 1
        if self.mutate is not None:
            path.write_bytes(self.mutate)
        return self.facts


class CountingControl:
    def __init__(self, stop=None):
        self.count, self.stop = 0, stop

    def check(self):
        self.count += 1
        if self.count == self.stop:
            raise Cancelled()


class MediaAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intent = with_intent(build_visual_plan(build_semantic_story(content())))
        cls.built = selected_fixture(cls.intent)

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = ManagedStorage(Path(self.temp.name) / "managed")
        self.provider = OfflineProvider()
        self.inspector = OfflineInspector()
        self.spec = AcquisitionSpec(providers=[self.provider.spec])

    def build(self, manifest=None, **kwargs):
        args = dict(storage=self.storage, providers=(self.provider,), inspector=self.inspector, spec=self.spec)
        args.update(kwargs)
        return build_acquisition(manifest or self.built, **args)

    def usable(self, m, **kwargs):
        args = dict(storage=self.storage, inspector=self.inspector, spec=self.spec)
        args.update(kwargs)
        return current_usability(m, **args)

    def stage(self, **kwargs):
        args = dict(storage=self.storage, providers=(self.provider,), inspector=self.inspector, spec=self.spec)
        args.update(kwargs)
        return MediaAcquisitionStage(**args)

    def executed(self):
        stage = self.stage()
        result = stage.execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.SUCCEEDED)
        m, execution = result.update.manifest, result.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing = [ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution)]
        return stage, m, execution

    def test_additive_empty_state(self):
        m = ProjectManifest("empty")
        self.assertEqual(m.acquisition, AcquisitionState())
        self.assertEqual(m.schema_version, 2)
        self.assertFalse(validate(m))

    def test_older_schema2_loads(self):
        data = to_data(ProjectManifest("old"))
        del data["acquisition"]
        path = Path(self.temp.name) / "old.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(load(path).acquisition, AcquisitionState())

    def test_malformed_present_rejected(self):
        for value in (None, [], {}, {"runs": []}, "bad"):
            data = to_data(ProjectManifest("bad"))
            data["acquisition"] = value
            with self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(data))

    def test_selected_exact_chain_and_digest(self):
        m = self.build()
        self.assertFalse(validate(m))
        run = m.acquisition.runs[0]
        self.assertEqual(run.selection_id, active(m).selection_id)
        self.assertEqual([s.shot_selection_id for s in run.shot_acquisitions],
                         [s.shot_selection_id for s in active(m).shot_selections])
        record = m.acquisition.materializations[0]
        self.assertEqual(record.candidate_id, active(m).shot_selections[0].selected_candidate.candidate_id)
        self.assertEqual(record.retrieval_id, active(m).retrieval_id)
        asset = m.acquisition.assets[0]
        self.assertEqual(asset.sha256, hashlib.sha256(self.provider.data).hexdigest())
        self.assertEqual(asset.asset_id, "asset:sha256:" + asset.sha256)
        self.assertEqual(asset.object_key, object_key(asset.sha256))
        self.assertTrue(self.usable(m))

    def test_all_unresolved_zero_calls_and_structural_success(self):
        m = build_selection(build_retrieval(self.intent))
        with patch.object(self.storage, "staging", side_effect=AssertionError("storage called")):
            out = self.build(m)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.inspector.calls, 0)
        self.assertFalse(validate(out))
        self.assertFalse(complete(out.acquisition.runs[0]))
        self.assertTrue(all(s.outcome == AcquisitionOutcome.NOT_SELECTED_UPSTREAM
                            for s in out.acquisition.runs[0].shot_acquisitions))

    def test_stale_selection_before_provider(self):
        m = deepcopy(self.built)
        m.selection.active_creator_selection_id = None
        with self.assertRaises(AcquisitionError):
            self.build(m)
        self.assertEqual(self.provider.calls, 0)

    def test_creator_rejected_independent_gate(self):
        m = deepcopy(self.built)
        old = active(m)
        changed = selection_identity(replace(old, shot_selections=[replace(s,
            source=SelectionSource.CREATOR, reason=SelectionReason.CREATOR_CHOICE) for s in old.shot_selections]))
        m.selection.runs = [changed]
        m.selection.active_creator_selection_id = changed.selection_id
        m = append_review(m, expected_selection_id=changed.selection_id,
            expected_choice=changed.shot_selections[0], expected_predecessor=None,
            status=ReviewStatus.REJECTED, locked=False)
        self.assertFalse(validate(m))
        with self.assertRaises(AcquisitionError):
            self.build(m)
        self.assertEqual(self.provider.calls, 0)

    def test_callback_review_revokes_acquisition_authorization(self):
        for boundary in ("resolve", "finalize"):
            for status in (ReviewStatus.REJECTED, ReviewStatus.APPROVED):
                with self.subTest(boundary=boundary, status=status):
                    self.provider.calls = self.provider.transfers = self.inspector.calls = 0
                    m = deepcopy(self.built)
                    old = active(m)
                    creator = selection_identity(replace(old, shot_selections=[replace(s,
                        source=SelectionSource.CREATOR, reason=SelectionReason.CREATOR_CHOICE)
                        for s in old.shot_selections]))
                    m.selection.runs = [creator]
                    m.selection.active_creator_selection_id = creator.selection_id
                    # Preserve a real existing acquisition domain and active pointer.
                    m = self.build(m)
                    before = deepcopy(m.acquisition)
                    self.provider.data = b"new synthetic bytes for revoked operation"
                    self.provider.calls = self.provider.transfers = self.inspector.calls = 0
                    self.assertFalse(validate(m))
                    self.assertTrue(self.usable(m))
                    self.inspector.calls = 0
                    original = getattr(self.provider if boundary == "resolve" else self.storage, boundary)

                    def revoke(*args, **kwargs):
                        value = original(*args, **kwargs)
                        reviewed = append_review(m, expected_selection_id=creator.selection_id,
                            expected_choice=creator.shot_selections[0], expected_predecessor=None,
                            status=status, locked=False)
                        m.selection = reviewed.selection
                        self.assertFalse(validate(m))
                        return value

                    target = self.provider if boundary == "resolve" else self.storage
                    with patch.object(target, boundary, side_effect=revoke), \
                            patch.object(self.storage, "staging", wraps=self.storage.staging) as staging:
                        result = self.stage().execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
                    self.assertEqual(result.result.status, StageStatus.FAILED)
                    self.assertIsNone(result.update)
                    self.assertEqual(result.result.diagnostics[0].code,
                        "acquisition_review_rejected" if status == ReviewStatus.REJECTED
                        else "acquisition_selection_stale")
                    self.assertEqual(self.provider.calls, 1)
                    self.assertEqual(self.provider.transfers, 0 if boundary == "resolve" else 1)
                    self.assertEqual(self.inspector.calls, 0 if boundary == "resolve" else 1)
                    self.assertEqual(staging.call_count, 0 if boundary == "resolve" else 1)
                    self.assertFalse(list(self.storage.root.glob("staging/*.part")))
                    self.assertEqual(m.acquisition, before)
                    self.assertEqual(m.acquisition.active_creator_acquisition_id,
                                     before.active_creator_acquisition_id)
                    self.assertNotIn("private", json.dumps(to_data(result.result)))
                    # Finalization never rolls back immutable objects on revocation.
                    self.assertTrue(self.storage.resolve(before.assets[0].object_key).exists())
                    if boundary == "finalize":
                        orphan_digest = hashlib.sha256(self.provider.data).hexdigest()
                        self.assertTrue(self.storage.resolve(object_key(orphan_digest)).exists())
                        self.assertNotIn(orphan_digest, [a.sha256 for a in m.acquisition.assets])
                    self.provider.data = b"synthetic-media"

    def test_rights_permission_explicit(self):
        self.provider.spec = replace(self.provider.spec, permits_acquisition=False)
        self.spec = replace(self.spec, providers=[self.provider.spec])
        m = self.build()
        self.assertTrue(all(s.outcome == AcquisitionOutcome.RIGHTS_BLOCKED for s in m.acquisition.runs[0].shot_acquisitions))
        self.assertEqual(self.provider.calls, 0)

    def test_missing_provider_is_unsupported(self):
        m = self.build(providers=())
        self.assertTrue(all(s.outcome == AcquisitionOutcome.UNSUPPORTED_SOURCE for s in m.acquisition.runs[0].shot_acquisitions))
        self.assertFalse(validate(m))

    def test_no_canonical_media_or_final_approval(self):
        m = self.build()
        self.assertEqual(m.media, self.built.media)
        data = json.dumps(to_data(m.acquisition))
        for forbidden in ("final_eligible", "rights_approved", "license_verified", "legally_cleared"):
            self.assertNotIn(forbidden, data)
        self.assertTrue(boundary_unchanged(self.built, m))

    def test_deterministic_spec_and_run(self):
        first = self.build()
        second = self.build(first)
        self.assertEqual(first.acquisition, second.acquisition)
        self.assertEqual(exact_signature(self.spec), exact_signature(deepcopy(self.spec)))

    def test_changed_bytes_distinct_materialization(self):
        first = self.build()
        self.provider.data = b"changed synthetic bytes"
        second = self.build(first)
        self.assertEqual(len(second.acquisition.materializations), 2)
        self.assertEqual(len(second.acquisition.assets), 2)
        self.assertNotEqual(first.acquisition.runs[0].acquisition_id, second.acquisition.runs[-1].acquisition_id)

    def test_multiple_shots_one_transfer(self):
        m = self.build()
        self.assertGreater(len(m.acquisition.runs[0].shot_acquisitions), 1)
        self.assertEqual(self.provider.transfers, 1)
        self.assertEqual(len(m.acquisition.materializations), 1)

    def test_same_bytes_different_candidate_separate_provenance(self):
        m = self.build()
        selection = active(m)
        retrieval = next(r for r in m.retrieval.runs if r.retrieval_id == selection.retrieval_id)
        second = next(c for c in retrieval.candidates
                      if c.candidate_id != selection.shot_selections[0].selected_candidate.candidate_id)
        from creator_studio.manifest.selection import SelectedCandidateRef
        changed = selection_identity(replace(selection, shot_selections=[replace(s,
            selected_candidate=SelectedCandidateRef(second.candidate_id, second.metadata_fingerprint),
            source=SelectionSource.CREATOR, reason=SelectionReason.CREATOR_CHOICE)
            for s in selection.shot_selections]))
        m.selection.runs.append(changed)
        m.selection.active_creator_selection_id = changed.selection_id
        out = self.build(m)
        self.assertFalse(validate(out))
        self.assertEqual(len(out.acquisition.assets), 1)
        self.assertEqual(len(out.acquisition.materializations), 2)
        self.assertNotEqual(out.acquisition.materializations[0].candidate_id,
                            out.acquisition.materializations[1].candidate_id)

    def test_capacity_preflight_before_provider(self):
        for bound in ("MAX_ACQUISITION_RUNS", "MAX_ASSETS", "MAX_MATERIALIZATIONS",
                      "MAX_TOTAL_HISTORICAL_SHOT_ACQUISITIONS"):
            with self.subTest(bound=bound), patch("creator_studio.acquisition.engine." + bound, 0):
                with self.assertRaises(AcquisitionError):
                    self.build()
        self.assertEqual(self.provider.calls, 0)

    def test_exact_transfer_count_limit_before_provider(self):
        m = deepcopy(self.built)
        selection = active(m)
        retrieval = next(r for r in m.retrieval.runs if r.retrieval_id == selection.retrieval_id)
        from creator_studio.manifest.selection import SelectedCandidateRef
        choices = [replace(s, source=SelectionSource.CREATOR, reason=SelectionReason.CREATOR_CHOICE,
            selected_candidate=SelectedCandidateRef(retrieval.candidates[i % 2].candidate_id,
                retrieval.candidates[i % 2].metadata_fingerprint)) for i, s in enumerate(selection.shot_selections)]
        changed = selection_identity(replace(selection, shot_selections=choices))
        m.selection.runs = [changed]
        m.selection.active_creator_selection_id = changed.selection_id
        with self.assertRaises(AcquisitionError):
            self.build(m, spec=replace(self.spec, max_acquisition_count=1))
        self.assertEqual(self.provider.calls, 0)

    def test_forged_automatic_nonbaseline_rejected(self):
        m = deepcopy(self.built)
        selection = active(m)
        retrieval = next(r for r in m.retrieval.runs if r.retrieval_id == selection.retrieval_id)
        from creator_studio.manifest.selection import SelectedCandidateRef
        candidate = next(c for c in retrieval.candidates
                         if c.candidate_id != selection.shot_selections[0].selected_candidate.candidate_id)
        changed = selection_identity(replace(selection, shot_selections=[replace(s,
            selected_candidate=SelectedCandidateRef(candidate.candidate_id, candidate.metadata_fingerprint))
            for s in selection.shot_selections]))
        m.selection.runs = [changed]
        m.selection.active_creator_selection_id = changed.selection_id
        with self.assertRaises(AcquisitionError):
            self.build(m)
        self.assertEqual(self.provider.calls, 0)

    def test_current_visual_retrieval_selection_staleness(self):
        m = self.build()
        for domain, pointer in (("visual_planning", "active_creator_plan_id"),
                ("retrieval", "active_creator_retrieval_id"), ("selection", "active_creator_selection_id")):
            changed = deepcopy(m)
            setattr(getattr(changed, domain), pointer, None)
            self.assertFalse(validate(changed))
            self.assertFalse(self.usable(changed))

    def test_inspection_pixel_count_bound(self):
        self.inspector.facts = replace(self.inspector.facts, width=16384, height=16384)
        with self.assertRaises(AcquisitionError):
            self.build()

    def test_still_image_no_duration(self):
        facts = replace(self.inspector.facts, media_kind=VisualMediaKind.IMAGE,
            media_format=MediaFormat.PNG, codec=MediaCodec.PNG, duration_seconds=None)
        self.assertTrue(inspection_valid(facts))
        self.assertFalse(inspection_valid(replace(facts, duration_seconds=1.0)))

    def test_raw_probe_payload_not_in_contract(self):
        data = to_data(self.inspector.facts)
        data["raw_probe"] = {"private": "payload"}
        with self.assertRaises(ValueError):
            decode(InspectionFacts, data)

    def test_provider_identity_mismatch_zero_resolution(self):
        self.provider.spec = replace(self.provider.spec, catalog_namespace="different")
        with self.assertRaises(AcquisitionError):
            self.build()
        self.assertEqual(self.provider.calls, 0)

    def test_zero_bytes_fail_stage(self):
        self.provider.data = b""
        result = self.stage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertFalse(self.built.acquisition.runs)

    def test_provider_timeout_sanitized(self):
        self.provider.failure = TimeoutError("private response")
        result = self.stage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.diagnostics[0].code, "acquisition_timeout")

    def test_stage_independently_allowlists_codes(self):
        error = AcquisitionError("acquisition_provider_failed")
        error.code = "https://private.invalid"
        with patch("creator_studio.acquisition.stage.build_acquisition", side_effect=error):
            result = self.stage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.diagnostics[0].code, "acquisition_validation_failed")

    def test_retry_same_candidate(self):
        self.provider.failure = RuntimeError("private")
        with self.assertRaises(AcquisitionError):
            self.build()
        first_request = self.provider.request
        self.provider.failure = None
        self.build()
        self.assertEqual(first_request, self.provider.request)

    def test_historical_validation_filesystem_free(self):
        m = self.build()
        with patch.object(Path, "open", side_effect=AssertionError()), patch.object(Path, "stat", side_effect=AssertionError()):
            self.assertFalse(validate(m))

    def test_provider_extra_filename_ignored(self):
        for filename in ("../escape", "..\\escape", "C:\\escape", "\\\\server\\share", "file:stream", "CON"):
            self.provider.filename = filename
            m = self.build()
            serialized = json.dumps(to_data(m.acquisition))
            self.assertNotIn(filename, serialized)
            self.assertNotIn("filename", serialized)
            self.assertEqual(len(list(self.storage.root.glob("objects/sha256/*/*.blob"))), 1)

    def test_operational_failure_preserves_existing_domain(self):
        m = self.build()
        before = deepcopy(m.acquisition)
        self.provider.failure = RuntimeError("private")
        result = self.stage().execute(StageContext(m, CancellationToken(), 2, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertEqual(m.acquisition, before)
        self.assertTrue(self.storage.resolve(before.assets[0].object_key).exists())

    def test_reuse_inspector_mutation_rejected(self):
        m = self.build()
        self.inspector.mutate = b"mutated final bytes"
        self.assertFalse(self.usable(m))
        self.assertFalse(validate(m))

    def test_manifest_acquisition_roundtrip(self):
        m = self.build()
        path = Path(self.temp.name) / "manifest.json"
        save(m, path)
        self.assertEqual(load(path).acquisition, m.acquisition)

    def test_effective_signature_must_be_retained_observation(self):
        m = self.build()
        run = m.acquisition.runs[0]
        effective = "0" * 64
        fingerprint = input_fingerprint(run.selection_id, run.selection_output_signature, effective)
        m.acquisition.runs[0] = assign_identity(replace(run,
            effective_selection_output_signature=effective, acquisition_input_fingerprint=fingerprint,
            acquisition_signature=acquisition_signature(fingerprint, run.acquisition_spec)))
        m.acquisition.active_creator_acquisition_id = m.acquisition.runs[0].acquisition_id
        self.assertTrue(validate(m))

    def test_unresolved_materialization_forgery_rejected(self):
        m = self.build(build_selection(build_retrieval(self.intent)))
        run = m.acquisition.runs[0]
        changed = [replace(s, outcome=AcquisitionOutcome.MATERIALIZED,
            materialization_id="materialization:" + "0" * 64) for s in run.shot_acquisitions]
        m.acquisition.runs[0] = assign_identity(replace(run, shot_acquisitions=changed))
        m.acquisition.active_creator_acquisition_id = m.acquisition.runs[0].acquisition_id
        self.assertTrue(validate(m))

    def test_no_orphan_materialization(self):
        m = self.build()
        record = m.acquisition.materializations[0]
        orphan = replace(record, rendition=replace(record.rendition, rendition_id="unreferenced"))
        m.acquisition.materializations.append(replace(orphan, materialization_id=materialization_id(orphan)))
        self.assertTrue(validate(m))

    def test_shot_outcome_reference_exclusivity(self):
        for outcome, reference in ((AcquisitionOutcome.MATERIALIZED, None),
                (AcquisitionOutcome.RIGHTS_BLOCKED, "materialization:" + "0" * 64)):
            m = self.build()
            run = m.acquisition.runs[0]
            shot = replace(run.shot_acquisitions[0], outcome=outcome, materialization_id=reference)
            m.acquisition.runs[0] = assign_identity(replace(run, shot_acquisitions=[shot, *run.shot_acquisitions[1:]]))
            m.acquisition.active_creator_acquisition_id = m.acquisition.runs[0].acquisition_id
            self.assertTrue(validate(m))

    def test_hints_never_supply_permission(self):
        from creator_studio.retrieval.models import CandidateProposal
        from creator_studio.manifest.retrieval import ProvenanceHint
        from creator_studio.manifest.rights import Rights
        self.provider.spec = replace(self.provider.spec, permits_acquisition=False)
        self.spec = replace(self.spec, providers=[self.provider.spec])
        for rights in (Rights.OWNED, Rights.LICENSED, Rights.PUBLIC_DOMAIN, Rights.UNKNOWN):
            m = selected_fixture(self.intent, [CandidateProposal("video:hint", VisualMediaKind.VIDEO,
                provenance_hint=ProvenanceHint(declared_rights=rights))])
            out = self.build(m)
            self.assertFalse(out.acquisition.assets)
            self.assertTrue(all(s.outcome == AcquisitionOutcome.RIGHTS_BLOCKED
                                for s in out.acquisition.runs[0].shot_acquisitions))
        self.assertEqual(self.provider.calls, 0)

    def test_missing_inspector_fails_closed(self):
        with self.assertRaises(AcquisitionError):
            self.build(inspector=UnavailableInspector())
        self.assertFalse(self.built.acquisition.runs)

    def test_postinspection_digest_authoritative(self):
        self.inspector.mutate = b"post-inspection synthetic content"
        m = self.build()
        self.assertEqual(m.acquisition.assets[0].sha256, hashlib.sha256(self.inspector.mutate).hexdigest())
        self.assertNotEqual(m.acquisition.assets[0].sha256, hashlib.sha256(self.provider.data).hexdigest())

    def test_exception_sanitized_stage(self):
        self.provider.failure = RuntimeError("https://private.invalid/x Authorization: hidden cookie body")
        result = self.stage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertEqual(result.result.diagnostics[0].code, "acquisition_provider_failed")
        self.assertNotIn("private", json.dumps(to_data(result.result)))
        self.assertFalse(self.built.acquisition.runs)

    def test_adapter_nonempty_result_fails(self):
        with patch.object(self.provider, "acquire", return_value={"private": "payload"}):
            with self.assertRaises(AcquisitionError):
                self.build()

    def test_provider_exception_code_not_trusted(self):
        error = AcquisitionError("acquisition_storage_failed")
        error.code = "https://private.invalid"
        error.args = ("Authorization private payload",)
        with patch.object(self.provider, "acquire", side_effect=error):
            result = self.stage().execute(StageContext(self.built, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.diagnostics[0].code, "acquisition_provider_failed")
        self.assertNotIn("private", json.dumps(to_data(result.result)))

    def test_provider_cannot_suppress_sink_failure(self):
        def acquire(handle, sink, control):
            sink.write(b"a")
            try:
                sink.write(b"exceeds limit")
            except AcquisitionError:
                pass
        with patch.object(self.provider, "acquire", side_effect=acquire):
            with self.assertRaises(AcquisitionError) as caught:
                self.build(spec=replace(self.spec, max_asset_bytes=1))
        self.assertEqual(caught.exception.code, "acquisition_limit_exceeded")

    def test_reference_only_hints_zero_calls(self):
        from creator_studio.retrieval.models import CandidateProposal
        from creator_studio.manifest.retrieval import UsageRestriction, ProvenanceHint
        from creator_studio.manifest.rights import Rights
        for proposal in (
            CandidateProposal("video:reference", VisualMediaKind.VIDEO, usage_restriction=UsageRestriction.REFERENCE_ONLY),
            CandidateProposal("video:reference", VisualMediaKind.VIDEO, provenance_hint=ProvenanceHint(declared_rights=Rights.REFERENCE_ONLY))):
            m = selected_fixture(self.intent, [proposal])
            out = self.build(m)
            self.assertFalse(out.acquisition.materializations)
        self.assertEqual(self.provider.calls, 0)

    def test_candidate_fingerprint_tamper_before_calls(self):
        m = deepcopy(self.built)
        retrieval = m.retrieval.runs[0]
        m.retrieval.runs[0] = replace(retrieval, candidates=[replace(retrieval.candidates[0],
            metadata_fingerprint="0" * 64), *retrieval.candidates[1:]])
        result = self.stage().execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertEqual(self.provider.calls, 0)

    def test_resolution_cancel(self):
        self.provider.cancel_resolve = True
        with self.assertRaises(Cancelled):
            self.build()
        self.assertEqual(self.provider.transfers, 0)

    def test_cancellation_every_observed_boundary(self):
        counter = CountingControl()
        self.build(control=counter)
        for stop in range(1, counter.count + 1):
            with self.subTest(stop=stop):
                with self.assertRaises(Cancelled):
                    self.build(control=CountingControl(stop))
                self.assertFalse(self.built.acquisition.runs)
                self.assertFalse(list((self.storage.root / "staging").glob("*.part")))

    def test_exact_two_artifacts_and_reuse(self):
        stage, m, previous = self.executed()
        self.assertEqual(len(previous.artifacts), 2)
        self.assertTrue(previous.artifacts[0].reference.startswith("acquisition/"))
        self.assertTrue(previous.artifacts[1].reference.startswith("acquisition_selection/"))
        calls = self.inspector.calls
        self.assertTrue(stage.validate_reuse(m, previous))
        self.assertGreater(self.inspector.calls, calls)
        self.assertNotIn(self.temp.name, json.dumps(to_data(previous.artifacts)))

    def test_artifact_tamper_order_count_signature(self):
        stage, m, previous = self.executed()
        for artifacts in (previous.artifacts[::-1], previous.artifacts[:1],
                          [replace(previous.artifacts[0], signature="0" * 64), previous.artifacts[1]]):
            changed = deepcopy(m)
            changed.processing[0].execution.artifacts = artifacts
            self.assertFalse(stage.validate_reuse(changed, changed.processing[0].execution))

    def test_exact_retained_execution_required(self):
        stage, m, previous = self.executed()
        self.assertFalse(stage.validate_reuse(m, replace(previous, metadata=["changed"])))

    def test_spec_change_blocks_reuse(self):
        stage, m, previous = self.executed()
        stage.spec = replace(stage.spec, max_asset_bytes=1000)
        self.assertFalse(stage.validate_reuse(m, previous))

    def test_review_change_stales_current_but_not_history(self):
        m = self.build()
        selection = active(m)
        reviewed = append_review(m, expected_selection_id=selection.selection_id,
            expected_choice=selection.shot_selections[0], expected_predecessor=None,
            status=ReviewStatus.APPROVED, locked=False)
        self.assertFalse(validate(reviewed))
        self.assertFalse(self.usable(reviewed))

    def test_no_active_history_scan(self):
        m = self.build()
        m.acquisition.active_creator_acquisition_id = None
        self.assertFalse(validate(m))
        self.assertFalse(self.usable(m))

    def test_inactive_identity_collision_no_reactivation(self):
        m = self.build()
        m.acquisition.active_creator_acquisition_id = None
        with self.assertRaises(AcquisitionError):
            self.build(m)
        self.assertIsNone(m.acquisition.active_creator_acquisition_id)

    def test_dependencies(self):
        self.assertEqual(self.stage().dependencies, ())
        self.assertEqual(self.stage(dependencies=("media_selection",)).dependencies, ("media_selection",))

    def test_readiness_has_no_io(self):
        with patch.object(self.storage, "verify", side_effect=AssertionError()), patch.object(self.provider, "resolve", side_effect=AssertionError()):
            self.stage().readiness(self.built)
        self.assertFalse(self.storage.root.exists())

    def test_storage_relocation_identity(self):
        first = self.build()
        alternate = ManagedStorage(Path(self.temp.name) / "other")
        second = self.build(storage=alternate)
        self.assertEqual(first.acquisition, second.acquisition)

    def test_object_first_proposal_failure_leaves_orphan(self):
        with patch("creator_studio.acquisition.engine.boundary_unchanged", return_value=False):
            with self.assertRaises(AcquisitionError):
                self.build()
        self.assertTrue(list(self.storage.root.glob("objects/sha256/*/*.blob")))
        self.assertFalse(self.built.acquisition.runs)

    def test_failed_manifest_save_keeps_final_object(self):
        m = self.build()
        with patch("creator_studio.manifest.persistence.os.replace", side_effect=OSError()):
            with self.assertRaises(Exception):
                save(m, Path(self.temp.name) / "manifest.json")
        self.assertTrue(self.storage.resolve(m.acquisition.assets[0].object_key).exists())

    def test_rendition_policy_deterministic(self):
        a = ResolvedRendition(RenditionObservation("a", VisualMediaKind.VIDEO, 640, 480), object())
        b = ResolvedRendition(RenditionObservation("b", VisualMediaKind.VIDEO, 1280, 720), object())
        self.assertIs(choose_rendition([a, b], VisualMediaKind.VIDEO), b)
        self.assertIs(choose_rendition([b, a], VisualMediaKind.VIDEO), b)
        self.assertEqual(repr(a), "<ResolvedRendition>")

    def test_no_prohibited_imports_or_generic_downloader(self):
        prohibited = {"requests", "httpx", "aiohttp", "PyQt6", "stock", "pipeline", "renderer", "subprocess"}
        for path in Path("creator_studio/acquisition").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({n.name.split('.')[0] for n in node.names} & prohibited)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[0], prohibited)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name, {"download", "acquire_url", "fetch", "download_url"})


def domain_unchanged_test(name):
    def test(self):
        self.assertEqual(getattr(self.build(), name), getattr(self.built, name))
    return test


for _field in fields(ProjectManifest):
    if _field.name != "acquisition":
        setattr(MediaAcquisitionTests, "test_domain_unchanged_" + _field.name, domain_unchanged_test(_field.name))


def invalid_inspection_test(field, value):
    def test(self):
        self.inspector.facts = replace(self.inspector.facts, **{field: value})
        self.assertFalse(inspection_valid(self.inspector.facts))
        with self.assertRaises(AcquisitionError):
            self.build()
    return test


for _name, _field, _value in (
    ("width_zero", "width", 0), ("height_negative", "height", -1),
    ("width_bound", "width", 16385),
    ("duration_zero", "duration_seconds", 0.0), ("duration_nan", "duration_seconds", float("nan")),
    ("duration_infinite", "duration_seconds", float("inf")), ("duration_missing", "duration_seconds", None),
    ("duration_bound", "duration_seconds", 86401.0), ("unknown_format", "media_format", "AVI"),
    ("kind_mismatch", "media_kind", VisualMediaKind.IMAGE), ("codec_mismatch", "codec", MediaCodec.PNG),
    ("inspector_metadata_bound", "inspector_id", "x" * 49), ("inspector_locator", "inspector_id", "https://invalid")):
    setattr(MediaAcquisitionTests, "test_inspection_" + _name, invalid_inspection_test(_field, _value))


def capacity_test(field, value):
    def test(self):
        self.spec = replace(self.spec, **{field: value})
        with self.assertRaises(AcquisitionError):
            self.build()
        if not spec_valid(self.spec):
            self.assertEqual(self.provider.calls, 0)
    return test


for _name, _field, _value in (("asset", "max_asset_bytes", 1), ("run", "max_run_bytes", 1),
    ("count", "max_acquisition_count", 0), ("asset_upper", "max_asset_bytes", MAX_ASSET_BYTES + 1),
    ("run_upper", "max_run_bytes", MAX_TRANSFERRED_BYTES_PER_RUN + 1)):
    setattr(MediaAcquisitionTests, "test_limit_" + _name, capacity_test(_field, _value))


def tamper_test(kind):
    def test(self):
        m = self.build()
        state = m.acquisition
        if kind == "candidate":
            state.materializations[0] = replace(state.materializations[0], candidate_id="candidate:forged")
        elif kind == "fingerprint":
            state.materializations[0] = replace(state.materializations[0], candidate_metadata_fingerprint="0" * 64)
        elif kind == "run":
            state.runs[0] = replace(state.runs[0], selection_id="selection:" + "0" * 64)
        elif kind == "shot":
            run = state.runs[0]
            state.runs[0] = assign_identity(replace(run, shot_acquisitions=[replace(run.shot_acquisitions[0],
                shot_selection_id="shot_selection:" + "0" * 64), *run.shot_acquisitions[1:]]))
        elif kind == "object_key":
            state.assets[0] = replace(state.assets[0], object_key="../outside")
        elif kind == "orphan_asset":
            state.assets.append(MaterializedAsset("asset:sha256:" + "0" * 64, "0" * 64, 1, object_key("0" * 64)))
        elif kind == "duplicate_run":
            state.runs.append(state.runs[0])
        elif kind == "duplicate_materialization":
            state.materializations.append(state.materializations[0])
        elif kind == "duplicate_asset":
            state.assets.append(state.assets[0])
        self.assertTrue(validate(m))
    return test


for _kind in ("candidate", "fingerprint", "run", "shot", "object_key", "orphan_asset",
              "duplicate_run", "duplicate_materialization", "duplicate_asset"):
    setattr(MediaAcquisitionTests, "test_historical_tamper_" + _kind, tamper_test(_kind))


if __name__ == "__main__":
    unittest.main()
