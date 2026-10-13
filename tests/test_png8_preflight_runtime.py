"""M77 authority, detached reports, deadlines and failure recovery."""
import ast
import copy
import dataclasses
import inspect
import pickle
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch
import creator_studio.png8_observer as api
import creator_studio.png8_observer.runtime as module
import creator_studio.png8_observer.preflight as parser
from creator_studio.source_snapshot import SourceSnapshotRuntime, VerifiedSourceSnapshot
from creator_studio.still_image_observation_method import StillImageObservationMethodSpec
from tests.test_png8_structural_preflight import capture, png


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")
    def __repr__(self):
        raise AssertionError("hostile repr")
    def __eq__(self, other):
        raise AssertionError("hostile equality")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.source, self.snapshot = capture(png())
        self.runtime = api.PNG8PreflightRuntime()

    def run_live(self):
        return self.runtime.preflight(self.source, self.snapshot)

    def failure(self, result, code):
        self.assertEqual(result.failure_code.value, code)
        self.assertIsNone(result.descriptor)
        self.assertIsNone(result.profile)
        api.validate_preflight_result(result)

    def test_live_and_retained_ownership(self):
        before = self.source.snapshot_bytes(self.snapshot)
        with patch.object(SourceSnapshotRuntime, "release", side_effect=AssertionError("release")):
            result = self.run_live()
        self.assertEqual(result.descriptor, self.snapshot.descriptor)
        self.assertIs(self.source.snapshot_bytes(self.snapshot), before)
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_foreign_released_unregistered(self):
        other = SourceSnapshotRuntime(str(Path.cwd()))
        self.failure(self.runtime.preflight(other, self.snapshot), "SNAPSHOT_AUTHORITY_INVALID")
        self.failure(self.runtime.preflight(self.source, object.__new__(VerifiedSourceSnapshot)), "SNAPSHOT_AUTHORITY_INVALID")
        self.source.release(self.snapshot)
        self.failure(self.run_live(), "SNAPSHOT_AUTHORITY_INVALID")

    def test_exact_inputs(self):
        class RuntimeSubclass(SourceSnapshotRuntime):
            pass
        class SnapshotSubclass(VerifiedSourceSnapshot):
            pass
        pairs = [(Hostile(), self.snapshot), (self.source, Hostile()),
                 (self.source, png()), (self.source, self.snapshot.descriptor),
                 (RuntimeSubclass(str(Path.cwd())), self.snapshot),
                 (self.source, object.__new__(SnapshotSubclass))]
        with patch.object(SourceSnapshotRuntime, "snapshot_bytes", side_effect=AssertionError("access")):
            for runtime, snapshot in pairs:
                self.failure(self.runtime.preflight(runtime, snapshot), "SNAPSHOT_AUTHORITY_INVALID")

    def test_acquisition_before_descriptor(self):
        with patch.object(SourceSnapshotRuntime, "snapshot_bytes", side_effect=module.SourceSnapshotError()), patch.object(VerifiedSourceSnapshot, "descriptor", property(lambda s: (_ for _ in ()).throw(AssertionError("descriptor")))):
            self.failure(self.run_live(), "SNAPSHOT_AUTHORITY_INVALID")

    def test_bad_bytes_and_descriptor(self):
        for value in (b"short", bytearray(png()), Hostile()):
            with patch.object(SourceSnapshotRuntime, "snapshot_bytes", return_value=value):
                self.failure(self.run_live(), "SNAPSHOT_AUTHORITY_INVALID")
        with patch.object(VerifiedSourceSnapshot, "descriptor", property(lambda s: Hostile())):
            self.failure(self.run_live(), "SNAPSHOT_AUTHORITY_INVALID")

    def test_size_limit(self):
        # Controlled public-access fixture: allocate only one byte beyond the
        # actual fixed bound, without running M77 hashing/copying that buffer.
        data = b"x" * 33554433
        descriptor = dataclasses.replace(self.snapshot.descriptor, byte_identity=dataclasses.replace(self.snapshot.descriptor.byte_identity, byte_count=len(data)))
        with patch.object(SourceSnapshotRuntime, "snapshot_bytes", return_value=data), patch.object(VerifiedSourceSnapshot, "descriptor", property(lambda s: descriptor)):
            self.failure(self.run_live(), "RESOURCE_LIMIT_EXCEEDED")

    def test_format_and_structure_recovery(self):
        for data, expected in ((b"wrong!!!", "UNSUPPORTED_FORMAT"), (png()[:-1], "STRUCTURAL_INVALID")):
            source, snapshot = capture(data)
            self.failure(self.runtime.preflight(source, snapshot), expected)
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_m79_public_validation(self):
        original_spec = module.validate_method_spec
        original_profile = module.validate_encoded_profile
        with patch.object(module, "validate_method_spec", wraps=original_spec) as method, patch.object(module, "validate_encoded_profile", wraps=original_profile) as profile:
            result = self.run_live()
        self.assertEqual(method.call_count, 1)
        self.assertIs(type(method.call_args.args[0]), StillImageObservationMethodSpec)
        profile.assert_called_once_with(result.profile)
        with self.assertRaises(TypeError):
            self.runtime.preflight(self.source, self.snapshot, StillImageObservationMethodSpec())

    def test_concurrent_gate(self):
        entered, finish = Event(), Event()
        original = SourceSnapshotRuntime.snapshot_bytes
        results = []
        def access(runtime, snapshot):
            entered.set()
            if not finish.wait(5):
                raise AssertionError("timeout")
            return original(runtime, snapshot)
        with patch.object(SourceSnapshotRuntime, "snapshot_bytes", autospec=True, side_effect=access) as accessed:
            thread = Thread(target=lambda: results.append(self.run_live()))
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                self.failure(self.run_live(), "RESOURCE_LIMIT_EXCEEDED")
                self.assertEqual(accessed.call_count, 1)
            finally:
                finish.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIs(results[0].outcome, api.PNG8PreflightOutcome.SUCCESS)
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_deadlines(self):
        with patch.object(module, "monotonic", return_value=100):
            self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)
        for checkpoint in range(1, 20):
            calls = [0]
            def clock():
                calls[0] += 1
                return 0 if calls[0] <= checkpoint else 31
            with patch.object(module, "monotonic", side_effect=clock):
                self.failure(self.run_live(), "DEADLINE_EXCEEDED")
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_exception_recovery(self):
        for error, code in ((RuntimeError("private"), "INTERNAL_FAILURE"), (MemoryError(), "RESOURCE_LIMIT_EXCEEDED")):
            with patch.object(module, "validate_method_spec", side_effect=error):
                self.failure(self.run_live(), code)
            self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_final_deadline_and_snapshot_exception(self):
        now = [0]
        original = module.PNG8PreflightResult
        def construct(*args):
            result = original(*args)
            if args[0] is api.PNG8PreflightOutcome.SUCCESS:
                now[0] = 30
            return result
        with patch.object(module, "monotonic", side_effect=lambda: now[0]), patch.object(module, "PNG8PreflightResult", side_effect=construct):
            self.failure(self.run_live(), "DEADLINE_EXCEEDED")
        with patch.object(SourceSnapshotRuntime, "snapshot_bytes", side_effect=RuntimeError("private")):
            self.failure(self.run_live(), "INTERNAL_FAILURE")
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_failure_allocation_memory(self):
        with patch.object(module, "validate_method_spec", side_effect=MemoryError()), patch.object(module, "_failed", side_effect=MemoryError()):
            with self.assertRaises(MemoryError):
                self.run_live()
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_baseexception_not_swallowed(self):
        with patch.object(module, "validate_method_spec", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.run_live()
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_crc_exception_cleanup(self):
        with patch.object(parser.zlib, "crc32", side_effect=MemoryError()):
            self.failure(self.run_live(), "RESOURCE_LIMIT_EXCEEDED")
        self.assertIs(self.run_live().outcome, api.PNG8PreflightOutcome.SUCCESS)

    def test_detached_roundtrips(self):
        result = self.run_live()
        variants = [copy.copy(result), copy.deepcopy(result), pickle.loads(pickle.dumps(result)), api.PNG8PreflightResult(result.outcome, result.descriptor, result.profile, None)]
        for variant in variants:
            self.assertEqual(api.validate_preflight_result(variant), result)
            self.failure(self.runtime.preflight(self.source, variant), "SNAPSHOT_AUTHORITY_INVALID")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.profile = None
        self.assertEqual(set(vars(result)), {"outcome", "descriptor", "profile", "failure_code"})
        self.assertFalse(any(type(v) in (bytes, memoryview, Path) for v in vars(result).values()))

    def test_result_validation_hostile(self):
        result = self.run_live()
        class Subclass(api.PNG8PreflightResult):
            pass
        invalid = [Hostile(), Subclass(result.outcome, result.descriptor, result.profile, None),
                   dataclasses.replace(result, outcome=Hostile()),
                   dataclasses.replace(result, descriptor=None), dataclasses.replace(result, profile=None),
                   dataclasses.replace(result, failure_code=api.PNG8PreflightFailureCode.INTERNAL_FAILURE),
                   dataclasses.replace(result, profile=dataclasses.replace(result.profile, coded_width_px=True)),
                   api.PNG8PreflightResult(api.PNG8PreflightOutcome.FAILURE, None, None, Hostile())]
        for value in invalid:
            with self.assertRaisesRegex(ValueError, "^png8_preflight_result_invalid$"):
                api.validate_preflight_result(value)

    def test_forged_result_shape_and_enums(self):
        result = self.run_live()
        forged = copy.copy(result)
        object.__setattr__(forged, "extra", Hostile())
        fake_outcome = str.__new__(api.PNG8PreflightOutcome, "SUCCESS")
        fake_code = str.__new__(api.PNG8PreflightFailureCode, "INTERNAL_FAILURE")
        variants = [forged, dataclasses.replace(result, outcome=fake_outcome),
                    api.PNG8PreflightResult(api.PNG8PreflightOutcome.FAILURE, None, None, fake_code),
                    api.PNG8PreflightResult(api.PNG8PreflightOutcome.FAILURE, result.descriptor, None, api.PNG8PreflightFailureCode.INTERNAL_FAILURE)]
        for value in variants:
            with self.assertRaisesRegex(ValueError, "^png8_preflight_result_invalid$"):
                api.validate_preflight_result(value)

    def test_public_api_and_static_boundary(self):
        self.assertEqual(api.__all__, ("PNG8PreflightOutcome", "PNG8PreflightFailureCode", "PNG8PreflightResult", "validate_preflight_result", "PNG8PreflightRuntime"))
        self.assertEqual({x.value for x in api.PNG8PreflightFailureCode}, {"SNAPSHOT_AUTHORITY_INVALID", "UNSUPPORTED_FORMAT", "STRUCTURAL_INVALID", "RESOURCE_LIMIT_EXCEEDED", "DEADLINE_EXCEEDED", "INTERNAL_FAILURE"})
        package = Path(api.__file__).parent
        forbidden_imports = {"PIL", "Pillow", "cv2", "imageio", "subprocess", "socket", "requests", "urllib", "hashlib"}
        forbidden_names = {"SourceObservationClaim", "VisualStreamObservation", "FrameObservation", "ObservationExecutionRecord", "VerifiedObservation", "TrustedObservation", "attest", "issuer", "release", "Manifest", "SUCCEEDED", "COMPLETE", "_payload", "_owner", "_lease", "_storage"}
        for path in package.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(a.name.split(".")[0] in forbidden_imports for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(any(part in forbidden_imports | {"renderer", "providers", "engine"} for part in (node.module or "").split(".")))
                    self.assertFalse(any(a.name in forbidden_names for a in node.names))
                if isinstance(node, ast.Attribute):
                    if node.attr == "release":
                        self.assertIn(ast.unparse(node.value), {"region", "view", "self._gate"})
                    else:
                        self.assertNotIn(node.attr, forbidden_names | {"open", "read_bytes", "resolve"})
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, forbidden_names)
        self.assertEqual(tuple(inspect.signature(api.PNG8PreflightRuntime.preflight).parameters), ("self", "runtime", "snapshot"))


if __name__ == "__main__":
    unittest.main()
