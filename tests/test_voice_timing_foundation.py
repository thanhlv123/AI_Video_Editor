"""Fully offline M70 acceptance tests. WAV bytes exist only in temporary stores."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest, validate
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.models import ProcessingState, Status, Scene, SubtitleTrack, SubtitleSegment
from creator_studio.manifest.semantic import exact_signature, output_signature as semantic_output_signature, ReviewStatus
from creator_studio.manifest.voice_timing import *
from creator_studio.manifest.voice_timing_validation import validate_history, voice_timing_errors
from creator_studio.content.ingest import ingest, apply_ingest
from creator_studio.content.models import IngestRequest
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.voice_timing import *
from creator_studio.voice_timing.engine import active_run, boundary_unchanged
from creator_studio.orchestrator.contracts import CancellationToken, Cancelled, StageContext, StageStatus
from creator_studio.manifest.signatures import dependency_signature, signature

POLICY = dict(acceptance_policy_id="test_policy", acceptance_policy_version="1")

def wav(*, payload=b"\x00" * 32000, channels=1, rate=16000, bits=16,
        tag=1, align=None, byte_rate=None, pad=True):
    align = channels * (bits // 8) if align is None else align
    byte_rate = rate * align if byte_rate is None else byte_rate
    body = b"WAVEfmt " + struct.pack("<IHHIIHH", 16, tag, channels, rate, byte_rate, align, bits)
    body += b"data" + struct.pack("<I", len(payload)) + payload
    if len(payload) % 2 and pad:
        body += b"\x00"
    return b"RIFF" + struct.pack("<I", len(body)) + body

def content(text="Hello hello.", manifest=None):
    return apply_ingest(manifest or ProjectManifest("M70"), ingest(IngestRequest("creator", text=text, language="en")))

class FakeGate:
    def __init__(self, callback=None):
        self.callback = callback
        self.requests = []

    def accept(self, request):
        self.requests.append(request)
        if self.callback:
            self.callback(request)
        return make_receipt(request)

class CountingControl:
    def __init__(self, stop):
        self.stop, self.count = stop, 0

    def check(self):
        self.count += 1
        if self.count == self.stop:
            raise Cancelled()

class VoiceTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "giọng nói.bin"
        self.path.write_bytes(wav())
        self.asset, self.inspection = inspect_stream(io.BytesIO(self.path.read_bytes()))
        self.store = LocalNarrationByteStore({self.asset.asset_id: self.path})
        self.base = build_semantic_story(content())
        self.narration = register_narration(self.base, self.asset, storage=self.store, logical_revision=1)
        self.doc = self.base.semantic.documents[0]
        self.story = self.doc.story_units[0].story_unit_id
        self.bindings = [source_binding(self.base, 0, 5, self.story), source_binding(self.base, 6, 12, self.story)]
        self.observations = [Observation(0, 100000, 300000, "Hello", MappingStatus.EXACT, (self.bindings[0],)),
            Observation(1, 400000, 700000, "hello.", MappingStatus.EXACT, (self.bindings[1],))]
        self.gate = FakeGate()

    def build(self, manifest=None, **kwargs):
        options = dict(storage=self.store, observations=self.observations, gate=self.gate, **POLICY)
        options.update(kwargs)
        return build_voice_timing(manifest or self.narration, **options)

    def eligibility(self, manifest, **kwargs):
        options = dict(storage=self.store, **POLICY)
        options.update(kwargs)
        return current_timing_eligibility(manifest, **options)

    def stage(self, **kwargs):
        options = dict(storage=self.store, observations=self.observations, gate=self.gate, **POLICY)
        options.update(kwargs)
        return VoiceTimingStage(**options)

    def reusable(self, dependencies=()):
        stage = self.stage(dependencies=dependencies)
        manifest = self.build()
        upstream = {}
        if stage.dependencies:
            from creator_studio.manifest.execution import ExecutionRecord
            execution = ExecutionRecord("semantic_story", "1", StageStatus.SUCCEEDED,
                dependency_signature="a" * 64)
            manifest.processing.append(ProcessingState(stage="semantic_story", status=Status.SUCCEEDED,
                execution=execution, dependency_signature=execution.dependency_signature))
            upstream["semantic_story"] = signature({"dependency_signature": execution.dependency_signature,
                "artifacts": execution.artifacts, "metadata": execution.metadata})
        result = stage.execute(StageContext(manifest, CancellationToken(), 1, lambda *args: None)).result
        result.dependency_signature = dependency_signature(stage.stage_id, stage.stage_version,
            {"inputs": stage.signature_inputs(manifest), "configuration": {}}, upstream)
        manifest.processing.append(ProcessingState(stage="voice_timing", status=Status.SUCCEEDED,
            execution=result, dependency_signature=result.dependency_signature))
        return stage, manifest, result

    def test_empty_additive_state(self):
        self.assertEqual(ProjectManifest("old").voice_timing, VoiceTimingState())
        self.assertFalse(validate(ProjectManifest("old")))

    def test_old_schema_two(self):
        data = to_data(self.base)
        del data["voice_timing"]
        loaded = decode(ProjectManifest, migrate_document(data))
        self.assertEqual(loaded.schema_version, 2)
        self.assertEqual(loaded.voice_timing, VoiceTimingState())

    def test_no_migration_authority(self):
        data = to_data(self.base)
        del data["voice_timing"]
        self.assertEqual(migrate_document(data)["voice_timing"], to_data(VoiceTimingState()))

    def test_success_changes_only_voice_timing(self):
        before = deepcopy(self.narration)
        result = self.build()
        self.assertEqual(before, self.narration)
        self.assertTrue(boundary_unchanged(before, result))
        self.assertFalse(validate(result))
        self.assertTrue(self.eligibility(result).eligible)
        self.assertTrue(self.eligibility(result).complete_coverage)

    def test_deterministic_run_and_units(self):
        self.assertEqual(self.build(), self.build())
        run = active_run(self.build())
        self.assertEqual(run.alignment_run_id, run_id(run))
        self.assertEqual(run.units[0].unit_id, unit_id(run.input_signature, run.units[0]))

    def test_revision_identity_distinct_same_bytes(self):
        new = register_narration(self.narration, self.asset, storage=self.store, logical_revision=2,
            predecessor_revision_id=self.narration.voice_timing.active_narration_revision_id)
        self.assertEqual(len(new.voice_timing.assets), 1)
        self.assertNotEqual(new.voice_timing.revisions[0].revision_id, new.voice_timing.revisions[1].revision_id)
        self.assertEqual(new.voice_timing.revisions[0], self.narration.voice_timing.revisions[0])
        self.assertIsNone(new.voice_timing.active_alignment_run_id)

    def test_generated_origin_generic(self):
        result = register_narration(self.base, self.asset, storage=self.store,
            logical_revision=1, origin=NarrationOrigin.GENERATED, provenance="GENERIC_OUTPUT")
        self.assertEqual(result.voice_timing.revisions[0].origin, NarrationOrigin.GENERATED)

    def test_immutable_request(self):
        self.build()
        request = self.gate.requests[0]
        with self.assertRaises(FrozenInstanceError):
            request.byte_count = 0
        with self.assertRaises(FrozenInstanceError):
            request.source_bindings[0].start_char = 8
        self.assertIsInstance(request.source_bindings, tuple)
        self.assertNotIn("Hello", request.output_payload_json)
        self.assertEqual(request.spec_signature, signed("spec", request.spec))

    def test_missing_gate(self):
        with self.assertRaises(VoiceTimingError) as caught:
            self.build(gate=None)
        self.assertEqual(caught.exception.code, "voice_gate_required")

    def test_no_narration_revision(self):
        with self.assertRaises(VoiceTimingError):
            self.build(self.base)

    def test_deleted_bytes_history_valid(self):
        result = self.build()
        self.path.unlink()
        with patch("builtins.open", side_effect=AssertionError("filesystem forbidden")):
            validate_history(result)
        self.assertFalse(validate(result))
        eligibility = self.eligibility(result)
        self.assertTrue(eligibility.historical_validity)
        self.assertFalse(eligibility.audio_usability)

    def test_changed_bytes_stale(self):
        result = self.build()
        data = self.path.read_bytes()
        self.path.write_bytes(data[:-2] + b"ab")
        self.assertFalse(self.eligibility(result).audio_usability)
        self.assertFalse(validate(result))

    def test_relocation_identity_neutral(self):
        result = self.build()
        moved = Path(self.temp.name) / "moved.wav"
        moved.write_bytes(self.path.read_bytes())
        store = LocalNarrationByteStore({self.asset.asset_id: moved})
        self.assertEqual(self.build(storage=store), result)
        self.assertTrue(self.eligibility(result, storage=store).eligible)

    def test_semantic_revision_stale_history_retained(self):
        result = self.build()
        changed = build_semantic_story(content("Different content.", result))
        self.assertFalse(validate(changed))
        self.assertFalse(self.eligibility(changed).current_semantic_binding)

    def test_semantic_review_change_not_historical_failure(self):
        result = self.build()
        d = replace(result.semantic.documents[0], review_status=ReviewStatus.APPROVED)
        result.semantic.documents[0] = replace(d, output_signature=semantic_output_signature(d))
        self.assertFalse(validate(result))
        self.assertFalse(self.eligibility(result).current_semantic_binding)

    def test_partial_has_no_invented_times(self):
        result = self.build(observations=self.observations[:1], omissions=[SourceOmission(0, self.bindings[1])])
        run = active_run(result)
        self.assertEqual(len(run.units), 1)
        self.assertFalse(self.eligibility(result).complete_coverage)
        self.assertTrue(self.eligibility(result).eligible)
        self.assertFalse(hasattr(run.omissions[0], "start_us"))

    def test_added_speech_no_source(self):
        obs = self.observations + [Observation(2, 800000, 900000, "extra", MappingStatus.SPEECH_ADDED)]
        result = self.build(observations=obs)
        self.assertEqual(active_run(result).units[-1].source_bindings, [])
        self.assertFalse(self.eligibility(result).complete_coverage)

    def test_explicit_mismatch(self):
        obs = [replace(self.observations[0], observed_text="paraphrase", mapping_status=MappingStatus.MISMATCH)]
        result = self.build(observations=obs)
        self.assertEqual(result.content.script, self.base.content.script)
        self.assertFalse(self.eligibility(result).complete_coverage)

    def test_case_and_punctuation_matching_preserves_source(self):
        obs = [replace(self.observations[0], observed_text="HELLO!", mapping_status=MappingStatus.NORMALIZED_MATCH)]
        result = self.build(observations=obs)
        self.assertEqual(result.semantic, self.base.semantic)
        self.assertEqual(result.content, self.base.content)

    def test_explicit_variant_evidence(self):
        obs = [replace(self.observations[0], observed_text="spoken variant",
            mapping_status=MappingStatus.EXPLICIT_VARIANT, variant_evidence_signature=exact_signature("explicit mapping"))]
        self.assertFalse(validate(self.build(observations=obs)))

    def test_repeated_words_offsets_and_ordinals(self):
        result = self.build()
        units = active_run(result).units
        self.assertNotEqual(units[0].unit_id, units[1].unit_id)
        self.assertNotEqual(units[0].source_bindings[0].start_char, units[1].source_bindings[0].start_char)

    def test_no_raw_transcript_persistence(self):
        run = active_run(self.build())
        data = json.dumps(to_data(run))
        self.assertNotIn("Hello", data)
        self.assertNotIn(str(self.path), data)
        self.assertNotIn("://", data)

    def test_exact_frames_floor_duration(self):
        _, evidence = inspect_stream(io.BytesIO(wav(rate=44100, payload=b"\x00" * 2)))
        self.assertEqual((evidence.frame_count, evidence.sample_rate, evidence.duration_us), (1, 44100, 22))

    def test_leading_trailing_silence_preserved(self):
        run = active_run(self.build())
        self.assertEqual(run.inspection.duration_us, 1000000)
        self.assertEqual(run.units[0].start_us, 100000)
        self.assertEqual(run.units[-1].end_us, 700000)

    def test_gap_allowed(self):
        self.assertFalse(validate(self.build()))

    def test_inspector_full_read_bounded(self):
        data = wav(payload=b"\x00" * (READ_CHUNK + 100))
        class Bounded(io.BytesIO):
            def read(self, n=-1):
                self_size.assertLessEqual(n, READ_CHUNK)
                self_size.assertGreaterEqual(n, 0)
                return super().read(min(n, 32768))
        self_size = self
        asset, _ = inspect_stream(Bounded(data))
        self.assertEqual(asset.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(asset.byte_count, len(data))

    def test_extension_not_trusted(self):
        self.assertTrue(self.eligibility(self.build()).audio_usability)

    def test_wrong_asset_association(self):
        with self.assertRaises(VoiceTimingError):
            verify_audio(LocalNarrationByteStore({"wrong": self.path}), self.asset)

    def test_unreadable_store(self):
        class Unreadable:
            def open_read(self, asset):
                raise PermissionError("private path")
        self.assertFalse(self.eligibility(self.build(), storage=Unreadable()).audio_usability)

    def test_gate_exception_controlled(self):
        def fail(request):
            raise RuntimeError("private provider exception")
        with self.assertRaises(VoiceTimingError) as caught:
            self.build(gate=FakeGate(fail))
        self.assertEqual(str(caught.exception), "voice_gate_failed")

    def test_callback_mutates_audio(self):
        before = deepcopy(self.narration)
        with self.assertRaises(VoiceTimingError):
            self.build(gate=FakeGate(lambda r: self.path.write_bytes(wav(payload=b"ab" * 16000))))
        self.assertEqual(self.narration, before)

    def test_callback_mutates_observations(self):
        before = deepcopy(self.narration)
        with self.assertRaises(VoiceTimingError):
            self.build(gate=FakeGate(lambda r: self.observations.pop()))
        self.assertEqual(self.narration, before)

    def test_callback_mutates_spec(self):
        spec = AlignmentSpec()
        def mutate(request):
            object.__setattr__(spec, "time_unit", "SECONDS")
        with self.assertRaises(VoiceTimingError):
            self.build(spec=spec, gate=FakeGate(mutate))

    def test_history_append_corrected_alignment(self):
        first = self.build()
        second = self.build(first, observations=[replace(self.observations[0], end_us=350000), self.observations[1]])
        self.assertEqual(len(second.voice_timing.runs), 2)
        self.assertEqual(second.voice_timing.runs[0], first.voice_timing.runs[0])

    def test_pointer_clear_no_reactivation(self):
        result = self.build()
        result.voice_timing.active_alignment_run_id = None
        self.assertFalse(validate(result))
        self.assertFalse(self.eligibility(result).active_alignment_pointer)
        self.assertIsNone(active_run(result))

    def test_narration_pointer_clear_requires_alignment_clear(self):
        result = self.build()
        result.voice_timing.active_narration_revision_id = None
        self.assertTrue(validate(result))

    def test_inactive_run_cannot_be_automatically_reactivated(self):
        result = self.build()
        result.voice_timing.active_alignment_run_id = None
        with self.assertRaises(VoiceTimingError):
            self.build(result)

    def test_active_exact_reuse(self):
        stage, manifest, previous = self.reusable()
        self.assertTrue(stage.validate_reuse(manifest, previous))

    def test_combined_dependency_signature(self):
        stage, manifest, previous = self.reusable(("semantic_story",))
        self.assertTrue(stage.validate_reuse(manifest, previous))
        manifest.processing[0].execution.metadata.append("changed")
        self.assertFalse(stage.validate_reuse(manifest, previous))

    def test_changed_runtime_observation_rejects_reuse(self):
        stage, manifest, previous = self.reusable()
        stage.observations[0] = replace(stage.observations[0], end_us=350000)
        self.assertFalse(stage.validate_reuse(manifest, previous))

    def test_stage_success_exact_artifacts(self):
        result = self.stage().execute(StageContext(self.narration, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.SUCCEEDED)
        self.assertEqual(len(result.result.artifacts), 2)
        self.assertTrue(result.result.artifacts[0].reference.startswith("voice_timing/alignment_run:"))
        self.assertTrue(result.result.artifacts[1].reference.startswith("voice_source/narration_revision:"))
        self.assertTrue(boundary_unchanged(self.narration, result.update.manifest))

    def test_stage_failure_no_update(self):
        result = self.stage(gate=None).execute(StageContext(self.narration, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertLessEqual(len(result.result.diagnostics), 32)

    def test_no_readiness_claims(self):
        eligibility = self.eligibility(self.build())
        for name in ("placement_readiness", "render_readiness", "subtitle_readiness", "authenticated", "approved"):
            self.assertFalse(hasattr(eligibility, name))

    def test_read_only_store_surface(self):
        for name in ("write", "stage", "finalize", "publish", "download", "delete", "gc"):
            self.assertFalse(hasattr(self.store, name))
            self.assertFalse(hasattr(NarrationByteStore, name))

    def test_historical_validation_no_gate(self):
        result = self.build()
        self.gate.accept = lambda r: self.fail("gate called")
        validate_history(result)

    def test_deterministic_codec_roundtrip(self):
        result = self.build()
        self.assertEqual(decode(ProjectManifest, to_data(result)), result)
        self.assertEqual(exact_signature(decode(ProjectManifest, to_data(result))), exact_signature(result))

    def test_cancellation_after_callback(self):
        control = CancellationToken()
        before = deepcopy(self.narration)
        with self.assertRaises(Cancelled):
            self.build(control=control, gate=FakeGate(lambda r: control.cancel()))
        self.assertEqual(self.narration, before)

    def test_cancellation_preflight(self):
        control = CancellationToken()
        control.cancel()
        with self.assertRaises(Cancelled):
            self.build(control=control)
        self.assertEqual(self.gate.requests, [])

    def test_cancellation_hashing(self):
        with self.assertRaises(Cancelled):
            inspect_stream(io.BytesIO(wav(payload=b"\x00" * (READ_CHUNK * 2))), control=CountingControl(15))

    def test_cancellation_unit_validation(self):
        result = self.build()
        from creator_studio.manifest.voice_timing_validation import validate_output
        with self.assertRaises(Cancelled):
            validate_output(result, active_run(result), CountingControl(2))

    def test_cancellation_before_callback(self):
        control = CancellationToken()
        from creator_studio.voice_timing import engine
        original = engine.validate_output
        def cancel(*args, **kwargs):
            output = original(*args, **kwargs)
            control.cancel()
            return output
        with patch.object(engine, "validate_output", cancel), self.assertRaises(Cancelled):
            self.build(control=control)
        self.assertEqual(self.gate.requests, [])

    def test_cancellation_immediately_before_success(self):
        control = CancellationToken()
        from creator_studio.voice_timing import engine
        original = engine.verify_audio
        calls = []
        def cancel(*args, **kwargs):
            output = original(*args, **kwargs)
            calls.append(1)
            if len(calls) == 3:
                control.cancel()
            return output
        before = deepcopy(self.narration)
        with patch.object(engine, "verify_audio", cancel), self.assertRaises(Cancelled):
            self.build(control=control)
        self.assertEqual(self.narration, before)

    def test_no_prohibited_imports(self):
        forbidden = {"PyQt6", "pipeline", "stock", "subprocess", "requests", "httpx", "urllib",
            "whisper", "tts", "renderer", "ffmpeg", "socket"}
        roots = [Path("creator_studio/voice_timing"), Path("creator_studio/manifest")]
        files = list(roots[0].glob("*.py")) + [roots[1] / "voice_timing.py", roots[1] / "voice_timing_validation.py"]
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [n.name for n in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                self.assertFalse(set(".".join(names).lower().split(".")) & {s.lower() for s in forbidden}, path)

    def test_legacy_voice_not_authority(self):
        manifest = deepcopy(self.base)
        manifest.voice.alignment_reference = "legacy.srt"
        manifest.voice.status = Status.SUCCEEDED
        with self.assertRaises(VoiceTimingError):
            self.build(manifest)
        self.assertEqual(manifest.voice_timing, VoiceTimingState())

    def test_scene_times_not_authority(self):
        manifest = deepcopy(self.base)
        manifest.scenes = [Scene(start=0.0, end=1.0)]
        self.assertFalse(validate(manifest))
        with self.assertRaises(VoiceTimingError):
            self.build(manifest)

    def test_subtitle_times_not_authority(self):
        manifest = deepcopy(self.base)
        scene = Scene(start=0.0, end=1.0)
        manifest.scenes = [scene]
        manifest.subtitle_tracks = [SubtitleTrack(segments=[SubtitleSegment(scene_id=scene.id,
            start=0.1, end=0.7, original_text="Other transcript")])]
        self.assertFalse(validate(manifest))
        with self.assertRaises(VoiceTimingError):
            self.build(manifest)

    def test_srt_input_not_automatically_authority(self):
        path = Path(self.temp.name) / "legacy.srt"
        path.write_text("1\n00:00:00,100 --> 00:00:00,700\nHello hello.\n", encoding="utf-8")
        with self.assertRaises(VoiceTimingError):
            self.build(observations=path)

    def test_nonempty_canonical_domains_preserved(self):
        from creator_studio.manifest.models import (MediaReference, MediaKind, Provenance,
            Rights, TimelineReference, AudioReference)
        manifest = deepcopy(self.narration)
        scene = Scene(start=0.0, end=1.0)
        media = MediaReference(kind=MediaKind.LOCAL, reference="owned.wav",
            provenance=Provenance(rights=Rights.OWNED), final_eligible=True)
        manifest.scenes = [scene]
        manifest.media = [media]
        manifest.timeline = [TimelineReference(scene_id=scene.id, media_id=media.id, start=0.0, end=1.0)]
        manifest.voice.audio_media_id = media.id
        manifest.voice.alignment_reference = "legacy.srt"
        manifest.subtitle_tracks = [SubtitleTrack(segments=[SubtitleSegment(scene_id=scene.id,
            start=0.1, end=0.7, original_text="Unrelated legacy transcript")])]
        manifest.audio = [AudioReference(media_id=media.id)]
        before = deepcopy(manifest)
        result = self.build(manifest)
        self.assertTrue(boundary_unchanged(before, result))
        self.assertEqual(manifest, before)

    def test_nonempty_m69_placements_unchanged(self):
        # Reuse the established fully offline M69 fixture; no real providers/tools.
        from tests.test_timeline_foundation import TimelineFoundationTests
        from creator_studio.manifest.editing import TimingState, EditPlacement
        from dataclasses import fields
        TimelineFoundationTests.setUpClass()
        fixture = TimelineFoundationTests()
        fixture.setUp()
        try:
            manifest = fixture.build()
            manifest = register_narration(manifest, self.asset, storage=self.store, logical_revision=1)
            doc = manifest.semantic.documents[0]
            story = doc.story_units[0]
            span = story.source_excerpts[0].source_span
            binding = source_binding(manifest, span.start, span.end, story.story_unit_id)
            # The observation remains one coarse lexical observation; no shot splitting.
            obs = Observation(0, 100000, 700000, story.source_excerpts[0].source_text,
                MappingStatus.EXACT, (binding,))
            before = deepcopy(manifest)
            result = self.build(manifest, observations=[obs])
            self.assertEqual(result.editing, before.editing)
            self.assertTrue(result.editing.plans[0].placements)
            self.assertEqual(result.editing.plans[0].timing_state, TimingState.UNRESOLVED)
            self.assertEqual([p.placement_id for p in result.editing.plans[0].placements],
                [p.placement_id for p in before.editing.plans[0].placements])
            self.assertFalse({"start_us", "end_us", "duration_us"} & {f.name for f in fields(EditPlacement)})
            self.assertEqual(len(active_run(result).units), 1)
        finally:
            fixture.doCleanups()

    def test_aggregate_limits_declared(self):
        self.assertEqual((MAX_ASSETS, MAX_REVISIONS, MAX_RUNS), (64, 64, 64))
        self.assertEqual((MAX_UNITS, MAX_TOTAL_UNITS, MAX_BINDINGS, MAX_TOTAL_BINDINGS,
            MAX_ISSUES, MAX_TOTAL_ISSUES), (100000, 500000, 200000, 1000000, 100000, 500000))

    def test_exact_cross_product_extent(self):
        # One frame at 44100Hz ends at 22.675... us; 23 is never valid.
        path = Path(self.temp.name) / "short"
        path.write_bytes(wav(rate=44100, payload=b"\x00\x00"))
        asset, _ = inspect_stream(io.BytesIO(path.read_bytes()))
        store = LocalNarrationByteStore({asset.asset_id: path})
        manifest = register_narration(self.base, asset, storage=store, logical_revision=1)
        obs = replace(self.observations[0], start_us=0, end_us=22)
        self.assertFalse(validate(self.build(manifest, storage=store, observations=[obs])))
        with self.assertRaises(VoiceTimingError):
            self.build(manifest, storage=store, observations=[replace(obs, end_us=23)])

    def test_short_reads_reject_missing_payload(self):
        class LyingStream(io.BytesIO):
            def read(self, n=-1):
                return b"" if self.tell() >= 44 else super().read(n)
        with self.assertRaises(VoiceTimingError):
            inspect_stream(LyingStream(wav()))

    def test_current_eligibility_rechecks_pointer_mutation_during_read(self):
        result = self.build()
        original = self.store.open_read
        class MutatingStore:
            def open_read(inner, asset):
                result.voice_timing.active_alignment_run_id = None
                return original(asset)
        with self.assertRaises(VoiceTimingError):
            self.eligibility(result, storage=MutatingStore())

    def test_registration_checks_exact_digest(self):
        asset = replace(self.asset, sha256="a" * 64, asset_id="asset:sha256:" + "a" * 64)
        with self.assertRaises(VoiceTimingError):
            register_narration(self.base, asset, storage=LocalNarrationByteStore({asset.asset_id: self.path}), logical_revision=1)

    def test_provider_trust_confidence_shortcuts_absent(self):
        for keyword in ("trusted", "confidence", "provider"):
            with self.assertRaises(TypeError):
                build_voice_timing(self.narration, storage=self.store, observations=self.observations,
                    gate=None, **POLICY, **{keyword: True})

    def test_no_provider_payload_provenance(self):
        for provenance in ({"provider": "data"}, "https://provider.invalid", "C:/private", "api_key=value"):
            with self.subTest(provenance=provenance), self.assertRaises(VoiceTimingError):
                register_narration(self.base, self.asset, storage=self.store, logical_revision=2,
                    provenance=provenance)

    def test_no_synthetic_silence_units(self):
        result = self.build(observations=self.observations[:1])
        self.assertEqual(len(active_run(result).units), 1)
        self.assertEqual(active_run(result).units[0].start_us, 100000)

    def test_omission_overlap_rejected(self):
        with self.assertRaises(VoiceTimingError):
            self.build(omissions=[SourceOmission(0, self.bindings[0])])

    def test_number_variant_requires_explicit_evidence(self):
        base = build_semantic_story(content("42"))
        manifest = register_narration(base, self.asset, storage=self.store, logical_revision=1)
        doc = base.semantic.documents[0]
        binding = source_binding(base, 0, 2, doc.story_units[0].story_unit_id)
        obs = Observation(0, 100, 200, "forty two", MappingStatus.NORMALIZED_MATCH, (binding,))
        with self.assertRaises(VoiceTimingError):
            self.build(manifest, observations=[obs])
        obs = replace(obs, mapping_status=MappingStatus.EXPLICIT_VARIANT,
            variant_evidence_signature=exact_signature(["42", "forty two"]))
        self.assertFalse(validate(self.build(manifest, observations=[obs])))

    def test_unicode_normalization_versioned_and_source_unchanged(self):
        base = build_semantic_story(content("Café"))
        manifest = register_narration(base, self.asset, storage=self.store, logical_revision=1)
        doc = base.semantic.documents[0]
        binding = source_binding(base, 0, 4, doc.story_units[0].story_unit_id)
        obs = Observation(0, 100, 200, "Cafe\u0301", MappingStatus.NORMALIZED_MATCH, (binding,))
        result = self.build(manifest, observations=[obs])
        self.assertEqual(result.semantic, base.semantic)
        self.assertEqual(active_run(result).spec.normalization_policy, "NFC_CASEFOLD_EDGE_PUNCT_WS_V1")

    def test_inspection_mismatch_current(self):
        with self.assertRaises(VoiceTimingError):
            verify_audio(self.store, self.asset, expected_inspection=replace(self.inspection, channels=2))

    def test_readiness_requires_gate_and_semantic(self):
        self.assertNotEqual(self.stage(gate=None).readiness(self.narration).kind.value, "ready")
        manifest = deepcopy(self.narration)
        manifest.semantic.active_creator_document_id = None
        self.assertNotEqual(self.stage().readiness(manifest).kind.value, "ready")

    def test_stage_runtime_policy_mutation_fenced(self):
        stage = self.stage()
        stage.gate = FakeGate(lambda r: setattr(stage, "acceptance_policy_version", "v2"))
        result = stage.execute(StageContext(self.narration, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(result.result.status, StageStatus.FAILED)
        self.assertIsNone(result.update)
        self.assertEqual(len(stage.gate.requests), 1)

    def test_stage_declaration_mutation_before_gate(self):
        from creator_studio.voice_timing import engine
        for field in ("acceptance_policy_id", "acceptance_policy_version", "spec",
                "dependencies", "observations", "omissions", "stage_id", "stage_version",
                "storage", "gate", "dependency_evidence"):
            with self.subTest(field=field):
                manifest = deepcopy(self.narration)
                manifest.processing.append(ProcessingState(stage="semantic_story"))
                gate = FakeGate()
                stage = self.stage(gate=gate, observations=list(self.observations),
                    dependencies=("semantic_story",))
                original = engine.verify_audio
                def verify(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if field == "spec":
                        stage.spec = replace(stage.spec, granularity="SEGMENT")
                    elif field == "dependencies": stage.dependencies = ()
                    elif field == "observations":
                        stage.observations = [replace(stage.observations[0], end_us=350000),
                            stage.observations[1]]
                    elif field == "omissions": stage.omissions = [SourceOmission(0, self.bindings[0])]
                    elif field == "storage": stage.storage = LocalNarrationByteStore({self.asset.asset_id: self.path})
                    elif field == "gate": stage.gate = FakeGate()
                    elif field == "dependency_evidence": manifest.processing[0].dependency_signature = "a" * 64
                    else: setattr(stage, field, "changed")
                    return result
                with patch.object(engine, "verify_audio", side_effect=verify):
                    outcome = stage.execute(StageContext(manifest, CancellationToken(), 1, lambda *a: None))
                self.assertEqual(outcome.result.status, StageStatus.FAILED)
                self.assertIsNone(outcome.update)
                self.assertEqual(len(gate.requests), 0)
                if field == "gate": self.assertEqual(len(stage.gate.requests), 0)

    def test_stage_unchanged_declaration_gate_once(self):
        outcome = self.stage().execute(StageContext(self.narration, CancellationToken(), 1, lambda *a: None))
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        self.assertEqual(len(self.gate.requests), 1)

    def test_stage_declaration_scalar_capture_and_reuse_mutation(self):
        for field in ("acceptance_policy_id", "acceptance_policy_version", "spec",
                "dependencies", "observations", "omissions", "stage_id", "stage_version"):
            with self.subTest(field=field):
                stage, manifest, previous = self.reusable()
                captured = stage._declaration()
                self.assertIs(type(captured), str)
                if field == "spec": stage.spec = replace(stage.spec, granularity="SEGMENT")
                elif field == "dependencies": stage.dependencies = ("semantic_story",)
                elif field == "observations": stage.observations = list(reversed(stage.observations))
                elif field == "omissions": stage.omissions = [SourceOmission(0, self.bindings[0])]
                else: setattr(stage, field, "changed")
                self.assertFalse(stage.validate_reuse(manifest, previous))
                self.assertIs(type(captured), str)

    def test_stage_final_declaration_fence(self):
        from creator_studio.voice_timing import engine
        for verification in (2, 3):
            with self.subTest(verification=verification):
                gate = FakeGate()
                stage = self.stage(gate=gate)
                original = engine.verify_audio
                calls = 0
                def verify(*args, **kwargs):
                    nonlocal calls
                    result = original(*args, **kwargs)
                    calls += 1
                    if calls == verification: stage.acceptance_policy_version = "changed"
                    return result
                with patch.object(engine, "verify_audio", side_effect=verify):
                    outcome = stage.execute(StageContext(self.narration, CancellationToken(), 1, lambda *a: None))
                self.assertEqual(outcome.result.status, StageStatus.FAILED)
                self.assertIsNone(outcome.update)
                self.assertEqual(len(gate.requests), 1)

    def test_actual_overlong_header_rejected_before_payload(self):
        size = (MAX_SECONDS + 1) * 8000 * 2
        data = bytearray(wav(rate=8000, payload=b"\x00\x00")[:44])
        struct.pack_into("<I", data, 4, 36 + size)
        struct.pack_into("<I", data, 40, size)
        with self.assertRaises(VoiceTimingError):
            inspect_stream(io.BytesIO(data))

    def test_duplicate_layout_with_correct_riff_size(self):
        good = wav()
        for body in (good[8:] + good[36:], good[8:36] + good[12:36] + good[36:],
            good[8:36] + b"JUNK\x00\x00\x00\x00" + good[36:]):
            with self.subTest(length=len(body)), self.assertRaises(VoiceTimingError):
                inspect_stream(io.BytesIO(b"RIFF" + struct.pack("<I", len(body)) + body))

    def test_empty_normalized_tokens_not_matches(self):
        with self.assertRaises(VoiceTimingError):
            self.build(observations=[replace(self.observations[0], observed_text="!",
                mapping_status=MappingStatus.NORMALIZED_MATCH)])

    def test_new_revision_clears_alignment_without_history_loss(self):
        first = self.build()
        second = register_narration(first, self.asset, storage=self.store, logical_revision=2)
        self.assertEqual(second.voice_timing.runs, first.voice_timing.runs)
        self.assertIsNone(second.voice_timing.active_alignment_run_id)
        self.assertFalse(self.eligibility(second).active_alignment_pointer)

    def test_semantic_locator_does_not_enter_identity(self):
        from creator_studio.manifest.semantic import SemanticSourceRevision
        first = deepcopy(self.narration)
        second = deepcopy(self.narration)
        for manifest, locator in ((first, "C:/first/source.txt"), (second, "D:/relocated/source.txt")):
            source = manifest.semantic.source_revisions[0]
            record = replace(source.content, source_locator=locator)
            manifest.semantic.source_revisions[0] = SemanticSourceRevision(source.source_revision_id,
                record, exact_signature(record))
        self.assertFalse(validate(first))
        self.assertFalse(validate(second))
        self.assertEqual(active_run(self.build(first)), active_run(self.build(second)))

    def test_orchestrator_registration_run_and_active_reuse(self):
        from creator_studio.manifest import save, load
        from creator_studio.orchestrator import ProjectOrchestrator, ManifestRepository
        path = Path(self.temp.name) / "manifest.json"
        save(self.narration, path)
        runner = ProjectOrchestrator(ManifestRepository(path))
        runner.register(self.stage())
        runner.run()
        first = load(path)
        self.assertEqual(first.processing[0].execution.status, StageStatus.SUCCEEDED)
        self.assertEqual(len(self.gate.requests), 1)
        runner.run()
        second = load(path)
        self.assertEqual(second.processing[0].execution.status, StageStatus.SKIPPED)
        self.assertEqual(first.voice_timing, second.voice_timing)
        self.assertEqual(len(self.gate.requests), 1)

    def test_import_graph_prohibited_runtime_dependencies(self):
        # Resolve project-local import edges statically, including package initializers.
        # This checks transitive dependencies without importing optional runtime stacks.
        import importlib.util
        pending = ["creator_studio.voice_timing", "creator_studio.manifest.voice_timing_validation"]
        visited = set()
        forbidden = {"pyqt6", "pipeline", "stock", "subprocess", "requests", "httpx", "urllib",
            "whisper", "tts", "renderer", "ffmpeg", "socket", "gui"}
        while pending:
            module = pending.pop()
            if module in visited:
                continue
            visited.add(module)
            parts = module.split(".")
            path = Path(*parts).with_suffix(".py")
            package_file = Path(*parts) / "__init__.py"
            is_package = package_file.exists()
            if is_package:
                path = package_file
            if not path.exists():
                continue
            package = module if is_package else module.rpartition(".")[0]
            for i in range(1, len(parts)):
                pending.append(".".join(parts[:i]))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                targets = []
                if isinstance(node, ast.Import):
                    targets = [n.name for n in node.names]
                elif isinstance(node, ast.ImportFrom):
                    target = node.module or ""
                    if node.level:
                        target = importlib.util.resolve_name("." * node.level + target, package)
                    targets = [target]
                for target in targets:
                    self.assertFalse(set(target.lower().split(".")) & forbidden, (module, target))
                    if target.startswith("creator_studio"):
                        pending.append(target)


    def test_preverification_fence(self):
        from creator_studio.voice_timing import engine
        for field in ("narration", "semantic", "observations", "spec", "processing"):
            manifest, obs, spec, gate = deepcopy(self.narration), list(self.observations), AlignmentSpec(), FakeGate()
            snapshots = []
            original = engine.verify_audio
            def verify(*args, **kwargs):
                result = original(*args, **kwargs)
                if field == "narration": manifest.voice_timing.active_narration_revision_id = None
                elif field == "semantic": manifest.semantic.active_creator_document_id = None
                elif field == "observations": obs.reverse()
                elif field == "spec": object.__setattr__(spec, "granularity", "changed")
                else: manifest.processing.append(ProcessingState(stage="voice_timing"))
                snapshots.append(deepcopy(manifest))
                return result
            with self.subTest(field=field), patch.object(engine, "verify_audio", side_effect=verify):
                with self.assertRaises(VoiceTimingError):
                    self.build(manifest, observations=obs, spec=spec, gate=gate)
            self.assertEqual(gate.requests, [])
            self.assertEqual(manifest, snapshots[0])

    def test_public_capacity_before_recursive_typing(self):
        from creator_studio.manifest.validation import require_valid, ManifestValidationError
        manifest = deepcopy(self.narration)
        manifest.voice_timing.assets = [self.asset] * 65
        with patch("creator_studio.manifest.validation.check_typed", side_effect=AssertionError("deep traversal")) as typed:
            self.assertEqual(validate(manifest)[0].code, "voice_timing_invalid")
            with self.assertRaises(ManifestValidationError):
                require_valid(manifest)
            typed.assert_not_called()

    def test_reuse_capacity_before_manifest_signature(self):
        stage, manifest, previous = self.reusable()
        manifest.voice_timing.assets = [self.asset] * 65
        with patch("creator_studio.voice_timing.stage.exact_signature", side_effect=AssertionError("serialization")) as sig:
            self.assertFalse(stage.validate_reuse(manifest, previous))
            sig.assert_not_called()

    def test_malformed_shallow_preflight_defers_to_strict_typing(self):
        from creator_studio.manifest.voice_timing_validation import preflight_history
        run = active_run(self.build())
        cases = [VoiceTimingState(assets="not-a-list"), VoiceTimingState(runs=None)]
        cases += [VoiceTimingState(runs=[value]) for value in ({}, "bad", 1)]
        cases += [VoiceTimingState(runs=[replace(run, units=value)]) for value in (None, "bad", {})]
        cases += [VoiceTimingState(runs=[replace(run, units=[replace(run.units[0], source_bindings=value)])])
                  for value in (None, "bad", {})]
        for state in cases:
            with self.subTest(state=state):
                preflight_history(state)
                manifest = deepcopy(self.narration)
                manifest.voice_timing = state
                errors = validate(manifest)
                self.assertEqual(errors[0].code, "contract")
                self.assertIn("voice_timing", errors[0].message)

    def test_shallow_capacity_exact_boundaries(self):
        from creator_studio.manifest import voice_timing_validation as v
        for field, limit in (("assets", MAX_ASSETS), ("revisions", MAX_REVISIONS), ("runs", MAX_RUNS)):
            state = VoiceTimingState()
            setattr(state, field, [None] * limit)
            v.preflight_history(state)
            getattr(state, field).append(None)
            with self.assertRaises(ValueError): v.preflight_history(state)
        run = active_run(self.build())
        run = replace(run, omissions=[SourceOmission(0, self.bindings[0])])
        state = VoiceTimingState(runs=[run])
        for constant, exact in (("MAX_UNITS", 2), ("MAX_TOTAL_UNITS", 2),
                ("MAX_BINDINGS", 3), ("MAX_TOTAL_BINDINGS", 3),
                ("MAX_ISSUES", 1), ("MAX_TOTAL_ISSUES", 1)):
            with self.subTest(constant=constant), patch.object(v, constant, exact):
                v.preflight_history(state)
            with patch.object(v, constant, exact - 1):
                with self.assertRaises(ValueError): v.preflight_history(state)
        aggregate = VoiceTimingState(runs=[run, run])
        for constant, exact in (("MAX_TOTAL_UNITS", 4), ("MAX_TOTAL_BINDINGS", 6),
                                ("MAX_TOTAL_ISSUES", 2)):
            with self.subTest(aggregate=constant), patch.object(v, constant, exact):
                v.preflight_history(aggregate)
            with patch.object(v, constant, exact - 1):
                with self.assertRaises(ValueError): v.preflight_history(aggregate)
        unit = replace(run.units[0], source_bindings=[self.bindings[0]] * 8)
        v.preflight_history(VoiceTimingState(runs=[replace(run, units=[unit])]))
        with self.assertRaises(ValueError):
            v.preflight_history(VoiceTimingState(runs=[replace(run, units=[replace(unit,
                source_bindings=unit.source_bindings + [self.bindings[0]])])]))

    def test_valid_cross_record_replay_and_locator_neutrality(self):
        from creator_studio.manifest.validation import require_valid
        from creator_studio.manifest.voice_timing_validation import source_record_fingerprint
        from creator_studio.manifest.content import ContentProvenance
        from creator_studio.voice_timing.engine import semantic_binding
        stage, retained, previous = self.reusable()
        require_valid(retained)
        source_a = retained.semantic.source_revisions[0].content
        for changes in ({"text": "\ufeffHello hello.\r\n"},
                        {"text": "Hello hello.", "provenance": ContentProvenance.IMPORTED_OWNED}):
            with self.subTest(changes=changes):
                request = IngestRequest("source_b", language="en", **changes)
                replay = build_semantic_story(apply_ingest(retained, ingest(request)))
                require_valid(replay)
                document = next(d for d in replay.semantic.documents
                    if d.semantic_document_id == replay.semantic.active_creator_document_id)
                source_b = next(s.content for s in replay.semantic.source_revisions
                    if s.source_revision_id == document.source_revision_id)
                self.assertEqual(source_a.normalized_text, source_b.normalized_text)
                self.assertNotEqual(source_record_fingerprint(source_a), source_record_fingerprint(source_b))
                self.assertEqual(replay.voice_timing, retained.voice_timing)
                self.assertNotEqual(semantic_binding(replay)[1], active_run(replay).source_record_fingerprint)
                eligibility = self.eligibility(replay)
                self.assertTrue(eligibility.historical_validity)
                self.assertTrue(eligibility.audio_usability)
                self.assertFalse(eligibility.current_semantic_binding)
                self.assertFalse(eligibility.eligible)
                self.assertFalse(stage.validate_reuse(replay, previous))
        relocation = ingest(IngestRequest("creator", text="Hello hello.", language="en"))
        relocation = replace(relocation, content=replace(relocation.content,
            source_locator="D:/relocated/source.txt"))
        relocated = build_semantic_story(apply_ingest(retained, relocation))
        require_valid(relocated)
        self.assertEqual(source_record_fingerprint(source_a),
            source_record_fingerprint(relocated.content.records[0]))
        self.assertTrue(self.eligibility(relocated).eligible)
        self.assertTrue(stage.validate_reuse(relocated, previous))

    def test_early_history_capacity(self):
        from creator_studio.manifest import voice_timing_validation as v
        manifest = deepcopy(self.narration)
        manifest.voice_timing.assets = [self.asset] * 65
        with patch.object(v, "check_typed") as typed:
            with self.assertRaises(ValueError): validate_history(manifest)
            typed.assert_not_called()
        with patch("creator_studio.voice_timing.engine.require_valid") as full:
            with self.assertRaises(VoiceTimingError): self.build(manifest)
            full.assert_not_called()
        manifest = self.build()
        run = active_run(manifest)
        manifest.voice_timing.runs = [replace(run, omissions=[SourceOmission(0, self.bindings[0])])]
        for limit in ("MAX_TOTAL_UNITS", "MAX_TOTAL_BINDINGS", "MAX_TOTAL_ISSUES",
                      "MAX_UNITS", "MAX_BINDINGS", "MAX_ISSUES"):
            with self.subTest(limit=limit), patch.object(v, limit, 0), patch.object(v, "check_typed") as typed:
                with self.assertRaises(ValueError): validate_history(manifest)
                typed.assert_not_called()
        manifest.voice_timing.runs = [replace(run, units=[replace(run.units[0], source_bindings=self.bindings * 5)])]
        with patch.object(v, "check_typed") as typed:
            with self.assertRaises(ValueError): validate_history(manifest)
            typed.assert_not_called()

    def test_early_runtime_capacity(self):
        from creator_studio.voice_timing import engine
        cases = [([self.observations[0]] * 100001, ()),
            ([replace(self.observations[0], source_bindings=(self.bindings[0],) * 8)] * 25001, ()),
            ([replace(self.observations[0], source_bindings=(self.bindings[0],) * 9)], ()),
            (self.observations, [SourceOmission(0, self.bindings[0])] * 100001)]
        before = deepcopy(self.narration)
        for obs, omissions in cases:
            with patch.object(engine, "observation_signature") as sig, patch.object(engine, "TimedUnit") as unit:
                with self.assertRaises(VoiceTimingError): self.build(observations=obs, omissions=omissions)
                sig.assert_not_called()
                unit.assert_not_called()
        self.assertEqual(before, self.narration)

    def test_preflight_cancellation(self):
        from creator_studio.voice_timing import engine
        from creator_studio.manifest.voice_timing_validation import preflight_history
        before = deepcopy(self.narration)
        with patch.object(engine, "observation_signature") as sig:
            with self.assertRaises(Cancelled):
                self.build(observations=[self.observations[0]] * 1000, control=CountingControl(5))
            sig.assert_not_called()
        manifest = self.build()
        run = active_run(manifest)
        manifest.voice_timing.runs = [replace(run, units=[run.units[0]] * 1000)]
        with self.assertRaises(Cancelled): preflight_history(manifest.voice_timing, CountingControl(4))
        self.assertEqual(before, self.narration)

    def test_fingerprint_field_sensitivity_and_replay(self):
        from creator_studio.manifest.content import SourceType, ContentProvenance, IngestDiagnostic
        from creator_studio.manifest.semantic import SemanticSourceRevision
        from creator_studio.manifest.voice_timing_validation import source_record_fingerprint, semantic_evidence
        from creator_studio.voice_timing.engine import semantic_binding
        record = self.narration.semantic.source_revisions[0].content
        fingerprint = source_record_fingerprint(record)
        self.assertEqual(fingerprint, source_record_fingerprint(replace(record, source_locator="elsewhere")))
        changes = dict(content_id="other", source_type=SourceType.TEXT_FILE,
            original_text="Hello  hello.", normalized_text="Changed", revision_signature="a" * 64,
            provenance=ContentProvenance.IMPORTED_OWNED, language="vi", title="Other",
            normalization_version="2", diagnostics=[IngestDiagnostic("other")])
        stage, retained, previous = self.reusable()
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = replace(record, source_locator="elsewhere", **{field: value})
                self.assertNotEqual(fingerprint, source_record_fingerprint(changed))
                replay = deepcopy(retained)
                source = replay.semantic.source_revisions[0]
                replay.semantic.source_revisions[0] = SemanticSourceRevision(source.source_revision_id,
                    changed, exact_signature(changed))
                with self.assertRaises(ValueError): semantic_evidence(replay, active_run(replay))
                self.assertFalse(stage.validate_reuse(replay, previous))
                self.assertFalse(self.eligibility(replay).eligible)
                try: binding = semantic_binding(replay)
                except VoiceTimingError: pass
                else: self.assertNotEqual(binding[1], fingerprint)


def add_case(name, function):
    function.__name__ = "test_" + name
    setattr(VoiceTimingTests, function.__name__, function)

for field, limit in (("assets", MAX_ASSETS), ("revisions", MAX_REVISIONS), ("runs", MAX_RUNS)):
    def case(self, field=field, limit=limit):
        result = self.build()
        getattr(result.voice_timing, field).extend([getattr(result.voice_timing, field)[0]] * limit)
        self.assertTrue(voice_timing_errors(result))
    add_case("history_limit_" + field, case)

for bound, small in (("MAX_UNITS", 1), ("MAX_TOTAL_UNITS", 1),
    ("MAX_BINDINGS", 1), ("MAX_TOTAL_BINDINGS", 1)):
    def case(self, bound=bound, small=small):
        result = self.build()
        with patch("creator_studio.manifest.voice_timing_validation." + bound, small):
            self.assertTrue(voice_timing_errors(result))
    add_case("enforced_" + bound.lower(), case)

for bound in ("MAX_ISSUES", "MAX_TOTAL_ISSUES"):
    def case(self, bound=bound):
        result = self.build(observations=self.observations[:1], omissions=[SourceOmission(0, self.bindings[1])])
        with patch("creator_studio.manifest.voice_timing_validation." + bound, 0):
            self.assertTrue(voice_timing_errors(result))
    add_case("enforced_" + bound.lower(), case)

for field in ("byte_count", "format_tag", "channels", "bits_per_sample", "sample_width", "sample_rate",
    "block_align", "byte_rate", "data_byte_count", "frame_count", "duration_us"):
    def case(self, field=field):
        from creator_studio.manifest.voice_timing_validation import validate_inspection
        for bad in (True, 1.0):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                validate_inspection(replace(self.inspection, **{field: bad}))
    add_case("inspection_exact_integer_" + field, case)

for field in ("asset_id", "sha256", "byte_count", "frame_count", "duration_us", "policy_id",
    "compression", "origin_policy", "contract_version", "evidence_signature"):
    def case(self, field=field):
        result = self.build()
        run = active_run(result)
        value = getattr(run.inspection, field)
        inspection = replace(run.inspection, **{field: value + 1 if type(value) is int else "wrong"})
        result.voice_timing.runs[0] = replace(run, inspection=inspection)
        self.assertTrue(voice_timing_errors(result))
    add_case("inspection_tamper_" + field, case)

for field, value in (("voice_timing", None), ("voice_timing", []), ("voice_timing", {}),
                     ("voice_timing", {"unknown": 1})):
    def case(self, value=value):
        data = to_data(self.base)
        data["voice_timing"] = value
        with self.assertRaises(ValueError):
            decode(ProjectManifest, migrate_document(data))
    add_case("malformed_present_" + str(len(VoiceTimingTests.__dict__)), case)

for field in ("assets", "revisions", "runs", "active_narration_revision_id", "active_alignment_run_id"):
    def case(self, field=field):
        data = to_data(self.build())
        data["voice_timing"][field + "_unknown"] = data["voice_timing"][field]
        with self.assertRaises(ValueError):
            decode(ProjectManifest, data)
    add_case("unknown_state_field_" + field, case)

for name, changes in {
    "float_start": {"start_us": 1.0}, "float_end": {"end_us": 200000.0},
    "boolean_start": {"start_us": True}, "boolean_end": {"end_us": True},
    "boolean_ordinal": {"ordinal": False}, "negative_start": {"start_us": -1},
    "zero_duration": {"end_us": 100000}, "reversed": {"end_us": 99999},
    "wrong_order": {"ordinal": 1}, "out_of_bounds": {"end_us": 1000001},
    "source_replay": {"source_bindings": ()},
    "coarse_precision": {"granularity": "SEGMENT"},
    "variant_without_evidence": {"mapping_status": MappingStatus.EXPLICIT_VARIANT},
    "approximate_exact": {"observed_text": "greeting"},
    "approximate_normalized": {"observed_text": "greeting", "mapping_status": MappingStatus.NORMALIZED_MATCH},
    "added_with_source": {"mapping_status": MappingStatus.SPEECH_ADDED},
    "unmapped_with_source": {"mapping_status": MappingStatus.UNMAPPED},
    "omitted_with_time": {"mapping_status": MappingStatus.SOURCE_OMITTED},
    "too_many_bindings": {"source_bindings": tuple([SourceBinding("x", "x", "x", 0, 1, "x")] * 9)},
}.items():
    def case(self, changes=changes):
        before = deepcopy(self.narration)
        with self.assertRaises(VoiceTimingError):
            self.build(observations=[replace(self.observations[0], **changes), self.observations[1]])
        self.assertEqual(self.narration, before)
    add_case("invalid_observation_" + name, case)

for name, changes in {
    "overlap": {"start_us": 299999}, "reversed_order": {"start_us": 0},
    "replayed_span": {"source_bindings": None},
}.items():
    def case(self, changes=changes):
        changes = dict(changes)
        if "source_bindings" in changes:
            changes["source_bindings"] = self.observations[0].source_bindings
            changes["observed_text"] = "Hello"
        with self.assertRaises(VoiceTimingError):
            self.build(observations=[self.observations[0], replace(self.observations[1], **changes)])
    add_case(name, case)

for field, value in (("start_char", 1), ("end_char", 4), ("excerpt_signature", "a" * 64),
    ("source_revision_id", "wrong"), ("semantic_document_id", "wrong"), ("story_unit_id", "wrong")):
    def case(self, field=field, value=value):
        binding = replace(self.bindings[0], **{field: value})
        with self.assertRaises(VoiceTimingError):
            self.build(observations=[replace(self.observations[0], source_bindings=(binding,))])
    add_case("binding_tamper_" + field, case)

for field in ("acceptance_policy_id", "acceptance_policy_version", "request_signature", "input_signature", "output_signature", "receipt_id", "contract_version"):
    def case(self, field=field):
        class WrongGate:
            def accept(self, request):
                return replace(make_receipt(request), **{field: "wrong"})
        with self.assertRaises(VoiceTimingError):
            self.build(gate=WrongGate())
    add_case("receipt_tamper_" + field, case)

for value in (None, {}, "trusted", True):
    def case(self, value=value):
        class WrongGate:
            def accept(self, request):
                return value
        with self.assertRaises(VoiceTimingError):
            self.build(gate=WrongGate())
    add_case("malformed_receipt_" + str(value), case)

for field in ("content", "semantic", "voice_timing", "timeline", "media", "voice", "subtitle_tracks", "scenes", "editing"):
    def case(self, field=field):
        def mutate(request):
            if field == "content":
                self.narration.content.script = "changed"
            elif field == "semantic":
                self.narration.semantic.active_creator_document_id = None
            elif field == "voice_timing":
                self.narration.voice_timing.active_narration_revision_id = None
            elif field == "voice":
                self.narration.voice.style = "changed"
            elif field == "editing":
                self.narration.editing.active_creator_edit_plan_id = "changed"
            else:
                getattr(self.narration, field).append(None)
        with self.assertRaises(VoiceTimingError):
            self.build(gate=FakeGate(mutate))
    add_case("callback_mutation_" + field, case)

for field in ("contract_version", "granularity", "time_unit", "overlap_policy", "normalization_policy", "source_coordinates", "matching_policy"):
    def case(self, field=field):
        changed = replace(AlignmentSpec(), **{field: "wrong"})
        result = self.build()
        self.assertFalse(self.eligibility(result, spec=changed).current_alignment_spec)
        with self.assertRaises(VoiceTimingError):
            self.build(spec=changed)
    add_case("spec_bound_" + field, case)

for field in ("acceptance_policy_id", "acceptance_policy_version"):
    def case(self, field=field):
        self.assertFalse(self.eligibility(self.build(), **{field: "changed"}).current_acceptance_policy)
    add_case("policy_stale_" + field, case)

for name in ("tuple", "iterator", "generator", "standalone"):
    def case(self, name=name):
        deps = {"tuple": ("semantic_story",), "iterator": iter(("semantic_story",)),
            "generator": (s for s in ("semantic_story",)), "standalone": ()}[name]
        self.assertEqual(self.stage(dependencies=deps).dependencies,
            () if name == "standalone" else ("semantic_story",))
    add_case("dependency_" + name, case)

for deps in (("edit_planning",), ("semantic_story", "semantic_story"), ("wrong",), ("semantic_story", "edit_planning"), "semantic_story"):
    def case(self, deps=deps):
        with self.assertRaises(ValueError):
            self.stage(dependencies=deps)
    add_case("invalid_dependency_" + str(len(VoiceTimingTests.__dict__)), case)

for name in ("missing", "extra", "order", "reference", "signature", "path", "url", "inactive"):
    def case(self, name=name):
        stage, manifest, previous = self.reusable()
        if name == "missing": previous.artifacts.pop()
        elif name == "extra": previous.artifacts.append(deepcopy(previous.artifacts[0]))
        elif name == "order": previous.artifacts.reverse()
        elif name == "signature": previous.artifacts[0].signature = "a" * 64
        elif name == "inactive": manifest.voice_timing.active_alignment_run_id = None
        else: previous.artifacts[0].reference = {"path": "C:/private", "url": "https://invalid.example", "reference": "wrong"}[name]
        self.assertFalse(stage.validate_reuse(manifest, previous))
    add_case("reuse_artifact_" + name, case)

for field in ("editing", "timeline", "media", "voice", "subtitle_tracks", "scenes", "content", "semantic", "visual_planning", "acquisition", "selection", "retrieval", "audio", "processing"):
    def case(self, field=field):
        result = self.build()
        self.assertEqual(getattr(result, field), getattr(self.narration, field))
    add_case("canonical_preserved_" + field, case)

for field in ("alignment_run_id", "input_signature", "output_signature", "request_signature", "source_record_fingerprint", "semantic_generated_binding", "narration_revision_id"):
    def case(self, field=field):
        result = self.build()
        result.voice_timing.runs[0] = replace(active_run(result), **{field: "wrong"})
        self.assertTrue(voice_timing_errors(result))
    add_case("historical_tamper_" + field, case)

for field in ("unit_id", "ordinal", "observed_signature", "normalized_signature"):
    def case(self, field=field):
        result = self.build()
        run = active_run(result)
        run.units[0] = replace(run.units[0], **{field: 1 if field == "ordinal" else "wrong"})
        self.assertTrue(voice_timing_errors(result))
    add_case("historical_unit_tamper_" + field, case)

def wav_invalid_cases():
    good = wav()
    yield "riff", b"RIFX" + good[4:]
    yield "wave", good[:8] + b"NOPE" + good[12:]
    yield "declared_size", good[:4] + struct.pack("<I", len(good)) + good[8:]
    yield "trailing", good + b"extra"
    yield "truncated_payload", good[:-2]
    yield "zero_frames", wav(payload=b"")
    yield "non_pcm", wav(tag=3)
    yield "extensible", wav(tag=65534)
    yield "compressed", wav(tag=2)
    yield "rate", wav(rate=12345)
    yield "channels", wav(channels=3)
    yield "bits", wav(bits=12)
    yield "align", wav(align=3)
    yield "byte_rate", wav(byte_rate=42)
    yield "partial_frame", wav(payload=b"x")
    yield "missing_pad", wav(payload=b"x", bits=8, pad=False)
    yield "nonzero_pad", wav(payload=b"x", bits=8)[:-1] + b"x"
    yield "fmt_length", good[:16] + struct.pack("<I", 18) + good[20:]
    yield "duplicate_fmt", good[:36] + good[12:36] + good[36:]
    yield "duplicate_data", good + good[36:]
    yield "ancillary", good[:36] + b"JUNK\x00\x00\x00\x00" + good[36:]
    yield "rf64", b"RF64" + good[4:]
    yield "mp3", b"ID3" + b"x" * 100
    yield "aac", b"\xff\xf1" + b"x" * 100
    yield "container", b"\x00\x00\x00\x18ftypM4A " + b"x" * 100
    yield "huge_declared", good[:4] + struct.pack("<I", MAX_BYTES) + good[8:]
    yield "too_long", wav(rate=8000, payload=b"\x00" * 2)[:40] + struct.pack("<I", 8000 * 2 * (MAX_SECONDS + 1))

for name, data in wav_invalid_cases():
    def case(self, data=data):
        with self.assertRaises(VoiceTimingError):
            inspect_stream(io.BytesIO(data))
    add_case("wav_reject_" + name, case)

for rate in RATES:
    def case(self, rate=rate):
        _, evidence = inspect_stream(io.BytesIO(wav(rate=rate, payload=b"\x00\x00")))
        self.assertEqual(evidence.sample_rate, rate)
    add_case("wav_supported_rate_" + str(rate), case)

for channels in (1, 2):
    for bits in (8, 16, 24, 32):
        def case(self, channels=channels, bits=bits):
            _, evidence = inspect_stream(io.BytesIO(wav(channels=channels, bits=bits,
                payload=b"\x00" * (channels * bits // 8))))
            self.assertEqual(evidence.frame_count, 1)
        add_case("wav_supported_" + str(channels) + "_" + str(bits), case)

if __name__ == "__main__":
    unittest.main()
