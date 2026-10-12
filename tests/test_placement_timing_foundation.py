"""Offline M71 authority, historical, runtime, mutation and isolation tests."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, validate, require_valid
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.placement_timing import *
from creator_studio.manifest.placement_timing_validation import (
    preflight_history, validate_plan, derive_entries, lexical_envelope)
from creator_studio.manifest.editing_validation import reconstruct
from creator_studio.manifest.editing import TimingState
from creator_studio.manifest.voice_timing import MappingStatus, SourceOmission
from creator_studio.manifest.models import ProcessingState, Status
from creator_studio.manifest.signatures import dependency_signature, signature
from creator_studio.placement_timing import *
from creator_studio.placement_timing.engine import active_plan, boundary_unchanged, bounded_payload
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
from creator_studio.acquisition.engine import build_acquisition
from creator_studio.acquisition.storage import ManagedStorage
from creator_studio.voice_timing import (register_narration, build_voice_timing,
    source_binding, Observation, inspect_stream, LocalNarrationByteStore)
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.visual.engine import build_visual_plan
from tests.test_semantic_story import content
from tests.test_media_retrieval import with_intent
from tests.test_media_selection import selected_fixture
from tests.test_voice_timing_foundation import wav, FakeGate as VoiceGate, CountingControl

POLICY = dict(acceptance_policy_id="editorial_policy", acceptance_policy_version="1",
    voice_acceptance_policy_id="test_policy", voice_acceptance_policy_version="1")

class Gate:
    def __init__(self, callback=None):
        self.calls = 0
        self.requests = []
        self.callback = callback

    def accept(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.callback:
            self.callback(request)
        return make_receipt(request)

class PlacementTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        text = "First paragraph.\n\nSecond paragraph."
        m = selected_fixture(with_intent(build_visual_plan(build_semantic_story(content(text)))))
        m = build_acquisition(m, storage=ManagedStorage(Path(cls.temp.name) / "media"))
        acquisition = m.acquisition.runs[0]
        edit = reconstruct(m, acquisition, __import__("creator_studio.manifest.editing", fromlist=["EditSpec"]).EditSpec())
        m.editing.plans.append(edit)
        m.editing.active_creator_edit_plan_id = edit.edit_plan_id
        audio = wav(payload=b"\x00" * 64000)
        path = Path(cls.temp.name) / "narration.wav"
        path.write_bytes(audio)
        asset, _ = inspect_stream(io.BytesIO(audio))
        cls.storage = LocalNarrationByteStore({asset.asset_id: path})
        m = register_narration(m, asset, storage=cls.storage, logical_revision=1)
        document = m.semantic.documents[0]
        observations = []
        for ordinal, story in enumerate(document.story_units):
            span = story.source_excerpts[0].source_span
            binding = source_binding(m, span.start, span.end, story.story_unit_id)
            observations.append(Observation(ordinal, 100000 + ordinal * 800000,
                600000 + ordinal * 800000, text[span.start:span.end], MappingStatus.EXACT, (binding,)))
        cls.base = build_voice_timing(m, storage=cls.storage, observations=observations,
            gate=VoiceGate(), acceptance_policy_id="test_policy", acceptance_policy_version="1")

    def setUp(self):
        self.m = deepcopy(self.base)
        self.gate = Gate()
        self.edit = self.m.editing.plans[0]
        self.run = self.m.voice_timing.runs[0]
        self.pids = [p.placement_id for p in self.edit.placements]

    def allocations(self):
        result = []
        for pid, unit in zip(self.pids, self.run.units):
            b = unit.source_bindings[0]
            a = PlacementAllocationDeclaration(pid, b.source_revision_id,
                b.semantic_document_id, b.story_unit_id, b.start_char, b.end_char, b.excerpt_signature)
            result.append(replace(a, declaration_ref=declaration_ref(a)))
        return result

    def boundaries(self, intervals=None):
        intervals = intervals or [(0, 700000), (800000, 2000000)]
        result = []
        for pid, interval in zip(self.pids, intervals):
            for side, time in zip(BoundarySide, interval):
                b = PlacementBoundaryDeclaration(pid, side, time)
                result.append(replace(b, declaration_ref=declaration_ref(b)))
        return result

    def build(self, manifest=None, **kwargs):
        args = dict(storage=self.storage, gate=self.gate, **POLICY)
        args.update(kwargs)
        return build_placement_timing(self.m if manifest is None else manifest, **args)

    def stage(self, **kwargs):
        args = dict(storage=self.storage, gate=self.gate, **POLICY)
        args.update(kwargs)
        return PlacementTimingStage(**args)

    def eligibility(self, m, **kwargs):
        args = dict(storage=self.storage, **POLICY)
        args.update(kwargs)
        return current_placement_timing_eligibility(m, **args)

    def accepted(self):
        return self.build(allocations=self.allocations())

    def executed(self, **kwargs):
        stage = self.stage(**kwargs)
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m, execution = outcome.update.manifest, outcome.result
        execution.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, {})
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=execution.dependency_signature, execution=execution))
        return stage, m, execution

    def test_empty_additive_schema_two(self):
        m = ProjectManifest("empty")
        self.assertEqual(m.schema_version, 2)
        self.assertEqual(m.placement_timing, PlacementTimingState())
        self.assertFalse(validate(m))

    def test_absent_migration_creates_no_authority(self):
        data = to_data(self.m)
        del data["placement_timing"]
        loaded = decode(ProjectManifest, migrate_document(data))
        self.assertEqual(loaded.placement_timing, PlacementTimingState())

    def test_present_malformed_states(self):
        for state in (None, [], {}, {"plans": []}, {"plans": [],
                "active_placement_timing_plan_id": None, "extra": 1}):
            data = to_data(self.m)
            data["placement_timing"] = state
            with self.subTest(state=state), self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(data))

    def test_gate_free_observation_has_no_authority(self):
        m = self.build(gate=None)
        p = active_plan(m)
        self.assertIsNone(p.request_signature)
        self.assertIsNone(p.receipt)
        self.assertTrue(all(e.outcome == PlacementTimingOutcome.UNRESOLVED for e in p.entries))
        self.assertTrue(self.eligibility(m).eligible)
        self.assertFalse(self.eligibility(m).complete_placement_timing)
        self.assertEqual(self.gate.calls, 0)

    def test_no_automatic_singleton_or_story_assignment(self):
        p = active_plan(self.build())
        self.assertEqual([e.placement_id for e in p.entries], self.pids)
        self.assertTrue(all(e.start_us is None and e.end_us is None and not e.boundaries for e in p.entries))

    def test_accepted_allocation_exact_endpoints(self):
        m = self.accepted()
        p = active_plan(m)
        self.assertFalse(validate(m))
        self.assertEqual([(e.start_us, e.end_us) for e in p.entries],
            [(u.start_us, u.end_us) for u in self.run.units])
        self.assertEqual(self.gate.calls, 1)
        self.assertTrue(self.eligibility(m).complete_placement_timing)

    def test_nonmaterialized_placement_timed(self):
        self.assertTrue(all(p.materialization_id is None for p in self.edit.placements))
        with patch("creator_studio.acquisition.engine.current_usability", side_effect=AssertionError("forbidden")), \
                patch("creator_studio.editing.engine.current_edit_eligibility", side_effect=AssertionError("forbidden")):
            self.assertTrue(self.eligibility(self.accepted()).complete_placement_timing)

    def test_declarations_require_gate(self):
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=self.allocations(), gate=None)
        with self.assertRaises(PlacementTimingError):
            self.build(explicit_boundaries=self.boundaries(), gate=None)

    def test_explicit_inside_unit_and_leading_trailing_regions(self):
        m = self.build(explicit_boundaries=self.boundaries([(0, 350000), (1200000, 2000000)]))
        self.assertTrue(self.eligibility(m).complete_placement_timing)
        for e in active_plan(m).entries:
            self.assertTrue(all(b.kind == BoundaryKind.ACCEPTED_EXPLICIT_TIME for b in e.boundaries))

    def test_partial_unit_edge_requires_explicit(self):
        a = self.allocations()[0]
        text = self.m.semantic.source_revisions[0].content.normalized_text
        a = replace(a, end_char=a.end_char - 1, excerpt_signature=exact_signature(text[a.start_char:a.end_char - 1]))
        a = replace(a, declaration_ref=declaration_ref(a))
        unresolved = active_plan(self.build(allocations=[a]))
        self.assertIsNone(unresolved.entries[0].start_us)
        b = self.boundaries([(0, 350000)])[1]
        mixed = active_plan(self.build(allocations=[a], explicit_boundaries=[b]))
        self.assertEqual(mixed.entries[0].outcome, PlacementTimingOutcome.TIMED)
        self.assertEqual([e.kind for e in mixed.entries[0].boundaries],
            [BoundaryKind.M70_UNIT_START, BoundaryKind.ACCEPTED_EXPLICIT_TIME])

    def test_competing_same_side_authority_rejected(self):
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=self.allocations(), explicit_boundaries=self.boundaries())
        self.assertEqual(self.gate.calls, 0)

    def test_receipt_can_coexist_with_unresolved(self):
        m = self.build(allocations=self.allocations()[:1])
        self.assertIsNotNone(active_plan(m).receipt)
        self.assertFalse(self.eligibility(m).complete_placement_timing)

    def test_interval_integer_and_range_validation(self):
        for interval in ((0.0, 5), (False, 5), (-1, 5), (5, 5), (6, 5), (0, 2000001)):
            boundaries = self.boundaries([(0, 5)])
            boundaries = [replace(b, time_us=t) for b, t in zip(boundaries, interval)]
            with self.subTest(interval=interval), self.assertRaises(PlacementTimingError):
                self.build(explicit_boundaries=boundaries)
        self.assertEqual(self.gate.calls, 0)

    def test_touching_and_gapped_intervals(self):
        for intervals in ([(0, 700000), (700000, 2000000)], [(5, 500000), (900000, 1999999)]):
            with self.subTest(intervals=intervals):
                self.assertTrue(self.eligibility(self.build(explicit_boundaries=self.boundaries(intervals))).complete_placement_timing)

    def test_overlap_and_order_are_unresolved(self):
        for intervals in ([(0, 1000000), (900000, 2000000)], [(900000, 1000000), (0, 800000)]):
            p = active_plan(self.build(explicit_boundaries=self.boundaries(intervals)))
            self.assertEqual(p.entries[1].outcome, PlacementTimingOutcome.ORDER_CONFLICT)
            self.assertIsNone(p.entries[1].start_us)

    def test_all_identity_layers_deterministic(self):
        a = active_plan(self.accepted())
        b = active_plan(self.accepted())
        for name in ("declaration_signature", "input_signature", "output_signature", "request_signature",
                "placement_timing_plan_id", "receipt"):
            self.assertEqual(getattr(a, name), getattr(b, name))
        self.assertEqual(a.receipt.receipt_id, receipt_id(a.receipt))
        self.assertEqual(a.placement_timing_plan_id, plan_id(a))

    def test_request_deeply_immutable_and_complete(self):
        p = active_plan(self.accepted())
        r = self.gate.requests[0]
        with self.assertRaises(FrozenInstanceError):
            r.edit_plan_id = "changed"
        self.assertIs(type(r.placement_ids), tuple)
        data = json.loads(r.proposal_json)
        self.assertEqual(data["allocations"], to_data(p.allocations))
        self.assertEqual(data["entries"], to_data(p.entries))
        self.assertEqual(data["lineage"], to_data(p.lineage))
        self.assertNotIn("receipt", data)
        self.assertNotIn("placement_timing_plan_id", data)

    def test_security_no_path_or_runtime_representation(self):
        serialized = json.dumps(to_data(active_plan(self.accepted())))
        for forbidden in (self.temp.name, "narration.wav", "object at", "0x", "http://", "https://", "api_key"):
            self.assertNotIn(forbidden, serialized)

    def test_stable_placement_foreign_keys(self):
        p = active_plan(self.accepted())
        self.assertEqual(p.placement_ids, self.pids)
        self.assertEqual([e.placement_id for e in p.entries], self.pids)

    def test_history_tampering(self):
        m = self.accepted()
        p = active_plan(m)
        variants = [replace(p, receipt=replace(p.receipt, receipt_id="bad")),
            replace(p, allocations=[replace(p.allocations[0], end_char=1)] + p.allocations[1:]),
            replace(p, entries=[replace(p.entries[0], start_us=0)] + p.entries[1:]),
            replace(p, acceptance_policy_id="other"), replace(p, placement_ids=list(reversed(p.placement_ids))),
            replace(p, request_signature=None), replace(p, receipt=None),
            replace(p, edit_plan_id="missing"), replace(p, alignment_run_id="missing")]
        for variant in variants:
            bad = deepcopy(m)
            bad.placement_timing.plans[0] = variant
            with self.subTest(variant=variant.placement_timing_plan_id):
                self.assertTrue(validate(bad))

    def test_active_pointer_staleness_preserves_history(self):
        m = self.accepted()
        for domain, field in (("editing", "active_creator_edit_plan_id"),
                ("voice_timing", "active_narration_revision_id"),
                ("voice_timing", "active_alignment_run_id"),
                ("placement_timing", "active_placement_timing_plan_id")):
            bad = deepcopy(m)
            setattr(getattr(bad, domain), field, None)
            if field == "active_narration_revision_id":
                bad.voice_timing.active_alignment_run_id = None
            self.assertFalse(validate(bad))
            self.assertFalse(self.eligibility(bad).eligible)
            self.assertFalse(self.eligibility(bad).complete_placement_timing)

    def test_missing_active_upstream_rejected_before_gate(self):
        for domain, field in (("editing", "active_creator_edit_plan_id"),
                ("voice_timing", "active_narration_revision_id"),
                ("voice_timing", "active_alignment_run_id")):
            bad = deepcopy(self.m)
            setattr(getattr(bad, domain), field, None)
            with self.assertRaises(PlacementTimingError):
                self.build(bad, allocations=self.allocations())
        self.assertEqual(self.gate.calls, 0)

    def test_cross_domain_retained_binding_rejected(self):
        p = active_plan(self.accepted())
        for field in ("source_revision_id", "source_record_fingerprint", "semantic_document_id",
                "semantic_generated_binding", "semantic_output_binding", "content_revision_signature", "analysis_signature"):
            bad = deepcopy(self.m)
            changed = replace(p, lineage=replace(p.lineage, **{field: "a" * 64}))
            with self.subTest(field=field), self.assertRaises((ValueError, StopIteration)):
                validate_plan(bad, changed)

    def test_builder_domain_atomicity(self):
        before = deepcopy(self.m)
        result = self.accepted()
        self.assertEqual(self.m, before)
        self.assertTrue(boundary_unchanged(before, result))
        for f in fields(ProjectManifest):
            if f.name != "placement_timing":
                self.assertEqual(getattr(before, f.name), getattr(result, f.name))
        self.assertEqual(result.editing.plans[0].timing_state, TimingState.UNRESOLVED)

    def test_failure_and_cancellation_no_partial_update(self):
        for stop in (1, 2, 5, 10, 20, 50, 100):
            before = deepcopy(self.m)
            with self.subTest(stop=stop), self.assertRaises(Cancelled):
                self.build(allocations=self.allocations(), control=CountingControl(stop))
            self.assertEqual(before, self.m)
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=self.allocations(), gate=object())
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_precallback_manifest_and_declaration_fences(self):
        allocations = self.allocations()
        for mutate in (lambda: setattr(self.m.editing, "active_creator_edit_plan_id", None),
                lambda: setattr(self.m.voice_timing, "active_alignment_run_id", None),
                lambda: allocations.clear()):
            self.m = deepcopy(self.base)
            allocations = self.allocations()
            def recheck():
                mutate()
            with self.assertRaises(PlacementTimingError):
                self.build(allocations=allocations, authorization_recheck=recheck)
            self.assertEqual(self.gate.calls, 0)

    def test_postcallback_mutation_fails(self):
        self.gate.callback = lambda request: setattr(self.m.voice_timing, "active_alignment_run_id", None)
        with self.assertRaises(PlacementTimingError):
            self.accepted()
        self.assertEqual(self.gate.calls, 1)
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_stage_gate_replacement_fails_before_callback(self):
        stage = self.stage(allocations=self.allocations())
        original = stage._execution_binding
        calls = [0]
        def binding(m):
            calls[0] += 1
            if calls[0] == 2:
                stage.gate = Gate()
            return original(m)
        with patch.object(stage, "_execution_binding", side_effect=binding):
            outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertEqual(self.gate.calls, 0)

    def test_active_only_reuse_no_gate_call(self):
        stage, m, execution = self.executed(allocations=self.allocations())
        self.assertEqual(self.gate.calls, 1)
        self.assertTrue(stage.validate_reuse(m, execution))
        reused = self.build(m, allocations=self.allocations())
        self.assertEqual(reused, m)
        self.assertEqual(self.gate.calls, 1)
        bad = deepcopy(m)
        bad.placement_timing.active_placement_timing_plan_id = None
        self.assertFalse(stage.validate_reuse(bad, execution))
        with self.assertRaises(PlacementTimingError):
            self.build(bad, allocations=self.allocations())

    def test_incomplete_gate_free_reuse_stays_incomplete(self):
        stage, m, execution = self.executed(gate=None)
        self.assertTrue(stage.validate_reuse(m, execution))
        reused = self.build(m, gate=None)
        self.assertEqual(reused, m)
        self.assertIsNone(active_plan(reused).receipt)
        self.assertFalse(self.eligibility(reused).complete_placement_timing)

    def test_artifact_exactness_and_tampering(self):
        stage, m, execution = self.executed(allocations=self.allocations())
        p = active_plan(m)
        self.assertEqual([a.reference for a in execution.artifacts],
            ["placement_timing/" + p.placement_timing_plan_id, "placement_timing_edit/" + p.edit_plan_id])
        for artifacts in (list(reversed(execution.artifacts)), execution.artifacts[:1],
                execution.artifacts + execution.artifacts[:1]):
            bad = deepcopy(execution)
            bad.artifacts = artifacts
            self.assertFalse(stage.validate_reuse(m, bad))

    def test_dependency_exact_tuple_and_normalization(self):
        for dependencies in ((), ("edit_planning", "voice_timing")):
            self.assertEqual(self.stage(dependencies=dependencies).dependencies, dependencies)
        for dependencies in (("edit_planning",), ("voice_timing",), ("voice_timing", "edit_planning"),
                ("edit_planning", "edit_planning"), ("unknown",), ("edit_planning", "voice_timing", "unknown")):
            with self.subTest(dependencies=dependencies), self.assertRaises(PlacementTimingError):
                self.stage(dependencies=dependencies)
        class OneShot:
            def __init__(self):
                self.calls = 0
            def __iter__(self):
                self.calls += 1
                if self.calls != 1:
                    raise AssertionError("second consumption")
                return iter(("edit_planning", "voice_timing"))
        source = OneShot()
        stage = self.stage(dependencies=source)
        self.assertEqual(source.calls, 1)
        self.assertEqual(stage.dependencies, ("edit_planning", "voice_timing"))
        self.assertEqual(self.stage(dependencies=(d for d in ())).dependencies, ())
        self.assertEqual(self.stage(dependencies=iter(())).dependencies, ())

    def test_public_preflight_before_recursive_typing(self):
        m = self.accepted()
        m.placement_timing.plans *= MAX_PLANS + 1
        with patch("creator_studio.manifest.validation.check_typed", side_effect=AssertionError("too late")):
            self.assertEqual(validate(m)[0].path, "placement_timing")
            with self.assertRaises(ValueError):
                require_valid(m)

    def test_capacity_equality_and_overflow(self):
        p = active_plan(self.accepted())
        preflight_history(PlacementTimingState([p] * MAX_PLANS))
        for state in (PlacementTimingState([p] * (MAX_PLANS + 1)),
                PlacementTimingState([replace(p, entries=p.entries * (MAX_ENTRIES_PER_PLAN // len(p.entries) + 1))]),
                PlacementTimingState([replace(p, allocations=p.allocations[:1] * (MAX_ALLOCATIONS_PER_ENTRY + 1))]),
                PlacementTimingState([replace(p, explicit_boundaries=self.boundaries()[:1] * 3)])):
            with self.assertRaises(ValueError):
                preflight_history(state)

    def test_malformed_shallow_preflight_defers_types(self):
        for state in (None, {}, [], "bad", PlacementTimingState(plans=[None, object()]),
                PlacementTimingState(plans=None)):
            preflight_history(state)
        m = deepcopy(self.m)
        m.placement_timing = None
        self.assertTrue(validate(m))

    def test_request_bound_before_callback(self):
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", 1):
            with self.assertRaises(PlacementTimingError):
                self.accepted()
        self.assertEqual(self.gate.calls, 0)

    def test_reuse_preflight_before_full_serialization(self):
        stage, m, execution = self.executed()
        m.placement_timing.plans *= MAX_PLANS + 1
        with patch("creator_studio.placement_timing.stage.exact_signature", side_effect=AssertionError("too late")):
            self.assertFalse(stage.validate_reuse(m, execution))

    def test_historical_validation_no_storage_gate_or_current_review(self):
        m = self.accepted()
        with patch("creator_studio.voice_timing.engine.verify_audio", side_effect=AssertionError("bytes")), \
                patch.object(self.gate, "accept", side_effect=AssertionError("gate")), \
                patch("creator_studio.placement_timing.engine.logical_inputs", side_effect=AssertionError("current")):
            self.assertFalse(validate(m))

    def test_lexical_blockers_and_explicit_editorial_override(self):
        allocations = self.allocations()[:1]
        unit = self.run.units[0]
        text = self.m.semantic.source_revisions[0].content.normalized_text
        for status, expected in ((MappingStatus.MISMATCH, TimingDiagnostic.MISMATCH),
                (MappingStatus.UNMAPPED, TimingDiagnostic.UNMAPPED),
                (MappingStatus.SPEECH_ADDED, TimingDiagnostic.SPEECH_ADDED)):
            run = replace(self.run, units=[replace(unit, mapping_status=status)])
            edges, _, diagnostics, _ = lexical_envelope(allocations, run, text)
            self.assertFalse(edges)
            self.assertIn(expected, diagnostics)
            plan = replace(active_plan(self.build()), explicit_boundaries=self.boundaries()[:2])
            entries, _ = derive_entries(plan, run, text)
            self.assertEqual(entries[0].outcome, PlacementTimingOutcome.TIMED)
        omitted = replace(self.run, omissions=[SourceOmission(0, unit.source_bindings[0])])
        self.assertIn(TimingDiagnostic.SOURCE_OMITTED, lexical_envelope(allocations, omitted, text)[2])

    def test_positive_timestamp_gap_is_retained_not_silence(self):
        a = self.allocations()[0]
        b = self.run.units[0].source_bindings[0]
        split = b.start_char + 5
        left = replace(b, end_char=split)
        right = replace(b, start_char=split)
        u = self.run.units[0]
        run = replace(self.run, units=[replace(u, unit_id="left", end_us=200000, source_bindings=[left]),
            replace(u, unit_id="right", start_us=400000, source_bindings=[right])])
        text = self.m.semantic.source_revisions[0].content.normalized_text
        edges, _, diagnostics, _ = lexical_envelope([a], run, text)
        self.assertFalse(diagnostics)
        self.assertEqual(edges[BoundarySide.START][0], u.start_us)
        self.assertEqual(edges[BoundarySide.END][0], u.end_us)

    def test_no_prohibited_imports_or_render_fields(self):
        banned = {"PyQt6", "pipeline", "stock", "subprocess", "requests", "httpx",
            "whisper", "ffmpeg", "renderer"}
        paths = list(Path("creator_studio/placement_timing").glob("*.py")) + [
            Path("creator_studio/manifest/placement_timing.py"),
            Path("creator_studio/manifest/placement_timing_validation.py")]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    self.assertFalse(set(name.split(".")) & banned, (path, name))
        names = {f.name for cls in (PlacementTimingPlan, PlacementTimingEntry, PlacementTimingSpec) for f in fields(cls)}
        self.assertFalse(names & {"fps", "frame", "render_offset", "media_duration", "timeline"})

    def test_unresolved_between_timed_and_shared_story_remain_unassigned(self):
        plan = active_plan(self.build())
        plan = replace(plan, placement_ids=[self.pids[0], "middle", self.pids[1]],
            explicit_boundaries=self.boundaries())
        text = self.m.semantic.source_revisions[0].content.normalized_text
        entries, _ = derive_entries(plan, self.run, text)
        self.assertEqual([e.outcome for e in entries], [PlacementTimingOutcome.TIMED,
            PlacementTimingOutcome.UNRESOLVED, PlacementTimingOutcome.TIMED])
        plan = replace(plan, explicit_boundaries=[])
        entries, _ = derive_entries(plan, self.run, text)
        self.assertTrue(all(e.start_us is None for e in entries))

    def test_partial_coverage_and_unrelated_units_block_derivation(self):
        allocation = self.allocations()[0]
        unit = self.run.units[0]
        text = self.m.semantic.source_revisions[0].content.normalized_text
        binding = replace(unit.source_bindings[0], end_char=allocation.end_char - 3)
        run = replace(self.run, units=[replace(unit, source_bindings=[binding])])
        edges, outcome, diagnostics, _ = lexical_envelope([allocation], run, text)
        self.assertFalse(edges)
        self.assertEqual(outcome, PlacementTimingOutcome.PARTIAL_COVERAGE)
        self.assertIn(TimingDiagnostic.PARTIAL_COVERAGE, diagnostics)
        run = replace(self.run, units=[replace(unit, source_bindings=unit.source_bindings + self.run.units[1].source_bindings)])
        self.assertIn(TimingDiagnostic.UNRELATED_UNIT, lexical_envelope([allocation], run, text)[2])

    def test_added_speech_inside_envelope_never_associated(self):
        allocation = self.allocations()[0]
        unit = self.run.units[0]
        binding = unit.source_bindings[0]
        split = binding.start_char + 5
        units = [replace(unit, unit_id="left", end_us=200000,
            source_bindings=[replace(binding, end_char=split)]),
            replace(unit, unit_id="added", start_us=250000, end_us=300000,
                mapping_status=MappingStatus.SPEECH_ADDED, source_bindings=[]),
            replace(unit, unit_id="right", start_us=400000,
                source_bindings=[replace(binding, start_char=split)])]
        text = self.m.semantic.source_revisions[0].content.normalized_text
        for status, reason in ((MappingStatus.SPEECH_ADDED, TimingDiagnostic.SPEECH_ADDED),
                (MappingStatus.MISMATCH, TimingDiagnostic.MISMATCH),
                (MappingStatus.UNMAPPED, TimingDiagnostic.UNMAPPED)):
            run = replace(self.run, units=[units[0], replace(units[1], mapping_status=status), units[2]])
            edges, _, diagnostics, used = lexical_envelope([allocation], run, text)
            self.assertFalse(edges)
            self.assertIn(reason, diagnostics)
            self.assertFalse(used)

    def test_source_omission_intersection_not_text_equality(self):
        allocations = self.allocations()
        wrong = replace(allocations[0], source_revision_id="other")
        wrong = replace(wrong, declaration_ref=declaration_ref(wrong))
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=[wrong])
        wrong = replace(allocations[0], semantic_document_id="other")
        wrong = replace(wrong, declaration_ref=declaration_ref(wrong))
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=[wrong])
        self.assertEqual(self.gate.calls, 0)

    def test_historical_review_change_preserved_current_stales(self):
        from creator_studio.manifest.semantic import ReviewStatus, output_signature as semantic_output
        m = self.accepted()
        doc = m.semantic.documents[0]
        doc = replace(doc, review_status=ReviewStatus.REJECTED)
        doc = replace(doc, output_signature=semantic_output(doc))
        m.semantic.documents[0] = doc
        self.assertFalse(validate(m))
        self.assertFalse(self.eligibility(m).eligible)

    def test_narration_new_revision_stales_without_rewriting_history(self):
        from creator_studio.manifest.voice_timing import revision_id
        m = self.accepted()
        original = deepcopy(m.placement_timing)
        revision = replace(m.voice_timing.revisions[0], revision_id="", logical_revision=2)
        revision = replace(revision, revision_id=revision_id(revision))
        m.voice_timing.revisions.append(revision)
        m.voice_timing.active_narration_revision_id = revision.revision_id
        m.voice_timing.active_alignment_run_id = None
        self.assertFalse(validate(m))
        self.assertFalse(self.eligibility(m).eligible)
        self.assertEqual(m.placement_timing, original)

    def test_duplicate_and_wrong_placement_declarations_rejected(self):
        a = self.allocations()[0]
        for allocations in ([a, a], [replace(a, placement_id="missing")]):
            with self.assertRaises(PlacementTimingError):
                self.build(allocations=allocations)
        b = self.boundaries()[0]
        with self.assertRaises(PlacementTimingError):
            self.build(explicit_boundaries=[b, b])
        self.assertEqual(self.gate.calls, 0)

    def test_receipt_policy_and_layer_tampering_no_success(self):
        for field in ("acceptance_policy_id", "acceptance_policy_version", "request_signature",
                "input_signature", "output_signature", "declaration_signature", "contract_version", "receipt_id"):
            class WrongGate:
                def accept(inner, request):
                    return replace(make_receipt(request), **{field: "bad"})
            with self.subTest(field=field), self.assertRaises(PlacementTimingError):
                self.build(allocations=self.allocations(), gate=WrongGate())
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_stage_policy_dependency_and_version_precallback_fences(self):
        for field, replacement in (("acceptance_policy_id", "changed"),
                ("acceptance_policy_version", "2"), ("dependencies", ()),
                ("stage_version", "2"), ("stage_id", "other")):
            stage = self.stage(allocations=self.allocations(), dependencies=("edit_planning", "voice_timing"))
            original = stage._execution_binding
            calls = [0]
            def binding(m):
                calls[0] += 1
                if calls[0] == 2:
                    setattr(stage, field, replacement)
                return original(m)
            with patch.object(stage, "_execution_binding", side_effect=binding):
                outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
            self.assertEqual(outcome.result.status, StageStatus.FAILED)
            self.assertEqual(self.gate.calls, 0)

    def test_final_proposal_mutation_no_success(self):
        from creator_studio.placement_timing import engine
        original = engine.require_valid
        def validation(m):
            original(m)
            if m.placement_timing.plans:
                m.placement_timing.active_placement_timing_plan_id = None
        with patch.object(engine, "require_valid", side_effect=validation):
            with self.assertRaises(PlacementTimingError):
                self.accepted()
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_cancellation_immediately_after_gate(self):
        control = CancellationToken()
        self.gate.callback = lambda request: control.cancel()
        with self.assertRaises(Cancelled):
            self.build(allocations=self.allocations(), control=control)
        self.assertEqual(self.gate.calls, 1)
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_request_byte_bound_equality(self):
        p = active_plan(self.accepted())
        size = len(bounded_payload(p))
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", size):
            self.assertEqual(len(bounded_payload(p)), size)
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", size - 1):
            with self.assertRaises(ValueError):
                bounded_payload(p)

    def test_history_aggregate_entry_bound(self):
        p = active_plan(self.accepted())
        entries = [p.entries[0]] * MAX_ENTRIES_PER_PLAN
        plans = [replace(p, entries=entries)] * (MAX_TOTAL_ENTRIES // MAX_ENTRIES_PER_PLAN)
        preflight_history(PlacementTimingState(plans))
        with self.assertRaises(ValueError):
            preflight_history(PlacementTimingState(plans + [replace(p, entries=[p.entries[0]])]))

    def test_history_aggregate_allocation_bound(self):
        p = active_plan(self.accepted())
        a = p.allocations[0]
        allocations = [replace(a, placement_id="p" + str(i // MAX_ALLOCATIONS_PER_ENTRY))
            for i in range(MAX_ALLOCATIONS_PER_PLAN)]
        plans = [replace(p, allocations=allocations)] * (MAX_TOTAL_ALLOCATIONS // MAX_ALLOCATIONS_PER_PLAN)
        preflight_history(PlacementTimingState(plans))
        with self.assertRaises(ValueError):
            preflight_history(PlacementTimingState(plans + [replace(p, allocations=[a])]))

    def test_history_aggregate_boundary_bound(self):
        p = active_plan(self.accepted())
        b = self.boundaries()[0]
        boundaries = [replace(b, placement_id="p" + str(i // 2)) for i in range(MAX_BOUNDARIES_PER_PLAN)]
        plans = [replace(p, explicit_boundaries=boundaries)] * (MAX_TOTAL_BOUNDARIES // MAX_BOUNDARIES_PER_PLAN)
        preflight_history(PlacementTimingState(plans))
        with self.assertRaises(ValueError):
            preflight_history(PlacementTimingState(plans + [replace(p, explicit_boundaries=[b])]))

    def test_per_entry_diagnostic_bound(self):
        p = active_plan(self.accepted())
        e = replace(p.entries[0], diagnostics=[TimingDiagnostic.NO_AUTHORITY] * MAX_DIAGNOSTICS_PER_ENTRY)
        preflight_history(PlacementTimingState([replace(p, entries=[e])]))
        e = replace(e, diagnostics=e.diagnostics + [TimingDiagnostic.NO_AUTHORITY])
        with self.assertRaises(ValueError):
            preflight_history(PlacementTimingState([replace(p, entries=[e])]))

    def test_no_gate_free_authority_injection(self):
        m = self.build(gate=None)
        p = active_plan(m)
        for changed in (replace(p, request_signature="a" * 64),
                replace(p, entries=[replace(p.entries[0], start_us=0, end_us=1)] + p.entries[1:]),
                replace(p, explicit_boundaries=self.boundaries()[:1])):
            bad = deepcopy(m)
            bad.placement_timing.plans[0] = changed
            self.assertTrue(validate(bad))

    def test_dependency_execution_evidence_participates_in_reuse(self):
        from creator_studio.manifest.execution import ExecutionRecord
        for stage_id in ("edit_planning", "voice_timing"):
            record = ExecutionRecord(stage_id, "1", StageStatus.SUCCEEDED, dependency_signature="a" * 64)
            self.m.processing.append(ProcessingState(stage=stage_id, status=Status.SUCCEEDED,
                dependency_signature=record.dependency_signature, execution=record))
        stage = self.stage(dependencies=("edit_planning", "voice_timing"))
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        m, record = outcome.update.manifest, outcome.result
        upstream = {s.stage: signature({"dependency_signature": s.execution.dependency_signature,
            "artifacts": s.execution.artifacts, "metadata": s.execution.metadata}) for s in m.processing}
        record.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(m), "configuration": {}}, upstream)
        m.processing.append(ProcessingState(stage=stage.stage_id, status=Status.SUCCEEDED,
            dependency_signature=record.dependency_signature, execution=record))
        self.assertTrue(stage.validate_reuse(m, record))
        m.processing[0].execution.metadata.append("changed")
        self.assertFalse(stage.validate_reuse(m, record))

    def test_no_successful_selection_required(self):
        from creator_studio.manifest.editing import EditSpec
        m = selected_fixture(self.m, proposals=[])
        m = build_acquisition(m, storage=ManagedStorage(Path(self.temp.name) / "empty-selection"))
        acquisition = next(r for r in m.acquisition.runs if r.acquisition_id == m.acquisition.active_creator_acquisition_id)
        edit = reconstruct(m, acquisition, EditSpec())
        m.editing.plans.append(edit)
        m.editing.active_creator_edit_plan_id = edit.edit_plan_id
        selection = next(r for r in m.selection.runs if r.selection_id == m.selection.active_creator_selection_id)
        self.assertTrue(all(s.selected_candidate is None for s in selection.shot_selections))
        boundaries = []
        for p, unit in zip(edit.placements, self.run.units):
            for side, time in ((BoundarySide.START, unit.start_us), (BoundarySide.END, unit.end_us)):
                b = PlacementBoundaryDeclaration(p.placement_id, side, time)
                boundaries.append(replace(b, declaration_ref=declaration_ref(b)))
        result = self.build(m, explicit_boundaries=boundaries)
        self.assertTrue(self.eligibility(result).complete_placement_timing)

    def test_explicit_start_with_derived_end(self):
        a = self.allocations()[0]
        text = self.m.semantic.source_revisions[0].content.normalized_text
        a = replace(a, start_char=a.start_char + 1, excerpt_signature=exact_signature(text[a.start_char + 1:a.end_char]))
        a = replace(a, declaration_ref=declaration_ref(a))
        b = self.boundaries([(200000, 600000)])[0]
        p = active_plan(self.build(allocations=[a], explicit_boundaries=[b]))
        self.assertEqual(p.entries[0].outcome, PlacementTimingOutcome.TIMED)
        self.assertEqual([e.kind for e in p.entries[0].boundaries],
            [BoundaryKind.ACCEPTED_EXPLICIT_TIME, BoundaryKind.M70_UNIT_END])

    def test_incomplete_accepted_reuse_keeps_receipt_and_outcomes(self):
        stage, m, execution = self.executed(allocations=self.allocations()[:1])
        self.assertTrue(stage.validate_reuse(m, execution))
        self.assertFalse(self.eligibility(m).complete_placement_timing)
        before = deepcopy(m)
        reused = self.build(m, allocations=self.allocations()[:1])
        self.assertEqual(reused, before)
        self.assertEqual(self.gate.calls, 1)

    def test_exact_request_wire_size_equality_and_overflow(self):
        from creator_studio.placement_timing.engine import request_for
        p = active_plan(self.accepted())
        r = request_for(p)
        projection = {f.name: getattr(r, f.name) for f in fields(r)}
        projection["placement_ids"] = list(r.placement_ids)
        size = len(json.dumps(projection, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", size):
            self.assertEqual(request_for(p), r)
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", size - 1):
            with self.assertRaises(ValueError):
                request_for(p)

    def test_migration_capacity_before_deepcopy(self):
        data = to_data(self.m)
        data["placement_timing"]["plans"] = [None] * (MAX_PLANS + 1)
        with patch("creator_studio.manifest.migrations.deepcopy", side_effect=AssertionError("too late")):
            with self.assertRaises(ValueError):
                migrate_document(data)

    def test_last_authorization_callback_cannot_stale_manifest_then_call_gate(self):
        calls = [0]
        def mutate():
            calls[0] += 1
            self.m.voice_timing.active_narration_revision_id = None
        with self.assertRaises(PlacementTimingError):
            self.build(allocations=self.allocations(), authorization_recheck=mutate)
        self.assertEqual(self.gate.calls, 0)

    def test_spec_precallback_and_postcallback_policy_fences(self):
        stage = self.stage(allocations=self.allocations())
        original = stage._execution_binding
        calls = [0]
        def binding(m):
            calls[0] += 1
            if calls[0] == 2:
                stage.spec = replace(stage.spec, engine_version="2")
            return original(m)
        with patch.object(stage, "_execution_binding", side_effect=binding):
            outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertEqual(self.gate.calls, 0)
        stage = self.stage(allocations=self.allocations())
        self.gate.callback = lambda request: setattr(stage, "acceptance_policy_id", "changed")
        outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertIsNone(outcome.update)
        self.assertEqual(self.m.placement_timing, PlacementTimingState())

    def test_artifact_signature_tamper_and_closed_outcome_contract(self):
        stage, m, execution = self.executed()
        execution.artifacts[0].signature = "a" * 64
        self.assertFalse(stage.validate_reuse(m, execution))
        self.assertNotIn("UPSTREAM_NOT_SELECTED", PlacementTimingOutcome.__members__)
        self.assertNotIn("UPSTREAM_NOT_MATERIALIZED", PlacementTimingOutcome.__members__)
        self.assertEqual(len(BoundaryKind), 3)
        self.assertEqual(len(PlacementTimingOutcome), 10)

    def test_m71001_nested_scalars_before_projection_or_hash(self):
        p = active_plan(self.accepted())
        huge = "x" * 10000
        variants = [replace(p, entries=[replace(p.entries[0], placement_id=huge)]),
            replace(p, entries=[replace(p.entries[0], boundaries=[replace(p.entries[0].boundaries[0], unit_id=huge)])]),
            replace(p, entries=[replace(p.entries[0], boundaries=[replace(p.entries[0].boundaries[0], declaration_ref=huge)])]),
            replace(p, entries=[replace(p.entries[0], diagnostics=[huge])])]
        for bad in variants:
            with self.subTest(entry=bad.entries[0].placement_id[:20]), \
                    patch("creator_studio.manifest.placement_timing.to_data") as projection, \
                    patch("creator_studio.manifest.placement_timing.exact_signature") as hashing, \
                    patch("creator_studio.manifest.placement_timing._canonical_chunks") as canonical:
                with self.assertRaises(ValueError):
                    preflight_history(PlacementTimingState([bad]))
                with self.assertRaises(ValueError):
                    canonical_payload(bad)
                with self.assertRaises(ValueError):
                    output_signature(bad)
                projection.assert_not_called()
                hashing.assert_not_called()
                canonical.assert_not_called()

    def test_m71001_raw_nested_scalar_before_migration_copy(self):
        data = to_data(self.accepted())
        plan = data["placement_timing"]["plans"][0]
        for target, name in ((plan["entries"][0], "placement_id"),
                (plan["entries"][0]["boundaries"][0], "unit_id"),
                (plan["entries"][0]["boundaries"][0], "declaration_ref"),
                (plan["allocations"][0], "story_unit_id")):
            old = target[name]
            target[name] = "x" * 10000
            with patch("creator_studio.manifest.migrations.deepcopy") as copying:
                with self.assertRaises(ValueError):
                    migrate_document(data)
                copying.assert_not_called()
            target[name] = old

    def test_m71001_reuse_scalar_before_manifest_hash(self):
        stage, m, previous = self.executed(allocations=self.allocations())
        p = active_plan(m)
        m.placement_timing.plans[0] = replace(p,
            entries=[replace(p.entries[0], placement_id="x" * 10000)])
        with patch("creator_studio.placement_timing.stage.exact_signature") as hashing:
            self.assertFalse(stage.validate_reuse(m, previous))
            hashing.assert_not_called()
        with patch("creator_studio.placement_timing.engine.exact_signature") as hashing:
            with self.assertRaises(ValueError):
                self.eligibility(m)
            hashing.assert_not_called()

    def test_m71001_runtime_declarations_before_sign_copy_request_gate(self):
        for name, record in (("allocations", self.allocations()[0]),
                ("explicit_boundaries", self.boundaries()[0])):
            bad = replace(record, placement_id="x" * 10000)
            with self.subTest(name=name), \
                    patch("creator_studio.placement_timing.stage.signed") as signing, \
                    patch("creator_studio.placement_timing.engine.request_for") as request, \
                    patch("creator_studio.placement_timing.engine.deepcopy") as copying:
                with self.assertRaises(ValueError):
                    self.stage(**{name: [bad]})
                with self.assertRaises(PlacementTimingError):
                    self.build(**{name: [bad]})
                signing.assert_not_called()
                request.assert_not_called()
                copying.assert_not_called()
                self.assertEqual(self.gate.calls, 0)

    def test_m71001_field_inventory_has_explicit_scalar_contracts(self):
        from typing import get_args, get_type_hints
        from creator_studio.manifest import placement_timing_validation as v
        covered = set(v._ID_PREFIXES) | v._DIGESTS | v._POLICIES | set(v._CLOSED) | set(v._SPEC_VALUES)
        for cls in v._RECORDS:
            for name, hint in get_type_hints(cls).items():
                if hint is str or str in get_args(hint):
                    self.assertIn(name, covered, (cls.__name__, name))
        self.assertEqual(MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES, 64 * 1024 * 1024)

    def test_m71001_bounded_serializer_stops_without_projection(self):
        from creator_studio.manifest import placement_timing as contract
        p = active_plan(self.accepted())
        p = replace(p, entries=p.entries * 100)
        # All individual contracts/counts pass. A small controlled budget tests
        # aggregate rejection without allocating a 64 MiB Python string.
        preflight_history(PlacementTimingState([p]))
        original = contract._canonical_chunks
        emitted = []
        def observe(value, **kwargs):
            for chunk in original(value, **kwargs):
                emitted.append(chunk)
                yield chunk
        with patch.object(contract, "to_data") as projection, \
                patch.object(contract, "_canonical_chunks", side_effect=observe):
            with self.assertRaises(ValueError):
                canonical_payload(p, max_bytes=1000)
            projection.assert_not_called()
        self.assertLess(sum(map(len, emitted)), 10000)
        self.assertLess(len(emitted), len(list(original(p))))
        self.gate.calls = 0
        with patch("creator_studio.placement_timing.engine.MAX_CANONICAL_ACCEPTANCE_REQUEST_BYTES", 1000):
            with self.assertRaises(PlacementTimingError):
                self.accepted()
        self.assertEqual(self.gate.calls, 0)

    def test_m71001_exact_byte_boundary_and_legacy_canonical_stability(self):
        from creator_studio.placement_timing.engine import request_for
        p = active_plan(self.accepted())
        data = to_data(p)
        del data["receipt"], data["placement_timing_plan_id"]
        legacy = json.dumps(data, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False)
        self.assertEqual(canonical_payload(p, max_bytes=len(legacy)), legacy)
        with self.assertRaises(ValueError):
            canonical_payload(p, max_bytes=len(legacy) - 1)
        request = request_for(p)
        projection = {f.name: getattr(request, f.name) for f in fields(request)}
        size = len(json.dumps(projection, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        self.assertEqual(canonical_payload(p, max_bytes=size, include_request=True), legacy)
        with self.assertRaises(ValueError):
            canonical_payload(p, max_bytes=size - 1, include_request=True)
        # Independent legacy signing oracle checks identities, not just new/new equality.
        old_signed = lambda domain, payload: exact_signature(["M71", domain, "1", payload])
        self.assertEqual(p.declaration_signature, old_signed("declarations", [p.allocations, p.explicit_boundaries]))
        self.assertEqual(p.output_signature, old_signed("output", [p.input_signature, p.entries, p.unallocated_unit_ids]))
        self.assertEqual(p.placement_timing_plan_id, "placement_timing:" + old_signed("plan",
            [p.input_signature, p.declaration_signature, p.output_signature, p.request_signature, p.receipt]))
        self.assertEqual(active_plan(self.accepted()), p)

    def test_m71001_malformed_evidence_defers_strict_types(self):
        p = active_plan(self.accepted())
        for malformed in (None, 17, "small", {}, [], object()):
            bad = replace(p, entries=[replace(p.entries[0], boundaries=[malformed])])
            preflight_history(PlacementTimingState([bad]))
            with self.assertRaises(ValueError):
                validate_plan(self.m, bad)
        raw = to_data(self.m)
        raw["placement_timing"] = {"plans": [], "active_placement_timing_plan_id": None, "extra": "small"}
        with self.assertRaises(ValueError):
            decode(ProjectManifest, migrate_document(raw))

    def test_m71001_runtime_declaration_field_limits_reject_before_expensive_work(self):
        from contextlib import ExitStack
        from creator_studio.placement_timing import engine
        from creator_studio.manifest import placement_timing as contract
        allocations, boundaries = self.allocations(), self.boundaries()
        cases = [("allocations", allocations, "excerpt_signature", 80)]
        for field, prefix in (("placement_id", "edit_placement:"),
                ("source_revision_id", "semantic_source:"),
                ("semantic_document_id", "semantic_document:"),
                ("story_unit_id", "story_unit:"),
                ("declaration_ref", "placement_declaration:")):
            cases.append(("allocations", allocations, field, len(prefix) + 65))
        for field, prefix in (("placement_id", "edit_placement:"),
                ("declaration_ref", "placement_declaration:")):
            cases.append(("explicit_boundaries", boundaries, field, len(prefix) + 65))
        cases.append(("allocations", allocations, "excerpt_signature", 65))
        for argument, declarations, field, length in cases:
            with self.subTest(argument=argument, field=field, length=length):
                self.assertLess(length, 256)
                # Put the invalid record last to prove every declaration is checked.
                bad = declarations[:-1] + [replace(declarations[-1], **{field: "a" * length})]
                with ExitStack() as stack:
                    mocks = [stack.enter_context(patch.object(module, name))
                        for module, name in ((engine, "runtime_snapshot"),
                            (engine, "signed"), (contract, "signed"),
                            (engine, "exact_signature"), (engine, "deepcopy"),
                            (engine, "PlacementTimingPlan"), (engine, "request_for"),
                            (self.gate, "accept"))]
                    with self.assertRaises(PlacementTimingError):
                        self.build(**{argument: bad})
                    for mock in mocks:
                        mock.assert_not_called()
                self.assertEqual(self.gate.calls, 0)

    def test_m71001_maximum_length_runtime_declarations_process_normally(self):
        from creator_studio.placement_timing import engine
        for argument, declarations in (("allocations", self.allocations()),
                ("explicit_boundaries", self.boundaries())):
            with self.subTest(argument=argument):
                # Repository-generated IDs/digests occupy their full field width.
                for declaration in declarations:
                    self.assertEqual(len(declaration.placement_id), len("edit_placement:") + 64)
                    self.assertEqual(len(declaration.declaration_ref), len("placement_declaration:") + 64)
                    if argument == "allocations":
                        for field, prefix in (("source_revision_id", "semantic_source:"),
                                ("semantic_document_id", "semantic_document:"),
                                ("story_unit_id", "story_unit:")):
                            self.assertEqual(len(getattr(declaration, field)), len(prefix) + 64)
                        self.assertEqual(len(declaration.excerpt_signature), 64)
                with patch.object(engine, "runtime_snapshot", wraps=engine.runtime_snapshot) as snapshot:
                    result = self.build(**{argument: declarations})
                self.assertTrue(snapshot.called)
                self.assertTrue(all(e.outcome == PlacementTimingOutcome.TIMED
                    for e in active_plan(result).entries))
        self.assertEqual(self.gate.calls, 2)

    def test_m71001_allocation_order_is_identity_significant(self):
        allocations = self.allocations()
        stage, m, previous = self.executed(allocations=allocations)
        first = active_plan(m)
        reordered = self.stage(allocations=list(reversed(allocations)))
        self.assertFalse(reordered.validate_reuse(m, previous))
        self.assertNotEqual(stage._declaration(), reordered._declaration())
        second = active_plan(self.build(m, allocations=list(reversed(allocations))))
        self.assertEqual(first.entries, second.entries)
        for name in ("declaration_signature", "input_signature", "request_signature", "placement_timing_plan_id"):
            self.assertNotEqual(getattr(first, name), getattr(second, name), name)
        self.assertNotEqual(first.receipt, second.receipt)
        self.assertEqual(self.gate.calls, 2)

    def test_m71002_all_raw_record_member_limits_before_migration_copy(self):
        from creator_studio.manifest import placement_timing_validation as v
        data = to_data(self.accepted())
        state = data["placement_timing"]
        plan = state["plans"][0]
        # Include explicit declarations alongside allocation-derived evidence.
        plan["explicit_boundaries"] = to_data(self.boundaries())
        records = [
            (state, PlacementTimingState), (plan, PlacementTimingPlan),
            (plan["spec"], PlacementTimingSpec),
            (plan["lineage"], PlacementTimingLineage),
            (plan["allocations"][0], PlacementAllocationDeclaration),
            (plan["explicit_boundaries"][0], PlacementBoundaryDeclaration),
            (plan["entries"][0], PlacementTimingEntry),
            (plan["entries"][0]["boundaries"][0], PlacementBoundaryEvidence),
            (plan["receipt"], PlacementTimingAcceptanceReceipt),
        ]
        self.assertEqual({cls for _, cls in records}, set(v._RECORDS))
        for record, cls in records:
            with self.subTest(record=cls.__name__):
                self.assertEqual(len(record), len(fields(cls)))
                v.preflight_record(record, cls, raw=True)
                # Only N+1 short unknown members: no large test allocation.
                old = record.copy()
                record.clear()
                record.update({f"unknown_{i}": "x" for i in range(len(fields(cls)) + 1)})
                with patch("creator_studio.manifest.migrations.deepcopy") as copying, \
                        patch.object(v, "_preflight_malformed") as traversal:
                    with self.assertRaises(ValueError):
                        migrate_document(data)
                    copying.assert_not_called()
                    traversal.assert_not_called()
                record.clear()
                record.update(old)

    def test_m71002_small_unknown_field_preserved_for_strict_decoder(self):
        from creator_studio.manifest.placement_timing_validation import preflight_document
        data = to_data(self.m)
        # Two members, within state capacity; optional active field is absent.
        data["placement_timing"] = {"plans": [], "unknown": "x"}
        before = deepcopy(data)
        preflight_document(data["placement_timing"])
        migrated = migrate_document(data)
        self.assertEqual(data, before)
        self.assertEqual(migrated["placement_timing"], before["placement_timing"])
        with self.assertRaisesRegex(ValueError, "unknown"):
            decode(ProjectManifest, migrated)

    def test_m71003_bounded_infinite_huge_and_three_element_sources(self):
        for path in (self.build, self.stage):
            for size in (None, 1000000000, 3):
                with self.subTest(path=path.__name__, size=size):
                    yielded = []
                    def source():
                        index = 0
                        while size is None or index < size:
                            index += 1
                            yielded.append(index)
                            if index > 3:
                                raise AssertionError("fourth element requested")
                            yield "edit_planning"
                    with self.assertRaises(PlacementTimingError):
                        path(dependencies=source())
                    self.assertEqual(yielded, [1, 2, 3])

    def test_m71003_generator_semantics_both_public_paths(self):
        valid = ((), ("edit_planning", "voice_timing"))
        invalid = (("edit_planning",), ("voice_timing", "edit_planning"),
            ("edit_planning", "edit_planning"), ("edit_planning", "voice_timing", "extra"))
        for path in (self.build, self.stage):
            for values in valid + invalid:
                with self.subTest(path=path.__name__, values=values):
                    source = (value for value in values)
                    if values in valid:
                        result = path(dependencies=source)
                        if path.__name__ == "stage":
                            self.assertEqual(result.dependencies, values)
                        else:
                            require_valid(result)
                    else:
                        with self.assertRaises(PlacementTimingError):
                            path(dependencies=source)

    def test_m71003_one_shot_through_snapshot_signature_execution_and_reuse(self):
        class OneShot:
            def __init__(self, values):
                self.values, self.calls = values, 0
            def __iter__(self):
                self.calls += 1
                if self.calls != 1:
                    raise AssertionError("source iterated again")
                return iter(self.values)
        for values in ((), ("edit_planning", "voice_timing")):
            source = OneShot(values)
            result = self.build(dependencies=source)
            require_valid(result)
            self.assertEqual(source.calls, 1)
            source = OneShot(values)
            stage = self.stage(dependencies=source)
            stage.signature_inputs(self.m)
            stage._declaration()
            outcome = stage.execute(StageContext(self.m, CancellationToken(), 1, lambda *a: None))
            self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
            stage.validate_reuse(outcome.update.manifest, outcome.result)
            self.assertEqual(source.calls, 1)
        # Valid active reuse must also leave the original source untouched.
        source = OneShot(())
        stage, manifest, execution = self.executed(dependencies=source)
        self.assertTrue(stage.validate_reuse(manifest, execution))
        self.build(manifest, dependencies=OneShot(()))
        self.assertEqual(source.calls, 1)


if __name__ == "__main__":
    unittest.main()
