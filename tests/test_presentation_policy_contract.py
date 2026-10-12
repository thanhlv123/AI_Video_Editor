"""Offline M75 policy, authority, identity, and hostile-object contracts."""
import ast
from copy import deepcopy
from dataclasses import dataclass, fields, replace, FrozenInstanceError
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch
from creator_studio.presentation_policy import *
from creator_studio.presentation_policy import models, validation, engine
from creator_studio.render_job import validate_draft
from creator_studio.manifest.render_preparation import PreparationRequirement
from tests import test_render_job_foundation as upstream


@dataclass
class RecursiveRecord:
    children: tuple["RecursiveRecord", ...]


def policy():
    return PresentationPolicySpec("1", "1", *tuple(PresentationChoice))


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upstream.RenderJobTests.setUpClass()
        cls.addClassCleanup(upstream.RenderJobTests.doClassCleanups)
        cls.fixture = upstream.RenderJobTests()
        cls.fixture.setUp()
        cls.draft = cls.fixture.draft
        cls.image = cls.fixture.image_draft()
        cls.base = cls.fixture.base
        cls.config = cls.fixture.configuration

    def build(self, draft=None):
        return build_detached_presentation_policy_proposal(
            self.draft if draft is None else draft, policy=policy())

    def live(self, draft=None, manifest=None, **kwargs):
        return build_presentation_policy_proposal(
            self.base if manifest is None else manifest,
            self.draft if draft is None else draft,
            output_profile=upstream.PROFILE, spec=upstream.SPEC,
            policy=kwargs.pop("policy", policy()), **dict(self.config, **kwargs))

    def test_exact_policy(self):
        self.assertEqual(validate_policy(policy()), policy())

    def test_missing_policy(self):
        with self.assertRaises(TypeError):
            build_detached_presentation_policy_proposal(self.draft)
        with self.assertRaises(TypeError):
            PresentationPolicySpec("1", "1")

    def test_policy_raw_and_unknown_fields(self):
        with self.assertRaises(ValueError):
            validate_policy(dict(vars(policy())))
        value = policy()
        object.__setattr__(value, "extension", 1)
        with self.assertRaises(ValueError):
            validate_policy(value)

    def test_still_interval(self):
        p = self.build(self.image)
        o, c = p.obligations[0], self.image.visual_clips[0]
        self.assertEqual((o.timeline_start_us, o.timeline_end_us),
                         (c.timeline_start_us, c.timeline_end_us))
        self.assertIs(o.required_still_holding, PresentationChoice.SINGLE_STILL_EXACT_INTERVAL)
        self.assertIsNone(o.required_video_lattice)
        self.assertIsNone(o.required_frame_rate_num)

    def test_required_display_facts(self):
        for draft in (self.draft, self.image):
            p = self.build(draft)
            for o in p.obligations:
                self.assertEqual((o.required_display_width_px, o.required_display_height_px),
                    (draft.output_profile.width_px, draft.output_profile.height_px))
                self.assertIs(o.required_square_pixels, PresentationChoice.SQUARE_PIXELS_NO_CONVERSION)
                self.assertIs(o.required_rotation, PresentationChoice.ZERO_ROTATION)
                self.assertIs(o.required_opacity, PresentationChoice.OPAQUE)
                self.assertIs(o.required_geometry, PresentationChoice.EXACT_DISPLAY_GEOMETRY_NO_TRANSFORMATION)

    def test_matching_geometry_still_blocked(self):
        for draft in (self.draft, self.image):
            a = draft.entry_assessments[0]
            self.assertEqual((a.source_width_px, a.source_height_px),
                (draft.output_profile.width_px, draft.output_profile.height_px))
            p = self.build(draft)
            self.assertEqual((p.obligations[0].source_width_px, p.obligations[0].source_height_px),
                (draft.output_profile.width_px, draft.output_profile.height_px))
            blocker = (PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED
                if draft is self.image else PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED)
            self.assertIn(blocker, p.draft.entry_assessments[0].requirements)
            self.assertIn(blocker, p.draft.requirements)
            a = assess_presentation_policy_proposal(p)
            for name in ("source_compliance", "renderer_adapter_compatibility", "executability"):
                self.assertIs(getattr(a, name), AssessmentBoundary.NOT_ASSESSED)

    def dimension_draft(self, draft, **dimensions):
        entry = replace(draft.entry_assessments[0], **dimensions)
        requirements = [r for r in entry.requirements if r not in (
            PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,
            PreparationRequirement.TRANSFORM_POLICY_REQUIRED)]
        if entry.source_width_px is None or entry.source_height_px is None:
            requirements.append(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED)
        elif (entry.source_width_px, entry.source_height_px) != (
                draft.output_profile.width_px, draft.output_profile.height_px):
            requirements.append(PreparationRequirement.TRANSFORM_POLICY_REQUIRED)
        return self.fixture.forged_requirements(replace(draft,
            entry_assessments=(entry,) + draft.entry_assessments[1:]), requirements)

    def assert_dimension_binding(self, name, alternate):
        for draft in (self.draft, self.image):
            with self.subTest(source_usage=draft.visual_clips[0].source_usage):
                original = self.build(draft)
                forged = self.dimension_draft(draft, **{name: alternate})
                self.assertEqual(validate_draft(forged), forged)
                rebuilt = self.build(forged)
                self.assertEqual(getattr(rebuilt.obligations[0], name), alternate)
                self.assertNotEqual(rebuilt.obligations[0], original.obligations[0])
                stale = replace(original, draft=forged)
                validation.preflight(stale)
                # Both authorities pass; only exact reconstruction must reject.
                with patch.object(validation, "derive_obligations",
                        wraps=validation.derive_obligations) as derive:
                    with self.assertRaises(PresentationPolicyError):
                        validate_proposal(stale)
                    derive.assert_called_once_with(forged, original.policy)

    def test_source_width_binding(self):
        self.assert_dimension_binding("source_width_px", 641)

    def test_source_height_binding(self):
        self.assert_dimension_binding("source_height_px", 481)

    def test_missing_dimensions(self):
        for draft in (self.draft, self.image):
            for dimensions in ({"source_width_px": None}, {"source_height_px": None},
                    {"source_width_px": None, "source_height_px": None}):
                with self.subTest(dimensions=dimensions):
                    changed = self.dimension_draft(draft, **dimensions)
                    self.assertEqual(validate_draft(changed), changed)
                    p = self.build(changed)
                    for name, value in dimensions.items():
                        self.assertIs(getattr(p.obligations[0], name), value)
                    self.assertIn(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,
                        p.draft.entry_assessments[0].requirements)
                    self.assertIn(PreparationRequirement.GEOMETRY_NOT_ESTABLISHED,
                        p.draft.requirements)

    def test_dimension_validation(self):
        from creator_studio.render_job.models import MAX_INTEGER
        self.assertEqual(models.MAX_INTEGER, MAX_INTEGER)
        p = self.build()
        for name in ("source_width_px", "source_height_px"):
            for value in (True, False, 0, -1, MAX_INTEGER + 1, 640.0, "640"):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(PresentationPolicyError):
                        validate_proposal(replace(p, obligations=(replace(
                            p.obligations[0], **{name: value}),) + p.obligations[1:]))
            for value in (1, MAX_INTEGER):
                changed = self.dimension_draft(self.draft, **{name: value})
                self.assertEqual(validate_draft(changed), changed)
                self.assertEqual(getattr(self.build(changed).obligations[0], name), value)

    def test_no_authorized_operations(self):
        names = {f.name for f in fields(PresentationObligation)}
        self.assertFalse(names & {"scale", "crop", "pad", "reframe", "retime", "trim", "loop",
            "freeze", "speed", "reverse", "frame_duplication", "frame_dropping", "fps_conversion"})

    def test_forbidden_imports_not_loaded(self):
        import sys
        self.assertNotIn("engine.renderer", sys.modules)
        self.assertNotIn("engine.timeline_renderer", sys.modules)

    def test_video_lattice(self):
        p = self.build()
        for o in p.obligations:
            self.assertEqual((o.required_frame_rate_num, o.required_frame_rate_den),
                (self.draft.output_profile.frame_rate_num, self.draft.output_profile.frame_rate_den))
            self.assertIs(o.required_video_lattice,
                PresentationChoice.EXACT_OUTPUT_LATTICE_WHOLE_VIDEO_NO_TRANSFORMATION)
            self.assertEqual(o.required_source_start_us, 0)
            self.assertIsNone(o.required_still_holding)

    def test_rational_30000_1001(self):
        # Re-sign a structurally valid detached profile; no live authority follows.
        from creator_studio.manifest.render_preparation_validation import frame_aligned, conclusion
        d = replace(self.draft, output_profile=replace(self.draft.output_profile,
            frame_rate_num=30000, frame_rate_den=1001))
        reqs = tuple(r for r in d.requirements if r is not PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        if not frame_aligned(d.output_duration_us, d.output_profile):
            reqs = (PreparationRequirement.FRAME_ALIGNMENT_REQUIRED,) + reqs
        d = self.fixture.resign(replace(d, requirements=reqs, conclusion=conclusion(reqs)))
        p = self.build(d)
        self.assertEqual((p.obligations[0].required_frame_rate_num,
                          p.obligations[0].required_frame_rate_den), (30000, 1001))

    def test_order(self):
        p = self.build()
        self.assertEqual(tuple(o.placement_id for o in p.obligations),
                         tuple(c.placement_id for c in self.draft.visual_clips))
        for obs in (p.obligations[:-1], p.obligations + p.obligations[:1],
                    tuple(reversed(p.obligations)), (p.obligations[0],) * len(p.obligations)):
            with self.assertRaises(ValueError):
                validate_proposal(replace(p, obligations=obs))

    def test_blockers(self):
        for d, blocker in ((self.draft, PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED),
                          (self.image, PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED)):
            p = self.build(d)
            self.assertIs(p.draft, d)
            self.assertIn(blocker, p.draft.entry_assessments[0].requirements)
            self.assertIn(blocker, p.draft.requirements)
            self.assertEqual(validate_draft(p.draft), d)

    def test_detached_assessment(self):
        a = assess_presentation_policy_proposal(self.build())
        self.assertTrue(a.structurally_valid and a.policy_declared)
        self.assertFalse(a.current_logically_bound)
        for name in ("source_compliance", "renderer_adapter_compatibility", "executability"):
            self.assertIs(getattr(a, name), AssessmentBoundary.NOT_ASSESSED)

    def test_live_gate(self):
        with patch("creator_studio.render_job.engine.construct_render_job_spec",
                   side_effect=AssertionError("completion forbidden")):
            p = self.live()
            self.assertEqual(p, self.build())
            a = assess_current_presentation_policy(self.base, self.draft,
                output_profile=upstream.PROFILE, spec=upstream.SPEC, policy=policy(), **self.config)
            self.assertTrue(a.current_logically_bound)
            self.assertIs(a.source_compliance, AssessmentBoundary.NOT_ASSESSED)
            self.assertIs(a.executability, AssessmentBoundary.NOT_ASSESSED)
            self.assertIs(a.renderer_adapter_compatibility, AssessmentBoundary.NOT_ASSESSED)

    def test_live_changed_manifest(self):
        m = deepcopy(self.base)
        m.render_preparation.active_render_preparation_plan_id = None
        with self.assertRaises(ValueError):
            self.live(manifest=m)

    def test_recomputed_integrity_is_not_authority(self):
        clip = replace(self.draft.visual_clips[0], placement_id="placement:forged")
        entry = replace(self.draft.entry_assessments[0], placement_id="placement:forged")
        forged = self.fixture.resign(replace(self.draft,
            visual_clips=(clip,) + self.draft.visual_clips[1:],
            entry_assessments=(entry,) + self.draft.entry_assessments[1:]))
        p = self.build(forged)
        self.assertFalse(assess_presentation_policy_proposal(p).current_logically_bound)
        with self.assertRaises(ValueError):
            self.live(forged)

    def test_live_stale_detached(self):
        self.assertEqual(validate_proposal(self.build(self.image)).draft, self.image)
        with self.assertRaises(ValueError):
            self.live(self.image)

    def assert_detached_valid_live_rejected(self, forged):
        self.assertEqual(validate_draft(forged), forged)
        p = self.build(forged)
        self.assertEqual(validate_proposal(p), p)
        self.assertFalse(assess_presentation_policy_proposal(p).current_logically_bound)
        with patch.object(engine, "build_render_job_draft", wraps=engine.build_render_job_draft) as fresh:
            with self.assertRaises(PresentationPolicyError):
                self.live(forged)
            fresh.assert_called_once()
        self.assertNotEqual(forged, self.draft)

    def test_live_substituted_asset(self):
        self.live()  # Establish a valid current authority baseline.
        c = replace(self.draft.visual_clips[0], asset_id="asset:forged",
            materialization_id="materialization:forged",
            asset_evidence_signature="a" * 64,
            materialization_evidence_signature="b" * 64)
        forged = self.fixture.resign(replace(self.draft,
            visual_clips=(c,) + self.draft.visual_clips[1:]))
        self.assert_detached_valid_live_rejected(forged)

    def test_live_reordered(self):
        self.assertGreaterEqual(len(self.draft.visual_clips), 2)
        from creator_studio.manifest.render_preparation_validation import frame_aligned, conclusion
        clips, entries = [], []
        cursor = 0
        for ordinal, (c, e) in enumerate(reversed(tuple(zip(
                self.draft.visual_clips, self.draft.entry_assessments)))):
            end = cursor + c.timeline_end_us - c.timeline_start_us
            clips.append(replace(c, ordinal=ordinal, timeline_start_us=cursor, timeline_end_us=end))
            reqs = tuple(r for r in e.requirements if r is not PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
            if not frame_aligned(cursor, self.draft.output_profile) or not frame_aligned(end, self.draft.output_profile):
                reqs = (PreparationRequirement.FRAME_ALIGNMENT_REQUIRED,) + reqs
            entries.append(replace(e, timeline_start_us=cursor, timeline_end_us=end,
                requirements=reqs, conclusion=conclusion(reqs)))
            cursor = end
        from creator_studio.manifest.render_preparation_validation import derive_uncovered_intervals
        uncovered = tuple(derive_uncovered_intervals(
            [(c.timeline_start_us, c.timeline_end_us) for c in clips], self.draft.output_duration_us))
        aggregate = []
        if not frame_aligned(self.draft.output_duration_us, self.draft.output_profile):
            aggregate.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        if uncovered:
            aggregate.append(PreparationRequirement.UNCOVERED_VISUAL_INTERVALS)
        for e in entries:
            for r in e.requirements:
                if r not in aggregate:
                    aggregate.append(r)
        forged = self.fixture.resign(replace(self.draft,
            visual_clips=tuple(clips), entry_assessments=tuple(entries),
            uncovered_intervals=uncovered, requirements=tuple(aggregate), conclusion=conclusion(aggregate)))
        self.assert_detached_valid_live_rejected(forged)

    def test_resigned_blocker_removal(self):
        from creator_studio.render_job.models import RenderJobError
        for d, blocker in ((self.image, PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED),
                          (self.draft, PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED)):
            with self.subTest(blocker=blocker):
                p = self.build(d)
                forged = self.fixture.forged_requirements(d,
                    tuple(r for r in d.entry_assessments[0].requirements if r is not blocker))
                self.assertNotEqual(forged.binding, d.binding)
                self.assertEqual(self.fixture.resign(forged), forged)
                # Preflight passes; rejection is specifically M74 semantic reconstruction.
                validation.preflight(forged, type(d))
                with self.assertRaises(RenderJobError):
                    self.build(forged)
                with self.assertRaises(RenderJobError):
                    validate_proposal(replace(p, draft=forged))

    def test_evidence_binding(self):
        p = self.build()
        for name in ("materialization_evidence_signature", "asset_evidence_signature"):
            with self.subTest(signature=name):
                original = getattr(p.draft.visual_clips[0], name)
                alternate = ("a" if original != "a" * 64 else "b") * 64
                self.assertEqual(getattr(p.obligations[0], name), original)
                for changed in (alternate, None, "A" * 64, "a" * 63,
                                getattr(p.draft.visual_clips[1], name)):
                    if changed == original:
                        continue
                    with self.assertRaises(ValueError):
                        validate_proposal(replace(p, obligations=(replace(p.obligations[0],
                            **{name: changed}),) + p.obligations[1:]))
                clip = replace(p.draft.visual_clips[0], **{name: alternate})
                d = self.fixture.resign(replace(p.draft,
                    visual_clips=(clip,) + p.draft.visual_clips[1:]))
                self.assertEqual(validate_draft(d), d)
                rebuilt = self.build(d)
                self.assertEqual(getattr(rebuilt.obligations[0], name), alternate)
                self.assertNotEqual(rebuilt.obligations, p.obligations)

    def test_policy_alternatives_closed(self):
        # V1 has no second valid policy: changing a choice must reject.
        with self.assertRaises(ValueError):
            self.live(policy=replace(policy(), opacity_rule=PresentationChoice.ZERO_ROTATION))

    def test_frozen_and_tuples(self):
        p = self.build()
        for value in (p, p.policy, p.obligations[0], assess_presentation_policy_proposal(p)):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        with self.assertRaises(ValueError):
            validate_proposal(replace(p, obligations=list(p.obligations)))

    def test_atomicity(self):
        before_m, before_d = deepcopy(self.base), deepcopy(self.draft)
        self.live()
        with self.assertRaises(ValueError):
            self.live(policy=replace(policy(), contract_version="2"))
        self.assertEqual(self.base, before_m)
        self.assertEqual(self.draft, before_d)

    def test_unresolved_fail_closed(self):
        from creator_studio.manifest.render_timeline import SourceUsage
        # Even internal derivation must not silently omit unresolved rows.
        d = replace(self.draft, visual_clips=(replace(self.draft.visual_clips[0],
            source_usage=SourceUsage.UNRESOLVED),))
        with self.assertRaises(ValueError):
            validation.derive_obligations(d, policy())

    def test_hostile_dictionary(self):
        events = []
        class Hostile(dict):
            def __len__(self):
                events.append("len")
                return 0
        p = self.build()
        object.__setattr__(p, "__dict__", Hostile(vars(p)))
        with self.assertRaises(ValueError):
            validate_proposal(p)
        self.assertEqual(events, [])

    def test_hostile_key(self):
        events = []
        class Key:
            def __hash__(self):
                events.append("hash")
                return 1
            def __eq__(self, other):
                events.append("eq")
                return False
            def __repr__(self):
                events.append("repr")
                return "key"
            def __str__(self):
                events.append("str")
                return "key"
        p = self.build()
        members = vars(p)
        del members["policy"]
        members[Key()] = policy()
        self.assertEqual(len(members), len(fields(p)))
        events.clear()
        with self.assertRaises(PresentationPolicyError):
            validate_proposal(p)
        self.assertEqual(events, [])

    def test_cycles(self):
        original = validation.require
        for indirect in (False, True):
            root = RecursiveRecord(())
            child = RecursiveRecord((root,)) if indirect else root
            root.children = (child,)
            ancestry_rejections = []
            def checked(condition):
                if not condition:
                    ancestry_rejections.append(any(
                        frame.function == "walk" and "not in ancestry" in "".join(frame.code_context or ())
                        for frame in inspect.stack()))
                return original(condition)
            with patch.object(validation, "require", side_effect=checked):
                with self.assertRaises(PresentationPolicyError):
                    validation.preflight(root, RecursiveRecord)
            self.assertEqual(ancestry_rejections, [True])
        leaf = RecursiveRecord(())
        validation.preflight(RecursiveRecord((leaf, leaf)), RecursiveRecord)

    def test_shared_acyclic(self):
        o = self.build().obligations[0]
        validation.preflight((o, o), tuple[PresentationObligation, ...])

    def test_depth_boundary(self):
        value, schema = 1, int
        for _ in range(32):
            value, schema = (value,), tuple[schema, ...]
        validation.preflight(value, schema)
        with self.assertRaises(ValueError):
            validation.preflight((value,), tuple[schema, ...])

    def test_node_boundary(self):
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 4):
            validation.preflight((1, 1, 1), tuple[int, ...])
            with self.assertRaises(ValueError):
                validation.preflight((1, 1, 1, 1), tuple[int, ...])

    def test_actual_node_boundary(self):
        shared = (1,) * 1000
        value = (shared,) * 1998 + ((),)
        schema = tuple[tuple[int, ...], ...]
        validation.preflight(value, schema)
        with self.assertRaises(ValueError):
            validation.preflight(value + ((),), schema)

    def test_capacity_4096_end_to_end(self):
        # Split the existing exact output interval into 4096 virtual still entries.
        # No media, runtime observations, or production limits are changed.
        from creator_studio.manifest.render_preparation_validation import frame_aligned, conclusion
        d = self.image
        c, e = d.visual_clips[0], d.entry_assessments[0]
        clips, entries, aggregate = [], [], []
        if not frame_aligned(d.output_duration_us, d.output_profile):
            aggregate.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
        for i in range(4096):
            start = i * d.output_duration_us // 4096
            end = (i + 1) * d.output_duration_us // 4096
            reqs = []
            if not frame_aligned(start, d.output_profile) or not frame_aligned(end, d.output_profile):
                reqs.append(PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
            reqs.extend(r for r in e.requirements if r is not PreparationRequirement.FRAME_ALIGNMENT_REQUIRED)
            placement = "placement:capacity:" + str(i)
            clips.append(replace(c, ordinal=i, placement_id=placement,
                timeline_start_us=start, timeline_end_us=end))
            entries.append(replace(e, placement_id=placement, timeline_start_us=start,
                timeline_end_us=end, requirements=tuple(reqs), conclusion=conclusion(reqs)))
            for r in reqs:
                if r not in aggregate:
                    aggregate.append(r)
        d = self.fixture.resign(replace(d, visual_clips=tuple(clips),
            entry_assessments=tuple(entries), uncovered_intervals=(),
            requirements=tuple(aggregate), conclusion=conclusion(aggregate)))
        self.assertEqual(validate_draft(d), d)
        obligations = validation.derive_obligations(d, policy())
        self.assertEqual(len(d.visual_clips), 4096)
        self.assertEqual(len(obligations), 4096)
        p = PresentationPolicyProposal(d, policy(), obligations)
        self.assertIs(validate_proposal(p), p)

    def test_capacity_4097_m75_boundary(self):
        from creator_studio.render_job.models import MAX_VISUAL_ENTRIES
        self.assertEqual(MAX_VISUAL_ENTRIES, 4096)
        self.assertEqual(models.MAX_PRESENTATION_OBLIGATIONS, 4096)
        p = self.build()
        # Earliest M75-owned boundary: tuple arity, before semantic reconstruction.
        with patch.object(validation, "validate_draft", side_effect=AssertionError("too late")):
            with self.assertRaises(PresentationPolicyError):
                validate_proposal(replace(p, obligations=(p.obligations[0],) * 4097))
        validation.preflight((p.obligations[0],) * 4096, tuple[PresentationObligation, ...])

    def test_scalar_bounds(self):
        for value in ("x" * 257, 1 << 63, -1, True, 0.0):
            with self.assertRaises(ValueError):
                validation.preflight(value, str if type(value) is str else int)

    def test_isolation(self):
        root = Path(__file__).resolve().parents[1] / "creator_studio" / "presentation_policy"
        forbidden = {"subprocess", "pathlib", "os", "engine.renderer", "engine.timeline_renderer"}
        for file in root.glob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(a.name in forbidden for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, forbidden)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"construct_render_job_spec", "RenderJobSpec", "open"})
        for cls in (PresentationPolicySpec, PresentationObligation, PresentationPolicyProposal,
                    PresentationPolicyAssessment):
            names = {f.name for f in fields(cls)}
            self.assertFalse(names & {"path", "source_path", "output_path", "codec", "stage",
                "history", "cache", "artifact", "render_ready", "source_compliant"})


def bad_policy_case(field, value):
    def test(self):
        with self.assertRaises(ValueError):
            validate_policy(replace(policy(), **{field: value}))
    return test

for _field in fields(PresentationPolicySpec):
    for _label, _value in (("none", None), ("bool", True), ("integer", 1),
                            ("unknown", "UNKNOWN"), ("version", "2")):
        setattr(PresentationTests, "test_policy_" + _field.name + "_" + _label,
                bad_policy_case(_field.name, _value))


def tamper_case(field):
    def test(self):
        p = self.build()
        o = p.obligations[0]
        old = getattr(o, field)
        if type(old) is int:
            changed = old + 1
        elif type(old) is str:
            changed = "substituted"
        else:
            changed = None if old is not None else 1
        obs = (replace(o, **{field: changed}),) + p.obligations[1:]
        with self.assertRaises(ValueError):
            validate_proposal(replace(p, obligations=obs))
    return test

for _field in fields(PresentationObligation):
    setattr(PresentationTests, "test_tamper_" + _field.name, tamper_case(_field.name))


def hostile_case(hook):
    def test(self):
        events = []
        def hostile(*args):
            events.append(hook)
            return None
        class Meta(type):
            __hash__ = hostile
            __eq__ = hostile
        cls = Meta("Hostile", (), {hook: hostile})
        p = self.build()
        object.__setattr__(p, "policy", cls())
        with self.assertRaises(ValueError):
            validate_proposal(p)
        self.assertEqual(events, [])
    return test

for _hook in ("__getattribute__", "__getattr__", "__repr__", "__str__", "__hash__",
              "__eq__", "__iter__", "__len__", "__contains__", "__getitem__", "__deepcopy__"):
    setattr(PresentationTests, "test_hostile_" + _hook, hostile_case(_hook))

if __name__ == "__main__":
    unittest.main()
