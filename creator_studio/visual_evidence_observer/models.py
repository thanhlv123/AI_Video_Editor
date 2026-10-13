"""Detached visual evidence reports; possession grants no execution authority."""

from dataclasses import dataclass, fields
from enum import Enum
from math import gcd

from ..raster_feature_observer.models import (
    LUMA_GRID_HEIGHT,
    LUMA_GRID_WIDTH,
    RasterFeatureObservation,
    validate_raster_feature_observation,
)
from ..source_snapshot import (
    SourceSnapshotDescriptor,
    validate_descriptor,
)
from ..still_image_observation_method import (
    EncodedStillImageProfile,
    validate_encoded_profile,
)


VISUAL_EVIDENCE_SCHEMA_VERSION = 1


class VisualEvidenceOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class VisualEvidenceFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UPSTREAM_FEATURE_FAILED = "UPSTREAM_FEATURE_FAILED"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class VisualEvidenceMethod(str, Enum):
    DETERMINISTIC_RASTER_FEATURES_V1 = (
        "DETERMINISTIC_RASTER_FEATURES_V1"
    )


@dataclass(frozen=True)
class VisualEvidenceObservation:
    schema_version: int
    method: VisualEvidenceMethod

    features: RasterFeatureObservation

    source_aspect_numerator: int
    source_aspect_denominator: int

    sample_aspect_numerator: int
    sample_aspect_denominator: int

    luma_range: int

    luma_grid_width: int
    luma_grid_height: int


@dataclass(frozen=True)
class VisualEvidenceResult:
    outcome: VisualEvidenceOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    evidence: VisualEvidenceObservation | None
    failure_code: VisualEvidenceFailureCode | None


def _validate_exact_shape(value, expected_type):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(expected_type)
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def _validate_aspect_ratio(
    numerator,
    denominator,
    width,
    height,
):
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or numerator <= 0
        or denominator <= 0
    ):
        raise ValueError()

    if gcd(
        numerator,
        denominator,
    ) != 1:
        raise ValueError()

    if (
        numerator * height
        != denominator * width
    ):
        raise ValueError()


def validate_visual_evidence_observation(evidence):
    """Validate one detached deterministic visual evidence package."""
    try:
        _validate_exact_shape(
            evidence,
            VisualEvidenceObservation,
        )

        if (
            type(evidence.schema_version) is not int
            or evidence.schema_version
            != VISUAL_EVIDENCE_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(evidence.method)
            is not VisualEvidenceMethod
            or evidence.method
            is not VisualEvidenceMethod.DETERMINISTIC_RASTER_FEATURES_V1
        ):
            raise ValueError()

        validate_raster_feature_observation(
            evidence.features
        )

        _validate_aspect_ratio(
            evidence.source_aspect_numerator,
            evidence.source_aspect_denominator,
            evidence.features.source_width,
            evidence.features.source_height,
        )

        _validate_aspect_ratio(
            evidence.sample_aspect_numerator,
            evidence.sample_aspect_denominator,
            evidence.features.width,
            evidence.features.height,
        )

        if (
            type(evidence.luma_range) is not int
            or evidence.luma_range < 0
            or evidence.luma_range > 255
        ):
            raise ValueError()

        if (
            evidence.luma_range
            != (
                evidence.features.max_luma
                - evidence.features.min_luma
            )
        ):
            raise ValueError()

        if (
            type(evidence.luma_grid_width) is not int
            or type(evidence.luma_grid_height) is not int
        ):
            raise ValueError()

        if (
            evidence.luma_grid_width
            != LUMA_GRID_WIDTH
            or evidence.luma_grid_height
            != LUMA_GRID_HEIGHT
        ):
            raise ValueError()

        if (
            len(evidence.features.luma_grid)
            != (
                evidence.luma_grid_width
                * evidence.luma_grid_height
            )
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "visual_evidence_observation_invalid"
        ) from None

    return evidence


def validate_visual_evidence_result(result):
    """Validate detached result shape without granting execution authority."""
    try:
        _validate_exact_shape(
            result,
            VisualEvidenceResult,
        )

        if type(result.outcome) is not VisualEvidenceOutcome:
            raise ValueError()

        if result.outcome is VisualEvidenceOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(
                result.descriptor
            )

            validate_encoded_profile(
                result.profile
            )

            validate_visual_evidence_observation(
                result.evidence
            )

            if (
                result.evidence.features.source_width
                != result.profile.coded_width_px
            ):
                raise ValueError()

            if (
                result.evidence.features.source_height
                != result.profile.coded_height_px
            ):
                raise ValueError()

        elif result.outcome is VisualEvidenceOutcome.FAILURE:
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.evidence is not None
                or type(result.failure_code)
                is not VisualEvidenceFailureCode
                or not any(
                    result.failure_code is code
                    for code
                    in VisualEvidenceFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "visual_evidence_result_invalid"
        ) from None

    return result