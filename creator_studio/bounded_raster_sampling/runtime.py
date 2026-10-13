"""Application-controlled bounded sampling over live M81 raster observation."""

from threading import Lock
from time import monotonic

from ..png8_raster_observer import (
    PNG8RasterFailureCode,
    PNG8RasterObservationRuntime,
    PNG8RasterOutcome,
    validate_raster_result,
)
from ..source_snapshot import (
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
    validate_descriptor,
)
from .models import (
    BoundedRasterFailureCode as Failure,
    BoundedRasterObservation,
    BoundedRasterOutcome as Outcome,
    BoundedRasterPixelFormat,
    BoundedRasterResult,
    BoundedRasterSamplingMethod,
    validate_bounded_raster_observation,
    validate_bounded_raster_result,
)
from .sampler import (
    _sample,
    _SamplingFailure,
)


def _failed(code):
    return BoundedRasterResult(
        Outcome.FAILURE,
        None,
        None,
        None,
        code,
    )


def _map_upstream_failure(code):
    if code is PNG8RasterFailureCode.SNAPSHOT_AUTHORITY_INVALID:
        return Failure.SNAPSHOT_AUTHORITY_INVALID

    if code is PNG8RasterFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is PNG8RasterFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    if code in (
        PNG8RasterFailureCode.PREFLIGHT_FAILED,
        PNG8RasterFailureCode.RASTER_INVALID,
    ):
        return Failure.UPSTREAM_RASTER_FAILED

    return Failure.INTERNAL_FAILURE


class BoundedRasterSamplingRuntime:
    def __init__(self):
        self._gate = Lock()
        self._raster = PNG8RasterObservationRuntime()

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
                    raise _SamplingFailure(
                        Failure.DEADLINE_EXCEEDED
                    )

            check()

            upstream = self._raster.observe(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_raster_result(upstream)

            except MemoryError:
                raise

            except Exception:
                raise _SamplingFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if upstream.outcome is not PNG8RasterOutcome.SUCCESS:
                code = _map_upstream_failure(
                    upstream.failure_code
                )

                check()

                return _failed(code)

            try:
                descriptor = snapshot.descriptor
                validate_descriptor(descriptor)

            except MemoryError:
                raise

            except Exception:
                raise _SamplingFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            if descriptor != upstream.descriptor:
                raise _SamplingFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            check()

            width, height, pixels = _sample(
                upstream.raster,
                check,
            )

            check()

            bounded = BoundedRasterObservation(
                source_width=upstream.raster.width,
                source_height=upstream.raster.height,
                width=width,
                height=height,
                stride=width * 4,
                pixel_format=(
                    BoundedRasterPixelFormat.RGBA8
                ),
                sampling_method=(
                    BoundedRasterSamplingMethod.NEAREST_CENTER
                ),
                pixels=pixels,
            )

            validate_bounded_raster_observation(
                bounded
            )

            result = BoundedRasterResult(
                outcome=Outcome.SUCCESS,
                descriptor=descriptor,
                profile=upstream.profile,
                raster=bounded,
                failure_code=None,
            )

            validate_bounded_raster_result(
                result
            )

            check()

            return result

        except _SamplingFailure as exc:
            return _failed(exc.code)

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