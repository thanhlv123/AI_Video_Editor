"""Deterministic bounded vision provider payload builder.

Detached raster, evidence, and payload objects grant no execution authority.
"""

from enum import Enum

from ..bounded_raster_sampling import (
    BoundedRasterObservation,
    validate_bounded_raster_observation,
)
from ..visual_evidence_observer import (
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)
from .encoder import (
    _PNGEncodingFailure,
    _PNGEncodingFailureCode,
    _encode_png_rgba8,
)
from .models import (
    VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION,
    BoundedVisionProviderPayload,
    VisionProviderPayloadEncoding,
    validate_bounded_vision_provider_payload,
)


class _PayloadBuildFailureCode(str, Enum):
    RASTER_INVALID = "RASTER_INVALID"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    COHERENCE_INVALID = "COHERENCE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    PAYLOAD_INVALID = "PAYLOAD_INVALID"


class _PayloadBuildFailure(Exception):
    def __init__(self, code):
        if type(code) is not _PayloadBuildFailureCode:
            raise ValueError(
                "payload_build_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _build_payload(
    raster,
    evidence,
    check,
):
    """
    Build one deterministic bounded provider payload.

    This function validates detached inputs only. It does not establish source
    authority and performs no filesystem or network access.
    """
    try:
        validate_bounded_raster_observation(
            raster
        )

    except MemoryError:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .RASTER_INVALID
        ) from None

    if type(raster) is not BoundedRasterObservation:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .RASTER_INVALID
        )

    try:
        validate_visual_evidence_observation(
            evidence
        )

    except MemoryError:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .EVIDENCE_INVALID
        ) from None

    if type(evidence) is not VisualEvidenceObservation:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .EVIDENCE_INVALID
        )

    try:
        check()

        features = evidence.features

        if (
            raster.source_width
            != features.source_width
        ):
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .COHERENCE_INVALID
            )

        if (
            raster.source_height
            != features.source_height
        ):
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .COHERENCE_INVALID
            )

        if (
            raster.width
            != features.width
        ):
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .COHERENCE_INVALID
            )

        if (
            raster.height
            != features.height
        ):
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .COHERENCE_INVALID
            )

        if (
            raster.width
            * raster.height
            != features.pixel_count
        ):
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .COHERENCE_INVALID
            )

        check()

        try:
            image_bytes = _encode_png_rgba8(
                raster,
                check,
            )

        except _PNGEncodingFailure as exc:
            if (
                exc.code
                is _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ):
                raise _PayloadBuildFailure(
                    _PayloadBuildFailureCode
                    .RESOURCE_LIMIT_EXCEEDED
                ) from None

            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .RASTER_INVALID
            ) from None

        check()

        payload = BoundedVisionProviderPayload(
            schema_version=(
                VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION
            ),
            encoding=(
                VisionProviderPayloadEncoding.PNG_RGBA8
            ),
            width=raster.width,
            height=raster.height,
            byte_length=len(
                image_bytes
            ),
            image_bytes=image_bytes,
            evidence=evidence,
        )

        try:
            validate_bounded_vision_provider_payload(
                payload
            )

        except MemoryError:
            raise

        except Exception:
            raise _PayloadBuildFailure(
                _PayloadBuildFailureCode
                .PAYLOAD_INVALID
            ) from None

        check()

        return payload

    except _PayloadBuildFailure:
        raise

    except MemoryError:
        raise _PayloadBuildFailure(
            _PayloadBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None