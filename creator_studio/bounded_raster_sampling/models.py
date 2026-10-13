"""Detached bounded raster reports; possession grants no execution authority."""

from dataclasses import dataclass, fields
from enum import Enum

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


MAX_SAMPLE_AXIS = 1024
MAX_SAMPLE_PIXELS = 1_048_576


class BoundedRasterOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class BoundedRasterFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    UPSTREAM_RASTER_FAILED = "UPSTREAM_RASTER_FAILED"
    SAMPLING_INVALID = "SAMPLING_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class BoundedRasterPixelFormat(str, Enum):
    RGBA8 = "RGBA8"


class BoundedRasterSamplingMethod(str, Enum):
    NEAREST_CENTER = "NEAREST_CENTER"


@dataclass(frozen=True)
class BoundedRasterObservation:
    source_width: int
    source_height: int
    width: int
    height: int
    stride: int
    pixel_format: BoundedRasterPixelFormat
    sampling_method: BoundedRasterSamplingMethod
    pixels: bytes


@dataclass(frozen=True)
class BoundedRasterResult:
    outcome: BoundedRasterOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    raster: BoundedRasterObservation | None
    failure_code: BoundedRasterFailureCode | None


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


def validate_bounded_raster_observation(raster):
    """Validate one detached bounded canonical RGBA8 raster."""
    try:
        _validate_exact_shape(
            raster,
            BoundedRasterObservation,
        )

        dimensions = (
            raster.source_width,
            raster.source_height,
            raster.width,
            raster.height,
            raster.stride,
        )

        if any(
            type(value) is not int
            for value in dimensions
        ):
            raise ValueError()

        if (
            raster.source_width <= 0
            or raster.source_height <= 0
            or raster.width <= 0
            or raster.height <= 0
            or raster.stride <= 0
        ):
            raise ValueError()

        if (
            raster.source_width > MAX_CODED_AXIS
            or raster.source_height > MAX_CODED_AXIS
            or raster.source_width
            * raster.source_height
            > MAX_DECODED_PIXELS
        ):
            raise ValueError()

        if (
            raster.width > MAX_SAMPLE_AXIS
            or raster.height > MAX_SAMPLE_AXIS
            or raster.width
            * raster.height
            > MAX_SAMPLE_PIXELS
        ):
            raise ValueError()

        # M82 never upscales.
        if (
            raster.width > raster.source_width
            or raster.height > raster.source_height
        ):
            raise ValueError()

        if (
            type(raster.pixel_format)
            is not BoundedRasterPixelFormat
            or raster.pixel_format
            is not BoundedRasterPixelFormat.RGBA8
        ):
            raise ValueError()

        if (
            type(raster.sampling_method)
            is not BoundedRasterSamplingMethod
            or raster.sampling_method
            is not BoundedRasterSamplingMethod.NEAREST_CENTER
        ):
            raise ValueError()

        if type(raster.pixels) is not bytes:
            raise ValueError()

        expected_stride = raster.width * 4

        if raster.stride != expected_stride:
            raise ValueError()

        if (
            len(raster.pixels)
            != expected_stride * raster.height
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "bounded_raster_observation_invalid"
        ) from None

    return raster


def validate_bounded_raster_result(result):
    """Validate detached result shape without granting execution authority."""
    try:
        _validate_exact_shape(
            result,
            BoundedRasterResult,
        )

        if type(result.outcome) is not BoundedRasterOutcome:
            raise ValueError()

        if result.outcome is BoundedRasterOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(
                result.descriptor
            )

            validate_encoded_profile(
                result.profile
            )

            validate_bounded_raster_observation(
                result.raster
            )

            if (
                result.raster.source_width
                != result.profile.coded_width_px
            ):
                raise ValueError()

            if (
                result.raster.source_height
                != result.profile.coded_height_px
            ):
                raise ValueError()

        elif result.outcome is BoundedRasterOutcome.FAILURE:
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.raster is not None
                or type(result.failure_code)
                is not BoundedRasterFailureCode
                or not any(
                    result.failure_code is code
                    for code
                    in BoundedRasterFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "bounded_raster_result_invalid"
        ) from None

    return result