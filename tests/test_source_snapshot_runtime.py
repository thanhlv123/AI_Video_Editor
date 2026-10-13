"""Synthetic runtime capture, bounds, lifetime and atomicity tests."""
import copy
import hashlib
import io
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch
from creator_studio.source_snapshot import (
    SourceSnapshotRuntime, SourceSnapshotRequest, SourceSnapshotOutcome as Outcome,
    SourceSnapshotFailureCode as Failure, SourceSnapshotError, VerifiedSourceSnapshot,
    validate_result,
)
from creator_studio.source_observation import SourceByteIdentity, SourceObservationAssessment
from creator_studio.source_observation.models import ObservationCoverage, AssessmentBoundary
from creator_studio.manifest.acquisition import object_key
from creator_studio.acquisition.storage import ManagedStorage
from creator_studio.acquisition.models import AcquisitionError
from creator_studio.orchestrator.contracts import CancellationToken
from tests.test_source_snapshot_contract import spec, descriptor
import creator_studio.source_snapshot.runtime as runtime_module

class Stream(io.BytesIO):
    def __init__(self, data, short=None, action=None):
        super().__init__(data)
        self.requests = []
        self.short, self.action = short, action
    def read(self, size=-1):
        if not 0 < size <= 1048576:
            raise AssertionError("unbounded read")
        self.requests.append(size)
        data = super().read(min(size, self.short) if self.short else size)
        if self.action:
            self.action(len(self.requests))
        return data

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = SourceSnapshotRuntime(str(self.root))
        self.data = b"synthetic source bytes"
        self.request = self.make_request(self.data)
        self.path = self.root / object_key(self.request.byte_identity.sha256)
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.data)

    def make_request(self, data, size=None):
        digest = hashlib.sha256(data).hexdigest()
        return SourceSnapshotRequest(SourceByteIdentity("asset:sha256:" + digest,
            digest, len(data) if size is None else size))

    def capture(self, request=None, control=None):
        return self.runtime.capture(spec(), request or self.request, control)

    def failure(self, expected, request=None, control=None):
        result, capability = self.capture(request, control)
        self.assertIs(result.outcome, Outcome.FAILURE)
        self.assertIs(result.failure_code, expected)
        self.assertIsNone(capability)
        self.assertIsNone(result.descriptor)
        self.assertFalse(self.runtime._capturing)
        self.assertIsNone(self.runtime._outstanding)
        self.assertIsNone(self.runtime._lease)
        validate_result(result)
        return result

    def test_matching_success(self):
        result, snapshot = self.capture()
        validate_result(result)
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertEqual(result.descriptor.byte_identity, self.request.byte_identity)
        payload = self.runtime.snapshot_bytes(snapshot)
        self.assertIs(type(payload), bytes)
        self.assertEqual(payload, self.data)
        self.assertEqual(len(payload), self.request.byte_identity.byte_count)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), self.request.byte_identity.sha256)
        self.assertIs(self.runtime.snapshot_bytes(snapshot), payload)
        for value in (result, snapshot, self.runtime):
            self.assertNotIn(str(self.root), repr(value))
        self.assertNotIn(repr(self.data), repr(snapshot))

    def test_capacity_pre_resolution(self):
        with patch.object(ManagedStorage, "resolve", side_effect=AssertionError("resolve")):
            self.failure(Failure.SNAPSHOT_CAPACITY_EXCEEDED, self.make_request(b"x", 33554433))
            self.failure(Failure.SNAPSHOT_CAPACITY_EXCEEDED, self.make_request(b"x", 536870912))

    def test_capacity_boundary_reaches_open(self):
        with patch.object(Path, "open", side_effect=FileNotFoundError) as opened:
            self.failure(Failure.SOURCE_MISSING, self.make_request(b"x", 33554432))
        opened.assert_called_once_with("rb")

    def test_actual_capacity_boundary(self):
        data = b"x" * 33554432
        request = self.make_request(data)
        stream = Stream(data)
        with patch.object(Path, "open", return_value=stream):
            result, snapshot = self.capture(request)
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertEqual(len(self.runtime.snapshot_bytes(snapshot)), 33554432)
        self.assertEqual(stream.requests, [1048576] * 32 + [1])
        self.assertTrue(stream.closed)

    def test_short_reads_and_extra_eof(self):
        stream = Stream(self.data, short=3)
        with patch.object(Path, "open", return_value=stream) as opened:
            result, snapshot = self.capture()
        opened.assert_called_once_with("rb")
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertEqual(self.runtime.snapshot_bytes(snapshot), self.data)
        self.assertEqual(stream.requests[-1], 1)
        self.assertTrue(stream.closed)

    def test_premature_eof(self):
        stream = Stream(self.data[:-1])
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.BYTE_COUNT_MISMATCH)
        self.assertTrue(stream.closed)

    def test_extra_byte(self):
        stream = Stream(self.data + b"extra never consumed")
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.BYTE_COUNT_MISMATCH)
        self.assertEqual(stream.requests, [len(self.data), 1])
        self.assertTrue(stream.closed)

    def test_same_size_substitution(self):
        self.path.write_bytes(b"z" * len(self.data))
        self.failure(Failure.SHA256_MISMATCH)

    def test_missing(self):
        self.path.unlink()
        self.failure(Failure.SOURCE_MISSING)

    def test_access_failure_sanitized(self):
        with patch.object(Path, "open", side_effect=PermissionError(str(self.root))):
            result = self.failure(Failure.SOURCE_ACCESS_FAILED)
        self.assertNotIn(str(self.root), repr(result))

    def test_read_failure_closes(self):
        stream = Stream(self.data, action=lambda n: (_ for _ in ()).throw(OSError(str(self.root))))
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.SOURCE_ACCESS_FAILED)
        self.assertTrue(stream.closed)

    def test_path_rejection(self):
        with patch.object(ManagedStorage, "resolve", side_effect=AcquisitionError("acquisition_storage_failed")):
            self.failure(Failure.SOURCE_PATH_REJECTED)

    def test_nonregular_managed_object(self):
        self.path.unlink()
        self.path.mkdir()
        self.failure(Failure.SOURCE_PATH_REJECTED)

    def test_mutation_deletion_no_reopen(self):
        _, snapshot = self.capture()
        payload = self.runtime.snapshot_bytes(snapshot)
        self.path.write_bytes(b"changed")
        with patch.object(Path, "open", side_effect=AssertionError("reopen")):
            self.assertIs(self.runtime.snapshot_bytes(snapshot), payload)
            self.path.unlink()
            self.assertIs(self.runtime.snapshot_bytes(snapshot), payload)

    def test_varying_read_sequence_matches(self):
        # A synthetic changing stream is authoritative only for its captured sequence.
        stream = Stream(self.data[:4] + b"Z" * (len(self.data) - 4), short=4)
        def mutate(n):
            if n == 1:
                position = stream.tell()
                stream.write(self.data[position:])
                stream.seek(position)
        stream.action = mutate
        with patch.object(Path, "open", return_value=stream):
            result, snapshot = self.capture()
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertEqual(self.runtime.snapshot_bytes(snapshot), self.data)

    def test_mutation_between_reads_fails(self):
        stream = Stream(self.data, short=4)
        def mutate(n):
            if n == 1:
                position = stream.tell()
                stream.seek(position)
                stream.write(b"Z")
                stream.seek(position)
        stream.action = mutate
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.SHA256_MISMATCH)

    def test_direct_construction_rejected(self):
        with self.assertRaises(SourceSnapshotError):
            VerifiedSourceSnapshot()

    def test_detached_descriptor_not_capability(self):
        with self.assertRaises(SourceSnapshotError):
            self.runtime.snapshot_bytes(descriptor())

    def test_foreign_and_release(self):
        _, snapshot = self.capture()
        other = SourceSnapshotRuntime(str(self.root))
        for method in (other.snapshot_bytes, other.release):
            with self.assertRaises(SourceSnapshotError):
                method(snapshot)
        self.runtime.release(snapshot)
        for method in (self.runtime.snapshot_bytes, self.runtime.release):
            with self.assertRaises(SourceSnapshotError):
                method(snapshot)
        self.assertIsNone(snapshot._payload)

    def test_uninitialized_capability_rejected(self):
        snapshot = object.__new__(VerifiedSourceSnapshot)
        with self.assertRaises(SourceSnapshotError):
            self.runtime.snapshot_bytes(snapshot)

    def test_no_serialization(self):
        _, snapshot = self.capture()
        with self.assertRaises(SourceSnapshotError):
            pickle.dumps(snapshot)

    def test_copy_rejected_original_live(self):
        self.check_copy_rejection(copy.copy)

    def test_deepcopy_rejected_original_live(self):
        self.check_copy_rejection(copy.deepcopy)

    def check_copy_rejection(self, copier):
        _, snapshot = self.capture()
        lease = self.runtime._lease
        payload = self.runtime.snapshot_bytes(snapshot)
        with self.assertRaises(SourceSnapshotError):
            copier(snapshot)
        self.assertIs(self.runtime._outstanding, snapshot)
        self.assertIs(self.runtime._lease, lease)
        self.assertTrue(snapshot._active)
        self.assertIs(self.runtime.snapshot_bytes(snapshot), payload)
        self.runtime.release(snapshot)
        self.assertIsNone(self.runtime._outstanding)
        self.assertIsNone(self.runtime._lease)

    def test_outstanding_limit_and_release(self):
        _, snapshot = self.capture()
        with patch.object(ManagedStorage, "resolve", side_effect=AssertionError("resolve")) as resolved, \
             patch.object(Path, "open", side_effect=AssertionError("open")) as opened:
            result, second = self.capture()
        resolved.assert_not_called()
        opened.assert_not_called()
        self.assertIs(result.outcome, Outcome.FAILURE)
        self.assertIs(result.failure_code, Failure.RESOURCE_EXHAUSTED)
        self.assertIsNone(second)
        self.runtime.release(snapshot)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_concurrent_limit(self):
        entered, finish = Event(), Event()
        results = []
        def action(n):
            if n == 1:
                entered.set()
                if not finish.wait(5):
                    raise AssertionError("synchronization timeout")
        stream = Stream(self.data, action=action)
        with patch.object(Path, "open", return_value=stream):
            thread = Thread(target=lambda: results.append(self.capture()))
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                result, snapshot = self.capture()
                self.assertIs(result.failure_code, Failure.RESOURCE_EXHAUSTED)
                self.assertIsNone(snapshot)
            finally:
                finish.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIs(results[0][0].outcome, Outcome.SUCCESS)

    def test_cancel_before_io(self):
        token = CancellationToken()
        token.cancel()
        with patch.object(ManagedStorage, "resolve", side_effect=AssertionError("I/O")):
            self.failure(Failure.CANCELLED, control=token)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_cancel_between_reads(self):
        token = CancellationToken()
        stream = Stream(self.data, short=3, action=lambda n: token.cancel())
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.CANCELLED, control=token)
        self.assertTrue(stream.closed)

    def test_no_callback_control(self):
        with self.assertRaises(SourceSnapshotError):
            self.capture(control=lambda: False)

    def test_deadline_before_io(self):
        with patch.object(runtime_module, "monotonic", side_effect=[0, 31]), \
             patch.object(ManagedStorage, "resolve", side_effect=AssertionError("I/O")):
            self.failure(Failure.DEADLINE_EXCEEDED)

    def test_deadline_between_reads(self):
        now = [0]
        stream = Stream(self.data, short=3, action=lambda n: now.__setitem__(0, 31))
        with patch.object(runtime_module, "monotonic", side_effect=lambda: now[0]), \
             patch.object(Path, "open", return_value=stream):
            self.failure(Failure.DEADLINE_EXCEEDED)
        self.assertTrue(stream.closed)

    def test_deadline_during_hash(self):
        now = [0]
        original = hashlib.sha256
        class Hash:
            def __init__(self):
                self.inner = original()
            def update(self, value):
                self.inner.update(value)
                now[0] = 31
            def hexdigest(self):
                return self.inner.hexdigest()
        with patch.object(runtime_module, "monotonic", side_effect=lambda: now[0]), \
             patch.object(runtime_module.hashlib, "sha256", Hash):
            self.failure(Failure.DEADLINE_EXCEEDED)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_deadline_before_publication(self):
        now = [0]
        original = hashlib.sha256
        class Hash:
            def __init__(self):
                self.inner = original()
            def update(self, value):
                self.inner.update(value)
            def hexdigest(self):
                now[0] = 31
                return self.inner.hexdigest()
        with patch.object(runtime_module, "monotonic", side_effect=lambda: now[0]), \
             patch.object(runtime_module.hashlib, "sha256", Hash):
            self.failure(Failure.DEADLINE_EXCEEDED)

    def test_hash_uses_frozen_returned_payload(self):
        original = hashlib.sha256
        observed = []
        class Hash:
            def __init__(self):
                self.inner = original()
            def update(self, value):
                observed.append(value.obj)
                self.inner.update(value)
            def hexdigest(self):
                return self.inner.hexdigest()
        with patch.object(runtime_module.hashlib, "sha256", Hash):
            _, snapshot = self.capture()
        self.assertTrue(observed)
        self.assertTrue(all(v is self.runtime.snapshot_bytes(snapshot) for v in observed))

    def test_memory_accumulation_failure(self):
        class Buffer(bytearray):
            def extend(self, chunk):
                raise MemoryError()
        with patch.object(runtime_module, "bytearray", Buffer, create=True):
            self.failure(Failure.RESOURCE_EXHAUSTED)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_memory_freeze_failure(self):
        class Buffer(bytearray):
            def __bytes__(self):
                raise MemoryError()
        stream = Stream(self.data)
        with patch.object(runtime_module, "bytearray", Buffer, create=True), \
             patch.object(Path, "open", return_value=stream):
            self.failure(Failure.RESOURCE_EXHAUSTED)
        self.assertTrue(stream.closed)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_success_pair_prepared_before_registration(self):
        original = runtime_module._prepare_success_pair
        observed = []
        def prepare(result, snapshot):
            self.assertIsNone(self.runtime._outstanding)
            self.assertIsNone(self.runtime._lease)
            self.assertFalse(snapshot._active)
            self.assertIs(result.outcome, Outcome.SUCCESS)
            self.assertEqual(hashlib.sha256(snapshot._payload).hexdigest(),
                             self.request.byte_identity.sha256)
            pair = original(result, snapshot)
            observed.append(pair)
            return pair
        with patch.object(runtime_module, "_prepare_success_pair", prepare):
            returned = self.capture()
        self.assertIs(returned, observed[0])
        self.assertIs(self.runtime._outstanding, returned[1])
        self.assertTrue(returned[1]._active)

    def test_memory_success_pair_preparation_failure(self):
        prepared = []
        def fail(result, snapshot):
            self.assertIs(result.outcome, Outcome.SUCCESS)
            self.assertEqual(snapshot._payload, self.data)
            self.assertEqual(hashlib.sha256(snapshot._payload).hexdigest(),
                             self.request.byte_identity.sha256)
            self.assertIsNone(self.runtime._outstanding)
            self.assertIsNone(self.runtime._lease)
            prepared.append(snapshot)
            raise MemoryError()
        with patch.object(runtime_module, "_prepare_success_pair", fail):
            self.failure(Failure.RESOURCE_EXHAUSTED)
        self.assertFalse(prepared[0]._active)
        with self.assertRaises(SourceSnapshotError):
            self.runtime.snapshot_bytes(prepared[0])
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def check_late_rollback(self, exception, failure_allocation=False):
        runtime = self.runtime
        original_lock = runtime._lock
        published = []
        class FailPublicationExit:
            def __enter__(self):
                return original_lock.__enter__()
            def __exit__(self, *args):
                snapshot = runtime._outstanding
                original_lock.__exit__(*args)
                if snapshot is not None and not published:
                    self_test.assertTrue(snapshot._active)
                    self_test.assertIs(runtime._lease, snapshot._lease)
                    self_test.assertEqual(snapshot._payload, self_test.data)
                    published.append(snapshot)
                    raise exception
        self_test = self
        with patch.object(runtime, "_lock", FailPublicationExit()):
            if failure_allocation:
                original_result = runtime_module.SourceSnapshotResult
                def result_factory(outcome, descriptor, code):
                    if outcome is Outcome.FAILURE:
                        raise MemoryError()
                    return original_result(outcome, descriptor, code)
                with patch.object(runtime_module, "SourceSnapshotResult", result_factory):
                    with self.assertRaises(MemoryError):
                        self.capture()
            elif isinstance(exception, MemoryError):
                self.failure(Failure.RESOURCE_EXHAUSTED)
            else:
                with self.assertRaisesRegex(RuntimeError, "publication fault"):
                    self.capture()
        self.assertEqual(len(published), 1)
        snapshot = published[0]
        self.assertIsNone(runtime._outstanding)
        self.assertIsNone(runtime._lease)
        self.assertFalse(runtime._capturing)
        self.assertFalse(snapshot._active)
        self.assertIsNone(snapshot._payload)
        with self.assertRaises(SourceSnapshotError):
            runtime.snapshot_bytes(snapshot)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_memory_post_registration_rollback(self):
        self.check_late_rollback(MemoryError())

    def test_unexpected_post_registration_rollback(self):
        self.check_late_rollback(RuntimeError("publication fault"))

    def test_failure_record_memory_propagates_after_rollback(self):
        self.check_late_rollback(MemoryError(), failure_allocation=True)

    def test_cancel_during_hash(self):
        token = CancellationToken()
        original = hashlib.sha256
        class Hash:
            def __init__(self):
                self.inner = original()
            def update(self, value):
                self.inner.update(value)
                token.cancel()
            def hexdigest(self):
                return self.inner.hexdigest()
        with patch.object(runtime_module.hashlib, "sha256", Hash):
            self.failure(Failure.CANCELLED, control=token)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_cancel_before_publication(self):
        token = CancellationToken()
        original = hashlib.sha256
        class Hash:
            def __init__(self):
                self.inner = original()
            def update(self, value):
                self.inner.update(value)
            def hexdigest(self):
                token.cancel()
                return self.inner.hexdigest()
        with patch.object(runtime_module.hashlib, "sha256", Hash):
            self.failure(Failure.CANCELLED, control=token)

    def test_deadline_before_hash_chunk(self):
        now = [0]
        original = hashlib.sha256
        def hash_factory():
            now[0] = 31
            return original()
        with patch.object(runtime_module, "monotonic", side_effect=lambda: now[0]), \
             patch.object(runtime_module.hashlib, "sha256", side_effect=hash_factory):
            self.failure(Failure.DEADLINE_EXCEEDED)

    def test_hash_failure_closes_and_recovers(self):
        stream = Stream(b"z" * len(self.data))
        with patch.object(Path, "open", return_value=stream):
            self.failure(Failure.SHA256_MISMATCH)
        self.assertTrue(stream.closed)
        self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)

    def test_invalid_inputs_precede_io(self):
        from dataclasses import replace
        with patch.object(ManagedStorage, "resolve", side_effect=AssertionError("I/O")):
            with self.assertRaises(SourceSnapshotError):
                self.runtime.capture(replace(spec(), deadline_seconds=True), self.request)
            with self.assertRaises(SourceSnapshotError):
                self.capture(replace(self.request, byte_identity="secret-path"))
        self.assertFalse(self.runtime._capturing)

    def test_independent_runtime_slots(self):
        _, first = self.capture()
        other = SourceSnapshotRuntime(str(self.root))
        result, second = other.capture(spec(), self.request)
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertEqual(other.snapshot_bytes(second), self.runtime.snapshot_bytes(first))

    def test_snapshot_not_published_during_reads(self):
        observations = []
        stream = Stream(self.data, short=3,
                        action=lambda n: observations.append(self.runtime._outstanding))
        with patch.object(Path, "open", return_value=stream):
            result, _ = self.capture()
        self.assertIs(result.outcome, Outcome.SUCCESS)
        self.assertTrue(observations)
        self.assertTrue(all(v is None for v in observations))

    def test_roots_sanitized(self):
        for root in ("relative-secret", "\\\\server\\share", "//server/share",
                     "\\\\?\\C:\\secret", "\\\\.\\C:\\secret", "https://secret/root", ""):
            with self.subTest(root=root):
                with self.assertRaisesRegex(SourceSnapshotError, "^source_snapshot_invalid$"):
                    SourceSnapshotRuntime(root)
        self.assertEqual(repr(self.runtime), "<SourceSnapshotRuntime>")

    def test_only_readonly_resolution(self):
        original = ManagedStorage.resolve
        keys = []
        def resolve(storage, key):
            keys.append(key)
            return original(storage, key)
        with patch.object(ManagedStorage, "resolve", resolve), \
             patch.object(ManagedStorage, "verify", side_effect=AssertionError("verify")), \
             patch.object(ManagedStorage, "finalize", side_effect=AssertionError("write")):
            self.assertIs(self.capture()[0].outcome, Outcome.SUCCESS)
        self.assertEqual(keys, [object_key(self.request.byte_identity.sha256)])

    def test_m76_unchanged(self):
        assessment = SourceObservationAssessment(True, True, ObservationCoverage.ABSENT)
        identity = self.request.byte_identity
        before = (identity.asset_id, identity.sha256, identity.byte_count)
        self.capture()
        self.assertEqual(before, (identity.asset_id, identity.sha256, identity.byte_count))
        self.assertIs(assessment.physical_byte_verification, AssessmentBoundary.NOT_ASSESSED)
        self.assertIs(assessment.presentation_compliance, AssessmentBoundary.NOT_ASSESSED)

if __name__ == "__main__":
    unittest.main()
