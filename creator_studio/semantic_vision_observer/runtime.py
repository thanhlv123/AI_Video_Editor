"""Authority-bound semantic vision observation runtime."""

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
from ..visual_evidence_observer import (
    VisualEvidenceFailureCode,
    VisualEvidenceObservationRuntime,
    VisualEvidenceOutcome,
    validate_visual_evidence_result,
)
from .adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
    SemanticVisionAdapterRequest,
)
from .builder import (
    _SemanticBuildFailure,
    _build_semantic_observation,
)
from .models import (
    SemanticVisionFailureCode as Failure,
    SemanticVisionOutcome as Outcome,
    SemanticVisionResult,
    validate_semantic_vision_result,
)
from .provider_contract import (
    SemanticVisionProviderFailure,
    SemanticVisionProviderFailureCode,
    _invoke_provider,
)


class _RuntimeFailure(Exception):
    def __init__(self, code):
        self.code = code


def _failed(code):
    return SemanticVisionResult(
        outcome=Outcome.FAILURE,
        descriptor=None,
        profile=None,
        observation=None,
        failure_code=code,
    )


def _map_evidence_failure(code):
    if code is VisualEvidenceFailureCode.SNAPSHOT_AUTHORITY_INVALID:
        return Failure.SNAPSHOT_AUTHORITY_INVALID

    if code is VisualEvidenceFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is VisualEvidenceFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    if code in (
        VisualEvidenceFailureCode.UPSTREAM_FEATURE_FAILED,
        VisualEvidenceFailureCode.EVIDENCE_INVALID,
    ):
        return Failure.UPSTREAM_EVIDENCE_FAILED

    return Failure.INTERNAL_FAILURE


def _map_raster_failure(code):
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
        return Failure.UPSTREAM_EVIDENCE_FAILED

    return Failure.INTERNAL_FAILURE


def _map_provider_failure(code):
    if code is SemanticVisionProviderFailureCode.UNAVAILABLE:
        return Failure.ADAPTER_UNAVAILABLE

    if code is SemanticVisionProviderFailureCode.RESPONSE_INVALID:
        return Failure.RESPONSE_INVALID

    if code is SemanticVisionProviderFailureCode.RESOURCE_LIMIT_EXCEEDED:
        return Failure.RESOURCE_LIMIT_EXCEEDED

    if code is SemanticVisionProviderFailureCode.DEADLINE_EXCEEDED:
        return Failure.DEADLINE_EXCEEDED

    return Failure.INTERNAL_FAILURE


class SemanticVisionObservationRuntime:
    def __init__(self, provider):
        self._gate = Lock()
        self._evidence = VisualEvidenceObservationRuntime()
        self._raster = BoundedRasterSamplingRuntime()
        self._provider = provider

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
                    raise _RuntimeFailure(
                        Failure.DEADLINE_EXCEEDED
                    )

            def provider_check():
                if monotonic() >= deadline:
                    raise SemanticVisionProviderFailure(
                        SemanticVisionProviderFailureCode
                        .DEADLINE_EXCEEDED
                    )

            check()

            evidence_result = self._evidence.observe(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_visual_evidence_result(
                    evidence_result
                )

            except MemoryError:
                raise

            except Exception:
                raise _RuntimeFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if (
                evidence_result.outcome
                is not VisualEvidenceOutcome.SUCCESS
            ):
                return _failed(
                    _map_evidence_failure(
                        evidence_result.failure_code
                    )
                )

            try:
                descriptor = snapshot.descriptor

                validate_descriptor(
                    descriptor
                )

            except MemoryError:
                raise

            except Exception:
                raise _RuntimeFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                ) from None

            if descriptor != evidence_result.descriptor:
                raise _RuntimeFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            check()

            raster_result = self._raster.observe(
                runtime,
                snapshot,
            )

            check()

            try:
                validate_bounded_raster_result(
                    raster_result
                )

            except MemoryError:
                raise

            except Exception:
                raise _RuntimeFailure(
                    Failure.INTERNAL_FAILURE
                ) from None

            if (
                raster_result.outcome
                is not BoundedRasterOutcome.SUCCESS
            ):
                return _failed(
                    _map_raster_failure(
                        raster_result.failure_code
                    )
                )

            if descriptor != raster_result.descriptor:
                raise _RuntimeFailure(
                    Failure.SNAPSHOT_AUTHORITY_INVALID
                )

            if raster_result.profile != evidence_result.profile:
                raise _RuntimeFailure(
                    Failure.INTERNAL_FAILURE
                )

            check()

            request = SemanticVisionAdapterRequest(
                schema_version=(
                    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
                ),
                raster=raster_result.raster,
                evidence=evidence_result.evidence,
            )

            response = _invoke_provider(
                self._provider,
                request,
                provider_check,
            )

            check()

            observation = _build_semantic_observation(
                evidence_result.evidence,
                response,
                check,
            )

            check()

            result = SemanticVisionResult(
                outcome=Outcome.SUCCESS,
                descriptor=descriptor,
                profile=evidence_result.profile,
                observation=observation,
                failure_code=None,
            )

            validate_semantic_vision_result(
                result
            )

            check()

            return result

        except _RuntimeFailure as exc:
            return _failed(
                exc.code
            )

        except SemanticVisionProviderFailure as exc:
            return _failed(
                _map_provider_failure(
                    exc.code
                )
            )

        except _SemanticBuildFailure as exc:
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