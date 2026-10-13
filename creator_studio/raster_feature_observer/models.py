"""Detached raster feature reports; possession grants no execution authority."""

from dataclasses import dataclass, fields
from enum import Enum

from ..bounded_raster_sampling.models import (
    MAX_SAMPLE_AXIS,
    MAX_SAMPLE_PIXELS,
)
from ..source_snapshot import (
    SourceSnapshotDescriptor,
    validate_descriptor,
)
from ..still_image_observation_method import (
    EncodedStillImageProfile,
    MAX_CODED_AXIS,
    MAX_DECODED_PIXELS,
    validate_encoded_profile,
)


LUMA_GRID_WIDTH = 8
LUMA_GRID_HEIGHT = 8
LUMA_GRID_SIZE = LUMA_GRID_WIDTH * LUMA_GRID_HEIGHT


class RasterFeatureOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class RasterFeatureFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UPSTREAM_RASTER_FAILED = "UPSTREAM_RASTER_FAILED"
    FEATURE_INVALID = "FEATURE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class RasterFeatureObservation:
    source_width: int
    source_height: int

    width: int
    height: int
    pixel_count: int

    mean_rgba: tuple
    min_rgba: tuple
    max_rgba: tuple

    mean_luma: int
    min_luma: int
    max_luma: int

    alpha_zero_pixels: int
    alpha_partial_pixels: int
    alpha_opaque_pixels: int

    luma_grid: bytes


@dataclass(frozen=True)
class RasterFeatureResult:
    outcome: RasterFeatureOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    features: RasterFeatureObservation | None
    failure_code: RasterFeatureFailureCode | None


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


def _validate_rgba_tuple(value):
    if (
        type(value) is not tuple
        or len(value) != 4
    ):
        raise ValueError()

    for channel in value:
        if (
            type(channel) is not int
            or channel < 0
            or channel > 255
        ):
            raise ValueError()


def validate_raster_feature_observation(features):
    """Validate one detached deterministic raster feature observation."""
    try:
        _validate_exact_shape(
            features,
            RasterFeatureObservation,
        )

        dimensions = (
            features.source_width,
            features.source_height,
            features.width,
            features.height,
            features.pixel_count,
        )

        if any(
            type(value) is not int
            for value in dimensions
        ):
            raise ValueError()

        if (
            features.source_width <= 0
            or features.source_height <= 0
            or features.width <= 0
            or features.height <= 0
            or features.pixel_count <= 0
        ):
            raise ValueError()

        if (
            features.source_width > MAX_CODED_AXIS
            or features.source_height > MAX_CODED_AXIS
            or features.source_width
            * features.source_height
            > MAX_DECODED_PIXELS
        ):
            raise ValueError()

        if (
            features.width > MAX_SAMPLE_AXIS
            or features.height > MAX_SAMPLE_AXIS
            or features.width
            * features.height
            > MAX_SAMPLE_PIXELS
        ):
            raise ValueError()

        if (
            features.width > features.source_width
            or features.height > features.source_height
        ):
            raise ValueError()

        if (
            features.pixel_count
            != features.width * features.height
        ):
            raise ValueError()

        _validate_rgba_tuple(
            features.mean_rgba
        )
        _validate_rgba_tuple(
            features.min_rgba
        )
        _validate_rgba_tuple(
            features.max_rgba
        )

        for index in range(4):
            if not (
                features.min_rgba[index]
                <= features.mean_rgba[index]
                <= features.max_rgba[index]
            ):
                raise ValueError()

        luma_values = (
            features.mean_luma,
            features.min_luma,
            features.max_luma,
        )

        if any(
            type(value) is not int
            or value < 0
            or value > 255
            for value in luma_values
        ):
            raise ValueError()

        if not (
            features.min_luma
            <= features.mean_luma
            <= features.max_luma
        ):
            raise ValueError()

        alpha_counts = (
            features.alpha_zero_pixels,
            features.alpha_partial_pixels,
            features.alpha_opaque_pixels,
        )

        if any(
            type(value) is not int
            or value < 0
            for value in alpha_counts
        ):
            raise ValueError()

        if (
            sum(alpha_counts)
            != features.pixel_count
        ):
            raise ValueError()

        if type(features.luma_grid) is not bytes:
            raise ValueError()

        if (
            len(features.luma_grid)
            != LUMA_GRID_SIZE
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "raster_feature_observation_invalid"
        ) from None

    return features


def validate_raster_feature_result(result):
    """Validate detached result shape without granting execution authority."""
    try:
        _validate_exact_shape(
            result,
            RasterFeatureResult,
        )

        if type(result.outcome) is not RasterFeatureOutcome:
            raise ValueError()

        if result.outcome is RasterFeatureOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(
                result.descriptor
            )

            validate_encoded_profile(
                result.profile
            )

            validate_raster_feature_observation(
                result.features
            )

            if (
                result.features.source_width
                != result.profile.coded_width_px
            ):
                raise ValueError()

            if (
                result.features.source_height
                != result.profile.coded_height_px
            ):
                raise ValueError()

        elif result.outcome is RasterFeatureOutcome.FAILURE:
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.features is not None
                or type(result.failure_code)
                is not RasterFeatureFailureCode
                or not any(
                    result.failure_code is code
                    for code
                    in RasterFeatureFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "raster_feature_result_invalid"
        ) from None

    return result