"""Synthetic offline M78 contract and detached authority boundary tests."""
import ast
from copy import copy, deepcopy
from dataclasses import dataclass, fields, replace, FrozenInstanceError
import importlib
import inspect
import pickle
import unittest
from unittest.mock import patch

import creator_studio.observation_execution as public
from creator_studio.observation_execution import (
    ObservationExecutionSpec, ObservationExecutionState, ObserverExecutionDescription,
    ObservationExecutionRecord, ObservationExecutionAssessment, ObservationExecutionError,
    validate_observation_execution_spec, validate_observer_execution_description,
    validate_observation_execution_record, validate_observation_execution_assessment,
    build_observation_execution_record, assess_observation_execution,
)
from creator_studio.observation_execution import models, validation, engine
from creator_studio.source_observation import models as facts
from creator_studio.source_observation import validation as fact_validation
from creator_studio.source_snapshot.models import (
    SourceSnapshotDescriptor, IMPLEMENTATION_ID, METHOD_ID,
)
from creator_studio.source_snapshot.validation import validate_descriptor


def identity(digest="a" * 64, count=1):
    return facts.SourceByteIdentity("asset:sha256:" + digest, digest, count)


def stream(**changes):
    # All optional fact fields start unknown; no decoded media is involved.
    values = {f.name: None for f in fields(facts.VisualStreamObservation)}
    values.update(stream_index=0, source_kind=facts.SourceKind.STILL_IMAGE,
                  orientation=facts.Orientation.UNKNOWN,
                  other_display_transform_status=facts.OtherDisplayTransformStatus.UNKNOWN,
                  alpha_presence=facts.AlphaPresence.UNKNOWN,
                  effective_opacity=facts.EffectiveOpacity.UNKNOWN,
                  presentation_multiplicity=facts.PresentationMultiplicity.UNKNOWN,
                  timestamp_enumeration_status=facts.TimestampEnumerationStatus.ABSENT,
                  frames=())
    values.update(changes)
    return facts.VisualStreamObservation(**values)


def claim(**changes):
    values = dict(byte_identity=identity(), observer_id="observer", observer_version="1",
                  observation_method_id="method", observation_method_version="1",
                  visual_stream_inventory_complete=False, visual_streams=(stream(),),
                  container_duration_us=None)
    values.update(changes)
    return facts.SourceObservationClaim(**values)


def record(**changes):
    values = dict(spec=ObservationExecutionSpec("1", "1"),
                  snapshot_descriptor=SourceSnapshotDescriptor(
                      identity(), IMPLEMENTATION_ID, "1", METHOD_ID, "1"),
                  observation_spec=facts.SourceObservationSpec("1", "1"),
                  observer=ObserverExecutionDescription("observer", "1", "method", "1",
                                                        "mapping-1", facts.SourceKind.STILL_IMAGE),
                  execution_state=ObservationExecutionState.SUCCEEDED,
                  declared_observation_coverage=facts.ObservationCoverage.COMPLETE,
                  claim=claim())
    values.update(changes)
    return ObservationExecutionRecord(**values)


@dataclass(frozen=True)
class RecursiveRecord:
    children: tuple["RecursiveRecord", ...]


class Hostile:
    def boom(self, *args, **kwargs):
        raise AssertionError("hostile hook called")
    __repr__ = __str__ = __eq__ = __hash__ = __iter__ = boom
    __len__ = __getitem__ = __getattribute__ = __getattr__ = boom


class HostileString(str):
    __repr__ = __str__ = __eq__ = __hash__ = __iter__ = Hostile.boom
    __len__ = __getitem__ = __getattribute__ = __getattr__ = Hostile.boom


class ObservationExecutionTests(unittest.TestCase):
    def invalid(self, function, value):
        with self.assertRaises(ObservationExecutionError) as caught:
            function(value)
        self.assertEqual(str(caught.exception), "observation_execution_invalid")
        self.assertIsNone(caught.exception.__cause__)

    def untrusted(self, value):
        result = assess_observation_execution(value)
        self.assertIs(result.structurally_valid, True)
        for f in fields(result)[1:]:
            self.assertIs(getattr(result, f.name), facts.AssessmentBoundary.NOT_ASSESSED)
        return result

    def test_public_api(self):
        expected = {
            "ObservationExecutionSpec", "ObservationExecutionState",
            "ObserverExecutionDescription", "ObservationExecutionRecord",
            "ObservationExecutionAssessment", "ObservationExecutionError",
            "validate_observation_execution_spec", "validate_observer_execution_description",
            "validate_observation_execution_record", "validate_observation_execution_assessment",
            "build_observation_execution_record", "assess_observation_execution"}
        self.assertEqual(set(public.__all__), expected)
        self.assertEqual(len(public.__all__), len(expected))
        self.assertFalse(hasattr(public, "AssessmentBoundary"))
        for name in ("execute", "attest", "trust", "authenticate", "issue_authority",
                     "register_producer", "register_observer", "restore_authority",
                     "verify_execution", "current_logically_bound", "snapshot_bytes",
                     "run_observer", "callback", "plugin", "SourceSnapshotRuntime",
                     "VerifiedSourceSnapshot", "Enum", "dataclass", "validate_claim"):
            self.assertFalse(hasattr(public, name))

    def test_import_no_execution_side_effect(self):
        with patch("builtins.open", side_effect=AssertionError("I/O")), \
             patch("creator_studio.source_snapshot.runtime.SourceSnapshotRuntime.capture",
                   side_effect=AssertionError("runtime")):
            self.assertIs(importlib.reload(public), public)

    def test_spec_exact_v1(self):
        value = ObservationExecutionSpec("1", "1")
        self.assertIs(validate_observation_execution_spec(value), value)
        self.assertEqual([f.name for f in fields(value)], ["contract_version", "engine_version"])

    def test_spec_versions_and_scalars(self):
        for name in ("contract_version", "engine_version"):
            for value in ("2", "", True, 1, Hostile(), HostileString("1")):
                self.invalid(validate_observation_execution_spec,
                             replace(record().spec, **{name: value}))

    def test_spec_missing_extra(self):
        for extra in (False, True):
            value = record().spec
            if extra:
                object.__setattr__(value, "extra", Hostile())
            else:
                object.__delattr__(value, "engine_version")
            self.invalid(validate_observation_execution_spec, value)

    def test_enum_closed(self):
        self.assertEqual([m.name for m in ObservationExecutionState],
                         ["NOT_EXECUTED", "SUCCEEDED", "FAILED"])
        self.invalid(validate_observation_execution_record, replace(record(), execution_state="SUCCEEDED"))

    def test_observer_bounds(self):
        for f in fields(ObserverExecutionDescription)[:5]:
            for text in ("x", "x" * 256, " "):
                value = replace(record().observer, **{f.name: text})
                self.assertIs(validate_observer_execution_description(value), value)
            for text in ("", "x" * 257, HostileString("x"), True, Hostile()):
                self.invalid(validate_observer_execution_description,
                             replace(record().observer, **{f.name: text}))

    def test_observer_kind_exact(self):
        for kind in facts.SourceKind:
            validate_observer_execution_description(replace(record().observer, source_kind=kind))
        self.invalid(validate_observer_execution_description,
                     replace(record().observer, source_kind="STILL_IMAGE"))

    def test_observer_field_set(self):
        self.assertEqual([f.name for f in fields(ObserverExecutionDescription)],
                         ["observer_id", "observer_version", "observation_method_id",
                          "observation_method_version", "fact_mapping_version", "source_kind"])
        for extra in (False, True):
            value = record().observer
            if extra:
                object.__setattr__(value, "extra", 1)
            else:
                object.__delattr__(value, "observer_id")
            self.invalid(validate_observer_execution_description, value)

    def test_state_matrix(self):
        for state in ObservationExecutionState:
            for coverage in facts.ObservationCoverage:
                for payload in (None, claim()):
                    value = record(execution_state=state,
                                   declared_observation_coverage=coverage, claim=payload)
                    valid = ((state is ObservationExecutionState.SUCCEEDED and
                              payload is not None and coverage is not facts.ObservationCoverage.ABSENT)
                             or (state is not ObservationExecutionState.SUCCEEDED and
                                 payload is None and coverage is facts.ObservationCoverage.ABSENT))
                    with self.subTest(state=state, coverage=coverage, claim=payload is not None):
                        if valid:
                            self.assertIs(validate_observation_execution_record(value), value)
                        else:
                            self.invalid(validate_observation_execution_record, value)

    def test_identity_matching(self):
        validate_observation_execution_record(record())

    def test_identity_asset_id_upstream_rejection(self):
        # Asset ID embeds digest upstream: isolated asset mismatch fails M76 first.
        value = replace(identity(), asset_id="asset:sha256:" + "b" * 64)
        with self.assertRaises(facts.SourceObservationError):
            fact_validation.validate_byte_identity(value)
        self.invalid(validate_observation_execution_record, record(claim=claim(byte_identity=value)))

    def test_identity_digest_upstream_rejection(self):
        value = replace(identity(), sha256="b" * 64)
        with self.assertRaises(facts.SourceObservationError):
            fact_validation.validate_byte_identity(value)
        self.invalid(validate_observation_execution_record, record(claim=claim(byte_identity=value)))

    def test_identity_valid_digest_pair_m78_mismatch(self):
        value = claim(byte_identity=identity("b" * 64))
        fact_validation.validate_claim(value)
        self.invalid(validate_observation_execution_record, record(claim=value))

    def test_identity_byte_count_m78_mismatch(self):
        value = claim(byte_identity=identity(count=2))
        fact_validation.validate_claim(value)
        self.invalid(validate_observation_execution_record, record(claim=value))

    def test_observer_method_agreement(self):
        for name in ("observer_id", "observer_version", "observation_method_id",
                     "observation_method_version"):
            value = claim(**{name: "different"})
            fact_validation.validate_claim(value)
            self.invalid(validate_observation_execution_record, record(claim=value))

    def test_mapping_version_descriptive(self):
        self.untrusted(record(observer=replace(record().observer, fact_mapping_version="anything")))

    def test_source_kind_matching(self):
        for kind in facts.SourceKind:
            value = record(observer=replace(record().observer, source_kind=kind),
                           claim=claim(visual_streams=(stream(source_kind=kind),)))
            fact_validation.validate_claim(value.claim)
            self.untrusted(value)

    def test_source_kind_mismatch_and_mixed(self):
        for streams in ((stream(source_kind=facts.SourceKind.WHOLE_VIDEO),),
                        (stream(), stream(stream_index=1, source_kind=facts.SourceKind.WHOLE_VIDEO))):
            value = claim(visual_streams=streams)
            fact_validation.validate_claim(value)
            self.invalid(validate_observation_execution_record, record(claim=value))

    def test_manual_succeeded_complete_forgery(self):
        self.untrusted(record())

    def test_builder_manual_equivalence(self):
        manual = record()
        before = deepcopy(manual)
        built = build_observation_execution_record(**vars(manual))
        self.assertEqual(manual, built)
        self.assertEqual(manual, before)
        self.assertIs(built.claim, manual.claim)
        self.assertEqual(self.untrusted(manual), self.untrusted(built))

    def test_builder_rejects_without_rewriting(self):
        value = record(claim=claim(observer_id="mismatch"))
        before = deepcopy(value)
        with self.assertRaises(ObservationExecutionError):
            build_observation_execution_record(**vars(value))
        self.assertEqual(value, before)

    def test_descriptor_detached_reconstruction(self):
        value = record()
        rebuilt = SourceSnapshotDescriptor(**vars(value.snapshot_descriptor))
        validate_descriptor(rebuilt)
        self.untrusted(replace(value, snapshot_descriptor=rebuilt))

    def test_large_descriptor_domain_no_runtime_eligibility(self):
        for count in (33554433, 536870912):
            value = record()
            ident = identity(count=count)
            value = replace(value, snapshot_descriptor=replace(value.snapshot_descriptor,
                            byte_identity=ident), claim=claim(byte_identity=ident))
            self.untrusted(value)

    def test_claim_replacement_untrusted(self):
        original = record()
        substituted = replace(original, claim=claim(container_duration_us=123))
        self.assertNotEqual(original, substituted)
        self.assertEqual(self.untrusted(original), self.untrusted(substituted))

    def test_partial_complete_untrusted(self):
        for coverage in (facts.ObservationCoverage.PARTIAL, facts.ObservationCoverage.COMPLETE):
            self.untrusted(record(declared_observation_coverage=coverage))

    def test_failed_not_executed_untrusted(self):
        for state in (ObservationExecutionState.FAILED, ObservationExecutionState.NOT_EXECUTED):
            self.untrusted(record(execution_state=state, claim=None,
                                  declared_observation_coverage=facts.ObservationCoverage.ABSENT))

    def test_completeness_facts_do_not_grant_authority(self):
        frame = facts.FrameObservation(0, None, None, facts.TimestampOrigin.UNKNOWN)
        for inventory in (False, True):
            for status in facts.TimestampEnumerationStatus:
                observed = stream(timestamp_enumeration_status=status,
                                  decoded_presentation_count=1,
                                  frames=() if status is facts.TimestampEnumerationStatus.ABSENT else (frame,))
                self.untrusted(record(claim=claim(visual_stream_inventory_complete=inventory,
                                                 visual_streams=(observed,))))

    def test_stream_capacity(self):
        streams = tuple(stream(stream_index=i) for i in range(16))
        validate_observation_execution_record(record(claim=claim(visual_streams=streams)))
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(visual_streams=streams + (stream(stream_index=16),))))

    def test_frame_capacity(self):
        frame = facts.FrameObservation(0, None, None, facts.TimestampOrigin.UNKNOWN)
        value = record(claim=claim(visual_streams=(stream(frames=(frame,) * 65537),)))
        self.invalid(validate_observation_execution_record, value)

    def test_aggregate_frame_capacity_across_streams(self):
        # Each stream is under 65536; aggregate claim is over it, with valid ordinals.
        frames = tuple(facts.FrameObservation(i, None, None, facts.TimestampOrigin.UNKNOWN)
                       for i in range(32769))
        streams = tuple(stream(stream_index=i, frames=frames,
                        timestamp_enumeration_status=facts.TimestampEnumerationStatus.PARTIAL)
                        for i in range(2))
        self.invalid(validate_observation_execution_record, record(claim=claim(visual_streams=streams)))

    def test_cycle_rejection(self):
        value = RecursiveRecord(())
        object.__setattr__(value, "children", (value,))
        with self.assertRaises(ObservationExecutionError):
            validation._preflight(value, RecursiveRecord)
        wrong = record()
        object.__setattr__(wrong, "claim", wrong)
        self.invalid(validate_observation_execution_record, wrong)

    def test_depth_bound(self):
        value = RecursiveRecord(())
        for _ in range(33):
            value = RecursiveRecord((value,))
        with self.assertRaises(ObservationExecutionError):
            validation._preflight(value, RecursiveRecord)

    def test_aggregate_top_level_budget(self):
        value = record()
        # Count visits through the actual walker, then put a ceiling strictly
        # between each component and their combined graph. Production stays 2M.
        def minimum_budget(item, schema):
            for budget in range(1, 300):
                with patch.object(fact_validation, "MAX_TRAVERSAL_NODES", budget):
                    try:
                        validation._preflight(item, schema)
                    except ObservationExecutionError:
                        continue
                    return budget
            self.fail("fixture budget unexpectedly large")
        components = [minimum_budget(getattr(value, f.name), f.type)
                      for f in fields(value) if f.name != "claim"]
        components.append(minimum_budget(value.claim, facts.SourceObservationClaim))
        whole = minimum_budget(value, ObservationExecutionRecord)
        self.assertGreater(whole, max(components))
        self.assertEqual(fact_validation.MAX_TRAVERSAL_NODES, 2_000_000)
        with patch.object(fact_validation, "MAX_TRAVERSAL_NODES", max(components)), \
             patch.object(validation, "_validate_descriptor", side_effect=AssertionError("late gate")):
            self.invalid(validate_observation_execution_record, value)

    def test_repeated_acyclic_references_charged(self):
        leaf = RecursiveRecord(())
        value = RecursiveRecord((leaf, leaf))
        validation._preflight(value, RecursiveRecord)
        with patch.object(fact_validation, "MAX_TRAVERSAL_NODES", 5):
            with self.assertRaises(ObservationExecutionError):
                validation._preflight(value, RecursiveRecord)

    def test_hostile_exact_type_rejection(self):
        self.invalid(validate_observation_execution_record, Hostile())
        for f in fields(ObservationExecutionRecord):
            self.invalid(validate_observation_execution_record, replace(record(), **{f.name: Hostile()}))
        class SubRecord(ObservationExecutionRecord):
            __getattribute__ = Hostile.boom
        self.invalid(validate_observation_execution_record, SubRecord(**vars(record())))
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(byte_identity=replace(identity(), byte_count=True))))

    def test_record_missing_extra_and_hostile_key(self):
        self.assertEqual([f.name for f in fields(ObservationExecutionRecord)],
                         ["spec", "snapshot_descriptor", "observation_spec", "observer",
                          "execution_state", "declared_observation_coverage", "claim"])
        for action in ("extra", "missing", "key"):
            value = record()
            if action == "extra":
                object.__setattr__(value, "extra", Hostile())
            elif action == "missing":
                object.__delattr__(value, "claim")
            else:
                del vars(value)["claim"]
                vars(value)[1] = None
            self.invalid(validate_observation_execution_record, value)

    def test_assessment_validation(self):
        value = self.untrusted(record())
        self.assertEqual([f.name for f in fields(value)],
                         ["structurally_valid", "physical_byte_verification",
                          "physical_observation_authority", "observation_execution",
                          "presentation_compliance", "renderer_adapter_compatibility", "executability"])
        self.assertIs(validate_observation_execution_assessment(value), value)
        for bad in (False, 1, Hostile()):
            self.invalid(validate_observation_execution_assessment, replace(value, structurally_valid=bad))
        for f in fields(value)[1:]:
            self.invalid(validate_observation_execution_assessment, replace(value, **{f.name: "NOT_ASSESSED"}))

    def test_all_records_frozen(self):
        for value in (record().spec, record().observer, record(), self.untrusted(record())):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)

    def test_copy_deepcopy_untrusted(self):
        value = record()
        for copied in (copy(value), deepcopy(value)):
            self.assertEqual(copied, value)
            self.assertEqual(self.untrusted(copied), self.untrusted(value))

    def test_pickle_reconstruction_no_authority(self):
        value = record()
        rebuilt = pickle.loads(pickle.dumps(value))
        self.assertEqual(rebuilt, value)
        self.untrusted(rebuilt)

    def test_errors_sanitized(self):
        sensitive_value = "sensitive-label-do-not-echo"
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(observer_id=sensitive_value)))
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(byte_identity=replace(identity(), sha256=sensitive_value))))
        self.invalid(validate_observation_execution_record,
                     record(snapshot_descriptor=replace(record().snapshot_descriptor,
                                                       capture_method_id=sensitive_value)))
        self.assertEqual(str(ObservationExecutionError()), "observation_execution_invalid")

    def test_upstream_spec_and_claim_validation(self):
        self.invalid(validate_observation_execution_record,
                     record(observation_spec=facts.SourceObservationSpec("2", "1")))
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(container_duration_us=-1)))
        self.invalid(validate_observation_execution_record,
                     record(claim=claim(visual_streams=(stream(coded_width_px=16385),))))

    def test_source_isolation(self):
        allowed = {"dataclasses", "enum", "models", "validation", "engine",
                   "source_observation.models", "source_observation.validation",
                   "source_snapshot.models", "source_snapshot.validation"}
        forbidden_calls = {"open", "capture", "release", "snapshot_bytes", "execute",
                           "run_observer", "attest", "trust", "register_producer"}
        for module in (public, models, validation, engine):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.fail("unexpected absolute module import")
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
                    self.assertTrue(all(a.name != "*" for a in node.names))
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                    self.assertNotIn(name, forbidden_calls)

    def test_upstream_and_runtime_boundary_isolation(self):
        value = record()
        before = deepcopy(value)
        with patch("creator_studio.source_snapshot.runtime.SourceSnapshotRuntime.capture",
                   side_effect=AssertionError("runtime")), \
             patch("creator_studio.source_snapshot.runtime.SourceSnapshotRuntime.snapshot_bytes",
                   side_effect=AssertionError("snapshot access")), \
             patch("creator_studio.presentation_policy.engine.assess_presentation_policy_proposal",
                   side_effect=AssertionError("policy")):
            self.untrusted(value)
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
