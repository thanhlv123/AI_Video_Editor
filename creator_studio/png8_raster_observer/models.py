"""Detached canonical PNG8 raster reports; possession grants no execution authority."""

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


class PNG8RasterOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class PNG8RasterFailureCode(str, Enum):
    SNAPSHOT_AUTHORITY_INVALID = "SNAPSHOT_AUTHORITY_INVALID"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    RASTER_INVALID = "RASTER_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class PNG8PixelFormat(str, Enum):
    RGBA8 = "RGBA8"


@dataclass(frozen=True)
class PNG8RasterObservation:
    width: int
    height: int
    stride: int
    pixel_format: PNG8PixelFormat
    pixels: bytes


@dataclass(frozen=True)
class PNG8RasterResult:
    outcome: PNG8RasterOutcome
    descriptor: SourceSnapshotDescriptor | None
    profile: EncodedStillImageProfile | None
    raster: PNG8RasterObservation | None
    failure_code: PNG8RasterFailureCode | None


def _validate_exact_shape(value, expected_type):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(value, "__dict__")
    names = {field.name for field in fields(expected_type)}

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(type(key) is not str for key in members)
        or set(members) != names
    ):
        raise ValueError()


def validate_raster_observation(raster):
    """Validate one detached canonical RGBA8 raster."""
    try:
        _validate_exact_shape(raster, PNG8RasterObservation)

        if type(raster.width) is not int or type(raster.height) is not int:
            raise ValueError()

        if type(raster.stride) is not int:
            raise ValueError()

        if raster.width <= 0 or raster.height <= 0:
            raise ValueError()

        if raster.width > MAX_CODED_AXIS or raster.height > MAX_CODED_AXIS:
            raise ValueError()

        if raster.width * raster.height > MAX_DECODED_PIXELS:
            raise ValueError()

        if type(raster.pixel_format) is not PNG8PixelFormat:
            raise ValueError()

        if raster.pixel_format is not PNG8PixelFormat.RGBA8:
            raise ValueError()

        if type(raster.pixels) is not bytes:
            raise ValueError()

        expected_stride = raster.width * 4

        if raster.stride != expected_stride:
            raise ValueError()

        if len(raster.pixels) != expected_stride * raster.height:
            raise ValueError()

    except MemoryError:
        raise
    except Exception:
        raise ValueError("png8_raster_observation_invalid") from None

    return raster


def validate_raster_result(result):
    """Validate detached result shape without granting execution authority."""
    try:
        _validate_exact_shape(result, PNG8RasterResult)

        if type(result.outcome) is not PNG8RasterOutcome:
            raise ValueError()

        if result.outcome is PNG8RasterOutcome.SUCCESS:
            if result.failure_code is not None:
                raise ValueError()

            validate_descriptor(result.descriptor)
            validate_encoded_profile(result.profile)
            validate_raster_observation(result.raster)

            if result.raster.width != result.profile.coded_width_px:
                raise ValueError()

            if result.raster.height != result.profile.coded_height_px:
                raise ValueError()

        elif result.outcome is PNG8RasterOutcome.FAILURE:
            if (
                result.descriptor is not None
                or result.profile is not None
                or result.raster is not None
                or type(result.failure_code) is not PNG8RasterFailureCode
                or not any(
                    result.failure_code is code
                    for code in PNG8RasterFailureCode
                )
            ):
                raise ValueError()

        else:
            raise ValueError()

    except MemoryError:
        raise
    except Exception:
        raise ValueError("png8_raster_result_invalid") from None

    return result