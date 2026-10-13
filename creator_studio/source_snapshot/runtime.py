"""Transient bounded capture over trusted local M68 managed storage."""
import hashlib
from pathlib import Path
from threading import Lock, Event
from time import monotonic
from ..acquisition.storage import ManagedStorage
from ..acquisition.models import AcquisitionError
from ..manifest.acquisition import object_key
from ..orchestrator.contracts import CancellationToken
from .models import (
    SourceSnapshotError, SourceSnapshotDescriptor, SourceSnapshotResult,
    SourceSnapshotOutcome, SourceSnapshotFailureCode as Failure,
    IMPLEMENTATION_ID, METHOD_ID,
)
from .validation import validate_spec, validate_request

_CONSTRUCTION = object()

class VerifiedSourceSnapshot:
    """Live capability; normal construction and serialization are rejected."""
    __slots__ = ("_owner", "_lease", "_payload", "_descriptor", "_active")

    def __init__(self, token=None, *, owner=None, payload=None, descriptor=None):
        if token is not _CONSTRUCTION:
            raise SourceSnapshotError()
        self._owner, self._lease = owner, object()
        self._payload, self._descriptor, self._active = payload, descriptor, False

    @property
    def descriptor(self):
        return self._descriptor

    def __repr__(self):
        return "<VerifiedSourceSnapshot>"

    def __reduce_ex__(self, protocol):
        raise SourceSnapshotError()

def _prepare_success_pair(result, snapshot):
    """Allocate the final return container before publishing authority."""
    return result, snapshot

class _CaptureFailure(Exception):
    def __init__(self, code):
        self.code = code

class SourceSnapshotRuntime:
    """Per-instance one-capture/one-snapshot service; root never appears in repr."""
    def __init__(self, managed_root):
        if type(managed_root) is not str:
            raise SourceSnapshotError()
        spelling = managed_root.replace("\\", "/")
        if (not spelling or spelling.startswith("//") or "://" in spelling
                or "\x00" in spelling or not Path(managed_root).is_absolute()):
            raise SourceSnapshotError()
        self._storage = ManagedStorage(managed_root)
        self._lock = Lock()
        self._owner = object()
        self._capturing = False
        self._outstanding = None
        self._lease = None

    def __repr__(self):
        return "<SourceSnapshotRuntime>"

    def _live(self, snapshot):
        if (type(snapshot) is not VerifiedSourceSnapshot
                or snapshot is not self._outstanding
                or snapshot._owner is not self._owner
                or snapshot._lease is not self._lease or not snapshot._active):
            raise SourceSnapshotError()

    def snapshot_bytes(self, snapshot):
        with self._lock:
            self._live(snapshot)
            return snapshot._payload

    def release(self, snapshot):
        with self._lock:
            self._live(snapshot)
            snapshot._active = False
            snapshot._payload = None
            self._outstanding = self._lease = None

    def capture(self, spec, request, control=None):
        validate_spec(spec)
        validate_request(request)
        # Exact public token and exact built-in event exclude callback interfaces.
        event = None
        if control is not None:
            if type(control) is not CancellationToken:
                raise SourceSnapshotError()
            event = object.__getattribute__(control, "__dict__").get("_event")
            if type(event) is not Event:
                raise SourceSnapshotError()
        identity = request.byte_identity
        def failed(code):
            return SourceSnapshotResult(SourceSnapshotOutcome.FAILURE, None, code), None
        if identity.byte_count > spec.max_snapshot_bytes:
            return failed(Failure.SNAPSHOT_CAPACITY_EXCEEDED)
        with self._lock:
            if self._capturing or self._outstanding is not None:
                return failed(Failure.RESOURCE_EXHAUSTED)
            self._capturing = True
        capture_finished = False
        try:
            deadline = monotonic() + spec.deadline_seconds
            def check():
                if event is not None and Event.is_set(event):
                    raise _CaptureFailure(Failure.CANCELLED)
                if monotonic() >= deadline:
                    raise _CaptureFailure(Failure.DEADLINE_EXCEEDED)
            check()
            try:
                path = self._storage.resolve(object_key(identity.sha256))
            except AcquisitionError:
                raise _CaptureFailure(Failure.SOURCE_PATH_REJECTED) from None
            check()
            accumulator = bytearray()
            with path.open("rb") as stream:
                while len(accumulator) < identity.byte_count:
                    check()
                    size = min(spec.read_chunk_bytes, identity.byte_count - len(accumulator))
                    chunk = stream.read(size)
                    check()
                    if type(chunk) is not bytes or not chunk or len(chunk) > size:
                        raise _CaptureFailure(Failure.BYTE_COUNT_MISMATCH)
                    accumulator.extend(chunk)
                check()
                extra = stream.read(spec.extra_eof_check_bytes)
                check()
                if type(extra) is not bytes or extra:
                    raise _CaptureFailure(Failure.BYTE_COUNT_MISMATCH)
            payload = bytes(accumulator)
            del accumulator
            check()
            digest = hashlib.sha256()
            for start in range(0, len(payload), spec.read_chunk_bytes):
                check()
                digest.update(memoryview(payload)[start:start + spec.read_chunk_bytes])
                check()
            if len(payload) != identity.byte_count:
                raise _CaptureFailure(Failure.BYTE_COUNT_MISMATCH)
            if digest.hexdigest() != identity.sha256:
                raise _CaptureFailure(Failure.SHA256_MISMATCH)
            descriptor = SourceSnapshotDescriptor(identity, IMPLEMENTATION_ID, "1", METHOD_ID, "1")
            snapshot = VerifiedSourceSnapshot(_CONSTRUCTION, owner=self._owner,
                                              payload=payload, descriptor=descriptor)
            result = SourceSnapshotResult(SourceSnapshotOutcome.SUCCESS, descriptor, None)
            prepared = _prepare_success_pair(result, snapshot)
            try:
                with self._lock:
                    check()
                    self._outstanding = snapshot
                    self._lease = snapshot._lease
                    snapshot._active = True
                    self._capturing = False
                    capture_finished = True
                # No ordinary success allocation remains after publication.
                return prepared
            except Exception:
                # Includes partial registration and lock-exit failures. Never
                # revoke authority belonging to a different capture.
                with self._lock:
                    if self._outstanding is snapshot:
                        self._outstanding = None
                        self._lease = None
                    snapshot._active = False
                    snapshot._payload = None
                raise
        except _CaptureFailure as exc:
            return failed(exc.code)
        except FileNotFoundError:
            return failed(Failure.SOURCE_MISSING)
        except OSError:
            return failed(Failure.SOURCE_ACCESS_FAILED)
        except MemoryError:
            return failed(Failure.RESOURCE_EXHAUSTED)
        finally:
            if not capture_finished:
                with self._lock:
                    self._capturing = False
