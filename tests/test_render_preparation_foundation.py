"""Offline M73 retained authority, adversarial bounds and transient boundaries.

Only synthetic upstream fixtures and injected collaborators are used.
No provider, real-world media, renderer, FFmpeg or network is invoked.
"""
import ast
from copy import deepcopy
from dataclasses import fields, replace, FrozenInstanceError
from itertools import repeat
from pathlib import Path
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, require_valid
from creator_studio.manifest.codec import decode, to_data
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.render_preparation import *
from creator_studio.manifest.render_preparation_validation import (
    validate_profile, validate_spec, frame_aligned, validate_plan, validate_history,
    preflight_record, preflight_history, preflight_document, bounded_value,
    derive_preparation, project_plan, derive_uncovered_intervals)
from creator_studio.manifest.render_timeline import RenderTimelineOutcome
from creator_studio.manifest.models import ProcessingState, Status
from creator_studio.manifest.signatures import dependency_signature
from creator_studio.render_preparation import *
from creator_studio.render_preparation.engine import (active_plan, normalize_dependencies,
    ObservationFence, callable_identity)
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
import tests.test_render_timeline_foundation as upstream

PROFILE = OutputProfile(640, 480, 24, 1)
SPEC = RenderPreparationSpec(*tuple(PreparationPolicy))

class RenderPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upstream.RenderTimelineTests.setUpClass()
        cls.addClassCleanup(upstream.RenderTimelineTests.doClassCleanups)
        fixture = upstream.RenderTimelineTests("test_empty_schema_and_missing_migration")
        fixture.setUp()
        cls.base = fixture.build(fixture.timed(materialized=True))
        cls.storage = fixture.storage

    def setUp(self):
        self.m = deepcopy(self.base)
        self.config = dict(upstream.CONFIG, acquisition_spec=self.m.acquisition.runs[0].acquisition_spec)

    def build(self, m=None, **kwargs):
        return build_render_preparation(self.m if m is None else m,
            output_profile=kwargs.pop("output_profile", PROFILE), spec=kwargs.pop("spec", SPEC),
            **self.config, **kwargs)

    def stage(self, **kwargs):
        return RenderPreparationStage(output_profile=PROFILE, spec=SPEC, **self.config, **kwargs)

    def retained(self):
        stage = self.stage()
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m, execution = outcome.update.manifest, outcome.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        return m, stage, execution

    def test_empty_additive_schema_two(self):
        m = ProjectManifest("empty")
        require_valid(m)
        self.assertEqual(m.schema_version, 2)
        self.assertEqual(m.render_preparation, RenderPreparationState())

    def test_missing_migration_fabricates_no_authority(self):
        raw = to_data(ProjectManifest("empty"))
        del raw["render_preparation"]
        loaded = decode(ProjectManifest, migrate_document(raw))
        self.assertEqual(to_data(loaded.render_preparation),
            {"plans": [], "active_render_preparation_plan_id": None})

    def test_explicit_profile_no_defaults(self):
        for args in ((), (640,), (640, 480), (640, 480, 24)):
            with self.subTest(args=args), self.assertRaises(TypeError):
                OutputProfile(*args)

    def test_explicit_policies_no_defaults(self):
        with self.assertRaises(TypeError):
            RenderPreparationSpec()
        validate_spec(SPEC)

    def test_frozen_runtime_and_retained_records(self):
        for record, name in ((PROFILE, "width_px"), (SPEC, "contract_version")):
            with self.assertRaises(FrozenInstanceError):
                setattr(record, name, 1)

    def test_exact_alignment_and_no_rounding(self):
        for time in (0, 125000, 500000, 1000000):
            self.assertTrue(frame_aligned(time, PROFILE))
        for time in (1, 41666, 41667, 499999, 500001):
            self.assertFalse(frame_aligned(time, PROFILE))

    def test_rational_lattice(self):
        profile = OutputProfile(1, 1, 30000, 1001)
        self.assertTrue(frame_aligned(1001000, profile))
        self.assertFalse(frame_aligned(1000000, profile))

    def test_narration_duration_binding(self):
        plan = active_plan(self.build())
        run = self.m.voice_timing.runs[0]
        self.assertEqual(plan.output_duration_us, run.inspection.duration_us)
        self.assertEqual(plan.narration_binding.inspection, run.inspection)
        self.assertEqual(plan.narration_binding.acceptance_receipt, run.receipt)
        self.assertNotEqual(max(e.timeline_end_us for e in plan.entries), plan.output_duration_us)

    def test_complete_upstream_still_gapped(self):
        from creator_studio.manifest.render_timeline_validation import complete_render_timeline
        timeline = self.m.render_timeline.plans[0]
        self.assertTrue(complete_render_timeline(self.m, timeline))
        plan = active_plan(self.build())
        self.assertIn(PreparationRequirement.UNCOVERED_VISUAL_INTERVALS, plan.requirements)
        self.assertEqual(len(plan.entries), len(timeline.entries))

    def test_source_use_preserved(self):
        plan = active_plan(self.build())
        for entry, old in zip(plan.entries, self.m.render_timeline.plans[0].entries):
            self.assertEqual((entry.source_usage, entry.source_start_us, entry.source_end_us,
                entry.source_duration_us), (old.source_usage, old.source_start_us,
                old.source_end_us, old.source_duration_us))

    def test_matching_video_geometry_not_presentation(self):
        entry = active_plan(self.build()).entries[0]
        self.assertNotIn(PreparationRequirement.TRANSFORM_POLICY_REQUIRED, entry.requirements)
        self.assertIn(PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED, entry.requirements)

    def test_geometry_mismatch(self):
        plan = active_plan(self.build(output_profile=OutputProfile(1280, 720, 24, 1)))
        self.assertTrue(all(PreparationRequirement.TRANSFORM_POLICY_REQUIRED in e.requirements for e in plan.entries))

    def test_unresolved_timing_and_source(self):
        timeline = self.m.render_timeline.plans[0]
        entry = replace(timeline.entries[0], timeline_start_us=None, timeline_end_us=None,
            source_usage=SourceUsage.UNRESOLVED, outcome=RenderTimelineOutcome.UNRESOLVED_TIMING)
        entries, covered = derive_preparation(self.m, replace(timeline, entries=[entry]), PROFILE)
        self.assertEqual(covered, [])
        self.assertIn(PreparationRequirement.FRAME_ALIGNMENT_NOT_ESTABLISHED, entries[0].requirements)
        self.assertIn(PreparationRequirement.SUPPORTED_SOURCE_USE_NOT_ESTABLISHED, entries[0].requirements)

    def test_still_image_missing_presentation_evidence(self):
        timeline = self.m.render_timeline.plans[0]
        entry = replace(timeline.entries[0], source_usage=SourceUsage.STILL_IMAGE,
            source_start_us=None, source_end_us=None, source_duration_us=None)
        entries, _ = derive_preparation(self.m, replace(timeline, entries=[entry]), PROFILE)
        self.assertIn(PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED, entries[0].requirements)
        self.assertNotIn(PreparationRequirement.TRANSFORM_POLICY_REQUIRED, entries[0].requirements)

    def test_image_dimension_mismatch(self):
        timeline = self.m.render_timeline.plans[0]
        entry = replace(timeline.entries[0], source_usage=SourceUsage.STILL_IMAGE)
        entries, _ = derive_preparation(self.m, replace(timeline, entries=[entry]), OutputProfile(1, 1, 24, 1))
        self.assertIn(PreparationRequirement.TRANSFORM_POLICY_REQUIRED, entries[0].requirements)

    def test_deterministic_repeatability_and_domain_separation(self):
        first, second = self.build(), self.build()
        self.assertEqual(first.render_preparation, second.render_preparation)
        plan = active_plan(first)
        signatures = [getattr(plan, name) for name in ("input_binding_signature", "output_profile_signature",
            "render_policy_signature", "preparation_signature", "output_signature")]
        self.assertEqual(len(set(signatures)), 5)
        self.assertNotEqual(signed("input_binding", []), signed("output", []))
        self.assertTrue(all(len(s) == 64 for s in signatures))

    def test_builder_atomicity_only_m73_changes(self):
        before = deepcopy(self.m)
        result = self.build()
        self.assertEqual(before, self.m)
        for f in fields(result):
            if f.name != "render_preparation":
                self.assertEqual(getattr(before, f.name), getattr(result, f.name), f.name)
        require_valid(result)

    def test_failure_atomicity(self):
        before = deepcopy(self.m)
        with self.assertRaises(ValueError):
            self.build(output_profile=OutputProfile(True, 480, 24, 1))
        self.assertEqual(before, self.m)

    def test_cancellation_atomicity(self):
        before = deepcopy(self.m)
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(Cancelled):
            self.build(control=token)
        self.assertEqual(before, self.m)

    def test_logical_eligibility_zero_storage_calls(self):
        m = self.build()
        with patch.object(self.storage, "open_read", side_effect=AssertionError("read")), \
                patch("creator_studio.voice_timing.engine.current_timing_eligibility", side_effect=AssertionError("voice")), \
                patch("creator_studio.render_timeline.engine.current_render_timeline_eligibility", side_effect=AssertionError("combined")):
            self.assertTrue(current_logically_eligible(m, output_profile=PROFILE, spec=SPEC, **self.config))

    def test_historical_callback_free_and_pointer_independent(self):
        m = self.build()
        for state, name in ((m.render_timeline, "active_render_timeline_plan_id"),
                (m.placement_timing, "active_placement_timing_plan_id"),
                (m.voice_timing, "active_alignment_run_id"), (m.voice_timing, "active_narration_revision_id"),
                (m.editing, "active_creator_edit_plan_id"), (m.acquisition, "active_creator_acquisition_id")):
            setattr(state, name, None)
        with patch.object(self.storage, "open_read", side_effect=FileNotFoundError()):
            validate_history(m)
        self.assertFalse(current_logically_eligible(m, output_profile=PROFILE, spec=SPEC, **self.config))

    def test_stale_active_m72(self):
        m = self.build()
        m.render_timeline.active_render_timeline_plan_id = None
        self.assertFalse(current_logically_eligible(m, output_profile=PROFILE, spec=SPEC, **self.config))
        validate_history(m)

    def test_active_only_reuse_blocked_result(self):
        m, stage, previous = self.retained()
        self.assertTrue(stage.validate_reuse(m, previous))
        self.assertEqual(self.build(m), m)
        self.assertEqual(active_plan(m).conclusion, PreparationConclusion.PREPARATION_REQUIREMENTS_OUTSTANDING)

    def test_inactive_identity_collision_no_resurrection(self):
        m = self.build()
        m.render_preparation.active_render_preparation_plan_id = None
        before = deepcopy(m)
        with self.assertRaises(ValueError):
            self.build(m)
        self.assertEqual(m, before)

    def test_no_execution_evidence_no_reuse(self):
        m = self.build()
        with self.assertRaises(ValueError):
            self.build(m)

    def test_exact_two_ordered_artifacts(self):
        m = self.build()
        plan = active_plan(m)
        artifacts = self.stage().artifacts(m, plan)
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(artifacts[0].reference, "render_preparation/" + plan.render_preparation_plan_id)
        self.assertEqual(artifacts[1].reference,
            "render_preparation_timeline/" + plan.timeline_binding.render_timeline_plan_id)

    def test_one_shot_dependencies(self):
        self.assertEqual(normalize_dependencies(iter(("render_timeline",))), ("render_timeline",))

    def test_infinite_dependencies_only_two_pulls(self):
        calls = []
        def iterator():
            while True:
                calls.append(1)
                yield "render_timeline"
        with self.assertRaises(ValueError):
            normalize_dependencies(iterator())
        self.assertEqual(len(calls), 2)

    def test_second_value_reject_without_third(self):
        pulls = []
        def iterator():
            for value in ("render_timeline", "other", "third"):
                pulls.append(value)
                yield value
        with self.assertRaises(ValueError):
            normalize_dependencies(iterator())
        self.assertEqual(pulls, ["render_timeline", "other"])

    def test_canonical_byte_boundary(self):
        plan = active_plan(self.build())
        payload = canonical_payload(plan)
        self.assertEqual(canonical_payload(plan, max_bytes=len(payload)), payload)
        with self.assertRaises(ValueError):
            canonical_payload(plan, max_bytes=len(payload) - 1)

    def test_raw_member_overflow_precedes_unknown_value(self):
        class Poison:
            def __getattribute__(self, name):
                raise AssertionError("unknown traversed")
        raw = {"plans": [], "active_render_preparation_plan_id": None, "unknown": Poison()}
        with self.assertRaises(ValueError):
            preflight_document(raw)

    def test_small_unknown_survives_preflight_to_decoder(self):
        raw = {"plans": [], "unknown": None}
        preflight_document(raw)
        with self.assertRaises(ValueError):
            decode(RenderPreparationState, raw)

    def test_preflight_before_copy_hash_callback(self):
        self.m.render_preparation.plans = [None] * 65
        with patch("creator_studio.render_preparation.engine.deepcopy", side_effect=AssertionError("copy")), \
                patch("creator_studio.render_preparation.engine.exact_signature", side_effect=AssertionError("hash")):
            class Control:
                def check(self):
                    raise AssertionError("callback")
            with self.assertRaises(ValueError):
                self.build(control=Control())

    def test_callback_capacity_mutation_rejected_before_hash(self):
        m = self.m
        class Control:
            def check(self):
                m.render_preparation.plans = [None] * 65
        with self.assertRaises(ValueError):
            self.build(control=Control())
        self.assertEqual(m.render_preparation.active_render_preparation_plan_id, None)

    def test_control_callable_replacement(self):
        class Control:
            def check(self):
                self.check = lambda: None
        with self.assertRaises(ValueError):
            self.build(control=Control())

    def test_fence_configuration_mutation(self):
        configuration = dict(self.config)
        fence = ObservationFence(self.m, PROFILE, SPEC, configuration)
        def callback():
            configuration["voice_acceptance_policy_version"] = "2"
        with self.assertRaises(ValueError):
            fence.call(lambda: callback)

    def test_fence_callback_result_capacity(self):
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        def callback():
            return [None] * (MAX_TOTAL_ENTRY_ASSESSMENTS + 1)
        with self.assertRaises(ValueError):
            fence.call(lambda: callback, result_check=bounded_value)

    def test_builtin_bound_callable_identity_stable(self):
        values = []
        self.assertEqual(callable_identity(values.append), callable_identity(values.append))
        self.assertNotEqual(callable_identity(values.append), callable_identity([].append))

    def test_transient_assessment_no_mutation(self):
        from creator_studio.render_timeline.models import RenderTimelineEligibility
        from creator_studio.voice_timing.models import TimingEligibility
        m = self.build()
        before = deepcopy(m)
        with patch("creator_studio.render_timeline.engine.current_render_timeline_eligibility",
                return_value=RenderTimelineEligibility(True, True, False, True, True)), \
                patch("creator_studio.voice_timing.engine.current_timing_eligibility",
                return_value=TimingEligibility(True, False, True, True, True, True, True, True)), \
                patch("creator_studio.render_timeline.engine.observe_media_usability", return_value=False):
            result = assess_render_preparation(m, output_profile=PROFILE, spec=SPEC,
                narration_storage=self.storage, visual_storage=object(), **self.config)
        self.assertTrue(result.current_logically_eligible)
        self.assertFalse(result.upstream_full_eligibility)
        self.assertFalse(result.current_narration_usable)
        self.assertFalse(result.current_visual_media_usable)
        self.assertEqual(result.renderer_compatibility, AssessmentBoundary.NOT_ASSESSED)
        self.assertEqual(result.executability, AssessmentBoundary.NOT_ASSESSED)
        self.assertEqual(before, m)

    def test_no_transient_or_forbidden_persistence(self):
        payload = canonical_payload(active_plan(self.build()))
        for forbidden in ("render_ready", "render_executable", "current_visual_media_usable", "output_path",
                "object_key", "storage_root", "http", "transcript", "UUID", "timestamp", "frame_index",
                "crop", "pad", "scale", "stretch", "freeze", "loop", "codec", "bitrate", "faststart"):
            self.assertNotIn(forbidden, payload)

    def test_prohibited_imports_absent(self):
        root = Path(__file__).resolve().parents[1] / "creator_studio"
        files = list((root / "render_preparation").glob("*.py")) + [root / "manifest" / "render_preparation.py",
            root / "manifest" / "render_preparation_validation.py"]
        forbidden = {"PyQt6", "pipeline", "stock", "subprocess", "whisper", "requests", "httpx", "core"}
        for path in files:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(n.name.split(".")[0] in forbidden for n in node.names))
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertFalse(module.split(".")[0] in forbidden)
                    self.assertNotIn("renderer", module)

    def test_scalar_boundary(self):
        bounded_value("x" * MAX_GENERAL_SCALAR)
        with self.assertRaises(ValueError):
            bounded_value("x" * (MAX_GENERAL_SCALAR + 1))

    def test_id_boundary(self):
        raw = {"active_render_preparation_plan_id": "x" * MAX_ID_LENGTH}
        preflight_document(raw)
        raw["active_render_preparation_plan_id"] += "x"
        with self.assertRaises(ValueError):
            preflight_document(raw)

    def test_signature_format_boundary(self):
        for value in ("a" * 64, "0" * 64):
            preflight_record({"output_signature": value}, RenderPreparationPlan, raw=True)
        for value in ("a" * 63, "a" * 65, "A" * 64, "g" * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight_record({"output_signature": value}, RenderPreparationPlan, raw=True)

    def test_depth_boundary(self):
        value = None
        for _ in range(MAX_TRAVERSAL_DEPTH):
            value = [value]
        bounded_value(value)
        with self.assertRaises(ValueError):
            bounded_value([value])

    def test_shared_node_boundary(self):
        # Two children share one budget; patch only the cap to keep this fast.
        with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_NODES", 5):
            bounded_value([[None], [None]])
            with self.assertRaises(ValueError):
                bounded_value([[None, None], [None]])

    def test_actual_node_boundary(self):
        # Exactly 2 million visits: root + 31 lists + 1,999,968 scalar visits.
        children = [[None] * 65536 for _ in range(30)]
        children.append([None] * (MAX_TRAVERSAL_NODES - 32 - 30 * 65536))
        bounded_value(children)
        children[-1].append(None)
        with self.assertRaises(ValueError):
            bounded_value(children)

    def test_aggregate_entries_boundary(self):
        raw = {"plans": [{"entries": [None] * MAX_ENTRIES_PER_PLAN} for _ in range(16)]}
        preflight_document(raw)
        raw["plans"].append({"entries": [None]})
        with self.assertRaises(ValueError):
            preflight_document(raw)

    def test_raw_preflight_before_migration_copy(self):
        raw = to_data(ProjectManifest("raw"))
        raw["render_preparation"] = {"plans": [None] * 65}
        with patch("creator_studio.manifest.migrations.deepcopy", side_effect=AssertionError("copy")):
            with self.assertRaises(ValueError):
                migrate_document(raw)

    def test_typed_preflight_before_recursive_validation(self):
        from creator_studio.manifest.validation import validate
        m = ProjectManifest("typed")
        m.render_preparation.plans = [None] * 65
        with patch("creator_studio.manifest.validation.check_typed", side_effect=AssertionError("typing")):
            self.assertEqual(validate(m)[0].code, "render_preparation_invalid")

    def test_output_duration_alignment_requirement(self):
        m = self.build(output_profile=OutputProfile(640, 480, 30000, 1001))
        plan = active_plan(m)
        self.assertFalse(frame_aligned(plan.output_duration_us, plan.output_profile))
        self.assertIn(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED, plan.requirements)

    def test_full_coverage_exact_interval(self):
        self.assertEqual(derive_uncovered_intervals([(0, 5), (5, 10)], 10), [])

    def test_maximum_uncovered_intervals(self):
        covered = [(2 * i + 1, 2 * i + 2) for i in range(MAX_ENTRIES_PER_PLAN)]
        gaps = derive_uncovered_intervals(covered, 2 * MAX_ENTRIES_PER_PLAN + 1)
        self.assertEqual(len(gaps), MAX_UNCOVERED_INTERVALS)

    def test_visual_end_cannot_extend_output(self):
        self.assertEqual(derive_uncovered_intervals([(0, 20)], 10), [])

    def test_narration_disappearance_is_only_transient(self):
        m = self.build()
        with patch.object(self.storage, "open_read", side_effect=FileNotFoundError()):
            validate_history(m)
            self.assertTrue(current_logically_eligible(m, output_profile=PROFILE, spec=SPEC, **self.config))

    def test_assessment_real_synthetic_narration_observation(self):
        m = self.build()
        class VisualStore:
            def verify(self, *args):
                raise FileNotFoundError()
        result = assess_render_preparation(m, output_profile=PROFILE, spec=SPEC,
            narration_storage=self.storage, visual_storage=VisualStore(), **self.config)
        self.assertTrue(result.current_logically_eligible)
        self.assertTrue(result.upstream_full_eligibility)
        self.assertTrue(result.current_narration_usable)
        self.assertFalse(result.current_visual_media_usable)
        self.assertFalse(result.deterministic_requirements_satisfied)

    def test_assessment_disappearing_synthetic_narration(self):
        m = self.build()
        class Missing:
            def open_read(self, *args):
                raise FileNotFoundError()
            def verify(self, *args):
                raise FileNotFoundError()
        result = assess_render_preparation(m, output_profile=PROFILE, spec=SPEC,
            narration_storage=Missing(), visual_storage=Missing(), **self.config)
        self.assertTrue(result.current_logically_eligible)
        self.assertFalse(result.upstream_full_eligibility)
        self.assertFalse(result.current_narration_usable)
        validate_history(m)

    def test_declared_timeline_dependency_requires_execution(self):
        stage = self.stage(dependencies=("render_timeline",))
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)

    def test_declared_timeline_dependency_exact_execution(self):
        from creator_studio.render_timeline.stage import RenderTimelineStage
        timeline_stage = RenderTimelineStage(**self.config)
        timeline = self.m.render_timeline.plans[0]
        from creator_studio.orchestrator.contracts import StageResult
        execution = StageResult(timeline_stage.stage_id, "1", StageStatus.SUCCEEDED,
            artifacts=timeline_stage.artifacts(self.m, timeline))
        execution.dependency_signature = dependency_signature(timeline_stage.stage_id, "1",
            {"inputs": timeline_stage.signature_inputs(self.m), "configuration": {}}, {})
        self.m.processing.append(ProcessingState(stage="render_timeline", status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        stage = self.stage(dependencies=("render_timeline",))
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m, own_execution = outcome.update.manifest, outcome.result
        own_execution.dependency_signature = dependency_signature(stage.stage_id, "1",
            {"inputs": stage.signature_inputs(m), "configuration": {}}, stage._upstream(m))
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=own_execution.dependency_signature, execution=own_execution))
        self.assertTrue(stage.validate_reuse(m, own_execution))
        m.processing[0].execution.artifacts.reverse()
        self.assertFalse(stage.validate_reuse(m, own_execution))

    def test_final_pure_fence_precedes_publication(self):
        from creator_studio.render_preparation import engine
        events = []
        original = engine.preflight
        class Control:
            def check(self):
                events.append("callback")
        def preflight(m):
            events.append("preflight")
            return original(m)
        with patch.object(engine, "preflight", side_effect=preflight):
            self.build(control=Control())
        self.assertEqual(events[-1], "preflight")

    def test_callback_exception_still_closes_capacity_fence(self):
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        def callback():
            self.m.render_preparation.plans = [None] * 65
            raise RuntimeError("external failure")
        with self.assertRaises(ValueError):
            fence.call(lambda: callback)

    def test_callable_object_class_call_replacement(self):
        class Callback:
            def __call__(self):
                Callback.__call__ = lambda self: None
        callback = Callback()
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        with self.assertRaises(ValueError):
            fence.call(lambda: callback)

    def test_collaborator_object_replacement(self):
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config, (object(),))
        def callback():
            fence.collaborators = (object(),)
        with self.assertRaises(ValueError):
            fence.call(lambda: callback)

    def test_plain_function_replacement(self):
        holder = [None]
        def callback():
            holder[0] = lambda: None
        holder[0] = callback
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        with self.assertRaises(ValueError):
            fence.call(lambda: holder[0])

    def test_builtin_bound_method_replacement(self):
        holder = [[]]
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        original = holder[0]
        def getter():
            if original:
                holder[0] = []
            return holder[0].append
        with self.assertRaises(ValueError):
            fence.call(getter, 1)

    def test_inspector_declared_configuration_replacement(self):
        class Inspector:
            inspector_id = "synthetic"
            inspector_version = "1"
            policy_id = "objective_media"
            policy_version = "1"
            def inspect(self):
                self.inspector_version = "2"
        inspector = Inspector()
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config, (inspector,))
        with self.assertRaises(ValueError):
            fence.call(lambda: inspector.inspect)

    def test_stage_version_mutation_rejects_reuse(self):
        m, stage, execution = self.retained()
        stage.stage_version = "2"
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_stage_dependency_mutation_rejects_reuse(self):
        m, stage, execution = self.retained()
        stage.dependencies = ("voice_timing",)
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_artifact_order_rejects_reuse(self):
        m, stage, execution = self.retained()
        execution.artifacts.reverse()
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_artifact_count_rejects_reuse(self):
        m, stage, execution = self.retained()
        execution.artifacts *= 2
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_artifact_signature_rejects_reuse(self):
        m, stage, execution = self.retained()
        execution.artifacts[0].signature = "b" * 64
        self.assertFalse(stage.validate_reuse(m, execution))

    def test_duplicate_history_identity_reject(self):
        m = self.build()
        m.render_preparation.plans *= 2
        with self.assertRaises(ValueError):
            validate_history(m)

    def test_builder_declared_dependency_requires_execution(self):
        before = deepcopy(self.m)
        with self.assertRaises(ValueError):
            self.build(dependencies=("render_timeline",))
        self.assertEqual(self.m, before)

    def test_dependency_iterator_mutation_is_fenced(self):
        def dependencies():
            self.m.render_preparation.plans = [None] * 65
            yield "render_timeline"
        with self.assertRaises(ValueError):
            self.build(dependencies=dependencies())

    def test_delegated_narration_verifier_replacement(self):
        from creator_studio.voice_timing import engine as voice_engine
        original = voice_engine.verify_audio
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        def callback():
            voice_engine.verify_audio = lambda *args, **kwargs: None
        try:
            with self.assertRaises(ValueError):
                fence.call(lambda: callback)
        finally:
            voice_engine.verify_audio = original

    def test_actual_stream_read_capacity_mutation(self):
        from creator_studio.render_preparation.engine import _Reader
        m = self.m
        class Stream:
            def read(self, size):
                m.render_preparation.plans = [None] * 65
                return b"x"
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        with self.assertRaises(ValueError):
            _Reader(Stream(), fence).read(1)

    def test_actual_stream_read_result_capacity(self):
        from creator_studio.render_preparation.engine import _Reader
        class Stream:
            def read(self, size):
                return b"xx"
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        with self.assertRaises(ValueError):
            _Reader(Stream(), fence).read(1)

    def test_subtitle_data_preserved(self):
        from creator_studio.manifest.models import SubtitleTrack
        self.m.subtitle_tracks.append(SubtitleTrack())
        result = self.build()
        self.assertEqual(result.subtitle_tracks, self.m.subtitle_tracks)
        self.assertEqual(active_plan(result).spec.subtitle_policy, PreparationPolicy.NO_SUBTITLE_OUTPUT_V1)

    def test_raw_upstream_member_overflow_before_unknown_walk(self):
        from creator_studio.manifest.render_preparation_validation import preflight_upstream_evidence
        raw = to_data(self.m)
        raw["voice_timing"] = {str(i): object() for i in range(MAX_TOTAL_ENTRY_ASSESSMENTS + 1)}
        with self.assertRaises(ValueError):
            preflight_upstream_evidence(raw, raw=True)

    def test_bounded_malformed_upstream_error_ownership(self):
        from creator_studio.manifest.validation import validate
        for field_name, value in (("assets", object()),
                ("revisions", {1: (object(),)}), ("runs", [False, {"nested": 3}])):
            with self.subTest(field=field_name):
                m = ProjectManifest("malformed")
                setattr(m.voice_timing, field_name, [value])
                with patch("creator_studio.manifest.validation.preflight_upstream_evidence"):
                    previous = [(e.path, e.code) for e in validate(m)]
                self.assertEqual(previous, [("manifest", "contract")])
                self.assertEqual([(e.path, e.code) for e in validate(m)], previous)

    def test_bounded_wrong_upstream_record_shape_reaches_decoder(self):
        from creator_studio.manifest.render_preparation_validation import preflight_upstream_evidence
        raw = to_data(ProjectManifest("malformed"))
        raw["voice_timing"]["unknown"] = {1: [False, None]}
        preflight_upstream_evidence(raw, raw=True)
        with self.assertRaises(ValueError):
            decode(ProjectManifest, raw)

    def test_malformed_containers_still_have_capacity_limits(self):
        from creator_studio.manifest.render_preparation_validation import preflight_upstream_evidence
        for value in ([None] * 1_000_001,
                {str(i): None for i in range(MAX_TOTAL_ENTRY_ASSESSMENTS + 1)},
                [[[[None]]]]):
            with self.subTest(container_type=type(value).__name__):
                with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_DEPTH", 4):
                    with self.assertRaises(ValueError):
                        preflight_upstream_evidence({"voice_timing": {"unexpected": value}}, raw=True)

    def test_opaque_upstream_leaves_are_uninspected_and_counted(self):
        from dataclasses import dataclass
        from creator_studio.manifest.render_preparation_validation import preflight_upstream_evidence
        events = []
        class Opaque:
            def __getattribute__(self, name):
                events.append("attribute")
                raise RuntimeError("opaque attribute")
            def __repr__(self):
                events.append("repr")
                raise RuntimeError("opaque repr")
            def __str__(self):
                events.append("str")
                raise RuntimeError("opaque str")
            def __hash__(self):
                events.append("hash")
                raise RuntimeError("opaque hash")
            def __deepcopy__(self, memo):
                events.append("copy")
                raise RuntimeError("opaque copy")
        @dataclass
        class UnexpectedRecord:
            child: object
            def __getattribute__(self, name):
                events.append("dataclass attribute")
                raise RuntimeError("opaque dataclass")
        raw = {"voice_timing": {"assets": [Opaque(), UnexpectedRecord(None)]}}
        # Six root nodes, the assets list and its two opaque leaves = nine.
        with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_NODES", 9):
            preflight_upstream_evidence(raw, raw=True)
        with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_NODES", 8):
            with self.assertRaises(ValueError):
                preflight_upstream_evidence(raw, raw=True)
        self.assertEqual(events, [])

    def test_own_malformed_preparation_remains_m73_invalid(self):
        from creator_studio.manifest.validation import validate
        m = ProjectManifest("malformed")
        m.render_preparation.plans = [object()]
        self.assertEqual([(e.path, e.code) for e in validate(m)],
            [("render_preparation", "render_preparation_invalid")])

    def test_upstream_sweep_shared_node_accounting(self):
        from creator_studio.manifest.render_preparation_validation import preflight_upstream_evidence
        raw = {"render_preparation": {"plans": [], "active_render_preparation_plan_id": None}}
        # Root state, empty list, null, then five absent upstream states = 8.
        with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_NODES", 8):
            preflight_upstream_evidence(raw, raw=True)
        with patch("creator_studio.manifest.render_preparation_validation.MAX_TRAVERSAL_NODES", 7):
            with self.assertRaises(ValueError):
                preflight_upstream_evidence(raw, raw=True)

    def test_tampered_conclusion_cannot_be_observed_as_satisfied(self):
        m = self.build()
        m.render_preparation.plans[0] = replace(active_plan(m),
            conclusion=PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED)
        with self.assertRaises(ValueError):
            assess_render_preparation(m, output_profile=PROFILE, spec=SPEC,
                narration_storage=self.storage, visual_storage=object(), **self.config)

    def test_return_capacity_precedes_post_callback_hash(self):
        from creator_studio.render_preparation import engine
        original = engine.exact_signature
        state = {"called": False, "bounded": False}
        def callback():
            state["called"] = True
            return True
        def check(result):
            self.assertIs(result, True)
            state["bounded"] = True
        def signature(value):
            if state["called"]:
                self.assertTrue(state["bounded"])
            return original(value)
        fence = ObservationFence(self.m, PROFILE, SPEC, self.config)
        with patch.object(engine, "exact_signature", side_effect=signature):
            self.assertTrue(fence.call(lambda: callback, result_check=check))

    def test_unbound_active_narration_not_reported_usable(self):
        from creator_studio.render_timeline.models import RenderTimelineEligibility
        from creator_studio.voice_timing.models import TimingEligibility
        m = self.build()
        m.voice_timing.active_alignment_run_id = None
        with patch("creator_studio.render_timeline.engine.current_render_timeline_eligibility",
                return_value=RenderTimelineEligibility(True, False, False, True, True)), \
                patch("creator_studio.voice_timing.engine.current_timing_eligibility",
                return_value=TimingEligibility(True, True, False, True, True, True, False, False)), \
                patch("creator_studio.render_timeline.engine.observe_media_usability", return_value=False):
            result = assess_render_preparation(m, output_profile=PROFILE, spec=SPEC,
                narration_storage=self.storage, visual_storage=object(), **self.config)
        self.assertFalse(result.current_narration_usable)

    def test_stage_preflight_before_dependency_iterator_callback(self):
        pulls = []
        def dependencies():
            pulls.append("render_timeline")
            yield "render_timeline"
        with self.assertRaises(ValueError):
            RenderPreparationStage(output_profile=OutputProfile(1 << 100, 1, 24, 1),
                spec=SPEC, dependencies=dependencies(), **self.config)
        self.assertEqual(pulls, [])

    def test_configuration_member_count_before_hash(self):
        from creator_studio.render_preparation.engine import configuration_snapshot
        with patch("creator_studio.render_preparation.engine.exact_signature", side_effect=AssertionError("hash")):
            with self.assertRaises(ValueError):
                configuration_snapshot(PROFILE, SPEC, {"unknown" + str(i): None for i in range(10)})


# Distinct generated cases retain separate unittest counts and failure names.
def profile_case(field_name, value, valid):
    def test(self):
        profile = replace(PROFILE, **{field_name: value})
        if valid:
            validate_profile(profile)
        else:
            with self.assertRaises(ValueError):
                validate_profile(profile)
    return test

for field_name in ("width_px", "height_px"):
    for label, value, valid in (("bool", True, False), ("float", 640.0, False), ("zero", 0, False),
            ("negative", -1, False), ("min", 1, True), ("max", 16384, True), ("overflow", 16385, False)):
        setattr(RenderPreparationTests, "test_profile_" + field_name + "_" + label,
            profile_case(field_name, value, valid))
for field_name in ("frame_rate_num", "frame_rate_den"):
    for label, value in (("bool", True), ("float", 24.0), ("zero", 0), ("negative", -1), ("overflow", 1000001)):
        setattr(RenderPreparationTests, "test_profile_" + field_name + "_" + label,
            profile_case(field_name, value, False))

def rational_case(num, den, valid):
    def test(self):
        profile = OutputProfile(1, 1, num, den)
        if valid:
            validate_profile(profile)
        else:
            with self.assertRaises(ValueError):
                validate_profile(profile)
    return test
for label, num, den, valid in (("one", 1, 1, True), ("240", 240, 1, True), ("below_one", 1, 2, False),
        ("above_240", 241, 1, False), ("unreduced", 48, 2, False), ("num_max", 1000000, 999999, True),
        ("den_max", 999999, 1000000, False)):
    setattr(RenderPreparationTests, "test_fps_" + label, rational_case(num, den, valid))

def pixel_case(width, height, valid):
    def test(self):
        if valid:
            validate_profile(OutputProfile(width, height, 24, 1))
        else:
            with self.assertRaises(ValueError):
                validate_profile(OutputProfile(width, height, 24, 1))
    return test
for label, w, h, valid in (("exact", 8192, 8192, True), ("overflow", 8192, 8193, False)):
    setattr(RenderPreparationTests, "test_pixel_budget_" + label, pixel_case(w, h, valid))

def malformed_case(value):
    def test(self):
        raw = to_data(ProjectManifest("malformed"))
        raw["render_preparation"] = value
        with self.assertRaises(ValueError):
            decode(ProjectManifest, migrate_document(raw))
    return test
for label, value in (("null", None), ("list", []), ("empty", {}), ("partial", {"plans": []}),
        ("unknown", {"plans": [], "active_render_preparation_plan_id": None, "unknown": 1})):
    setattr(RenderPreparationTests, "test_malformed_state_" + label, malformed_case(value))

def policy_case(name):
    def test(self):
        with self.assertRaises(ValueError):
            validate_spec(replace(SPEC, **{name: "UNKNOWN"}))
    return test
for name in ("pixel_policy", "duration_policy", "coverage_policy", "geometry_policy", "narration_policy",
        "visual_audio_policy", "subtitle_policy"):
    setattr(RenderPreparationTests, "test_unknown_policy_" + name, policy_case(name))

def tamper_case(group, name):
    def test(self):
        m = self.build()
        plan = active_plan(m)
        record = getattr(plan, group) if group else plan
        value = getattr(record, name)
        if type(value) is int:
            changed = value + 1
        elif name == "spec":
            changed = replace(value, engine_version="2")
        elif name == "inspection":
            changed = replace(value, frame_count=value.frame_count + 1)
        elif name == "acceptance_receipt":
            changed = replace(value, acceptance_policy_version="2")
        else:
            changed = "b" * 64
        altered = replace(record, **{name: changed})
        altered_plan = replace(plan, **{group: altered}) if group else altered
        with self.assertRaises((ValueError, StopIteration)):
            validate_plan(m, altered_plan)
    return test
for group, names in (("timeline_binding", ("render_timeline_plan_id", "input_binding_signature",
        "source_usage_signature", "output_signature", "timing_evidence_signature", "media_binding_signature", "spec")),
        ("narration_binding", ("placement_timing_plan_id", "placement_output_signature", "alignment_run_id",
        "alignment_output_signature", "alignment_input_signature", "alignment_request_signature", "acceptance_receipt",
        "narration_revision_id", "narration_asset_id", "narration_sha256", "narration_byte_count", "inspection",
        "narration_duration_us")), ("", ("render_preparation_plan_id", "input_binding_signature",
        "output_profile_signature", "render_policy_signature", "preparation_signature", "output_signature",
        "output_duration_us"))):
    for name in names:
        setattr(RenderPreparationTests, "test_tamper_" + group + "_" + name, tamper_case(group, name))

def dependency_case(value):
    def test(self):
        with self.assertRaises(ValueError):
            normalize_dependencies(value)
    return test
for label, value in (("str", "render_timeline"), ("bytes", b"render_timeline"), ("dict", {}),
        ("other", ("placement_timing",)), ("extra", ("render_timeline", "other")),
        ("reversed", ("other", "render_timeline"))):
    setattr(RenderPreparationTests, "test_dependency_reject_" + label, dependency_case(value))

def raw_capacity_case(cls, name, limit):
    def test(self):
        raw = {name: [None] * limit}
        preflight_record(raw, cls, raw=True)
        raw[name].append(None)
        with self.assertRaises(ValueError):
            preflight_record(raw, cls, raw=True)
    return test
for cls, name, limit in ((RenderPreparationState, "plans", MAX_PLANS),
        (RenderPreparationPlan, "entries", MAX_ENTRIES_PER_PLAN),
        (RenderPreparationEntryAssessment, "requirements", MAX_REQUIREMENTS_PER_ENTRY),
        (RenderPreparationPlan, "requirements", MAX_PLAN_REQUIREMENTS),
        (RenderPreparationPlan, "uncovered_intervals", MAX_UNCOVERED_INTERVALS)):
    setattr(RenderPreparationTests, "test_capacity_" + cls.__name__ + "_" + name,
        raw_capacity_case(cls, name, limit))

def coverage_case(covered, expected):
    def test(self):
        self.assertEqual(derive_uncovered_intervals(covered, 10),
            [UncoveredInterval(start, end) for start, end in expected])
    return test
for label, covered, expected in (("leading", [(2, 10)], [(0, 2)]),
        ("interior", [(0, 3), (7, 10)], [(3, 7)]), ("trailing", [(0, 7)], [(7, 10)]),
        ("empty", [], [(0, 10)])):
    setattr(RenderPreparationTests, "test_coverage_" + label, coverage_case(covered, expected))

def entry_alignment_case(name):
    def test(self):
        timeline = self.m.render_timeline.plans[0]
        entry = replace(timeline.entries[0], **{name: getattr(timeline.entries[0], name) + 1})
        entries, _ = derive_preparation(self.m, replace(timeline, entries=[entry]), PROFILE)
        self.assertIn(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED, entries[0].requirements)
        self.assertEqual(getattr(entries[0], name), getattr(entry, name))
    return test
for name in ("timeline_start_us", "timeline_end_us"):
    setattr(RenderPreparationTests, "test_nonexact_" + name, entry_alignment_case(name))

def unsupported_case(kind):
    def test(self):
        from creator_studio.manifest.retrieval import VisualMediaKind
        timeline = self.m.render_timeline.plans[0]
        entry = replace(timeline.entries[0], media_kind=VisualMediaKind(kind),
            source_usage=SourceUsage.UNRESOLVED, outcome=RenderTimelineOutcome.UNSUPPORTED_MEDIA_TYPE)
        entries, covered = derive_preparation(self.m, replace(timeline, entries=[entry]), PROFILE)
        self.assertEqual(entries[0].source_usage, SourceUsage.UNRESOLVED)
        self.assertEqual(covered, [])
        self.assertIn(PreparationRequirement.SUPPORTED_SOURCE_USE_NOT_ESTABLISHED, entries[0].requirements)
    return test
for kind in ("GRAPHIC", "UNKNOWN"):
    setattr(RenderPreparationTests, "test_unsupported_" + kind, unsupported_case(kind))

def stale_pointer_case(state, name):
    def test(self):
        m = self.build()
        setattr(getattr(m, state), name, None)
        self.assertFalse(current_logically_eligible(m, output_profile=PROFILE, spec=SPEC, **self.config))
        validate_history(m)
    return test
for state, name in (("placement_timing", "active_placement_timing_plan_id"),
        ("voice_timing", "active_alignment_run_id"), ("voice_timing", "active_narration_revision_id"),
        ("editing", "active_creator_edit_plan_id"), ("acquisition", "active_creator_acquisition_id"),
        ("selection", "active_creator_selection_id"), ("retrieval", "active_creator_retrieval_id"),
        ("visual_planning", "active_creator_plan_id"), ("semantic", "active_creator_document_id")):
    setattr(RenderPreparationTests, "test_current_pointer_" + name, stale_pointer_case(state, name))

if __name__ == "__main__":
    unittest.main()
