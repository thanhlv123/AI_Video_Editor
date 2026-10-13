"""Application-controlled PNG8 raster observation over live M77 bytes."""

from threading import Lock
from time import monotonic

from ..png8_observer import (
    PNG8PreflightFailureCode,
    PNG8PreflightOutcome,
    PNG8PreflightRuntime,
    validate_preflight_result,
)
from ..source_snapshot import (
    SourceSnapshotError,
    SourceSnapshotRuntime,
    VerifiedSourceSnapshot,
    validate_descriptor,
)
from .decoder import _decode, _RasterFailure
from .models import (
    PNG8PixelFormat,
    PNG8RasterFailureCode as Failure,
    PNG8RasterObservation,
    PNG8RasterOutcome as Outcome,
    PNG8RasterResult,
    validate_raster_observation,
    validate_raster_result,
)


def _failed(code):
    return PNG8RasterResult(
        Outcome.FAILURE,
        None,
        None,
        None,
        code,
    )


def _map_preflight_failure(code):
    if code is PNG8PreflightFailureCode.SNAPSHOT_AUTHORITY_INVALID:
        return Failure.SNAPSHOT_AUTHORITY_INVALID

    if code is PNG8PreflightFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is PNG8PreflightFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    if code in (
        PNG8PreflightFailureCode.UNSUPPORTED_FORMAT,
        PNG8PreflightFailureCode.STRUCTURAL_INVALID,
    ):
        return Failure.PREFLIGHT_FAILED

    return Failure.INTERNAL_FAILURE


class PNG8RasterObservationRuntime:
    def __init__(self):
        self._gate = Lock()
        self._preflight = PNG8PreflightRuntime()

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

        data = None

        try:
            deadline = monotonic() + 30

            def check():
                if monotonic() >= deadline:
                    raise _RasterFailure(
                        Failure.DEADLINE_EXCEEDED
                    )

            check()

            preflight = self._preflight.preflight(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_preflight_result(preflight)

            except MemoryError:
                raise

            except Exception:
                raise _RasterFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if preflight.outcome is not PNG8PreflightOutcome.SUCCESS:
                code = _map_preflight_failure(
                    preflight.failure_code
                )

                check()

                return _failed(code)

            try:
                data = runtime.snapshot_bytes(snapshot)

            except SourceSnapshotError:
                raise _RasterFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            check()

            try:
                descriptor = snapshot.descriptor
                validate_descriptor(descriptor)

            except MemoryError:
                raise

            except Exception:
                raise _RasterFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            if descriptor != preflight.descriptor:
                raise _RasterFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            if (
                type(data) is not bytes
                or len(data)
                != descriptor.byte_identity.byte_count
            ):
                raise _RasterFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            profile = preflight.profile

            pixels = _decode(
                data,
                profile.coded_width_px,
                profile.coded_height_px,
                profile.color_type,
                check,
            )

            check()

            raster = PNG8RasterObservation(
                width=profile.coded_width_px,
                height=profile.coded_height_px,
                stride=profile.coded_width_px * 4,
                pixel_format=PNG8PixelFormat.RGBA8,
                pixels=pixels,
            )

            validate_raster_observation(raster)

            result = PNG8RasterResult(
                outcome=Outcome.SUCCESS,
                descriptor=descriptor,
                profile=profile,
                raster=raster,
                failure_code=None,
            )

            validate_raster_result(result)

            check()

            return result

        except _RasterFailure as exc:
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
            data = None
            self._gate.release()