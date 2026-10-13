"""Application-controlled structural execution over live M77 bytes."""
from threading import Lock
from time import monotonic
from ..source_snapshot import (
    SourceSnapshotRuntime, VerifiedSourceSnapshot, SourceSnapshotError,
    validate_descriptor,
)
from ..still_image_observation_method import (
    StillImageObservationMethodSpec, validate_method_spec,
    validate_encoded_profile, MAX_INPUT_BYTES,
)
from .models import PNG8PreflightResult, PNG8PreflightOutcome as Outcome
from .models import PNG8PreflightFailureCode as Failure
from .preflight import _parse, _PreflightFailure


def _failed(code):
    return PNG8PreflightResult(Outcome.FAILURE, None, None, code)


class PNG8PreflightRuntime:
    def __init__(self):
        self._gate = Lock()

    def preflight(self, runtime, snapshot):
        if type(runtime) is not SourceSnapshotRuntime or type(snapshot) is not VerifiedSourceSnapshot:
            return _failed(Failure.SNAPSHOT_AUTHORITY_INVALID)
        if not self._gate.acquire(blocking=False):
            return _failed(Failure.RESOURCE_LIMIT_EXCEEDED)
        data = None
        try:
            deadline = monotonic() + 30
            def check():
                if monotonic() >= deadline:
                    raise _PreflightFailure(Failure.DEADLINE_EXCEEDED)
            check()
            check()
            try:
                data = runtime.snapshot_bytes(snapshot)
            except SourceSnapshotError:
                raise _PreflightFailure(Failure.SNAPSHOT_AUTHORITY_INVALID) from None
            check()
            try:
                descriptor = snapshot.descriptor
                validate_descriptor(descriptor)
            except MemoryError:
                raise
            except Exception:
                raise _PreflightFailure(Failure.SNAPSHOT_AUTHORITY_INVALID) from None
            if type(data) is not bytes or len(data) != descriptor.byte_identity.byte_count:
                raise _PreflightFailure(Failure.SNAPSHOT_AUTHORITY_INVALID)
            if len(data) > MAX_INPUT_BYTES:
                raise _PreflightFailure(Failure.RESOURCE_LIMIT_EXCEEDED)
            validate_method_spec(StillImageObservationMethodSpec())
            check()
            profile = _parse(data, check)
            check()
            validate_encoded_profile(profile)
            result = PNG8PreflightResult(Outcome.SUCCESS, descriptor, profile, None)
            check()
            return result
        except _PreflightFailure as exc:
            return _failed(exc.code)
        except MemoryError:
            return _failed(Failure.RESOURCE_LIMIT_EXCEEDED)
        except Exception:
            return _failed(Failure.INTERNAL_FAILURE)
        finally:
            data = None
            self._gate.release()
