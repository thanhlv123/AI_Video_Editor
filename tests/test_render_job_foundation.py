"""Synthetic offline M74 boundary, evidence, lane and graph-safety tests."""
import ast
from copy import deepcopy
from dataclasses import fields, replace, FrozenInstanceError
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from creator_studio.manifest import ProjectManifest
from creator_studio.manifest.codec import to_data
from creator_studio.manifest.render_preparation import (
    PreparationRequirement, PreparationConclusion, OutputProfile,
    RenderPreparationSpec, PreparationPolicy, assign_identity)
from creator_studio.manifest.render_timeline import (SourceUsage, RenderTimelineOutcome,
    RenderDiagnostic, signed as timeline_signed)
from creator_studio.manifest.retrieval import VisualMediaKind
from creator_studio.manifest.placement_timing import PlacementTimingOutcome
from creator_studio.manifest.validation import ManifestValidationError, require_valid as manifest_require_valid
from creator_studio.manifest.acquisition import AcquisitionOutcome
from creator_studio.manifest.acquisition import AcquisitionSpec
from creator_studio.manifest.editing import EditSpec
from creator_studio.manifest.placement_timing import PlacementTimingSpec
from creator_studio.manifest.render_timeline import RenderTimelineSpec
from creator_studio.manifest.voice_timing import AlignmentSpec
from creator_studio.render_job import *
from creator_studio.render_job import models as domain, validation as validation
from creator_studio.render_job.engine import build_render_job_draft
from creator_studio.render_job import engine as job_engine
import tests.test_render_preparation_foundation as upstream

ROOT = Path(__file__).resolve().parents[1]
PROFILE = upstream.PROFILE
SPEC = upstream.SPEC

class RenderJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upstream.RenderPreparationTests.setUpClass()
        cls.addClassCleanup(upstream.RenderPreparationTests.doClassCleanups)
        fixture = upstream.RenderPreparationTests()
        fixture.setUp()
        cls.base = fixture.build()
        cls.configuration = dict(fixture.config)
        for key, value in dict(acquisition_spec=AcquisitionSpec(), edit_spec=EditSpec(),
            timing_spec=PlacementTimingSpec(), timeline_spec=RenderTimelineSpec(),
            voice_spec=AlignmentSpec()).items():
            cls.configuration.setdefault(key, value)
        cls.draft = build_render_job_draft(cls.base, output_profile=PROFILE, spec=SPEC,
                                         **cls.configuration)

    def setUp(self):
        self.m = deepcopy(self.base)
        self.config = deepcopy(self.configuration)

    def build(self, manifest=None, **kwargs):
        return build_render_job_draft(self.m if manifest is None else manifest,
            output_profile=kwargs.pop("output_profile", PROFILE), spec=kwargs.pop("spec", SPEC),
            **dict(self.config, **kwargs))

    def test_schema_unaffected(self):
        m = ProjectManifest("synthetic")
        self.assertEqual(m.schema_version, 2)
        self.assertFalse(any("render_job" in f.name for f in fields(m)))
        self.assertEqual(m.processing, [])
        from creator_studio.manifest.migrations import migrate_document
        self.assertEqual(migrate_document(to_data(m)), to_data(m))

    def test_missing_active(self):
        self.m.render_preparation.active_render_preparation_plan_id = None
        with self.assertRaises(ValueError):
            self.build()

    def test_missing_plans(self):
        self.m.render_preparation.plans.clear()
        with self.assertRaises(ValueError):
            self.build()

    def test_inactive_plan(self):
        self.m.render_timeline.active_render_timeline_plan_id = None
        with self.assertRaises(ValueError):
            self.build()

    def test_stale_profile(self):
        with self.assertRaises(ValueError):
            self.build(output_profile=OutputProfile(1, 1, 24, 1))

    def test_exact_expected_configuration(self):
        for name, wrong in dict(edit_spec=replace(EditSpec(), engine_version="9"),
                acceptance_policy_id="different", voice_acceptance_policy_id="different",
                timeline_spec=replace(RenderTimelineSpec(), engine_version="9")).items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.build(**{name: wrong})

    def test_expected_spec_mismatch(self):
        with self.assertRaises(ValueError):
            self.build(spec=replace(SPEC, engine_version="9"))

    def test_explicit_configuration_required(self):
        with self.assertRaises(ValueError):
            build_render_job_draft(self.m, output_profile=PROFILE, spec=SPEC)

    def test_current_eligibility_required(self):
        with patch("creator_studio.render_preparation.engine.current_logically_eligible", return_value=False):
            with self.assertRaises(ValueError):
                self.build()

    def test_no_runtime_observation(self):
        targets = ("creator_studio.render_preparation.engine.assess_render_preparation",
            "creator_studio.render_timeline.engine.observe_media_usability",
            "creator_studio.render_timeline.engine.current_render_timeline_eligibility",
            "creator_studio.voice_timing.engine.current_timing_eligibility",
            "creator_studio.voice_timing.engine.verify_audio",
            "creator_studio.acquisition.engine.current_usability",
            "creator_studio.acquisition.engine.inspect_media")
        from contextlib import ExitStack
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError("observation")))
            self.assertEqual(self.build(), self.draft)

    def test_blocked_spec_denied(self):
        self.assertTrue(self.draft.requirements)
        with self.assertRaises(ValueError):
            construct_render_job_spec(self.m, self.draft, output_profile=PROFILE,
                                      spec=SPEC, **self.config)

    def test_detached_only_spec_construction_denied(self):
        with self.assertRaises(TypeError):
            construct_render_job_spec(self.draft)

    def test_live_spec_construction_exact_equality_gate(self):
        manifest_before = deepcopy(self.m)
        draft_before = deepcopy(self.draft)
        # The valid live draft passes the identity gate and reaches the detached
        # completeness validator, where current M73 presentation blockers deny it.
        with patch.object(job_engine, "validate_spec_job", wraps=validate_spec_job) as checked:
            with self.assertRaises(RenderJobError):
                construct_render_job_spec(self.m, self.draft, output_profile=PROFILE,
                                          spec=SPEC, **self.config)
        checked.assert_called_once()
        self.assertEqual(self.m, manifest_before)
        self.assertEqual(self.draft, draft_before)

    def test_live_spec_construction_requires_expected_configuration(self):
        with self.assertRaises(RenderJobError):
            construct_render_job_spec(self.m, self.draft, output_profile=PROFILE, spec=SPEC)

    def test_forged_removed_blocker(self):
        entry = replace(self.draft.entry_assessments[0], requirements=())
        with self.assertRaises(ValueError):
            validate_draft(replace(self.draft, entry_assessments=(entry,) + self.draft.entry_assessments[1:]))

    def test_forged_upstream_conclusion(self):
        plan = self.m.render_preparation.plans[0]
        self.m.render_preparation.plans[0] = assign_identity(replace(plan,
            requirements=[], conclusion=PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED))
        with self.assertRaises(ValueError):
            self.build()

    def test_success_atomicity_and_detachment(self):
        before = deepcopy(self.m)
        draft = self.build()
        self.assertEqual(self.m, before)
        self.assertEqual(draft, self.build())
        self.m.render_preparation.plans[0].requirements.clear()
        self.m.render_preparation.plans[0].entries[0].requirements.clear()
        self.m.render_timeline.plans[0].entries[0].diagnostics.clear()
        self.assertEqual(draft, self.draft)
        self.assertIsNot(draft.output_profile, self.base.render_preparation.plans[0].output_profile)

    def test_failure_atomicity(self):
        before = deepcopy(self.m)
        with self.assertRaises(ValueError):
            self.build(output_profile=OutputProfile(True, 1, 1, 1))
        self.assertEqual(self.m, before)

    def test_frozen_and_tuples(self):
        with self.assertRaises(FrozenInstanceError):
            self.draft.output_duration_us = 2
        for name in ("visual_clips", "entry_assessments", "requirements", "uncovered_intervals", "lane_reasons"):
            self.assertIs(type(getattr(self.draft, name)), tuple)
        self.assertIs(type(self.draft.entry_assessments[0].requirements), tuple)
        self.assertIs(type(self.draft.visual_clips[0].diagnostics), tuple)

    def test_list_alias_rejected(self):
        with self.assertRaises(ValueError):
            validate_draft(replace(self.draft, visual_clips=list(self.draft.visual_clips)))

    def test_assessment_separation(self):
        detached = assess_render_job_draft(self.draft)
        live = assess_current_render_job(self.m, output_profile=PROFILE, spec=SPEC, **self.config)
        self.assertTrue(detached.structurally_valid)
        self.assertFalse(detached.current_logically_eligible)
        self.assertFalse(detached.logical_job_constructible)
        self.assertFalse(detached.preparation_requirements_satisfied)
        self.assertIs(detached.renderer_adapter_compatibility, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(detached.executability, AssessmentBoundary.NOT_ASSESSED)
        self.assertTrue(live.current_logically_eligible)
        self.assertFalse(live.preparation_requirements_satisfied)
        self.assertFalse(live.logical_job_constructible)
        self.assertIs(live.renderer_adapter_compatibility, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(live.executability, AssessmentBoundary.NOT_ASSESSED)

    def test_detached_assessment_never_promotes_hypothetical_complete_data(self):
        hypothetical = replace(self.draft, requirements=(), lane_reasons=(),
            entry_assessments=tuple(replace(e, requirements=())
                                    for e in self.draft.entry_assessments))
        # M73 V1 cannot genuinely produce this state for supported sources.
        # Isolate the assessment decision to prove it never promotes detached data.
        with patch.object(job_engine, "validate_draft", return_value=hypothetical):
            result = assess_render_job_draft(hypothetical)
        self.assertTrue(result.structurally_valid)
        self.assertTrue(result.preparation_requirements_satisfied)
        self.assertFalse(result.current_logically_eligible)
        self.assertFalse(result.logical_job_constructible)
        self.assertIs(result.renderer_adapter_compatibility, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(result.executability, AssessmentBoundary.NOT_ASSESSED)

    def test_default_m72_v1_spec_passes_detached_validation(self):
        self.assertEqual(self.draft.timeline_binding.spec, RenderTimelineSpec())
        self.assertEqual(validate_draft(self.draft), self.draft)

    def test_recomputed_nondefault_m72_spec_denied(self):
        spec = replace(RenderTimelineSpec(), engine_version="9")
        forged = self.resign(replace(self.draft,
            timeline_binding=replace(self.draft.timeline_binding, spec=spec)))
        self.assertNotEqual(forged.binding.output_signature, self.draft.binding.output_signature)
        with self.assertRaises(RenderJobError):
            validate_draft(forged)

    def test_raw_roundtrip(self):
        raw = json.loads(canonical_payload(self.draft))
        self.assertEqual(validate_draft(raw, raw=True), self.draft)

    def test_rational_profile(self):
        profile = OutputProfile(640, 480, 30000, 1001)
        fixture = upstream.RenderPreparationTests()
        fixture.setUp()
        m = fixture.build(output_profile=profile)
        draft = self.build(m, output_profile=profile)
        self.assertEqual((draft.output_profile.frame_rate_num, draft.output_profile.frame_rate_den), (30000, 1001))

    def test_complete_lane_exact_adjacency(self):
        a = replace(self.draft.visual_clips[0], source_usage=SourceUsage.STILL_IMAGE,
                    timeline_start_us=0, timeline_end_us=5, outcome=RenderTimelineOutcome.READY)
        b = replace(a, timeline_start_us=5, timeline_end_us=10)
        self.assertEqual(exact_lane_reasons((a, b), 10), ())

    def test_empty_lane(self):
        self.assertEqual(exact_lane_reasons((), 10), (LaneReason.EMPTY_VISUAL_LANE,))

    def test_no_repair_and_retained_order(self):
        clips = tuple(replace(c, timeline_end_us=c.timeline_end_us + 1) for c in self.draft.visual_clips)
        before = clips
        exact_lane_reasons(clips, self.draft.output_duration_us)
        self.assertEqual(before, clips)
        self.assertEqual([c.placement_id for c in self.draft.visual_clips],
            [c.placement_id for c in self.base.render_timeline.plans[0].entries])

    def test_raw_unknown_field(self):
        raw = json.loads(canonical_payload(self.draft))
        raw["x"] = object()
        with self.assertRaises(ValueError):
            validate_draft(raw, raw=True)

    def test_raw_overflow_before_value(self):
        class Poison:
            def __getattribute__(self, name):
                raise AssertionError("introspection")
        raw = {"x" + str(i): Poison() for i in range(100)}
        with self.assertRaises(ValueError):
            validation.preflight(raw, raw=True)

    def test_no_arbitrary_introspection(self):
        class Poison:
            def __getattribute__(self, name):
                raise AssertionError("introspection")
        with self.assertRaises(ValueError):
            validation.preflight(Poison())

    def test_live_preflight_before_validation(self):
        self.m.render_preparation.plans = [self.m.render_preparation.plans[0]] * 65
        with patch("creator_studio.render_job.engine.require_valid", side_effect=AssertionError("recursive")):
            with self.assertRaises(ValueError):
                self.build()

    def test_projection_preflight_before_serialization(self):
        bad = replace(self.draft, visual_clips=self.draft.visual_clips * 4097)
        with patch.object(validation, "canonical_chunks", side_effect=AssertionError("serialize")):
            with self.assertRaises(ValueError):
                canonical_payload(bad)

    def test_canonical_exact_boundary(self):
        payload = canonical_payload(self.draft)
        self.assertEqual(canonical_payload(self.draft, max_bytes=len(payload)), payload)
        with self.assertRaises(ValueError):
            canonical_payload(self.draft, max_bytes=len(payload)-1)

    def test_traversal_nodes_exact_boundary(self):
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 1):
            validation.preflight(1, int)
            with self.assertRaises(ValueError):
                validation.preflight(self.draft)
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 0):
            with self.assertRaises(ValueError):
                validation.preflight(1, int)

    def test_depth_exact_boundary(self):
        with patch.object(validation, "MAX_TRAVERSAL_DEPTH", 1):
            validation.preflight(self.draft.binding, domain.RenderJobBinding)
        with patch.object(validation, "MAX_TRAVERSAL_DEPTH", 0):
            with self.assertRaises(ValueError):
                validation.preflight(self.draft.binding, domain.RenderJobBinding)

    def test_direct_cycle(self):
        raw = json.loads(canonical_payload(self.draft))
        raw["narration"]["binding"] = raw["narration"]
        with self.assertRaises(ValueError):
            validation.preflight(raw, raw=True)

    def test_indirect_cycle_live(self):
        self.m.render_preparation.plans[0].entries.append(self.m)
        with self.assertRaises(ValueError):
            self.build()

    def test_repeated_acyclic_reference(self):
        clip = self.draft.visual_clips[0]
        validation.preflight((clip, clip), tuple[domain.RenderVisualClip, ...])

    def test_visual_capacity(self):
        clip = self.draft.visual_clips[0]
        validation.preflight((clip,) * 4096, tuple[domain.RenderVisualClip, ...])
        with self.assertRaises(ValueError):
            validation.preflight((clip,) * 4097, tuple[domain.RenderVisualClip, ...])

    def test_requirement_capacities_independent(self):
        entry = replace(self.draft.entry_assessments[0], requirements=(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,) * 16)
        draft = replace(self.draft, entry_assessments=(entry,),
            requirements=(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,) * 32,
            lane_reasons=(LaneReason.GAP,) * 32)
        validation.preflight(draft)
        for bad in (replace(draft, requirements=draft.requirements + draft.requirements[:1]),
                    replace(draft, lane_reasons=draft.lane_reasons + draft.lane_reasons[:1]),
                    replace(draft, entry_assessments=(replace(entry, requirements=entry.requirements + entry.requirements[:1]),))):
            with self.assertRaises(ValueError):
                validation.preflight(bad)

    def test_id_boundary(self):
        validation.validate_binding(replace(self.draft.binding, render_preparation_plan_id="a" * 96))
        with self.assertRaises(ValueError):
            validation.validate_binding(replace(self.draft.binding, render_preparation_plan_id="a" * 97))

    def test_scalar_boundary(self):
        validation.preflight("a" * 256, str)
        with self.assertRaises(ValueError):
            validation.preflight("a" * 257, str)

    def test_upstream_long_text_not_m74_scalar(self):
        validation.preflight("a" * 10000, str, upstream=True)

    def test_count_mismatch(self):
        plan = self.m.render_preparation.plans[0]
        self.m.render_preparation.plans[0] = assign_identity(replace(plan, entries=[]))
        with self.assertRaises(ValueError):
            self.build()

    def test_asset_mismatch(self):
        plan = self.m.render_timeline.plans[0]
        from creator_studio.manifest.render_timeline import assign_identity as identity
        self.m.render_timeline.plans[0] = identity(replace(plan,
            entries=[replace(plan.entries[0], asset_id="asset:wrong")] + plan.entries[1:]))
        with self.assertRaises(ValueError):
            self.build()

    def test_source_architecture(self):
        forbidden = {"subprocess", "core", "engine.renderer", "engine.timeline_renderer",
                     "pathlib", "uuid", "datetime"}
        for path in (ROOT / "creator_studio/render_job").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names]
                    self.assertFalse(any(n == f or n.startswith(f + ".") for n in names for f in forbidden))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"open", "float", "eval", "exec"})

    def test_constants(self):
        expected = dict(MAX_VISUAL_ENTRIES=4096, MAX_REASONS_PER_ENTRY=16,
            MAX_PLAN_REASONS=32, MAX_ID_LENGTH=96, SIGNATURE_LENGTH=64,
            MAX_GENERAL_SCALAR=256, MAX_CANONICAL_PAYLOAD_BYTES=64 * 1024 * 1024,
            MAX_TRAVERSAL_DEPTH=32, MAX_TRAVERSAL_NODES=2_000_000)
        for name, value in expected.items():
            self.assertEqual(getattr(domain, name), value)

    def test_interior_gap(self):
        a = replace(self.draft.visual_clips[0], timeline_start_us=0, timeline_end_us=4)
        b = replace(a, timeline_start_us=5, timeline_end_us=10)
        self.assertIn(LaneReason.GAP, exact_lane_reasons((a, b), 10))

    def test_overlap(self):
        a = replace(self.draft.visual_clips[0], timeline_start_us=0, timeline_end_us=6)
        b = replace(a, timeline_start_us=5, timeline_end_us=10)
        self.assertIn(LaneReason.OVERLAP, exact_lane_reasons((a, b), 10))

    def test_unsupported_source(self):
        clip = replace(self.draft.visual_clips[0], source_usage=SourceUsage.UNRESOLVED)
        self.assertIn(LaneReason.UNSUPPORTED_SOURCE_USE, exact_lane_reasons((clip,), 10))

    def test_whole_video_source_coordinates(self):
        clip = replace(self.draft.visual_clips[0], timeline_start_us=0, timeline_end_us=10,
            source_start_us=0, source_end_us=10, source_duration_us=10)
        self.assertEqual(exact_lane_reasons((clip,), 10), ())
        for bad in (replace(clip, source_start_us=1), replace(clip, source_end_us=9),
                    replace(clip, source_duration_us=11)):
            self.assertIn(LaneReason.UNSUPPORTED_SOURCE_USE, exact_lane_reasons((bad,), 10))

    def test_image_presentation_blocker(self):
        from creator_studio.manifest.render_preparation_validation import derive_preparation
        timeline = self.m.render_timeline.plans[0]
        image = replace(timeline.entries[0], source_usage=SourceUsage.STILL_IMAGE)
        entries, _ = derive_preparation(self.m, replace(timeline, entries=[image]), PROFILE)
        self.assertIn(PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED, entries[0].requirements)
        from creator_studio.render_job.engine import _copy_record
        projected = domain.RenderEntryAssessment(**{f.name: tuple(entries[0].requirements)
            if f.name == "requirements" else getattr(entries[0], f.name)
            for f in fields(domain.RenderEntryAssessment)})
        self.assertEqual(projected.requirements, tuple(entries[0].requirements))

    def test_video_presentation_blocker(self):
        self.assertIn(PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED,
                      self.draft.entry_assessments[0].requirements)

    def test_geometry_and_audio_subtitle_policies(self):
        self.assertIs(self.draft.spec.geometry_policy, PreparationPolicy.IDENTITY_GEOMETRY_ONLY_V1)
        self.assertIs(self.draft.spec.visual_audio_policy, PreparationPolicy.MUTE_ALL_VISUAL_SOURCE_AUDIO_V1)
        self.assertIs(self.draft.spec.subtitle_policy, PreparationPolicy.NO_SUBTITLE_OUTPUT_V1)
        self.assertEqual(self.draft.narration.binding.inspection.origin_policy, "PCM_FRAME_ZERO")

    def test_complete_spec_direct_validation_denied(self):
        with self.assertRaises(ValueError):
            validate_spec_job(RenderJobSpec(self.draft))

    def test_detached_spec_validation_has_no_authority_field(self):
        self.assertEqual(tuple(f.name for f in fields(RenderJobSpec)), ("draft",))
        self.assertFalse(any(hasattr(RenderJobSpec(self.draft), name) for name in (
            "current_logically_eligible", "logical_job_constructible",
            "renderer_adapter_compatibility", "executability")))

    def test_detached_asset_tampering(self):
        clip = replace(self.draft.visual_clips[0], asset_id="asset:forged")
        with self.assertRaises(ValueError):
            validate_draft(replace(self.draft, visual_clips=(clip,) + self.draft.visual_clips[1:]))

    def test_resigned_asset_has_structure_without_live_provenance(self):
        old = self.draft.visual_clips[0]
        forged_asset = "asset:sha256:" + "f" * 64
        forged_materialization = "materialization:" + "e" * 64
        clip = replace(old, asset_id=forged_asset,
            materialization_id=forged_materialization,
            asset_evidence_signature=timeline_signed("asset_evidence",
                [forged_asset, "f" * 64, 17]),
            materialization_evidence_signature=timeline_signed(
                "materialization_evidence", [forged_materialization, forged_asset]))
        moved_media = timeline_signed("media_binding", [
            [clip.placement_id, clip.materialization_id, clip.asset_id,
             clip.materialization_evidence_signature, clip.asset_evidence_signature]])
        forged = self.resign(replace(self.draft,
            visual_clips=(clip,) + self.draft.visual_clips[1:],
            timeline_binding=replace(self.draft.timeline_binding,
                                     media_binding_signature=moved_media)))
        self.assertNotEqual(forged, self.draft)
        self.assertEqual(validate_draft(forged), forged)
        detached = assess_render_job_draft(forged)
        self.assertTrue(detached.structurally_valid)
        self.assertFalse(detached.current_logically_eligible)
        self.assertFalse(detached.logical_job_constructible)
        self.assertIs(detached.renderer_adapter_compatibility, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(detached.executability, AssessmentBoundary.NOT_ASSESSED)
        with patch.object(job_engine, "validate_spec_job", side_effect=AssertionError("equality bypass")):
            with self.assertRaises(RenderJobError):
                construct_render_job_spec(self.m, forged, output_profile=PROFILE,
                                          spec=SPEC, **self.config)

    def test_detached_order_tampering(self):
        with self.assertRaises(ValueError):
            validate_draft(replace(self.draft, visual_clips=tuple(reversed(self.draft.visual_clips))))

    def test_resigned_multi_placement_order_has_no_live_authority(self):
        manifest_require_valid(self.m)
        live = self.build()
        self.assertGreaterEqual(len(live.visual_clips), 2)
        self.assertEqual(len(live.visual_clips), len(self.m.editing.plans[0].placements))
        self.assertEqual([c.placement_id for c in live.visual_clips],
                         [p.placement_id for p in self.m.editing.plans[0].placements])
        # Move each placement identity, media evidence and assessment to the
        # other's chronological slot. Keep the valid intervals and M73 semantics.
        moved_clips = tuple(replace(source, ordinal=index,
            timeline_start_us=slot.timeline_start_us,
            timeline_end_us=slot.timeline_end_us)
            for index, (source, slot) in enumerate(zip(reversed(live.visual_clips),
                                                       live.visual_clips)))
        moved_assessments = tuple(replace(source,
            timeline_start_us=slot.timeline_start_us,
            timeline_end_us=slot.timeline_end_us)
            for source, slot in zip(reversed(live.entry_assessments),
                                    live.entry_assessments))
        moved_media = timeline_signed("media_binding", [
            [c.placement_id, c.materialization_id, c.asset_id,
             c.materialization_evidence_signature, c.asset_evidence_signature]
            for c in moved_clips])
        moved_timing = timeline_signed("timing_evidence", [
            [c.placement_id, c.timeline_start_us, c.timeline_end_us]
            for c in moved_clips])
        forged = self.resign(replace(live, visual_clips=moved_clips,
            entry_assessments=moved_assessments,
            timeline_binding=replace(live.timeline_binding,
                timing_evidence_signature=moved_timing,
                media_binding_signature=moved_media)))
        self.assertEqual([c.placement_id for c in forged.visual_clips],
                         list(reversed([c.placement_id for c in live.visual_clips])))
        self.assertEqual(validate_draft(forged), forged)
        detached = assess_render_job_draft(forged)
        self.assertFalse(detached.current_logically_eligible)
        self.assertFalse(detached.logical_job_constructible)
        with patch.object(job_engine, "validate_spec_job", side_effect=AssertionError("equality bypass")):
            with self.assertRaises(RenderJobError):
                construct_render_job_spec(self.m, forged, output_profile=PROFILE,
                                          spec=SPEC, **self.config)

    def test_typed_unknown_attribute(self):
        bad = deepcopy(self.draft)
        object.__setattr__(bad, "unexpected", "closed")
        with self.assertRaises(ValueError):
            validate_draft(bad)

    def test_raw_unknown_nested_field(self):
        raw = json.loads(canonical_payload(self.draft))
        raw["visual_clips"][0]["trim"] = True
        with self.assertRaises(ValueError):
            validate_draft(raw, raw=True)

    def test_policy_no_source_expansion(self):
        self.assertEqual({s.value for s in SourceUsage}, {"STILL_IMAGE", "WHOLE_VIDEO", "UNRESOLVED"})

    def test_m73_ordered_assessments_exact(self):
        for projected, source in zip(self.draft.entry_assessments, self.base.render_preparation.plans[0].entries):
            for f in fields(source):
                expected = tuple(source.requirements) if f.name == "requirements" else getattr(source, f.name)
                self.assertEqual(getattr(projected, f.name), expected)

    def test_m72_source_binding_exact(self):
        source = self.base.render_timeline.plans[0]
        for f in fields(self.draft.source_binding):
            self.assertEqual(getattr(self.draft.source_binding, f.name), getattr(source, f.name))

    def test_max_integer_accepted_by_preflight(self):
        validation.preflight((1 << 63) - 1, int)
        with self.assertRaises(ValueError):
            validation.preflight(1 << 63, int)

    def test_bool_float_raw_timestamp_rejected(self):
        for value in (True, 0.0, -1, 1 << 63):
            raw = json.loads(canonical_payload(self.draft))
            raw["visual_clips"][0]["timeline_start_us"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_draft(raw, raw=True)

    def test_six_file_scope(self):
        names = {p.name for p in (ROOT / "creator_studio/render_job").iterdir() if p.is_file()}
        self.assertEqual(names, {"__init__.py", "models.py", "validation.py", "engine.py", "README.md"})

    def test_repeated_references_consume_shared_budget(self):
        binding = self.draft.binding
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 15):
            validation.preflight((binding, binding), tuple[domain.RenderJobBinding, ...])
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 14):
            with self.assertRaises(ValueError):
                validation.preflight((binding, binding), tuple[domain.RenderJobBinding, ...])

    def test_source_coordinate_bool_rejected(self):
        clip = replace(self.draft.visual_clips[0], timeline_start_us=0, timeline_end_us=1,
                       source_start_us=0, source_end_us=True, source_duration_us=1)
        self.assertIn(LaneReason.UNSUPPORTED_SOURCE_USE, exact_lane_reasons((clip,), 1))

    def test_diagnostic_capacity(self):
        from creator_studio.manifest.render_timeline import RenderDiagnostic
        clip = replace(self.draft.visual_clips[0], diagnostics=(RenderDiagnostic.UNRESOLVED_TIMING,) * 16)
        validation.preflight(clip, domain.RenderVisualClip)
        with self.assertRaises(ValueError):
            validation.preflight(replace(clip, diagnostics=clip.diagnostics + clip.diagnostics[:1]), domain.RenderVisualClip)

    def test_canonical_limit_argument_overflow(self):
        with self.assertRaises(ValueError):
            canonical_payload(self.draft, max_bytes=64 * 1024 * 1024 + 1)

    def test_preflight_before_projection_copy(self):
        self.m.render_preparation.plans *= 65
        with patch("creator_studio.render_job.engine._copy_record", side_effect=AssertionError("copy")):
            with self.assertRaises(ValueError):
                self.build()

    def test_forged_detached_entry_conclusion_even_with_recomputed_signatures(self):
        plan = self.m.render_preparation.plans[0]
        forged_entry = replace(plan.entries[0], conclusion=PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED)
        forged_plan = assign_identity(replace(plan, entries=[forged_entry] + plan.entries[1:]))
        binding = domain.RenderJobBinding(**{f.name: getattr(forged_plan, f.name)
                                             for f in fields(domain.RenderJobBinding)})
        entry = replace(self.draft.entry_assessments[0], conclusion=forged_entry.conclusion)
        with self.assertRaises(ValueError):
            validate_draft(replace(self.draft, binding=binding,
                entry_assessments=(entry,) + self.draft.entry_assessments[1:]))

    def resign(self, draft):
        """Recompute retained contracts, deliberately granting no semantics."""
        from creator_studio.manifest.render_preparation import RenderPreparationPlan, RenderPreparationEntryAssessment
        from creator_studio.manifest.render_timeline import RenderTimelinePlan, RenderTimelineEntry, assign_identity as timeline_identity
        source, binding = draft.source_binding, draft.timeline_binding
        clips = [RenderTimelineEntry(**{f.name: list(c.diagnostics) if f.name == "diagnostics"
            else getattr(c, f.name) for f in fields(RenderTimelineEntry)}) for c in draft.visual_clips]
        timeline = timeline_identity(RenderTimelinePlan("", source.acquisition_id,
            source.edit_plan_id, source.edit_output_signature, source.placement_timing_plan_id,
            binding.timing_evidence_signature, binding.media_binding_signature, binding.spec, clips))
        binding = replace(binding, **{name: getattr(timeline, name) for name in (
            "render_timeline_plan_id", "input_binding_signature", "source_usage_signature", "output_signature")})
        entries = [RenderPreparationEntryAssessment(**{f.name: list(e.requirements)
            if f.name == "requirements" else getattr(e, f.name)
            for f in fields(RenderPreparationEntryAssessment)}) for e in draft.entry_assessments]
        plan = assign_identity(RenderPreparationPlan("", binding, draft.narration.binding,
            draft.output_profile, draft.spec, draft.output_duration_us, entries,
            list(draft.uncovered_intervals), list(draft.requirements), draft.conclusion))
        return replace(draft, timeline_binding=binding, binding=domain.RenderJobBinding(
            **{f.name: getattr(plan, f.name) for f in fields(domain.RenderJobBinding)}),
            lane_reasons=exact_lane_reasons(draft.visual_clips, draft.output_duration_us))

    def image_draft(self):
        """A complete, semantically valid M72 still projection and M73 assessment."""
        clip = replace(self.draft.visual_clips[0], media_kind=VisualMediaKind.IMAGE,
            source_duration_us=None, source_usage=SourceUsage.STILL_IMAGE,
            source_start_us=None, source_end_us=None)
        assessment = self.draft.entry_assessments[0]
        requirements = tuple(PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED
            if r is PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED else r
            for r in assessment.requirements)
        draft = replace(self.draft, visual_clips=(clip,) + self.draft.visual_clips[1:],
            entry_assessments=(replace(assessment, source_usage=SourceUsage.STILL_IMAGE,
                source_duration_us=None, source_start_us=None, source_end_us=None),)
                + self.draft.entry_assessments[1:])
        return self.forged_requirements(draft, requirements)

    def forged_requirements(self, draft, requirements):
        from creator_studio.manifest.render_preparation_validation import conclusion
        entry = replace(draft.entry_assessments[0], requirements=tuple(requirements),
                        conclusion=conclusion(requirements))
        entries = (entry,) + draft.entry_assessments[1:]
        from creator_studio.manifest.render_preparation_validation import frame_aligned
        aggregate = []
        if not frame_aligned(draft.output_duration_us, draft.output_profile):
            aggregate.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        if draft.uncovered_intervals:
            aggregate.append(PreparationRequirement.UNCOVERED_VISUAL_INTERVALS)
        for e in entries:
            for r in e.requirements:
                if r not in aggregate:
                    aggregate.append(r)
        return self.resign(replace(draft, entry_assessments=entries,
            requirements=tuple(aggregate), conclusion=conclusion(aggregate)))

    def test_rehashed_transform_removal(self):
        draft = replace(self.draft, output_profile=replace(PROFILE, width_px=1))
        # Build a valid M73 projection using the real production derivation.
        fixture = upstream.RenderPreparationTests()
        fixture.setUp()
        draft = self.build(fixture.build(output_profile=draft.output_profile),
                           output_profile=draft.output_profile)
        self.assertIn(PreparationRequirement.TRANSFORM_POLICY_REQUIRED, draft.entry_assessments[0].requirements)
        forged = self.forged_requirements(draft, [r for r in draft.entry_assessments[0].requirements
            if r is not PreparationRequirement.TRANSFORM_POLICY_REQUIRED])
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_source_presentation_removal(self):
        requirements = tuple(r for r in self.draft.entry_assessments[0].requirements
            if r is not PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED)
        self.assertNotEqual(requirements, self.draft.entry_assessments[0].requirements)
        with self.assertRaises(ValueError):
            validate_draft(self.forged_requirements(self.draft, requirements))

    def test_rehashed_image_presentation_removal(self):
        valid = self.image_draft()
        self.assertEqual(validate_draft(valid), valid)
        requirements = tuple(r for r in valid.entry_assessments[0].requirements
            if r is not PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED)
        with self.assertRaises(ValueError):
            validate_draft(self.forged_requirements(valid, requirements))

    def test_rehashed_frame_removal(self):
        fixture = upstream.RenderPreparationTests()
        fixture.setUp()
        profile = OutputProfile(640, 480, 30000, 1001)
        draft = self.build(fixture.build(output_profile=profile), output_profile=profile)
        self.assertIn(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED, draft.entry_assessments[0].requirements)
        forged = self.forged_requirements(draft, [r for r in draft.entry_assessments[0].requirements
            if r is not PreparationRequirement.FRAME_ALIGNMENT_REQUIRED])
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_unestablished_frame_removal(self):
        clip = replace(self.draft.visual_clips[0], timeline_start_us=None,
            timeline_end_us=None, outcome=RenderTimelineOutcome.UNRESOLVED_TIMING,
            timing_outcome=PlacementTimingOutcome.UNRESOLVED,
            diagnostics=(RenderDiagnostic.UNRESOLVED_TIMING,),
            source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None)
        entry = replace(self.draft.entry_assessments[0], timeline_start_us=None,
            timeline_end_us=None, source_usage=SourceUsage.UNRESOLVED,
            source_start_us=None, source_end_us=None,
            source_width_px=None, source_height_px=None)
        clips = (clip,) + self.draft.visual_clips[1:]
        from creator_studio.manifest.render_preparation_validation import (
            derive_preparation, derive_uncovered_intervals)
        timeline = self.base.render_timeline.plans[0]
        upstream_entry = replace(timeline.entries[0], timeline_start_us=None,
            timeline_end_us=None, outcome=RenderTimelineOutcome.UNRESOLVED_TIMING,
            timing_outcome=PlacementTimingOutcome.UNRESOLVED,
            diagnostics=[RenderDiagnostic.UNRESOLVED_TIMING],
            source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None)
        m73_entries, covered = derive_preparation(self.base, replace(timeline,
            entries=[upstream_entry] + timeline.entries[1:]), PROFILE)
        expected = tuple(m73_entries[0].requirements)
        self.assertIn(PreparationRequirement.FRAME_ALIGNMENT_NOT_ESTABLISHED, expected)
        draft = replace(self.draft, visual_clips=clips,
            entry_assessments=(entry,) + self.draft.entry_assessments[1:],
            uncovered_intervals=tuple(derive_uncovered_intervals(covered,
                self.draft.output_duration_us)))
        valid = self.forged_requirements(draft, expected)
        self.assertEqual(validate_draft(valid), valid)
        forged = self.forged_requirements(valid, tuple(r for r in expected
            if r is not PreparationRequirement.FRAME_ALIGNMENT_NOT_ESTABLISHED))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_unsupported_requirement_addition(self):
        forged = self.forged_requirements(self.draft, self.draft.entry_assessments[0].requirements +
            (PreparationRequirement.SUPPORTED_SOURCE_USE_NOT_ESTABLISHED,))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_unsupported_requirement_removal(self):
        clip = replace(self.draft.visual_clips[0], source_usage=SourceUsage.UNRESOLVED)
        entry = replace(self.draft.entry_assessments[0], source_usage=SourceUsage.UNRESOLVED,
            source_start_us=None, source_end_us=None,
            source_duration_us=clip.source_duration_us,
            source_width_px=None, source_height_px=None)
        draft = replace(self.draft, visual_clips=(clip,) + self.draft.visual_clips[1:],
                        entry_assessments=(entry,) + self.draft.entry_assessments[1:])
        forged = self.forged_requirements(draft, (PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_geometry_requirement_removal(self):
        clip = replace(self.draft.visual_clips[0], source_usage=SourceUsage.UNRESOLVED,
            source_start_us=None, source_end_us=None,
            source_duration_us=self.draft.visual_clips[0].source_duration_us + 1,
            outcome=RenderTimelineOutcome.SOURCE_TRIM_REQUIRED,
            diagnostics=(RenderDiagnostic.SOURCE_TRIM_REQUIRED,))
        entry = replace(self.draft.entry_assessments[0], source_usage=SourceUsage.UNRESOLVED,
            source_start_us=None, source_end_us=None, source_duration_us=clip.source_duration_us,
            source_width_px=None, source_height_px=None)
        clips = (clip,) + self.draft.visual_clips[1:]
        from creator_studio.manifest.render_preparation_validation import (
            derive_preparation, derive_uncovered_intervals)
        timeline = self.base.render_timeline.plans[0]
        m73_entries, _ = derive_preparation(self.base, replace(timeline,
            entries=[replace(timeline.entries[0], source_usage=SourceUsage.UNRESOLVED,
                source_start_us=None, source_end_us=None,
                source_duration_us=timeline.entries[0].source_duration_us + 1,
                outcome=RenderTimelineOutcome.SOURCE_TRIM_REQUIRED,
                diagnostics=[RenderDiagnostic.SOURCE_TRIM_REQUIRED])]
                + timeline.entries[1:]), PROFILE)
        expected = tuple(m73_entries[0].requirements)
        self.assertIn(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED, expected)
        covered = [(c.timeline_start_us, c.timeline_end_us) for c in clips
            if c.outcome is RenderTimelineOutcome.READY and c.source_usage in
            (SourceUsage.STILL_IMAGE, SourceUsage.WHOLE_VIDEO)]
        draft = replace(self.draft, visual_clips=clips,
            entry_assessments=(entry,) + self.draft.entry_assessments[1:],
            uncovered_intervals=tuple(derive_uncovered_intervals(covered,
                self.draft.output_duration_us)))
        valid = self.forged_requirements(draft, expected)
        self.assertEqual(validate_draft(valid), valid)
        forged = self.forged_requirements(valid, tuple(r for r in expected
            if r is not PreparationRequirement.GEOMETRY_NOT_ESTABLISHED))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_uncovered_forgery(self):
        forged = self.resign(replace(self.draft, uncovered_intervals=(
            domain.UncoveredInterval(0, self.draft.output_duration_us),)))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_aggregate_forgery(self):
        with self.assertRaises(ValueError):
            validate_draft(self.resign(replace(self.draft, requirements=())))

    def test_rehashed_uncovered_aggregate_removal(self):
        self.assertTrue(self.draft.uncovered_intervals)
        requirements = tuple(r for r in self.draft.requirements
            if r is not PreparationRequirement.UNCOVERED_VISUAL_INTERVALS)
        self.assertNotEqual(requirements, self.draft.requirements)
        from creator_studio.manifest.render_preparation_validation import conclusion
        forged = self.resign(replace(self.draft, requirements=requirements,
            conclusion=conclusion(requirements)))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_rehashed_consistent_entry_conclusion_forgery(self):
        with self.assertRaises(ValueError):
            validate_draft(self.forged_requirements(self.draft, ()))

    def test_rehashed_consistent_plan_conclusion_forgery(self):
        forged = self.resign(replace(self.draft, requirements=(),
            conclusion=PreparationConclusion.PREPARATION_REQUIREMENTS_SATISFIED))
        with self.assertRaises(ValueError):
            validate_draft(forged)

    def test_valid_blocked_presentation_detached(self):
        self.assertEqual(validate_draft(self.resign(self.draft)), self.draft)
        valid = self.image_draft()
        self.assertEqual(validate_draft(valid), valid)

    def test_m72_valid_semantic_rows(self):
        video = self.draft.visual_clips[0]
        image = self.image_draft().visual_clips[0]
        interval = video.timeline_end_us - video.timeline_start_us
        rows = [video, image,
            replace(video, timing_outcome=PlacementTimingOutcome.UNRESOLVED,
                timeline_start_us=None, timeline_end_us=None,
                source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
                outcome=RenderTimelineOutcome.UNRESOLVED_TIMING,
                diagnostics=(RenderDiagnostic.UNRESOLVED_TIMING,)),
            replace(video, source_duration_us=interval + 1,
                source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
                outcome=RenderTimelineOutcome.SOURCE_TRIM_REQUIRED,
                diagnostics=(RenderDiagnostic.SOURCE_TRIM_REQUIRED,)),
            replace(video, source_duration_us=interval - 1,
                source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
                outcome=RenderTimelineOutcome.MEDIA_TOO_SHORT,
                diagnostics=(RenderDiagnostic.MEDIA_TOO_SHORT,)),
            replace(video, source_duration_us=None,
                source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
                outcome=RenderTimelineOutcome.SOURCE_DURATION_UNRESOLVED,
                diagnostics=(RenderDiagnostic.SOURCE_DURATION_UNRESOLVED,)),
            replace(image, media_kind=VisualMediaKind.GRAPHIC,
                source_usage=SourceUsage.UNRESOLVED,
                outcome=RenderTimelineOutcome.UNSUPPORTED_MEDIA_TYPE,
                diagnostics=(RenderDiagnostic.UNSUPPORTED_MEDIA_TYPE,)),
            replace(video, acquisition_outcome=AcquisitionOutcome.RIGHTS_BLOCKED,
                materialization_id=None, asset_id=None,
                materialization_evidence_signature=None, asset_evidence_signature=None,
                media_kind=None, source_duration_us=None,
                source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
                outcome=RenderTimelineOutcome.NO_MATERIALIZED_MEDIA,
                diagnostics=(RenderDiagnostic.NO_MATERIALIZED_MEDIA,))]
        for row in rows:
            with self.subTest(outcome=row.outcome, kind=row.media_kind):
                validation.validate_m72_entry(row)

    def test_m72_rehashed_cross_field_forgeries(self):
        video = self.draft.visual_clips[0]
        image_draft = self.image_draft()
        image = image_draft.visual_clips[0]
        interval = video.timeline_end_us - video.timeline_start_us
        trim = replace(video, source_duration_us=interval + 1,
            source_usage=SourceUsage.UNRESOLVED, source_start_us=None, source_end_us=None,
            outcome=RenderTimelineOutcome.SOURCE_TRIM_REQUIRED,
            diagnostics=(RenderDiagnostic.SOURCE_TRIM_REQUIRED,))
        validation.validate_m72_entry(trim)
        cases = (
            ("video_to_still", self.draft, replace(video, source_usage=SourceUsage.STILL_IMAGE)),
            ("image_to_video", image_draft, replace(image, source_usage=SourceUsage.WHOLE_VIDEO)),
            ("still_start", image_draft, replace(image, source_start_us=0)),
            ("still_end", image_draft, replace(image, source_end_us=interval)),
            ("still_duration", image_draft, replace(image, source_duration_us=interval)),
            ("video_nonzero_start", self.draft, replace(video, source_start_us=1)),
            ("video_wrong_end", self.draft, replace(video, source_end_us=interval - 1)),
            ("video_wrong_duration", self.draft, replace(video, source_duration_us=interval + 1)),
            ("ready_unresolved_use", self.draft, replace(video, source_usage=SourceUsage.UNRESOLVED)),
            ("trim_forged_ready", self.draft, replace(trim, outcome=RenderTimelineOutcome.READY)),
            ("kind_use_mismatch", image_draft, replace(image, media_kind=VisualMediaKind.VIDEO)),
            ("outcome_use_mismatch", self.draft, replace(trim, source_usage=SourceUsage.WHOLE_VIDEO)),
            ("ready_diagnostic", self.draft, replace(video,
                diagnostics=(RenderDiagnostic.MEDIA_TOO_SHORT,))),
            ("trim_diagnostic", self.draft, replace(trim,
                diagnostics=(RenderDiagnostic.MEDIA_TOO_SHORT,))),
            ("nonmaterialized_with_asset", self.draft, replace(video,
                acquisition_outcome=AcquisitionOutcome.RIGHTS_BLOCKED)),
            ("wrong_ordinal", self.draft, replace(video, ordinal=1)),
        )
        for label, base, forged_clip in cases:
            with self.subTest(case=label):
                draft = self.resign(replace(base,
                    visual_clips=(forged_clip,) + base.visual_clips[1:]))
                self.assertNotEqual(draft.timeline_binding.output_signature,
                    base.timeline_binding.output_signature)
                with self.assertRaises(RenderJobError):
                    validate_draft(draft)

    def test_bounded_live_type_errors_belong_to_manifest(self):
        cases = (
            ("project_id", lambda m: setattr(m, "project_id", []), "contract"),
            ("project_id_bytes", lambda m: setattr(m, "project_id", b"small"), "contract"),
            ("voice_timing", lambda m: setattr(m.voice_timing, "runs", {}), "contract"),
            ("render_timeline", lambda m: setattr(m.render_timeline, "plans", {}), "contract"),
            ("render_preparation", lambda m: setattr(m.render_preparation, "plans", {}), "contract"),
        )
        for label, mutate, code in cases:
            with self.subTest(field=label):
                manifest = deepcopy(self.base)
                mutate(manifest)
                calls = []
                def checked(value):
                    calls.append(1)
                    return manifest_require_valid(value)
                with patch("creator_studio.render_job.engine.require_valid", side_effect=checked):
                    with self.assertRaises(ManifestValidationError) as raised:
                        self.build(manifest)
                self.assertEqual(calls, [1])
                self.assertIn(code, {error.code for error in raised.exception.errors})

    def test_oversized_live_values_stop_before_manifest_validation(self):
        cases = (
            ("project_id", lambda m: setattr(m, "project_id", "x" * 257)),
            ("voice_timing", lambda m: setattr(m.voice_timing, "runs", [None] * 65)),
            ("render_timeline", lambda m: setattr(m.render_timeline, "plans", [None] * 65)),
            ("render_preparation", lambda m: setattr(m.render_preparation, "plans", [None] * 65)),
        )
        for label, mutate in cases:
            with self.subTest(field=label):
                manifest = deepcopy(self.base)
                mutate(manifest)
                calls = []
                with patch("creator_studio.render_job.validation.MAX_CANONICAL_PAYLOAD_BYTES", 256), \
                     patch("creator_studio.render_job.engine.require_valid",
                           side_effect=lambda value: calls.append(1)):
                    with self.assertRaises(RenderJobError):
                        self.build(manifest)
                self.assertEqual(calls, [])

    def hostile_paths(self, mutate):
        for family in ("live", "draft", "spec"):
            events = []
            if family == "live":
                value = deepcopy(self.base)
                mutate(value, events)
                call = lambda: self.build(value)
            else:
                value = deepcopy(self.draft)
                mutate(value, events)
                call = (lambda: validate_draft(value)) if family == "draft" else (
                    lambda: validation.validate_spec_job(domain.RenderJobSpec(value)))
            with self.subTest(family=family), self.assertRaises(ValueError):
                call()
            self.assertEqual(events, [], family)

    def test_hostile_instance_dictionary_subclasses(self):
        for hook in ("__len__", "__iter__", "__contains__", "__getitem__", "keys", "items"):
            def mutate(value, events):
                def hostile(*args):
                    events.append(hook)
                    return 0
                cls = type("HostileDict", (dict,), {hook: hostile})
                members = object.__getattribute__(value, "__dict__")
                object.__setattr__(value, "__dict__", cls(members))
            with self.subTest(hook=hook):
                self.hostile_paths(mutate)

    def test_hostile_nested_instance_dictionary(self):
        def mutate(value, events):
            target = value.render_preparation if type(value) is ProjectManifest else value.binding
            class HostileDict(dict):
                def __len__(self):
                    events.append("len")
                    return 0
                def __iter__(self):
                    events.append("iter")
                    return iter(())
            members = object.__getattribute__(target, "__dict__")
            object.__setattr__(target, "__dict__", HostileDict(members))
        self.hostile_paths(mutate)

    def test_hostile_instance_dictionary_key(self):
        def mutate(value, events):
            class Key:
                def __hash__(self):
                    events.append("hash")
                    return 123
                def __eq__(self, other):
                    events.append("eq")
                    return False
                def __repr__(self):
                    events.append("repr")
                    return "key"
                def __str__(self):
                    events.append("str")
                    return "key"
            members = object.__getattribute__(value, "__dict__")
            members.pop(next(iter(members)))
            members[Key()] = None
            events.clear()  # Construction necessarily hashes; validation must not.
        self.hostile_paths(mutate)

    def test_hostile_leaf_hooks(self):
        for hook in ("__getattribute__", "__getattr__", "__repr__", "__str__",
                     "__hash__", "__deepcopy__", "__iter__", "__len__"):
            def mutate(value, events):
                def hostile(*args):
                    events.append(hook)
                    return None
                cls = type("HostileLeaf", (), {hook: hostile})
                members = object.__getattribute__(value, "__dict__")
                members["project_id" if type(value) is ProjectManifest else "output_duration_us"] = cls()
            with self.subTest(hook=hook):
                self.hostile_paths(mutate)

    def test_hostile_leaf_metaclass_hooks(self):
        def mutate(value, events):
            class HostileMeta(type):
                def __hash__(cls):
                    events.append("class hash")
                    return 1
                def __eq__(cls, other):
                    events.append("class equality")
                    return False
            class HostileLeaf(metaclass=HostileMeta):
                pass
            members = object.__getattribute__(value, "__dict__")
            members["project_id" if type(value) is ProjectManifest else "output_duration_us"] = HostileLeaf()
        self.hostile_paths(mutate)

    def test_actual_depth_32_boundary(self):
        value, schema = 1, int
        for _ in range(32):
            value, schema = (value,), tuple[schema, ...]
        validation.preflight(value, schema)
        with self.assertRaises(ValueError):
            validation.preflight((value,), tuple[schema, ...])

    def test_actual_two_million_node_boundary(self):
        shared = (1,) * 1000
        value = (shared,) * 1998 + ((),)
        schema = tuple[tuple[int, ...], ...]
        validation.preflight(value, schema)
        with self.assertRaises(ValueError):
            validation.preflight(value + ((),), schema)

# Independent named cases keep counts explicit and failures localized.
def projection_case(name):
    def test(self):
        plan = self.base.render_preparation.plans[0]
        self.assertEqual(getattr(self.draft.binding, name), getattr(plan, name))
    return test

for _name in ("render_preparation_plan_id", "input_binding_signature", "output_profile_signature",
              "render_policy_signature", "preparation_signature", "output_signature"):
    setattr(RenderJobTests, "test_binding_" + _name, projection_case(_name))

def m72_case(name):
    def test(self):
        for clip, entry in zip(self.draft.visual_clips, self.base.render_timeline.plans[0].entries):
            expected = tuple(entry.diagnostics) if name == "diagnostics" else getattr(entry, name)
            self.assertEqual(getattr(clip, name), expected)
    return test

for _field in fields(domain.RenderVisualClip):
    setattr(RenderJobTests, "test_m72_exact_" + _field.name, m72_case(_field.name))

def m73_case(name):
    def test(self):
        plan = self.base.render_preparation.plans[0]
        actual = getattr(self.draft, name)
        expected = getattr(plan, name)
        if type(expected) is list:
            expected = tuple(expected)
        self.assertEqual(actual, expected)
    return test

for _name in ("output_profile", "spec", "timeline_binding", "output_duration_us",
              "uncovered_intervals", "requirements", "conclusion"):
    setattr(RenderJobTests, "test_m73_exact_" + _name, m73_case(_name))

def narration_case(name):
    def test(self):
        self.assertEqual(getattr(self.draft.narration.binding, name),
            getattr(self.base.render_preparation.plans[0].narration_binding, name))
    return test

for _field in fields(domain.NarrationBinding):
    setattr(RenderJobTests, "test_narration_exact_" + _field.name, narration_case(_field.name))

def lane_case(start, end, reason):
    def test(self):
        clip = replace(self.draft.visual_clips[0], timeline_start_us=start, timeline_end_us=end,
                       source_usage=SourceUsage.STILL_IMAGE, outcome=RenderTimelineOutcome.READY)
        self.assertIn(reason, exact_lane_reasons((clip,), 10))
    return test

for _name, _start, _end, _reason in (
    ("leading_gap", 1, 10, LaneReason.INEXACT_START),
    ("leading_gap_reason", 1, 10, LaneReason.GAP),
    ("unresolved_start", None, 10, LaneReason.UNRESOLVED_INTERVAL),
    ("unresolved_end", 0, None, LaneReason.UNRESOLVED_INTERVAL),
    ("zero_interval", 0, 0, LaneReason.INVALID_INTERVAL),
    ("negative_interval", -1, 10, LaneReason.INVALID_INTERVAL),
    ("reversed_interval", 9, 1, LaneReason.INVALID_INTERVAL),
    ("excess", 0, 11, LaneReason.EXCESS_COVERAGE),
    ("endpoint", 0, 9, LaneReason.ENDPOINT_MISMATCH),
    ("bool_start", False, 10, LaneReason.INVALID_INTERVAL),
    ("float_start", 0.0, 10, LaneReason.INVALID_INTERVAL),
    ("overflow_end", 0, 1 << 63, LaneReason.INVALID_INTERVAL)):
    setattr(RenderJobTests, "test_lane_" + _name, lane_case(_start, _end, _reason))

def signature_case(value):
    def test(self):
        with self.assertRaises(ValueError):
            validate_binding(replace(self.draft.binding, input_binding_signature=value))
    return test

for _name, _value in (("uppercase", "A" * 64), ("short", "a" * 63),
                      ("long", "a" * 65), ("invalid", "g" * 64), ("empty", "")):
    setattr(RenderJobTests, "test_signature_" + _name, signature_case(_value))

def absent_case(name):
    def test(self):
        raw = canonical_payload(self.draft)
        self.assertNotIn('"' + name + '"', raw)
        self.assertFalse(hasattr(self.draft, name))
        self.assertFalse(hasattr(__import__("creator_studio.render_job", fromlist=[name]), name))
    return test

for _name in ("render_ready", "render_executable", "render_succeeded", "container", "video_codec",
    "audio_codec", "pixel_format", "crf", "preset", "bitrate", "muxer", "faststart",
    "source_path", "output_path", "temp_path", "storage_root", "subtitle_tracks", "transcript",
    "provider_payload", "runtime_identity", "timestamp", "uuid", "history", "cache", "artifacts",
    "dependencies", "stage", "trim", "loop", "freeze", "speed", "reverse", "transition",
    "frame_drop", "frame_duplication", "scale", "crop", "pad", "setsar", "rotation",
    "gain", "mix", "music", "sfx", "resampling"):
    setattr(RenderJobTests, "test_absent_" + _name, absent_case(_name))

if __name__ == "__main__":
    unittest.main()
