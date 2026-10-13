"""Synthetic offline M76 schema, authority, capacity and isolation tests."""
import ast
from copy import deepcopy
from dataclasses import dataclass, fields, replace, FrozenInstanceError
import inspect
import unittest
from unittest.mock import patch
from creator_studio.source_observation import *
from creator_studio.source_observation import models, validation, engine
from creator_studio.source_observation.models import MAX_INTEGER
from creator_studio.presentation_policy import validate_proposal
from creator_studio.presentation_policy import engine as policy_engine
from creator_studio.presentation_policy import (
    build_detached_presentation_policy_proposal, PresentationPolicySpec, PresentationChoice)
from creator_studio.manifest.render_preparation import PreparationRequirement
from tests import test_render_job_foundation as upstream


def stream(**changes):
    values = dict(stream_index=0, source_kind=SourceKind.STILL_IMAGE,
        coded_width_px=None, coded_height_px=None, display_width=None, display_height=None,
        sample_aspect_ratio=None, reported_display_aspect_ratio=None,
        orientation=Orientation.UNKNOWN, rotation_degrees=None,
        other_display_transform_status=OtherDisplayTransformStatus.UNKNOWN,
        alpha_presence=AlphaPresence.UNKNOWN, effective_opacity=EffectiveOpacity.UNKNOWN,
        pixel_format=None, decoded_presentation_count=None,
        presentation_multiplicity=PresentationMultiplicity.UNKNOWN,
        nominal_frame_rate=None, average_frame_rate=None, time_base=None,
        stream_start_ticks=None, stream_duration_ticks=None,
        presentation_start_ticks=None, presentation_end_exclusive_ticks=None,
        timestamp_enumeration_status=TimestampEnumerationStatus.ABSENT, frames=())
    return VisualStreamObservation(**dict(values, **changes))

def identity(digest="a" * 64, count=1):
    return SourceByteIdentity("asset:sha256:" + digest, digest, count)

def claim(**changes):
    values = dict(byte_identity=identity(), observer_id="observer", observer_version="1",
        observation_method_id="reported", observation_method_version="1",
        visual_stream_inventory_complete=False, visual_streams=(stream(),), container_duration_us=None)
    return SourceObservationClaim(**dict(values, **changes))

@dataclass
class RecursiveRecord:
    children: tuple["RecursiveRecord", ...]

class SourceObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        upstream.RenderJobTests.setUpClass()
        cls.addClassCleanup(upstream.RenderJobTests.doClassCleanups)
        cls.fixture = upstream.RenderJobTests()
        cls.fixture.setUp()
        cls.base = cls.fixture.base
        cls.config = cls.fixture.configuration
        cls.policy = PresentationPolicySpec("1", "1", *tuple(PresentationChoice))
        cls.proposal = build_detached_presentation_policy_proposal(cls.fixture.draft, policy=cls.policy)
        cls.spec = SourceObservationSpec("1", "1")

    def bindings(self, proposal=None, present=True):
        proposal = self.proposal if proposal is None else proposal
        return tuple(ObservationBinding(*(getattr(o, n) for n in (
            "ordinal", "placement_id", "materialization_id", "asset_id",
            "materialization_evidence_signature", "asset_evidence_signature")),
            ObservationReferenceStatus.PRESENT if present else ObservationReferenceStatus.ABSENT,
            i if present else None) for i, o in enumerate(proposal.obligations))

    def claims(self, proposal=None):
        proposal = self.proposal if proposal is None else proposal
        assets = {a.asset_id: a for a in self.base.acquisition.assets}
        return tuple(claim(byte_identity=SourceByteIdentity(a.asset_id, a.sha256, a.byte_count))
            for o in proposal.obligations for a in (assets[o.asset_id],))

    def bundle(self, **changes):
        values = dict(proposal=self.proposal, spec=self.spec,
                      claims=self.claims(), bindings=self.bindings())
        return validate_bundle(SourceObservationBundle(**dict(values, **changes)))

    def live(self, proposal=None, manifest=None, **changes):
        values = dict(output_profile=upstream.PROFILE, spec=upstream.SPEC,
            policy=self.policy, observation_spec=self.spec, claims=self.claims(),
            bindings=self.bindings(), **self.config)
        return build_source_observation_bundle(self.base if manifest is None else manifest,
            self.proposal if proposal is None else proposal, **dict(values, **changes))

    def invalid(self, function, *args):
        with self.assertRaises(SourceObservationError) as caught:
            function(*args)
        self.assertEqual(str(caught.exception), "source_observation_invalid")

    def test_explicit_public_exports(self):
        import creator_studio.source_observation as public
        expected = {
            name for name, value in vars(models).items()
            if isinstance(value, type) and
            (value.__module__ == models.__name__ or name == "AssessmentBoundary")
        }
        expected.update(("validate_spec", "validate_byte_identity", "validate_rational",
            "validate_claim", "validate_bundle", "build_detached_source_observation_bundle",
            "build_source_observation_bundle", "assess_source_observation_bundle",
            "assess_current_source_observation"))
        self.assertEqual(set(public.__all__), expected)
        self.assertEqual(len(public.__all__), len(expected))
        for name in public.__all__:
            self.assertTrue(hasattr(public, name))
        for name in ("dataclass", "Enum", "PresentationPolicyProposal", "preflight",
                     "require", "coverage", "MAX_INTEGER"):
            self.assertFalse(hasattr(public, name))

    def test_spec(self):
        self.assertEqual(validate_spec(self.spec), self.spec)
        for s in (SourceObservationSpec("2", "1"), SourceObservationSpec("1", "2"),
                  SourceObservationSpec(1, "1"), {"contract_version": "1"}):
            self.invalid(validate_spec, s)

    def test_spec_subclass_extra_missing(self):
        class Child(SourceObservationSpec):
            pass
        self.invalid(validate_spec, Child("1", "1"))
        for action in (lambda s: object.__setattr__(s, "extra", 1),
                       lambda s: object.__delattr__(s, "engine_version")):
            s = SourceObservationSpec("1", "1")
            action(s)
            self.invalid(validate_spec, s)
        with self.assertRaises(TypeError):
            SourceObservationSpec("1")

    def test_byte_identity(self):
        self.assertEqual(validate_byte_identity(identity()), identity())
        for i in (identity("A" * 64), identity("a" * 63), identity("g" * 64),
                  identity(count=True), identity(count=0), identity(count=-1), identity(count=536870913),
                  replace(identity(), asset_id="asset:sha256:" + "b" * 64)):
            self.invalid(validate_byte_identity, i)
        validate_byte_identity(identity(count=536870912))

    def test_rational_exact(self):
        for r in (ExactRational(30000, 1001), ExactRational(-3, 2), ExactRational(2, 4)):
            self.assertIs(validate_rational(r), r)
        self.assertNotEqual(ExactRational(2, 4), ExactRational(1, 2))
        for r in (ExactRational(1, 0), ExactRational(1, -1), ExactRational(True, 2),
                  ExactRational(1, True), ExactRational(1.0, 2), ExactRational(MAX_INTEGER+1, 2)):
            self.invalid(validate_rational, r)

    def test_still_ambiguous_states(self):
        for orientation in Orientation:
            for multiplicity in PresentationMultiplicity:
                c = claim(visual_streams=(stream(coded_width_px=123, coded_height_px=456,
                    display_width=ExactRational(246, 1), display_height=ExactRational(456, 1),
                    sample_aspect_ratio=ExactRational(2, 1), orientation=orientation,
                    alpha_presence=AlphaPresence.PRESENT,
                    presentation_multiplicity=multiplicity),))
                self.assertIs(validate_claim(c), c)

    def test_video_facts_and_defective_timestamps(self):
        frames = tuple(FrameObservation(i, pts, duration, TimestampOrigin.STREAM_TIMEBASE)
                       for i, (pts, duration) in enumerate(((-4, 1), (0, 3), (0, 1), (-2, 0), (None, None))))
        s = stream(source_kind=SourceKind.WHOLE_VIDEO, time_base=ExactRational(1, 90000),
            nominal_frame_rate=ExactRational(30000, 1001), average_frame_rate=ExactRational(25, 1),
            stream_start_ticks=-5, stream_duration_ticks=100, presentation_start_ticks=-4,
            presentation_end_exclusive_ticks=99, decoded_presentation_count=5,
            timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE, frames=frames)
        self.assertEqual(validate_claim(claim(visual_streams=(s,))).visual_streams[0].frames, frames)

    def test_inventory(self):
        for complete in (True, False):
            validate_claim(claim(visual_stream_inventory_complete=complete,
                visual_streams=(stream(), stream(stream_index=2))))
        self.invalid(validate_claim, claim(visual_streams=(stream(), stream())))
        self.invalid(validate_claim, claim(visual_stream_inventory_complete=1))

    def test_enumeration_consistency(self):
        f = FrameObservation(0, None, None, TimestampOrigin.UNKNOWN)
        validate_claim(claim(visual_streams=(stream(),)))
        validate_claim(claim(visual_streams=(stream(frames=(f, replace(f, ordinal=3)),
            timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),)))
        for s in (stream(timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),
                  stream(frames=(f,)),
                  stream(frames=(f,), timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE),
                  stream(frames=(f,), timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE,
                         decoded_presentation_count=2),
                  stream(frames=(replace(f, ordinal=1),), timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE,
                         decoded_presentation_count=1)):
            self.invalid(validate_claim, claim(visual_streams=(s,)))
        validate_claim(claim(visual_streams=(stream(frames=(replace(f, ordinal=3),),
            decoded_presentation_count=10, timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),)))
        validate_claim(claim(visual_streams=(stream(decoded_presentation_count=0,
            timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE),)))

    def test_no_sort_or_repair(self):
        frames = tuple(FrameObservation(i, p, None, TimestampOrigin.UNKNOWN) for i, p in ((1, 3), (0, 5)))
        c = claim(visual_streams=(stream(frames=frames,
            timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),))
        self.invalid(validate_claim, c)
        self.assertEqual(c.visual_streams[0].frames, frames)

    def test_internal_contradictions(self):
        for changes in (dict(stream_index=-1), dict(stream_duration_ticks=-1),
            dict(presentation_start_ticks=2, presentation_end_exclusive_ticks=1),
            dict(presentation_multiplicity=PresentationMultiplicity.SINGLE_STILL, decoded_presentation_count=2),
            dict(presentation_multiplicity=PresentationMultiplicity.ANIMATED, decoded_presentation_count=1),
            dict(orientation=Orientation.IDENTITY, rotation_degrees=ExactRational(90, 1)),
            dict(orientation=Orientation.ROTATED_90, rotation_degrees=ExactRational(0, 1)),
            dict(sample_aspect_ratio=ExactRational(0, 1))):
            self.invalid(validate_claim, claim(visual_streams=(stream(**changes),)))

    def test_claim_closed(self):
        for changes in (dict(observer_id=""), dict(observer_version=1),
                        dict(observation_method_id="x" * 257), dict(container_duration_us=-1),
                        dict(visual_streams=[stream()])):
            self.invalid(validate_claim, claim(**changes))
        c = claim()
        object.__setattr__(c, "metadata", {})
        self.invalid(validate_claim, c)

    def test_bindings_order_identity_signatures(self):
        b = self.bundle()
        for name in ("ordinal", "placement_id", "materialization_id", "asset_id",
                     "materialization_evidence_signature", "asset_evidence_signature"):
            value = 1 if name == "ordinal" else "substitute"
            altered = replace(b.bindings[0], **{name: value})
            self.invalid(validate_bundle, replace(b, bindings=(altered,) + b.bindings[1:]))
        for bindings in (b.bindings[:-1], b.bindings + b.bindings[:1],
                         tuple(reversed(b.bindings)), (b.bindings[0],) * len(b.bindings)):
            if bindings != b.bindings:
                self.invalid(validate_bundle, replace(b, bindings=bindings))

    def test_absent_reference(self):
        b = self.bundle(claims=(), bindings=self.bindings(present=False))
        self.assertIs(assess_source_observation_bundle(b).observation_coverage, ObservationCoverage.ABSENT)
        for index in (-1, 0, True):
            self.invalid(validate_bundle, replace(b, bindings=(replace(b.bindings[0], observation_index=index),) + b.bindings[1:]))

    def test_coverage_and_boundaries(self):
        b = self.bundle()
        a = assess_source_observation_bundle(b)
        self.assertFalse(a.current_logically_bound)
        self.assertIs(a.observation_coverage, ObservationCoverage.COMPLETE)
        for n in ("physical_byte_verification", "physical_observation_authority", "presentation_compliance",
                  "renderer_adapter_compatibility", "executability"):
            self.assertIs(getattr(a, n), AssessmentBoundary.NOT_ASSESSED)
        if len(b.bindings) > 1:
            partial = replace(b, bindings=(replace(b.bindings[0], observation_status=ObservationReferenceStatus.ABSENT,
                observation_index=None),) + b.bindings[1:])
            self.assertIs(assess_source_observation_bundle(partial).observation_coverage, ObservationCoverage.PARTIAL)

    def test_live_exact_and_assessment(self):
        self.assertEqual(self.live(), self.bundle())
        a = assess_current_source_observation(self.base, self.proposal, output_profile=upstream.PROFILE,
            spec=upstream.SPEC, policy=self.policy, observation_spec=self.spec,
            claims=self.claims(), bindings=self.bindings(), **self.config)
        self.assertTrue(a.structurally_valid)
        self.assertTrue(a.current_logically_bound)
        self.assertIs(a.physical_byte_verification, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(a.presentation_compliance, AssessmentBoundary.NOT_ASSESSED)

    def test_live_byte_count(self):
        claims = self.claims()
        original = claims[0].byte_identity
        different = 1 if original.byte_count != 1 else 2
        wrong = replace(claims[0], byte_identity=replace(original, byte_count=different))
        detached = self.bundle(claims=(wrong,) + claims[1:])
        self.assertFalse(assess_source_observation_bundle(detached).current_logically_bound)
        calls = []
        def real_upstream(*args, **kwargs):
            fresh = policy_engine.build_presentation_policy_proposal(*args, **kwargs)
            self.assertEqual(fresh, detached.proposal)
            calls.append(fresh)
            return fresh
        checks = []
        def checked_require(condition):
            checks.append(condition)
            validation.require(condition)
        with patch.object(engine, "build_presentation_policy_proposal", side_effect=real_upstream) as live:
            with patch.object(engine, "require", side_effect=checked_require):
                self.invalid(lambda: self.live(claims=detached.claims))
            live.assert_called_once()
        self.assertEqual(calls, [self.proposal])
        # Equality and all retained lookups succeed before byte identity comparison.
        self.assertEqual(checks, [True, True, True, True, False])
        self.assertEqual(wrong.byte_identity.asset_id, original.asset_id)
        self.assertEqual(wrong.byte_identity.sha256, original.sha256)
        self.assertNotEqual(wrong.byte_identity.byte_count, original.byte_count)
        self.assertEqual(self.claims(), claims)

    def test_upstream_invalid_manifest_state_rejection(self):
        m = deepcopy(self.base)
        m.acquisition.assets[0] = replace(m.acquisition.assets[0], byte_count=m.acquisition.assets[0].byte_count+1)
        with self.assertRaises(SourceObservationError):
            self.live(manifest=m)

    def test_invalid_policy_version(self):
        # M75 V1 offers no alternate valid policy tuple for stale-policy equality testing.
        with self.assertRaises(SourceObservationError):
            self.live(policy=replace(self.policy, contract_version="2"))

    def test_forged_proposal_preflight_before_live(self):
        forged = replace(self.proposal, obligations=tuple(reversed(self.proposal.obligations)))
        if forged != self.proposal:
            with patch.object(engine, "build_presentation_policy_proposal") as live:
                with self.assertRaises(SourceObservationError):
                    self.live(proposal=forged)
                live.assert_not_called()

    def test_defensive_equality_simulated_upstream_contract_divergence(self):
        # DEFENSIVE INVARIANT TEST - SIMULATED UPSTREAM CONTRACT DIVERGENCE.
        # Not a reachable stale-authority V1 case.
        unequal = build_detached_presentation_policy_proposal(
            self.fixture.image_draft(), policy=self.policy)
        self.assertEqual(validate_proposal(unequal), unequal)
        self.assertNotEqual(unequal, self.proposal)
        with patch.object(engine, "build_presentation_policy_proposal", return_value=unequal):
            self.invalid(self.live)

    def test_blockers_preserved(self):
        for draft, blocker in ((self.fixture.draft, PreparationRequirement.SOURCE_PRESENTATION_NOT_ESTABLISHED),
                              (self.fixture.image_draft(), PreparationRequirement.IMAGE_PRESENTATION_NOT_ESTABLISHED)):
            p = build_detached_presentation_policy_proposal(draft, policy=self.policy)
            claims = tuple(replace(c, visual_streams=(stream(coded_width_px=upstream.PROFILE.width_px,
                coded_height_px=upstream.PROFILE.height_px, sample_aspect_ratio=ExactRational(1, 1),
                orientation=Orientation.IDENTITY, rotation_degrees=ExactRational(0, 1),
                effective_opacity=EffectiveOpacity.OPAQUE),)) for c in self.claims(p))
            b = self.bundle(proposal=p, claims=claims, bindings=self.bindings(p))
            self.assertIs(b.proposal, p)
            self.assertIn(blocker, b.proposal.draft.requirements)
            self.assertIn(blocker, b.proposal.draft.entry_assessments[0].requirements)

    def test_dimensions(self):
        for w, h in ((16384, 1), (10000, 10000), (1, 16384)):
            validate_claim(claim(visual_streams=(stream(coded_width_px=w, coded_height_px=h),)))
        for w, h in ((16385, 1), (10001, 10000), (0, 1), (True, 1), (1 << 200, 1)):
            self.invalid(validate_claim, claim(visual_streams=(stream(coded_width_px=w, coded_height_px=h),)))
        self.invalid(validate_claim, claim(visual_streams=(stream(display_width=ExactRational(100000001, 10000),
            display_height=ExactRational(10000, 1)),)))
        validate_claim(claim(visual_streams=(stream(display_width=ExactRational(10000, 1),
            display_height=ExactRational(10000, 1)),)))

    def test_stream_capacity(self):
        streams = tuple(stream(stream_index=i) for i in range(17))
        validate_claim(claim(visual_streams=streams[:16]))
        self.invalid(validate_claim, claim(visual_streams=streams))

    def test_claim_capacity(self):
        b = self.bundle()
        validate_bundle(replace(b, claims=(b.claims[0],) * 4096,
            bindings=self.bindings(present=False)))
        self.invalid(validate_bundle, replace(b, claims=(b.claims[0],) * 4097))

    def test_binding_capacity_preflight(self):
        b = self.bundle()
        validation.preflight((b.bindings[0],) * 4096, tuple[ObservationBinding, ...])
        self.invalid(lambda v: validation.preflight(v, tuple[ObservationBinding, ...]), (b.bindings[0],) * 4097)
        # Full semantic binding capacity also requires an upstream valid 4096-obligation M75 graph.

    def test_capacity_4096_semantic_and_shared_claim(self):
        from creator_studio.manifest.render_preparation_validation import frame_aligned, conclusion
        d = self.fixture.image_draft()
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
        d = self.fixture.resign(replace(d, visual_clips=tuple(clips), entry_assessments=tuple(entries),
            uncovered_intervals=(), requirements=tuple(aggregate), conclusion=conclusion(aggregate)))
        p = build_detached_presentation_policy_proposal(d, policy=self.policy)
        bindings = tuple(replace(b, observation_index=0) for b in self.bindings(p))
        b = self.bundle(proposal=p, claims=self.claims(p)[:1], bindings=bindings)
        self.assertEqual(len(b.bindings), 4096)
        self.assertIs(assess_source_observation_bundle(b).observation_coverage, ObservationCoverage.COMPLETE)
        self.invalid(validate_bundle, replace(b, bindings=bindings + bindings[:1]))

    def test_real_upstream_current_authority_rejection(self):
        # REAL UPSTREAM CURRENT-AUTHORITY REJECTION.
        for mode in ("asset", "materialization"):
            d = self.fixture.draft
            c = d.visual_clips[0]
            changes = dict(materialization_id="materialization:" + "e" * 64,
                           materialization_evidence_signature="b" * 64)
            if mode == "asset":
                changes.update(asset_id="asset:sha256:" + "f" * 64,
                               asset_evidence_signature="a" * 64)
            forged = self.fixture.resign(replace(d, visual_clips=(replace(c, **changes),) + d.visual_clips[1:]))
            p = build_detached_presentation_policy_proposal(forged, policy=self.policy)
            self.assertEqual(validate_proposal(p), p)
            claims = self.claims()
            if mode == "asset":
                claims = (replace(claims[0], byte_identity=identity("f" * 64, 17)),) + claims[1:]
            b = self.bundle(proposal=p, claims=claims, bindings=self.bindings(p))
            self.assertFalse(assess_source_observation_bundle(b).current_logically_bound)
            fresh_drafts = []
            def fresh_builder(*args, **kwargs):
                fresh = real_draft_builder(*args, **kwargs)
                fresh_drafts.append(fresh)
                return fresh
            real_draft_builder = policy_engine.build_render_job_draft
            with patch.object(engine, "build_presentation_policy_proposal",
                              wraps=policy_engine.build_presentation_policy_proposal) as live:
                with patch.object(policy_engine, "build_render_job_draft", side_effect=fresh_builder):
                    with patch.object(engine, "require", wraps=validation.require) as m76_gate:
                        self.invalid(lambda: self.live(proposal=p, claims=claims, bindings=b.bindings))
                        m76_gate.assert_not_called()
                live.assert_called_once()
            self.assertEqual(fresh_drafts, [self.proposal.draft])
            self.assertNotEqual(p.draft, fresh_drafts[0])

    def test_asset_digest_structural_rejection_before_upstream(self):
        claims = self.claims()
        for changes in (dict(sha256="f" * 64),
                        dict(asset_id="asset:sha256:" + "f" * 64),
                        dict(asset_id="asset:sha256:" + "f" * 64, sha256="f" * 64)):
            wrong = replace(claims[0], byte_identity=replace(claims[0].byte_identity, **changes))
            malformed = (wrong,) + claims[1:]
            self.invalid(lambda: self.bundle(claims=malformed))
            with patch.object(engine, "build_presentation_policy_proposal") as live:
                self.invalid(lambda: self.live(claims=malformed))
                live.assert_not_called()

    def test_live_stale_other_valid_draft(self):
        p = build_detached_presentation_policy_proposal(self.fixture.image_draft(), policy=self.policy)
        self.bundle(proposal=p, claims=self.claims(p), bindings=self.bindings(p))
        with self.assertRaises(SourceObservationError):
            self.live(proposal=p, claims=self.claims(p), bindings=self.bindings(p))

    def test_live_all_boundaries_not_assessed(self):
        a = assess_current_source_observation(self.base, self.proposal, output_profile=upstream.PROFILE,
            spec=upstream.SPEC, policy=self.policy, observation_spec=self.spec,
            claims=self.claims(), bindings=self.bindings(), **self.config)
        for name in ("physical_byte_verification", "physical_observation_authority", "presentation_compliance",
                     "renderer_adapter_compatibility", "executability"):
            self.assertIs(getattr(a, name), AssessmentBoundary.NOT_ASSESSED)

    def test_exact_record_subclasses_and_collections(self):
        class Child(ExactRational):
            pass
        self.invalid(validate_rational, Child(1, 1))
        self.invalid(validate_claim, claim(visual_streams=(stream(frames=[]),)))
        self.invalid(validate_bundle, replace(self.bundle(), bindings=list(self.bindings())))
        self.invalid(validate_claim, claim(visual_streams=(stream(orientation="UNKNOWN"),)))

    def test_frame_scalar_safety(self):
        base = FrameObservation(0, None, None, TimestampOrigin.UNKNOWN)
        for changes in (dict(ordinal=True), dict(pts_ticks=1.0), dict(duration_ticks=-1),
                        dict(timestamp_origin="UNKNOWN"), dict(duration_ticks=True)):
            c = claim(visual_streams=(stream(frames=(replace(base, **changes),),
                timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),))
            self.invalid(validate_claim, c)

    def test_actual_depth_32_and_two_million_nodes(self):
        value, schema = 1, int
        for _ in range(32):
            value, schema = (value,), tuple[schema, ...]
        validation.preflight(value, schema)
        self.invalid(lambda v: validation.preflight(v, tuple[schema, ...]), (value,))
        shared = (1,) * 1000
        value = (shared,) * 1998 + ((),)
        schema = tuple[tuple[int, ...], ...]
        validation.preflight(value, schema)
        self.invalid(lambda v: validation.preflight(v, schema), value + ((),))

    def test_preflight_before_publication_or_live_work(self):
        with patch.object(engine, "build_presentation_policy_proposal", side_effect=AssertionError):
            with self.assertRaises(SourceObservationError):
                self.live(claims=[claim()])

    def test_no_timestamp_synthesis(self):
        c = claim(visual_streams=(stream(source_kind=SourceKind.WHOLE_VIDEO,
            nominal_frame_rate=ExactRational(30, 1), average_frame_rate=ExactRational(30, 1),
            stream_duration_ticks=300, decoded_presentation_count=10),))
        validate_claim(c)
        self.assertEqual(c.visual_streams[0].frames, ())
        self.assertIsNone(c.visual_streams[0].time_base)
        self.assertIsNone(c.visual_streams[0].presentation_start_ticks)

    def test_frame_claim_capacity(self):
        frames = tuple(FrameObservation(i, None, None, TimestampOrigin.UNKNOWN) for i in range(65537))
        s = stream(decoded_presentation_count=65536,
            timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE, frames=frames[:65536])
        validate_claim(claim(visual_streams=(s,)))
        self.invalid(validate_claim, claim(visual_streams=(replace(s, frames=frames),)))
        self.invalid(validate_claim, claim(visual_streams=(s, replace(s, stream_index=1))))

    def test_frame_bundle_capacity(self):
        b = self.bundle()
        frames = tuple(FrameObservation(i, None, None, TimestampOrigin.UNKNOWN) for i in range(65536))
        c = claim(visual_streams=(stream(frames=frames, decoded_presentation_count=65536,
            timestamp_enumeration_status=TimestampEnumerationStatus.COMPLETE),))
        validate_bundle(replace(b, claims=(c, c), bindings=self.bindings(present=False)))
        extra = claim(visual_streams=(stream(frames=frames[:1],
            timestamp_enumeration_status=TimestampEnumerationStatus.PARTIAL),))
        self.invalid(validate_bundle, replace(b, claims=(c, c, extra), bindings=self.bindings(present=False)))

    def test_scalar_and_integer_bounds(self):
        validate_claim(claim(observer_id="x" * 256))
        self.invalid(validate_claim, claim(observer_id="x" * 257))
        for value in (-MAX_INTEGER, MAX_INTEGER):
            validate_claim(claim(visual_streams=(stream(stream_start_ticks=value),)))
        for value in (-MAX_INTEGER-1, MAX_INTEGER+1, True, 1.2):
            self.invalid(validate_claim, claim(visual_streams=(stream(stream_start_ticks=value),)))

    def test_hostile_objects_no_hooks(self):
        calls = []
        class Meta(type):
            def __eq__(self, other):
                calls.append("meta_eq")
                raise AssertionError
            def __hash__(self):
                calls.append("meta_hash")
                raise AssertionError
        class Hostile(metaclass=Meta):
            def __getattribute__(self, name):
                calls.append(name)
                raise AssertionError
            def __repr__(self):
                calls.append("repr")
                raise AssertionError
        self.invalid(validate_claim, claim(observer_id=Hostile()))
        self.invalid(validate_bundle, Hostile())
        self.assertEqual(calls, [])

    def test_hostile_dictionary_and_key(self):
        class BadDict(dict):
            def __len__(self):
                raise AssertionError
            def __iter__(self):
                raise AssertionError
        s = SourceObservationSpec("1", "1")
        object.__setattr__(s, "__dict__", BadDict(vars(s)))
        self.invalid(validate_spec, s)
        class Key(str):
            def __hash__(self):
                if getattr(self, "armed", False):
                    raise AssertionError
                return str.__hash__(self)
        key = Key("contract_version")
        data = {key: "1", "engine_version": "1"}
        key.armed = True
        s = SourceObservationSpec("1", "1")
        object.__setattr__(s, "__dict__", data)
        self.invalid(validate_spec, s)

    def test_cycles_and_shared_references(self):
        r = RecursiveRecord(())
        r.children = (r,)
        self.invalid(lambda v: validation.preflight(v, RecursiveRecord), r)
        a, b = RecursiveRecord(()), RecursiveRecord(())
        a.children = (b,)
        b.children = (a,)
        self.invalid(lambda v: validation.preflight(v, RecursiveRecord), a)
        leaf = RecursiveRecord(())
        validation.preflight(RecursiveRecord((leaf, leaf)), RecursiveRecord)

    def test_depth_and_node_boundaries(self):
        r = RecursiveRecord(())
        for _ in range(15):
            r = RecursiveRecord((r,))
        with patch.object(validation, "MAX_TRAVERSAL_DEPTH", 31):
            validation.preflight(r, RecursiveRecord)
        with patch.object(validation, "MAX_TRAVERSAL_DEPTH", 30):
            self.invalid(lambda v: validation.preflight(v, RecursiveRecord), r)
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 3):
            validation.preflight(self.spec, SourceObservationSpec)
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 2):
            self.invalid(validate_spec, self.spec)
        leaf = RecursiveRecord(())
        with patch.object(validation, "MAX_TRAVERSAL_NODES", 5):
            self.invalid(lambda v: validation.preflight(v, RecursiveRecord), RecursiveRecord((leaf, leaf)))

    def test_immutability_and_atomicity(self):
        before = deepcopy(self.base)
        b = self.live()
        self.assertEqual(self.base, before)
        self.assertEqual(b.proposal, self.proposal)
        for value in (b, b.spec, b.claims[0], b.claims[0].byte_identity, b.bindings[0], stream(), ExactRational(1, 1)):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        with self.assertRaises(SourceObservationError):
            self.live(claims=list(self.claims()))
        self.assertEqual(self.base, before)
        self.assertEqual(self.proposal, b.proposal)

    def test_detached_builder(self):
        b = build_detached_source_observation_bundle(self.proposal, spec=self.spec,
            claims=self.claims(), bindings=self.bindings())
        self.assertEqual(b, self.bundle())
        self.assertFalse(assess_source_observation_bundle(b).current_logically_bound)

    def test_no_paths_metadata_or_authority_fields(self):
        forbidden = {"path", "metadata", "render_ready", "source_verified", "media_verified",
                     "export_ready", "digest", "manifest", "active_pointer"}
        for cls in (SourceObservationSpec, SourceByteIdentity, ExactRational, FrameObservation,
                    VisualStreamObservation, SourceObservationClaim, ObservationBinding,
                    SourceObservationBundle, SourceObservationAssessment):
            self.assertFalse(forbidden & {f.name for f in fields(cls)})

    def test_runtime_and_scope_isolation(self):
        forbidden_imports = {"pathlib", "os", "subprocess", "PIL", "cv2", "requests", "socket",
                             "hashlib", "renderer", "storage", "ffmpeg", "ffprobe"}
        forbidden_calls = {"open", "exists", "stat", "resolve", "construct_render_job_spec", "validate_spec_job"}
        for module in (models, validation, engine):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(forbidden_imports & {a.name.split(".")[0] for a in node.names})
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(forbidden_imports & set((node.module or "").split(".")))
                if isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                    self.assertNotIn(name, forbidden_calls)

if __name__ == "__main__":
    unittest.main()
