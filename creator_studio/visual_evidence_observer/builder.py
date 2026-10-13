"""Private deterministic visual evidence builder. No execution authority."""

from math import gcd

from ..raster_feature_observer.models import (
    RasterFeatureObservation,
    validate_raster_feature_observation,
)
from .models import (
    LUMA_GRID_HEIGHT,
    LUMA_GRID_WIDTH,
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceFailureCode as Failure,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)


class _EvidenceFailure(Exception):
    def __init__(self, code):
        self.code = code


def _reduced_aspect(width, height):
    """Return one positive aspect ratio reduced to lowest integer terms."""
    if (
        type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
    ):
        raise _EvidenceFailure(
            Failure.EVIDENCE_INVALID
        )

    divisor = gcd(
        width,
        height,
    )

    if divisor <= 0:
        raise _EvidenceFailure(
            Failure.EVIDENCE_INVALID
        )

    return (
        width // divisor,
        height // divisor,
    )


def _build(features, check):
    """
    Build deterministic M84 evidence from one M83 feature observation.

    This is private computation only. A detached feature observation does not
    grant public execution authority. The M84 runtime must establish authority
    through the live source snapshot and M83 runtime.
    """
    try:
        validate_raster_feature_observation(
            features
        )

    except MemoryError:
        raise _EvidenceFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _EvidenceFailure(
            Failure.EVIDENCE_INVALID
        ) from None

    if type(features) is not RasterFeatureObservation:
        raise _EvidenceFailure(
            Failure.EVIDENCE_INVALID
        )

    try:
        check()

        (
            source_aspect_numerator,
            source_aspect_denominator,
        ) = _reduced_aspect(
            features.source_width,
            features.source_height,
        )

        check()

        (
            sample_aspect_numerator,
            sample_aspect_denominator,
        ) = _reduced_aspect(
            features.width,
            features.height,
        )

        evidence = VisualEvidenceObservation(
            schema_version=(
                VISUAL_EVIDENCE_SCHEMA_VERSION
            ),
            method=(
                VisualEvidenceMethod
                .DETERMINISTIC_RASTER_FEATURES_V1
            ),
            features=features,
            source_aspect_numerator=(
                source_aspect_numerator
            ),
            source_aspect_denominator=(
                source_aspect_denominator
            ),
            sample_aspect_numerator=(
                sample_aspect_numerator
            ),
            sample_aspect_denominator=(
                sample_aspect_denominator
            ),
            luma_range=(
                features.max_luma
                - features.min_luma
            ),
            luma_grid_width=(
                LUMA_GRID_WIDTH
            ),
            luma_grid_height=(
                LUMA_GRID_HEIGHT
            ),
        )

        try:
            validate_visual_evidence_observation(
                evidence
            )

        except MemoryError:
            raise

        except Exception:
            raise _EvidenceFailure(
                Failure.EVIDENCE_INVALID
            ) from None

        check()

        return evidence

    except _EvidenceFailure:
        raise

    except MemoryError:
        raise _EvidenceFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None