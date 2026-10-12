"""Offline M72 source authority, retention, bounds, atomicity and stage tests.

All media/narration evidence is synthetic. No production provider or media tool.
"""
import ast
from copy import deepcopy
from dataclasses import fields, replace
from itertools import repeat
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, require_valid, validate
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.render_timeline import *
from creator_studio.manifest.render_timeline_validation import (RECORDS, preflight_record,
    preflight_history, preflight_document, derive_entries, project_plan, validate_plan,
    validate_history, complete_render_timeline, uncovered_intervals)
from creator_studio.manifest.acquisition import (AcquisitionProviderSpec, AcquisitionSpec,
    MaterializedAsset, MaterializationRecord, RenditionObservation, InspectionFacts,
    MediaFormat, MediaCodec, ShotAcquisition, AcquisitionState, object_key,
    materialization_id, assign_identity as acquisition_identity, acquisition_signature)
from creator_studio.manifest.editing import EditSpec, EditingState
from creator_studio.manifest.editing_validation import reconstruct
from creator_studio.manifest.placement_timing import PlacementTimingState
from creator_studio.manifest.models import ProcessingState, Status
from creator_studio.manifest.signatures import dependency_signature
from creator_studio.manifest.semantic import exact_signature
from creator_studio.render_timeline import *
from creator_studio.render_timeline.engine import active_plan, normalize_dependencies, preflight
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
import tests.test_placement_timing_foundation as upstream

CONFIG = dict(upstream.POLICY)

class RenderTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upstream.PlacementTimingTests.setUpClass()
        cls.addClassCleanup(upstream.PlacementTimingTests.doClassCleanups)
        cls.base = deepcopy(upstream.PlacementTimingTests.base)
        cls.storage = upstream.PlacementTimingTests.storage

    def setUp(self):
        self.m = deepcopy(self.base)
        self.config = dict(storage=self.storage, **CONFIG)

    def timed(self, materialized=False, duration=0.5, inspector_version="1", digest="a" * 64):
        m = deepcopy(self.m)
        if materialized:
            old = m.acquisition.runs[0]
            selection = m.selection.runs[0]
            retrieval = m.retrieval.runs[0]
            candidate_by_id = {c.candidate_id: c for c in retrieval.candidates}
            candidate = candidate_by_id[selection.shot_selections[0].selected_candidate.candidate_id]
            provider = AcquisitionProviderSpec(candidate.provider_id, candidate.catalog_namespace,
                permits_acquisition=True)
            spec = AcquisitionSpec(providers=[provider])
            asset = MaterializedAsset("asset:sha256:" + digest, digest, 17, object_key(digest))
            records, shots = [], []
            for shot in selection.shot_selections:
                candidate = candidate_by_id[shot.selected_candidate.candidate_id]
                record = MaterializationRecord("", retrieval.retrieval_id, candidate.candidate_id,
                    candidate.metadata_fingerprint, provider,
                    RenditionObservation("original", VisualMediaKind.VIDEO, 640, 480),
                    InspectionFacts("synthetic", inspector_version, VisualMediaKind.VIDEO,
                        MediaFormat.MP4, MediaCodec.H264, 640, 480, duration), asset.asset_id)
                record = replace(record, materialization_id=materialization_id(record))
                if record not in records:
                    records.append(record)
                shots.append(ShotAcquisition(shot.shot_selection_id, AcquisitionOutcome.MATERIALIZED,
                    record.materialization_id))
            run = acquisition_identity(replace(old, acquisition_spec=spec,
                acquisition_signature=acquisition_signature(old.acquisition_input_fingerprint, spec),
                shot_acquisitions=shots))
            m.acquisition = AcquisitionState([run], records, [asset], run.acquisition_id)
            edit = reconstruct(m, run, EditSpec())
            m.editing = EditingState([edit], edit.edit_plan_id)
        fixture = upstream.PlacementTimingTests("test_empty_additive_schema_two")
        fixture.m = m
        fixture.storage = self.storage
        fixture.gate = upstream.Gate()
        fixture.edit = m.editing.plans[0]
        fixture.run = m.voice_timing.runs[0]
        fixture.pids = [p.placement_id for p in fixture.edit.placements]
        return fixture.accepted()

    def build(self, m=None, **kwargs):
        m = m if m is not None else self.timed()
        config = dict(self.config)
        if m.acquisition.runs[0].acquisition_spec != AcquisitionSpec():
            config["acquisition_spec"] = m.acquisition.runs[0].acquisition_spec
        return build_render_timeline(m, **config, **kwargs)

    def eligibility(self, m, **kwargs):
        config = dict(self.config, acquisition_spec=m.acquisition.runs[0].acquisition_spec)
        return current_render_timeline_eligibility(m, **config, **kwargs)

    def test_empty_schema_and_missing_migration(self):
        m = ProjectManifest("empty")
        self.assertEqual(m.schema_version, 2)
        self.assertEqual(m.render_timeline, RenderTimelineState())
        require_valid(m)
        raw = to_data(m)
        del raw["render_timeline"]
        loaded = decode(ProjectManifest, migrate_document(raw))
        self.assertEqual(loaded.render_timeline, RenderTimelineState())
        self.assertFalse(loaded.render_timeline.plans)

    def test_present_malformed_state_strict(self):
        for value in (None, [], {}, {"plans": []}, {"plans": [],
                "active_render_timeline_plan_id": None, "unknown": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                raw = to_data(ProjectManifest("bad"))
                raw["render_timeline"] = value
                decode(ProjectManifest, migrate_document(raw))

    def test_exact_whole_video_shared_asset(self):
        m = self.timed(materialized=True)
        before = deepcopy(m)
        result = self.build(m)
        self.assertEqual(m, before)
        plan = active_plan(result)
        require_valid(result)
        self.assertTrue(complete_render_timeline(result, plan))
        self.assertTrue(self.eligibility(result).eligible)
        self.assertEqual(len({e.asset_id for e in plan.entries}), 1)
        self.assertEqual(len({e.placement_id for e in plan.entries}), len(plan.entries))
        self.assertEqual([e.placement_id for e in plan.entries],
            [p.placement_id for p in result.editing.plans[0].placements])
        for e, timing in zip(plan.entries, result.placement_timing.plans[0].entries):
            self.assertEqual(e.source_usage, SourceUsage.WHOLE_VIDEO)
            self.assertEqual((e.source_start_us, e.source_end_us, e.source_duration_us), (0, 500000, 500000))
            self.assertEqual((e.timeline_start_us, e.timeline_end_us), (timing.start_us, timing.end_us))
        self.assertEqual(active_plan(self.build(m)), plan)
        for f in fields(m):
            if f.name != "render_timeline":
                self.assertEqual(getattr(m, f.name), getattr(result, f.name), f.name)

    def test_timed_no_materialization_preserves_interval(self):
        result = self.build()
        plan = active_plan(result)
        for e, timing in zip(plan.entries, result.placement_timing.plans[0].entries):
            self.assertEqual(e.outcome, RenderTimelineOutcome.NO_MATERIALIZED_MEDIA)
            self.assertEqual((e.timeline_start_us, e.timeline_end_us), (timing.start_us, timing.end_us))
            self.assertIsNone(e.asset_id)
        self.assertTrue(self.eligibility(result).eligible)
        self.assertFalse(complete_render_timeline(result, plan))

    def test_gate_free_unresolved_timing(self):
        m = upstream.build_placement_timing(self.m, storage=self.storage, **CONFIG)
        result = self.build(m)
        for e in active_plan(result).entries:
            self.assertEqual(e.outcome, RenderTimelineOutcome.UNRESOLVED_TIMING)
            self.assertIsNone(e.timeline_start_us)
            self.assertIsNone(e.timeline_end_us)

    def test_video_length_decisions(self):
        for duration, expected in ((1.0, RenderTimelineOutcome.SOURCE_TRIM_REQUIRED),
                (0.25, RenderTimelineOutcome.MEDIA_TOO_SHORT),
                (0.1, RenderTimelineOutcome.SOURCE_DURATION_UNRESOLVED)):
            with self.subTest(duration=duration):
                result = self.build(self.timed(materialized=True, duration=duration))
                for e in active_plan(result).entries:
                    self.assertEqual(e.outcome, expected)
                    self.assertEqual(e.source_usage, SourceUsage.UNRESOLVED)
                    self.assertIsNone(e.source_start_us)
                    self.assertIsNone(e.source_end_us)

    def test_history_current_pointer_separation(self):
        result = self.build(self.timed(materialized=True))
        for state, pointer in (("acquisition", "active_creator_acquisition_id"),
                ("selection", "active_creator_selection_id"), ("editing", "active_creator_edit_plan_id"),
                ("placement_timing", "active_placement_timing_plan_id"),
                ("voice_timing", "active_narration_revision_id"),
                ("voice_timing", "active_alignment_run_id"),
                ("visual_planning", "active_creator_plan_id"), ("semantic", "active_creator_document_id")):
            with self.subTest(state=state, pointer=pointer):
                m = deepcopy(result)
                setattr(getattr(m, state), pointer, None)
                validate_history(m)
                self.assertTrue(complete_render_timeline(m, active_plan(m)))
                self.assertFalse(self.eligibility(m).eligible)

    def test_current_expected_spec_policy_separation(self):
        m = self.build()
        bad = dict(self.config, acceptance_policy_version="2")
        self.assertFalse(current_render_timeline_eligibility(m, **bad).eligible)
        self.assertFalse(self.eligibility(m, spec=replace(RenderTimelineSpec(), engine_version="2")).eligible)
        validate_history(m)

    def test_no_history_scan_or_inactive_resurrection(self):
        m = self.build()
        with self.assertRaises(ValueError):
            self.build(m)  # Retained entries alone are insufficient reuse evidence.
        m.render_timeline.active_render_timeline_plan_id = None
        before = deepcopy(m)
        with self.assertRaises(ValueError):
            self.build(m)
        self.assertEqual(before, m)

    def test_reuse_incomplete_without_upgrade(self):
        stage = RenderTimelineStage(**self.config)
        m = self.timed()
        result = stage.execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.SUCCEEDED)
        m, execution = result.update.manifest, result.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        self.assertTrue(stage.validate_reuse(m, execution))
        self.assertEqual(self.build(m).render_timeline, m.render_timeline)
        self.assertFalse(complete_render_timeline(m, active_plan(m)))
        for artifacts in (execution.artifacts[::-1], execution.artifacts[:1],
                execution.artifacts * 2, [replace(execution.artifacts[0], signature="b" * 64), execution.artifacts[1]]):
            changed = deepcopy(m)
            changed.processing[0].execution.artifacts = artifacts
            self.assertFalse(stage.validate_reuse(changed, changed.processing[0].execution))
        m.render_timeline.active_render_timeline_plan_id = None
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_exact_two_artifacts(self):
        m = self.build()
        plan = active_plan(m)
        artifacts = RenderTimelineStage.artifacts(m, plan)
        self.assertEqual(len(artifacts), 2)
        self.assertEqual([a.reference for a in artifacts], [
            "render_timeline/" + plan.render_timeline_plan_id,
            "render_timeline_timing/" + plan.placement_timing_plan_id])
        self.assertNotEqual(artifacts[0].signature, artifacts[1].signature)

    def test_gap_coverage_not_completeness(self):
        m = self.build(self.timed(materialized=True))
        plan = active_plan(m)
        self.assertEqual(uncovered_intervals(m, plan), ((0, 100000), (600000, 900000), (1400000, 2000000)))
        self.assertTrue(complete_render_timeline(m, plan))
        incomplete = self.build()
        self.assertEqual(uncovered_intervals(incomplete, active_plan(incomplete)), ((0, 2000000),))

    def test_historical_validation_no_observations(self):
        m = self.build(self.timed(materialized=True))
        with patch("builtins.open", side_effect=AssertionError("filesystem")), \
                patch("pathlib.Path.open", side_effect=AssertionError("filesystem")), \
                patch("creator_studio.acquisition.engine.current_usability", side_effect=AssertionError("usability")), \
                patch("creator_studio.placement_timing.engine.current_placement_timing_eligibility", side_effect=AssertionError("current")):
            validate_history(m)
            self.assertTrue(complete_render_timeline(m, active_plan(m)))

    def test_usability_false_does_not_rewrite_history(self):
        m = self.build(self.timed(materialized=True))
        before = deepcopy(m)
        with patch("creator_studio.acquisition.engine.current_usability", return_value=False):
            self.assertFalse(observe_media_usability(m, storage=object()))
        self.assertEqual(before, m)
        self.assertTrue(complete_render_timeline(m, active_plan(m)))

    def test_usability_callback_mutation_rejected(self):
        m = self.build()
        def mutate(*args, **kwargs):
            m.render_timeline.active_render_timeline_plan_id = None
            return True
        with patch("creator_studio.acquisition.engine.current_usability", side_effect=mutate):
            with self.assertRaises(ValueError):
                observe_media_usability(m, storage=object())

    def test_builder_current_callback_mutation_rejected(self):
        m = self.timed()
        def mutate(*args, **kwargs):
            m.project_name = "mutated"
            return SimpleNamespace(eligible=True)
        with patch("creator_studio.render_timeline.engine.current_placement_timing_eligibility", side_effect=mutate):
            with self.assertRaises(ValueError):
                self.build(m)

    def test_cancellation_and_failure_leave_caller(self):
        m = self.timed()
        before = deepcopy(m)
        for stop in (1, 2, 8, 20, 80, 150):
            control = upstream.CountingControl(stop)
            try:
                self.build(m, control=control)
            except Cancelled:
                pass
            self.assertEqual(before, m)
        with self.assertRaises(ValueError):
            self.build(m, spec=replace(RenderTimelineSpec(), engine_version="2"))
        self.assertEqual(before, m)

    def test_tamper_entries_order_identity_time_source(self):
        m = self.build(self.timed(materialized=True))
        plan = active_plan(m)
        changes = [replace(plan, entries=plan.entries[::-1]),
            replace(plan, entries=[plan.entries[0]] * len(plan.entries)),
            replace(plan, entries=plan.entries[:1]),
            replace(plan, media_binding_signature="b" * 64),
            replace(plan, timing_evidence_signature="b" * 64)]
        for name, value in (("timeline_start_us", True), ("timeline_start_us", 100000.0),
                ("source_start_us", False), ("source_end_us", 500000.0),
                ("source_end_us", 499999), ("materialization_id", "materialization:" + "b" * 64),
                ("asset_evidence_signature", "b" * 64), ("ordinal", 99),
                ("source_usage", SourceUsage.STILL_IMAGE)):
            changes.append(replace(plan, entries=[replace(plan.entries[0], **{name: value}), *plan.entries[1:]]))
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises((ValueError, StopIteration)):
                validate_plan(m, changed)

    def test_changed_upstream_evidence_invalidates(self):
        original = self.build(self.timed(materialized=True))
        for domain in ("materialization", "timing", "edit", "asset"):
            m = deepcopy(original)
            if domain == "materialization":
                r = m.acquisition.materializations[0]
                m.acquisition.materializations[0] = replace(r, inspection=replace(r.inspection, duration_seconds=1.0))
            elif domain == "timing":
                p = m.placement_timing.plans[0]
                m.placement_timing.plans[0] = replace(p, output_signature="b" * 64)
            elif domain == "edit":
                p = m.editing.plans[0]
                m.editing.plans[0] = replace(p, placements=p.placements[::-1])
            else:
                a = m.acquisition.assets[0]
                m.acquisition.assets[0] = replace(a, byte_count=a.byte_count + 1)
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                validate_history(m)

    def test_preflight_before_hash_copy_callback(self):
        m = self.timed()
        m.render_timeline.plans = [None] * (MAX_PLANS + 1)
        with patch("creator_studio.render_timeline.engine.exact_signature", side_effect=AssertionError("hash")), \
                patch("creator_studio.render_timeline.engine.deepcopy", side_effect=AssertionError("copy")), \
                patch("creator_studio.acquisition.engine.current_usability", side_effect=AssertionError("callback")):
            with self.assertRaises(ValueError):
                self.build(m)
            with self.assertRaises(ValueError):
                observe_media_usability(m, storage=object())

    def test_canonical_exact_budget(self):
        plan = active_plan(self.build())
        payload = canonical_payload(plan)
        self.assertEqual(canonical_payload(plan, max_bytes=len(payload)), payload)
        with self.assertRaises(ValueError):
            canonical_payload(plan, max_bytes=len(payload) - 1)
        with patch("creator_studio.manifest.codec.to_data", side_effect=AssertionError("projection")):
            with self.assertRaises(ValueError):
                canonical_payload(plan, max_bytes=10)

    def test_no_persisted_locators_or_transforms(self):
        m = self.build(self.timed(materialized=True))
        data = canonical_payload(active_plan(m))
        for text in ("object_key", "objects/sha256", "http", "transcript", "fps", "track_id",
                "crop", "zoom", "loop", "freeze", "speed", "transition", "render_executable"):
            self.assertNotIn(text, data)

    def test_narration_disappearance_only_current(self):
        m = self.build(self.timed(materialized=True))
        with patch.object(self.storage, "open_read", side_effect=FileNotFoundError()):
            self.assertFalse(self.eligibility(m).eligible)
            validate_history(m)
            self.assertTrue(complete_render_timeline(m, active_plan(m)))

    def test_expected_acquisition_policy_and_timing_spec(self):
        m = self.build(self.timed(materialized=True))
        bad = dict(self.config, acquisition_spec=AcquisitionSpec())
        self.assertFalse(current_render_timeline_eligibility(m, **bad).eligible)
        config = dict(self.config, acquisition_spec=m.acquisition.runs[0].acquisition_spec,
            timing_spec=replace(m.placement_timing.plans[0].spec, engine_version="2"))
        self.assertFalse(current_render_timeline_eligibility(m, **config).eligible)
        validate_history(m)

    def test_caller_trim_and_transform_arguments_rejected(self):
        m = self.timed()
        before = deepcopy(m)
        for key, value in (("source_start_us", 0), ("source_end_us", 500000),
                ("source_usage", "FIRST_N_SECONDS"), ("trim_policy", "CENTER"),
                ("trim_policy", "RANDOM"), ("fps", 30), ("loop", True),
                ("freeze", True), ("speed", 0.5), ("track_id", "one")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.build(m, **{key: value})
            self.assertEqual(before, m)

    def test_active_pointer_missing_no_fallback(self):
        m = self.build()
        m.placement_timing.active_placement_timing_plan_id = None
        before = deepcopy(m)
        with self.assertRaises(ValueError):
            self.build(m)
        self.assertEqual(before, m)
        validate_history(m)

    def test_stage_callback_configuration_mutation_rejected(self):
        stage = RenderTimelineStage(**self.config)
        m = self.timed()
        def mutate(*args, **kwargs):
            stage.dependencies = ("placement_timing",)
            return SimpleNamespace(eligible=True)
        with patch("creator_studio.render_timeline.engine.current_placement_timing_eligibility", side_effect=mutate):
            result = stage.execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertEqual(m.render_timeline, RenderTimelineState())

    def test_configuration_mutation_during_current_observation(self):
        m = self.build(self.timed(materialized=True))
        spec = deepcopy(m.acquisition.runs[0].acquisition_spec)
        def mutate(*args, **kwargs):
            spec.providers.clear()
            return SimpleNamespace(eligible=True)
        config = dict(self.config, acquisition_spec=spec)
        with patch("creator_studio.render_timeline.engine.current_placement_timing_eligibility", side_effect=mutate):
            with self.assertRaises(ValueError):
                current_render_timeline_eligibility(m, **config)

    def test_empty_plan_never_complete(self):
        # Completeness never succeeds through an invalid/empty retained projection.
        plan = RenderTimelinePlan("", "", "", "", "", "", "", RenderTimelineSpec(), [])
        self.assertFalse(complete_render_timeline(self.m, plan))

    def test_unknown_closed_diagnostics_and_usage_rejected(self):
        m = self.build()
        raw = to_data(m)
        entry = raw["render_timeline"]["plans"][0]["entries"][0]
        for name, value in (("diagnostics", ["secret exception text"]),
                ("source_usage", "FIRST_N_SECONDS"), ("outcome", "UPSTREAM_STALE"),
                ("outcome", "CAPACITY_BLOCKED")):
            changed = deepcopy(raw)
            changed["render_timeline"]["plans"][0]["entries"][0][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(changed))

    def test_stage_reuse_rejects_version_dependency_status(self):
        stage = RenderTimelineStage(**self.config)
        result = stage.execute(StageContext(self.timed(), CancellationToken(), 1, lambda *a: None))
        m, execution = result.update.manifest, result.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        for name, value in (("stage_version", "2"), ("status", StageStatus.FAILED),
                ("dependency_signature", "b" * 64)):
            changed = deepcopy(m)
            setattr(changed.processing[0].execution, name, value)
            self.assertFalse(stage.validate_reuse(changed, changed.processing[0].execution))

    def test_complete_dependency_tuple_stage_reuse(self):
        deps = ("media_acquisition", "edit_planning", "placement_timing")
        stage = RenderTimelineStage(dependencies=deps, **self.config)
        m = self.timed()
        from creator_studio.orchestrator.contracts import StageResult
        from creator_studio.manifest.signatures import signature
        upstream_signatures = {}
        for dependency in deps:
            execution = StageResult(dependency, "1", StageStatus.SUCCEEDED)
            m.processing.append(ProcessingState(stage=dependency, status=Status.SUCCEEDED,
                execution=execution))
            upstream_signatures[dependency] = signature({"dependency_signature": execution.dependency_signature,
                "artifacts": execution.artifacts, "metadata": execution.metadata})
        result = stage.execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.SUCCEEDED)
        m, execution = result.update.manifest, result.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, upstream_signatures)
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        self.assertTrue(stage.validate_reuse(m, execution))
        m.processing[0].execution.metadata = ["changed"]
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_proposed_history_capacity_rejects_before_observation(self):
        m = self.build()
        m = upstream.build_placement_timing(m, storage=self.storage, **CONFIG)
        before = deepcopy(m)
        with patch("creator_studio.render_timeline.engine.MAX_PLANS", 1), patch(
                "creator_studio.render_timeline.engine.current_placement_timing_eligibility",
                side_effect=AssertionError("observation before capacity")):
            with self.assertRaises(ValueError):
                self.build(m)
        self.assertEqual(before, m)
        with patch("creator_studio.render_timeline.engine.MAX_TOTAL_ENTRIES", 3):
            with self.assertRaises(ValueError):
                self.build(m)
        with patch("creator_studio.render_timeline.engine.MAX_TOTAL_ENTRIES", 4):
            result = self.build(m)
        self.assertEqual(sum(len(p.entries) for p in result.render_timeline.plans), 4)
        self.assertEqual(before, m)

    def test_media_usability_injected_absence_corruption(self):
        m = self.build(self.timed(materialized=True))
        before = deepcopy(m)
        facts = m.acquisition.materializations[0].inspection
        class Storage:
            missing = False
            def verify(self, asset, control):
                control.check()
                if self.missing:
                    raise FileNotFoundError()
                return Path("synthetic-no-file")
        class Inspector:
            inspector_id = "synthetic"
            inspector_version = "1"
            policy_id = "objective_media"
            policy_version = "1"
            corrupt = False
            def inspect(self, path, control):
                control.check()
                return replace(facts, duration_seconds=1.0) if self.corrupt else facts
        storage, inspector = Storage(), Inspector()
        config = dict(storage=storage, inspector=inspector,
            acquisition_spec=m.acquisition.runs[0].acquisition_spec)
        self.assertTrue(observe_media_usability(m, **config))
        storage.missing = True
        self.assertFalse(observe_media_usability(m, **config))
        storage.missing, inspector.corrupt = False, True
        self.assertFalse(observe_media_usability(m, **config))
        self.assertEqual(m, before)
        self.assertTrue(complete_render_timeline(m, active_plan(m)))

    def test_final_cancellation_callback_has_pure_fence(self):
        m = self.timed()
        counter = upstream.CountingControl(None)
        self.build(m, control=counter)
        final_count = counter.count
        class MutatingControl:
            count = 0
            def check(self):
                self.count += 1
                if self.count == final_count:
                    m.project_name = "changed at final cancellation boundary"
        with self.assertRaises(ValueError):
            self.build(m, control=MutatingControl())

    def test_callback_capacity_before_hash_or_copy(self):
        for domain, member, limit in (("render_timeline", "plans", MAX_PLANS),
                ("acquisition", "runs", 64), ("editing", "plans", 64)):
            for stage_path in (False, True):
                m = self.timed()
                mutated = [False]
                class Control:
                    count = 0
                    def check(self):
                        self.count += 1
                        if self.count == 3:
                            setattr(getattr(m, domain), member, [None] * (limit + 1))
                            mutated[0] = True
                reached = [0]
                def guarded(value):
                    if mutated[0]:
                        reached[0] += 1
                    self.assertFalse(mutated[0], "recursive operation after capacity mutation")
                    return exact_signature(value)
                def guarded_copy(value):
                    reached[0] += 1
                    raise AssertionError("copy")
                with self.subTest(domain=domain, stage=stage_path), patch(
                        "creator_studio.render_timeline.engine.exact_signature", side_effect=guarded), patch(
                        "creator_studio.render_timeline.stage.exact_signature", side_effect=guarded), patch(
                        "creator_studio.render_timeline.engine.deepcopy", side_effect=guarded_copy):
                    if stage_path:
                        result = RenderTimelineStage(**self.config).execute(
                            StageContext(m, Control(), 1, lambda *a: None))
                        self.assertEqual(result.result.status, StageStatus.FAILED)
                    else:
                        with self.assertRaises(ValueError):
                            self.build(m, control=Control())
                    self.assertTrue(mutated[0])
                self.assertEqual(reached[0], 0)

    def test_usability_callable_configuration_and_capacity_mutations(self):
        for mutation in ("storage", "inspector", "configuration", "control", "capacity", None):
            m = self.build(self.timed(materialized=True))
            facts = m.acquisition.materializations[0].inspection
            class Control:
                def check(self):
                    pass
            control = Control()
            class Storage:
                def verify(self, asset, token):
                    if mutation == "storage":
                        self.verify = lambda *args: Path("synthetic")
                    if mutation == "control":
                        control.check = lambda: None
                    if mutation == "capacity":
                        m.render_timeline.plans = [None] * (MAX_PLANS + 1)
                    return Path("synthetic")
            class Inspector:
                inspector_id = "synthetic"
                inspector_version = "1"
                policy_id = "objective_media"
                policy_version = "1"
                def inspect(self, path, token):
                    if mutation == "inspector":
                        self.inspect = lambda *args: facts
                    if mutation == "configuration":
                        self.inspector_version = "2"
                    return facts
            kwargs = dict(storage=Storage(), inspector=Inspector(), control=control,
                acquisition_spec=m.acquisition.runs[0].acquisition_spec)
            with self.subTest(mutation=mutation):
                if mutation is None:
                    self.assertTrue(observe_media_usability(m, **kwargs))
                else:
                    with self.assertRaises(ValueError):
                        observe_media_usability(m, **kwargs)

    def test_media_capacity_rejected_before_post_observation_hash(self):
        import creator_studio.render_timeline.engine as engine
        m = self.build(self.timed(materialized=True))
        class Storage:
            def verify(self, asset, control):
                m.render_timeline.plans = [None] * (MAX_PLANS + 1)
                return Path("synthetic")
        def guarded(value):
            self.assertLessEqual(len(m.render_timeline.plans), MAX_PLANS)
            return exact_signature(value)
        with patch.object(engine, "exact_signature", side_effect=guarded), self.assertRaises(ValueError):
            observe_media_usability(m, storage=Storage(),
                acquisition_spec=m.acquisition.runs[0].acquisition_spec)

    def test_stage_post_builder_capacity_rejected_before_hash(self):
        import creator_studio.render_timeline.stage as adapter
        m = self.timed()
        original = adapter.build_render_timeline
        mutated = [False]
        def callback(*args, **kwargs):
            proposal = original(*args, **kwargs)
            m.render_timeline.plans = [None] * (MAX_PLANS + 1)
            mutated[0] = True
            return proposal
        reached = [0]
        def guarded(value):
            if mutated[0]:
                reached[0] += 1
            self.assertFalse(mutated[0], "post-builder stage hash")
            return exact_signature(value)
        with patch.object(adapter, "build_render_timeline", side_effect=callback), patch.object(
                adapter, "exact_signature", side_effect=guarded):
            result = RenderTimelineStage(**self.config).execute(
                StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertTrue(mutated[0])
        self.assertEqual(reached[0], 0)
        self.assertEqual(result.result.status, StageStatus.FAILED)

    def test_narration_callable_identity_forms(self):
        from creator_studio.render_timeline.engine import narration_storage_fence
        class Callable:
            def __call__(self, *args):
                pass
        class Storage:
            def open_read(self, *args):
                pass
        storage = Storage()
        for implementation in (storage.open_read, lambda *a: None, Callable(), [].append):
            storage.open_read = implementation
            config = {"storage": storage}
            self.assertEqual(narration_storage_fence(config), narration_storage_fence(config))
            previous = narration_storage_fence(config)
            storage.open_read = lambda *a: None
            self.assertNotEqual(previous, narration_storage_fence(config))

    def test_stage_post_builder_narration_callable_replacement(self):
        import creator_studio.render_timeline.stage as adapter
        delegate = self.storage
        class Storage:
            def open_read(self, *args, **kwargs):
                return delegate.open_read(*args, **kwargs)
        storage = Storage()
        stage = RenderTimelineStage(**dict(self.config, storage=storage))
        original = adapter.build_render_timeline
        called = []
        def callback(*args, **kwargs):
            proposal = original(*args, **kwargs)
            storage.open_read = delegate.open_read
            called.append(True)
            return proposal
        with patch.object(adapter, "build_render_timeline", side_effect=callback):
            result = stage.execute(StageContext(self.timed(), CancellationToken(), 1, lambda *a: None))
        self.assertTrue(called)
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)

    def test_real_narration_callable_fence_identical_bytes(self):
        from io import BytesIO
        from creator_studio.render_timeline.engine import callable_identity
        delegate = self.storage
        for path in ("eligibility", "builder", "stage", "reuse", "builder_reuse"):
            for mutation in (None, "open_read", "control"):
                with self.subTest(path=path, mutation=mutation):
                    stage = RenderTimelineStage(**self.config)
                    outcome = stage.execute(StageContext(self.timed(), CancellationToken(), 1, lambda *a: None))
                    m, execution = outcome.update.manifest, outcome.result
                    execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
                        {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
                    m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
                        dependency_signature=execution.dependency_signature, execution=execution))
                    control = CancellationToken()
                    reads = []
                    assets = []
                    class Storage:
                        def replacement(self, asset_id):
                            with delegate.open_read(asset_id) as stream:
                                data = stream.read()
                            reads.append(data)
                            assets.append(asset_id)
                            return BytesIO(data)
                        def open_read(self, asset_id):
                            stream = self.replacement(asset_id)
                            if mutation == "open_read":
                                self.open_read = self.replacement
                            if mutation == "control":
                                control.check = lambda: None
                            return stream
                    storage = Storage()
                    identity = callable_identity(storage.open_read)
                    config = dict(self.config, storage=storage)
                    stage.timing_configuration = config
                    if path == "reuse":
                        success = stage.validate_reuse(m, execution)
                    elif path == "stage":
                        result = stage.execute(StageContext(self.timed(), control, 1, lambda *a: None))
                        success = result.result.status == StageStatus.SUCCEEDED
                        if not success:
                            self.assertIsNone(result.update)
                    else:
                        try:
                            if path == "eligibility":
                                success = current_render_timeline_eligibility(m, control=control, **config).eligible
                            else:
                                build_render_timeline(m if path == "builder_reuse" else self.timed(),
                                    control=control, **config)
                                success = True
                        except ValueError:
                            success = False
                    # Reuse has no supplied control; its separate control fence is tested above.
                    self.assertEqual(success, mutation is None or (path == "reuse" and mutation == "control"))
                    self.assertTrue(reads)
                    if mutation == "open_read":
                        self.assertNotEqual(identity, callable_identity(storage.open_read))
                        with storage.open_read(assets[0]) as stream:
                            self.assertEqual(stream.read(), reads[0])
                    else:
                        self.assertEqual(identity, callable_identity(storage.open_read))

    def test_stage_storage_reference_replacement(self):
        m = self.timed()
        delegate = self.storage
        stage = RenderTimelineStage(**self.config)
        called = [False]
        class Storage:
            def open_read(self, *args, **kwargs):
                called[0] = True
                stage.timing_configuration["storage"] = delegate
                return delegate.open_read(*args, **kwargs)
        stage.timing_configuration["storage"] = Storage()
        outcome = stage.execute(StageContext(m, CancellationToken(), 1, lambda *a: None))
        self.assertTrue(called[0])
        self.assertEqual(outcome.result.status, StageStatus.FAILED)

    def test_pure_preflight_has_no_callbacks(self):
        from creator_studio.render_timeline.engine import preflight_for_expensive_operation
        m = self.timed()
        before = deepcopy(m)
        preflight_for_expensive_operation(m)
        self.assertEqual(m, before)

    def test_timing_callback_capacity_before_hash(self):
        import creator_studio.render_timeline.engine as engine
        for domain, member, limit in (("render_timeline", "plans", MAX_PLANS),
                ("acquisition", "assets", 16384), ("editing", "plans", 64)):
            m = self.build()
            original = engine.current_placement_timing_eligibility
            mutated = [False]
            def callback(*args, **kwargs):
                result = original(*args, **kwargs)
                setattr(getattr(m, domain), member, [None] * (limit + 1))
                mutated[0] = True
                return result
            def guarded(value):
                self.assertFalse(mutated[0], "post-callback hash")
                return exact_signature(value)
            with self.subTest(domain=domain), patch.object(engine,
                    "current_placement_timing_eligibility", side_effect=callback), patch.object(
                    engine, "exact_signature", side_effect=guarded), self.assertRaises(ValueError):
                self.eligibility(m)
            self.assertTrue(mutated[0])

    def test_valid_provenance_identity(self):
        original = active_plan(self.build(self.timed(materialized=True)))
        for kwargs in (dict(inspector_version="2"), dict(digest="b" * 64)):
            changed_manifest = self.build(self.timed(materialized=True, **kwargs))
            require_valid(changed_manifest)
            changed = active_plan(changed_manifest)
            visible = lambda p: [(e.media_kind, e.source_duration_us, e.source_usage,
                e.source_start_us, e.source_end_us, e.outcome) for e in p.entries]
            self.assertEqual(visible(original), visible(changed))
            self.assertNotEqual(original.source_usage_signature, changed.source_usage_signature)
            self.assertNotEqual(original.output_signature, changed.output_signature)
            self.assertNotEqual(original.render_timeline_plan_id, changed.render_timeline_plan_id)

    def test_mixed_valid_history_replay(self):
        first = self.build(self.timed(materialized=True, duration=0.5))
        second = self.build(self.timed(materialized=True, duration=1.0))
        require_valid(first)
        require_valid(second)
        first.acquisition = second.acquisition
        first.editing = second.editing
        first.placement_timing = second.placement_timing
        with self.assertRaises((ValueError, StopIteration)):
            validate_history(first)

    def test_stage_cancellation_propagates(self):
        m = self.timed()
        before = deepcopy(m)
        stage = RenderTimelineStage(**self.config)
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(Cancelled):
            stage.execute(StageContext(m, token, 1, lambda *a: None))
        self.assertEqual(m, before)

class PureContractTests(unittest.TestCase):
    def fixture(self, kind=VisualMediaKind.IMAGE, duration=None, outcome=PlacementTimingOutcome.TIMED,
            start=0, end=500000):
        record = MaterializationRecord("materialization:" + "a" * 64, "retrieval:" + "a" * 64,
            "candidate:" + "a" * 64, "a" * 64, AcquisitionProviderSpec("test", "test", permits_acquisition=True),
            RenditionObservation("one", kind, 640, 480),
            InspectionFacts("test", "1", kind, MediaFormat.PNG if kind != VisualMediaKind.VIDEO else MediaFormat.MP4,
                MediaCodec.PNG if kind != VisualMediaKind.VIDEO else MediaCodec.H264, 640, 480, duration),
            "asset:sha256:" + "a" * 64)
        asset = MaterializedAsset(record.asset_id, "a" * 64, 1, "not-copied")
        placement = SimpleNamespace(placement_id="edit_placement:" + "a" * 64, ordinal=0,
            planned_shot_id="planned_shot:" + "a" * 64, shot_selection_id="shot_selection:" + "a" * 64,
            acquisition_outcome=AcquisitionOutcome.MATERIALIZED, materialization_id=record.materialization_id)
        shot = ShotAcquisition(placement.shot_selection_id, placement.acquisition_outcome, placement.materialization_id)
        timing = SimpleNamespace(entries=[SimpleNamespace(placement_id=placement.placement_id,
            outcome=outcome, start_us=start, end_us=end)])
        return (SimpleNamespace(acquisition=AcquisitionState(materializations=[record], assets=[asset])),
            SimpleNamespace(placements=[placement]), SimpleNamespace(shot_acquisitions=[shot]), timing)

    def test_image_full_interval_no_source_coordinates(self):
        entry = derive_entries(*self.fixture())[0]
        self.assertEqual(entry.outcome, RenderTimelineOutcome.READY)
        self.assertEqual(entry.source_usage, SourceUsage.STILL_IMAGE)
        self.assertEqual((entry.source_duration_us, entry.source_start_us, entry.source_end_us), (None, None, None))

    def test_graphic_and_unknown_unsupported(self):
        for kind in (VisualMediaKind.GRAPHIC, VisualMediaKind.UNKNOWN):
            entry = derive_entries(*self.fixture(kind=kind))[0]
            self.assertEqual(entry.outcome, RenderTimelineOutcome.UNSUPPORTED_MEDIA_TYPE)
            self.assertEqual(entry.source_usage, SourceUsage.UNRESOLVED)

    def test_all_non_timed_outcomes_explanatory(self):
        for outcome in PlacementTimingOutcome:
            if outcome != PlacementTimingOutcome.TIMED:
                with self.subTest(outcome=outcome):
                    entry = derive_entries(*self.fixture(outcome=outcome, start=None, end=None))[0]
                    self.assertEqual(entry.timing_outcome, outcome)
                    self.assertEqual(entry.outcome, RenderTimelineOutcome.UNRESOLVED_TIMING)
                    self.assertIsNone(entry.timeline_start_us)
                    self.assertIsNone(entry.timeline_end_us)

    def test_bool_float_time_rejected(self):
        for start, end in ((True, 500000), (0, False), (0.0, 500000), (0, 500000.0)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                derive_entries(*self.fixture(start=start, end=end))

    def test_exact_binary_duration_normalization(self):
        for value, expected in ((0.5, 500000), (0.25, 250000), (0.015625, 15625),
                (2.0, 2000000), (0.1, None), (0.3, None), (True, None), (1, None),
                (float("inf"), None), (float("nan"), None), (-1.0, None), (0.0, None)):
            with self.subTest(value=value):
                self.assertEqual(normalize_duration(value), expected)

    def test_closed_authority_surface(self):
        self.assertEqual({v.value for v in SourceUsage}, {"UNRESOLVED", "STILL_IMAGE", "WHOLE_VIDEO"})
        self.assertNotIn("AUDIO", VisualMediaKind.__members__)
        for cls in RECORDS:
            self.assertFalse({"fps", "track_id", "loop", "freeze", "speed", "render_executable"} &
                {f.name for f in fields(cls)})

    def test_dependencies_approved_and_rejected(self):
        self.assertEqual(normalize_dependencies(()), ())
        expected = ("media_acquisition", "edit_planning", "placement_timing")
        self.assertEqual(normalize_dependencies(iter(expected)), expected)
        for bad in (expected[::-1], expected[:2], expected + ("extra",), ("edit_planning",) * 3,
                "", None, ("unknown",)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_dependencies(bad)

    def test_infinite_and_huge_dependencies_consumed_four(self):
        for limit in (None, 10**9):
            count = [0]
            def values():
                while limit is None or count[0] < limit:
                    count[0] += 1
                    yield "media_acquisition"
            with self.assertRaises(ValueError):
                normalize_dependencies(values())
            self.assertEqual(count[0], 4)

    def test_one_shot_dependencies(self):
        class Once:
            count = 0
            def __iter__(self):
                self.count += 1
                if self.count != 1:
                    raise AssertionError("second iterator")
                return iter(("media_acquisition", "edit_planning", "placement_timing"))
        original = Once()
        stage = RenderTimelineStage(dependencies=original)
        self.assertEqual(original.count, 1)
        stage._declaration()
        self.assertEqual(original.count, 1)

    def test_raw_record_member_equality_overflow_every_record(self):
        for cls in RECORDS:
            raw = {f.name: None for f in fields(cls)}
            preflight_record(raw, cls, raw=True)
            raw["extra"] = None
            with self.subTest(cls=cls), self.assertRaises(ValueError):
                preflight_record(raw, cls, raw=True)

    def test_large_unknown_raw_rejected_before_deepcopy(self):
        document = to_data(ProjectManifest("raw"))
        document["render_timeline"] = {str(i): 0 for i in range(5000)}
        with patch("creator_studio.manifest.migrations.deepcopy", side_effect=AssertionError("copy")):
            with self.assertRaises(ValueError):
                migrate_document(document)

    def test_small_unknown_preserved_to_strict_decode(self):
        raw = to_data(ProjectManifest("raw"))
        raw["render_timeline"] = {"plans": [], "unknown": 1}
        migrated = migrate_document(raw)
        self.assertEqual(migrated["render_timeline"], raw["render_timeline"])
        with self.assertRaises(ValueError):
            decode(ProjectManifest, migrated)

    def test_nested_scalar_malformed_bounds(self):
        for raw in ({"plans": "x" * 257}, {"plans": [{"entries": ["x" * 257]}]},
                {"plans": [{"entries": [{"timeline_start_us": 1 << 100}]}]}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                preflight_document(raw)
        for raw in (None, [], {}, {"plans": [None]}, {"plans": [{"entries": None}]}):
            preflight_document(raw)

    def test_capacity_equal_and_overflow(self):
        entry = derive_entries(*self.fixture())[0]
        plan = RenderTimelinePlan("", "", "", "", "", "", "", RenderTimelineSpec(), [entry])
        preflight_history(RenderTimelineState([plan] * MAX_PLANS))
        with self.assertRaises(ValueError):
            preflight_history(RenderTimelineState([plan] * (MAX_PLANS + 1)))
        full = replace(plan, entries=[entry] * MAX_ENTRIES_PER_PLAN)
        preflight_record(full, RenderTimelinePlan)
        with self.assertRaises(ValueError):
            preflight_record(replace(full, entries=full.entries + [entry]), RenderTimelinePlan)
        preflight_history(RenderTimelineState([full] * 16))
        with self.assertRaises(ValueError):
            preflight_history(RenderTimelineState([full] * 16 + [plan]))
        diagnostics = [RenderDiagnostic.MEDIA_TOO_SHORT] * MAX_DIAGNOSTICS_PER_ENTRY
        preflight_record(replace(entry, diagnostics=diagnostics), RenderTimelineEntry)
        with self.assertRaises(ValueError):
            preflight_record(replace(entry, diagnostics=diagnostics + diagnostics[:1]), RenderTimelineEntry)

    def test_source_usage_binds_provenance_assets_and_order(self):
        entry = derive_entries(*self.fixture())[0]
        plan = RenderTimelinePlan("", "", "", "", "", "", "", RenderTimelineSpec(), [entry])
        original = assign_identity(plan)
        for name, value in (("materialization_id", "materialization:" + "b" * 64),
                ("materialization_evidence_signature", "b" * 64),
                ("asset_id", "asset:sha256:" + "b" * 64),
                ("asset_evidence_signature", "b" * 64)):
            changed = assign_identity(replace(plan, entries=[replace(entry, **{name: value})]))
            self.assertNotEqual(original.source_usage_signature, changed.source_usage_signature)
            self.assertNotEqual(original.output_signature, changed.output_signature)
            self.assertNotEqual(original.render_timeline_plan_id, changed.render_timeline_plan_id)
        other = replace(entry, placement_id="edit_placement:" + "b" * 64)
        self.assertNotEqual(assign_identity(replace(plan, entries=[entry, other])).source_usage_signature,
            assign_identity(replace(plan, entries=[other, entry])).source_usage_signature)
        self.assertEqual(original, assign_identity(plan))
        self.assertNotIn("not-copied", canonical_payload(original))
        self.assertFalse({"path", "object_key", "url"} & {f.name for f in fields(entry)})

    def test_domain_separation(self):
        self.assertNotEqual(signed("input_binding", ["x"]), signed("output", ["x"]))
        self.assertNotEqual(signed("output", ["x"]), exact_signature(["M71", "output", "1", ["x"]]))

    def test_coverage_limit_4097(self):
        entries = [SimpleNamespace(outcome=RenderTimelineOutcome.READY,
            timeline_start_us=2 * i + 1, timeline_end_us=2 * i + 2) for i in range(4096)]
        plan = SimpleNamespace(entries=entries, placement_timing_plan_id="timing")
        m = SimpleNamespace(placement_timing=SimpleNamespace(plans=[SimpleNamespace(
            placement_timing_plan_id="timing", narration_duration_us=8193)]))
        with patch("creator_studio.manifest.render_timeline_validation.validate_plan"):
            self.assertEqual(len(uncovered_intervals(m, plan)), 4097)
            entries.append(SimpleNamespace(outcome=RenderTimelineOutcome.READY,
                timeline_start_us=8193, timeline_end_us=8194))
            m.placement_timing.plans[0].narration_duration_us = 8195
            with self.assertRaises(ValueError):
                uncovered_intervals(m, plan)

    def test_unresolved_between_timed_does_not_fill(self):
        args = self.fixture()
        m, edit, acquisition, timing = args
        first = edit.placements[0]
        edit.placements = [first, SimpleNamespace(**vars(first)), SimpleNamespace(**vars(first))]
        timing.entries = [timing.entries[0], SimpleNamespace(**vars(timing.entries[0])),
            SimpleNamespace(**vars(timing.entries[0]))]
        for index, (p, t) in enumerate(zip(edit.placements, timing.entries)):
            p.placement_id = "edit_placement:" + str(index) * 64
            p.ordinal = index
            t.placement_id = p.placement_id
        timing.entries[1].outcome = PlacementTimingOutcome.UNRESOLVED
        timing.entries[1].start_us = timing.entries[1].end_us = None
        timing.entries[2].start_us, timing.entries[2].end_us = 1000000, 1500000
        entries = derive_entries(*args)
        self.assertEqual(entries[0].timeline_end_us, 500000)
        self.assertIsNone(entries[1].timeline_start_us)
        self.assertEqual(entries[2].timeline_start_us, 1000000)

    def test_raw_member_overflow_before_value_walk_every_record(self):
        for cls in RECORDS:
            raw = {str(i): "x" * 1000 for i in range(len(fields(cls)) + 1)}
            with self.subTest(cls=cls), patch(
                    "creator_studio.manifest.render_timeline_validation.bounded_value",
                    side_effect=AssertionError("walked")):
                with self.assertRaises(ValueError):
                    preflight_record(raw, cls, raw=True)

    def test_upstream_capacity_before_hash(self):
        from creator_studio.manifest.render_timeline_validation import preflight_upstream
        m = ProjectManifest("bounds")
        for state, member, limit in (("acquisition", "runs", 64),
                ("acquisition", "assets", 16384), ("acquisition", "materializations", 16384),
                ("editing", "plans", 64)):
            changed = deepcopy(m)
            setattr(getattr(changed, state), member, [None] * (limit + 1))
            with self.subTest(state=state, member=member), self.assertRaises(ValueError):
                preflight_upstream(changed)

    def test_production_import_isolation_and_exact_arithmetic(self):
        paths = list(Path("creator_studio/render_timeline").glob("*.py")) + [
            Path("creator_studio/manifest/render_timeline.py"),
            Path("creator_studio/manifest/render_timeline_validation.py")]
        forbidden = {"PyQt6", "pipeline", "stock", "subprocess", "requests", "httpx", "whisper"}
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], forbidden)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden)
        source = Path("creator_studio/manifest/render_timeline.py").read_text(encoding="utf-8")
        self.assertIn("as_integer_ratio()", source)
        for name in ("round(", "floor(", "ceil(", "epsilon", "tolerance"):
            self.assertNotIn(name, source)

if __name__ == "__main__":
    unittest.main()
