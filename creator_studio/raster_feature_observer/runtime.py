"""Authority-bound deterministic raster feature observation runtime."""

from threading import Lock
from time import monotonic

from ..bounded_raster_sampling import (
    BoundedRasterFailureCode,
    BoundedRasterOutcome,
    BoundedRasterSamplingRuntime,
    validate_bounded_raster_result,
)
from ..source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
    validate_descriptor,
)
from .features import (
    _FeatureFailure,
    _extract,
)
from .models import (
    RasterFeatureFailureCode as Failure,
    RasterFeatureOutcome as Outcome,
    RasterFeatureResult,
    validate_raster_feature_result,
)


def _failed(code):
    return RasterFeatureResult(
        outcome=Outcome.FAILURE,
        descriptor=None,
        profile=None,
        features=None,
        failure_code=code,
    )


def _map_upstream_failure(code):
    if code is BoundedRasterFailureCode.SNAPSHOT_AUTHORITY_INVALID:
        return Failure.SNAPSHOT_AUTHORITY_INVALID

    if code is BoundedRasterFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is BoundedRasterFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    if code in (
        BoundedRasterFailureCode.UPSTREAM_RASTER_FAILED,
        BoundedRasterFailureCode.SAMPLING_INVALID,
    ):
        return Failure.UPSTREAM_RASTER_FAILED

    return Failure.INTERNAL_FAILURE


class RasterFeatureObservationRuntime:
    def __init__(self):
        self._gate = Lock()
        self._bounded = BoundedRasterSamplingRuntime()

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
                    raise _FeatureFailure(
                        Failure.DEADLINE_EXCEEDED
                    )

            check()

            upstream = self._bounded.observe(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_bounded_raster_result(
                    upstream
                )

            except MemoryError:
                raise

            except Exception:
                raise _FeatureFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if upstream.outcome is not BoundedRasterOutcome.SUCCESS:
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
                raise _FeatureFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            if descriptor != upstream.descriptor:
                raise _FeatureFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            check()

            features = _extract(
                upstream.raster,
                check,
            )

            check()

            result = RasterFeatureResult(
                outcome=Outcome.SUCCESS,
                descriptor=descriptor,
                profile=upstream.profile,
                features=features,
                failure_code=None,
            )

            validate_raster_feature_result(
                result
            )

            check()

            return result

        except _FeatureFailure as exc:
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