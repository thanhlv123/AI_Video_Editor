"""Authority-bound deterministic visual evidence observation runtime."""

from threading import Lock
from time import monotonic

from ..raster_feature_observer import (
    RasterFeatureFailureCode,
    RasterFeatureObservationRuntime,
    RasterFeatureOutcome,
    validate_raster_feature_result,
)
from ..source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
    validate_descriptor,
)
from .builder import (
    _build,
    _EvidenceFailure,
)
from .models import (
    VisualEvidenceFailureCode as Failure,
    VisualEvidenceOutcome as Outcome,
    VisualEvidenceResult,
    validate_visual_evidence_result,
)


def _failed(code):
    return VisualEvidenceResult(
        outcome=Outcome.FAILURE,
        descriptor=None,
        profile=None,
        evidence=None,
        failure_code=code,
    )


def _map_upstream_failure(code):
    if code is RasterFeatureFailureCode.SNAPSHOT_AUTHORITY_INVALID:
        return Failure.SNAPSHOT_AUTHORITY_INVALID

    if code is RasterFeatureFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is RasterFeatureFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    if code in (
        RasterFeatureFailureCode.UPSTREAM_RASTER_FAILED,
        RasterFeatureFailureCode.FEATURE_INVALID,
    ):
        return Failure.UPSTREAM_FEATURE_FAILED

    return Failure.INTERNAL_FAILURE


class VisualEvidenceObservationRuntime:
    def __init__(self):
        self._gate = Lock()
        self._features = RasterFeatureObservationRuntime()

    def observe(self, runtime, snapshot):
        if (
            type(runtime) is not SourceSnapshotRuntime
            or type(snapshot) is not VerifiedSourceSnapshot
        ):
            return _failed(
                Failure.SNAPSHOT_AUTHORITY_INVALID
            )

        if not self._gate.acquire(blocking=False):
            return _failed(
                Failure.RESOURCE_LIMIT_EXCEEDED
            )

        try:
            deadline = monotonic() + 30

            def check():
                if monotonic() >= deadline:
                    raise _EvidenceFailure(
                        Failure.DEADLINE_EXCEEDED
                    )

            check()

            upstream = self._features.observe(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_raster_feature_result(
                    upstream
                )

            except MemoryError:
                raise

            except Exception:
                raise _EvidenceFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if upstream.outcome is not RasterFeatureOutcome.SUCCESS:
                code = _map_upstream_failure(
                    upstream.failure_code
                )

                check()

                return _failed(code)

            try:
                descriptor = snapshot.descriptor

                validate_descriptor(
                    descriptor
                )

            except MemoryError:
                raise

            except Exception:
                raise _EvidenceFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            if descriptor != upstream.descriptor:
                raise _EvidenceFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            check()

            evidence = _build(
                upstream.features,
                check,
            )

            check()

            result = VisualEvidenceResult(
                outcome=Outcome.SUCCESS,
                descriptor=descriptor,
                profile=upstream.profile,
                evidence=evidence,
                failure_code=None,
            )

            validate_visual_evidence_result(
                result
            )

            check()

            return result

        except _EvidenceFailure as exc:
            return _failed(
                exc.code
            )

        except MemoryError:
            return _failed(
                Failure.RESOURCE_LIMIT_EXCEEDED
            )

        except Exception:
            return _failed(
                Failure.INTERNAL_FAILURE
            )

        finally:
            self._gate.release()