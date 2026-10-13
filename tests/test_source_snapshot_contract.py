"""Offline exact detached-contract tests for M77."""
import dataclasses
import importlib
import unittest
from unittest.mock import patch
import creator_studio.source_snapshot as api
from creator_studio.source_snapshot import (
    SourceSnapshotSpec, SourceSnapshotRequest, SourceSnapshotDescriptor,
    SourceSnapshotResult, SourceSnapshotOutcome as Outcome,
    SourceSnapshotFailureCode as Failure, SourceSnapshotError,
    validate_spec, validate_request, validate_descriptor, validate_result,
)
from creator_studio.source_snapshot.models import IMPLEMENTATION_ID, METHOD_ID
from creator_studio.source_observation import SourceByteIdentity

def spec():
    return SourceSnapshotSpec("1", "1", 33554432, 1048576, 1, 1, 30,
                              extra_eof_check_bytes=1, max_descriptor_string_length=256)

def identity():
    return SourceByteIdentity("asset:sha256:" + "a" * 64, "a" * 64, 1)

def descriptor():
    return SourceSnapshotDescriptor(identity(), IMPLEMENTATION_ID, "1", METHOD_ID, "1")

class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")
    def __eq__(self, other):
        raise AssertionError("hostile equality")
    def __repr__(self):
        raise AssertionError("hostile repr")
    def __hash__(self):
        raise AssertionError("hostile hash")

class ContractTests(unittest.TestCase):
    def invalid(self, function, value):
        with self.assertRaisesRegex(SourceSnapshotError, "^source_snapshot_invalid$"):
            function(value)

    def test_import_api(self):
        with patch("pathlib.Path.open", side_effect=AssertionError("I/O")):
            importlib.reload(api)
        self.assertEqual(len(api.__all__), 13)
        self.assertTrue(all(hasattr(api, n) for n in api.__all__))
        self.assertFalse(any(n in api.__all__ for n in
                             ("hashlib", "Path", "ManagedStorage", "RenderJobSpec", "renderer")))

    def test_exact_spec(self):
        self.assertIs(validate_spec(spec()).__class__, SourceSnapshotSpec)

    def test_explicit_spec_field_set(self):
        expected = {"contract_version", "engine_version", "max_snapshot_bytes",
                    "read_chunk_bytes", "max_concurrent_captures",
                    "max_outstanding_snapshots", "deadline_seconds",
                    "extra_eof_check_bytes", "max_descriptor_string_length"}
        self.assertEqual({f.name for f in dataclasses.fields(SourceSnapshotSpec)}, expected)
        self.assertTrue(all(f.default is dataclasses.MISSING and
                            f.default_factory is dataclasses.MISSING
                            for f in dataclasses.fields(SourceSnapshotSpec)))

    def test_eof_accepted(self):
        validate_spec(dataclasses.replace(spec(), extra_eof_check_bytes=1))

    def test_eof_wrong(self):
        self.invalid(validate_spec, dataclasses.replace(spec(), extra_eof_check_bytes=2))

    def test_eof_bool(self):
        self.invalid(validate_spec, dataclasses.replace(spec(), extra_eof_check_bytes=True))

    def test_descriptor_limit_accepted(self):
        validate_spec(dataclasses.replace(spec(), max_descriptor_string_length=256))

    def test_descriptor_limit_wrong(self):
        self.invalid(validate_spec, dataclasses.replace(spec(), max_descriptor_string_length=255))

    def test_descriptor_limit_bool(self):
        self.invalid(validate_spec, dataclasses.replace(spec(), max_descriptor_string_length=True))

    def test_missing_new_fields(self):
        for name in ("extra_eof_check_bytes", "max_descriptor_string_length"):
            with self.subTest(name=name):
                value = spec()
                object.__delattr__(value, name)
                self.invalid(validate_spec, value)
                kwargs = dataclasses.asdict(spec())
                del kwargs[name]
                with self.assertRaises(TypeError):
                    SourceSnapshotSpec(**kwargs)

    def test_each_wrong_spec_value(self):
        for field in dataclasses.fields(spec()):
            value = getattr(spec(), field.name)
            with self.subTest(field=field.name):
                self.invalid(validate_spec, dataclasses.replace(spec(), **{
                    field.name: "2" if type(value) is str else value + 1}))

    def test_spec_bool_and_hostile_scalars(self):
        for name in ("max_snapshot_bytes", "read_chunk_bytes", "max_concurrent_captures",
                     "max_outstanding_snapshots", "deadline_seconds",
                     "extra_eof_check_bytes", "max_descriptor_string_length"):
            self.invalid(validate_spec, dataclasses.replace(spec(), **{name: True}))
        self.invalid(validate_spec, dataclasses.replace(spec(), contract_version=Hostile()))

    def test_spec_subclass(self):
        class Sub(SourceSnapshotSpec):
            pass
        self.invalid(validate_spec, Sub("1", "1", 33554432, 1048576, 1, 1, 30,
                              extra_eof_check_bytes=1, max_descriptor_string_length=256))

    def test_missing_extra_fields(self):
        for cls, validate, value in (
            (SourceSnapshotSpec, validate_spec, spec()),
            (SourceSnapshotRequest, validate_request, SourceSnapshotRequest(identity())),
            (SourceSnapshotDescriptor, validate_descriptor, descriptor()),
            (SourceSnapshotResult, validate_result, SourceSnapshotResult(Outcome.SUCCESS, descriptor(), None)),
        ):
            with self.subTest(cls=cls):
                object.__setattr__(value, "extra", 1)
                self.invalid(validate, value)
                object.__delattr__(value, "extra")
                object.__delattr__(value, dataclasses.fields(cls)[0].name)
                self.invalid(validate, value)

    def test_request_identity_reused(self):
        value = SourceSnapshotRequest(identity())
        self.assertIs(validate_request(value), value)
        self.assertIs(type(value.byte_identity), SourceByteIdentity)

    def test_identity_invalid(self):
        for changes in ({"sha256": "A" * 64}, {"asset_id": "wrong"},
                        {"byte_count": 0}, {"byte_count": True},
                        {"byte_count": 536870913}, {"sha256": Hostile()}):
            self.invalid(validate_request, SourceSnapshotRequest(dataclasses.replace(identity(), **changes)))
        self.invalid(validate_request, SourceSnapshotRequest(Hostile()))

    def test_identity_capacity_is_not_structure(self):
        for size in (33554432, 33554433, 536870912):
            validate_request(SourceSnapshotRequest(dataclasses.replace(identity(), byte_count=size)))

    def test_no_locator_or_payload_fields(self):
        for cls in (SourceSnapshotRequest, SourceSnapshotDescriptor, SourceSnapshotResult):
            names = {f.name for f in dataclasses.fields(cls)}
            self.assertFalse(names & {"path", "filename", "url", "object_key", "payload", "token"})

    def test_fixed_descriptor(self):
        validate_descriptor(descriptor())
        for name in ("snapshot_implementation_id", "snapshot_implementation_version",
                     "capture_method_id", "capture_method_version"):
            for value in ("wrong", "x" * 257, Hostile()):
                self.invalid(validate_descriptor, dataclasses.replace(descriptor(), **{name: value}))

    def test_result_invariants(self):
        validate_result(SourceSnapshotResult(Outcome.SUCCESS, descriptor(), None))
        for code in Failure:
            validate_result(SourceSnapshotResult(Outcome.FAILURE, None, code))
        for value in (
            SourceSnapshotResult(Outcome.SUCCESS, None, None),
            SourceSnapshotResult(Outcome.SUCCESS, descriptor(), Failure.CANCELLED),
            SourceSnapshotResult(Outcome.FAILURE, descriptor(), Failure.CANCELLED),
            SourceSnapshotResult(Outcome.FAILURE, None, None),
            SourceSnapshotResult("SUCCESS", descriptor(), None),
            SourceSnapshotResult(Outcome.FAILURE, None, "CANCELLED"),
            SourceSnapshotResult(Hostile(), None, None),
        ):
            self.invalid(validate_result, value)

    def test_closed_enums(self):
        self.assertEqual({v.value for v in Outcome}, {"SUCCESS", "FAILURE"})
        self.assertEqual({v.value for v in Failure}, set("SOURCE_MISSING SOURCE_ACCESS_FAILED "
            "SOURCE_PATH_REJECTED SNAPSHOT_CAPACITY_EXCEEDED BYTE_COUNT_MISMATCH SHA256_MISMATCH "
            "CANCELLED DEADLINE_EXCEEDED RESOURCE_EXHAUSTED".split()))

    def test_frozen(self):
        for value in (spec(), SourceSnapshotRequest(identity()), descriptor(),
                      SourceSnapshotResult(Outcome.SUCCESS, descriptor(), None), identity()):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(value, dataclasses.fields(value)[0].name, "changed")

    def test_hostile_top_level(self):
        for validate in (validate_spec, validate_request, validate_descriptor, validate_result):
            self.invalid(validate, Hostile())

    def test_error_fixed(self):
        self.assertEqual(str(SourceSnapshotError()), "source_snapshot_invalid")

    def test_production_isolation(self):
        from pathlib import Path
        import ast
        root = Path(__file__).resolve().parents[1] / "creator_studio/source_snapshot"
        prohibited = {"subprocess", "PIL", "cv2", "requests", "urllib", "ffmpeg",
                      "ffprobe", "renderer", "pipeline", "provider", "stock"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({n.name.split('.')[0] for n in node.names} & prohibited)
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(set((node.module or '').split('.')) & prohibited)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, {"verify", "finalize", "write", "unlink", "mkdir"})

if __name__ == "__main__":
    unittest.main()
