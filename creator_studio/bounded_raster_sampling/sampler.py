"""Private deterministic bounded RGBA8 sampler. No execution authority."""

from ..png8_raster_observer import (
    PNG8PixelFormat,
    PNG8RasterObservation,
    validate_raster_observation,
)
from .models import (
    MAX_SAMPLE_AXIS,
    MAX_SAMPLE_PIXELS,
    BoundedRasterFailureCode as Failure,
)


class _SamplingFailure(Exception):
    def __init__(self, code):
        self.code = code


def _target_dimensions(source_width, source_height):
    """Return deterministic bounded dimensions without upscaling."""
    if (
        type(source_width) is not int
        or type(source_height) is not int
        or source_width <= 0
        or source_height <= 0
    ):
        raise _SamplingFailure(
            Failure.SAMPLING_INVALID
        )

    if (
        source_width <= MAX_SAMPLE_AXIS
        and source_height <= MAX_SAMPLE_AXIS
        and source_width * source_height
        <= MAX_SAMPLE_PIXELS
    ):
        return source_width, source_height

    if source_width >= source_height:
        width = MAX_SAMPLE_AXIS
        height = max(
            1,
            (
                source_height
                * MAX_SAMPLE_AXIS
            )
            // source_width,
        )

    else:
        height = MAX_SAMPLE_AXIS
        width = max(
            1,
            (
                source_width
                * MAX_SAMPLE_AXIS
            )
            // source_height,
        )

    if (
        width <= 0
        or height <= 0
        or width > MAX_SAMPLE_AXIS
        or height > MAX_SAMPLE_AXIS
        or width * height > MAX_SAMPLE_PIXELS
        or width > source_width
        or height > source_height
    ):
        raise _SamplingFailure(
            Failure.SAMPLING_INVALID
        )

    return width, height


def _center_index(
    destination_index,
    source_size,
    destination_size,
):
    """
    Map one destination pixel center to its nearest source pixel using
    deterministic integer arithmetic.
    """
    return min(
        source_size - 1,
        (
            (2 * destination_index + 1)
            * source_size
        )
        // (2 * destination_size),
    )


def _sample(raster, check):
    """
    Sample one already-produced M81 RGBA8 raster.

    Private function only. A detached raster does not grant public execution
    authority; the M82 runtime must establish authority through the live
    source snapshot and M81 runtime first.
    """
    try:
        validate_raster_observation(raster)

    except MemoryError:
        raise _SamplingFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _SamplingFailure(
            Failure.SAMPLING_INVALID
        ) from None

    if (
        type(raster) is not PNG8RasterObservation
        or type(raster.pixel_format)
        is not PNG8PixelFormat
        or raster.pixel_format
        is not PNG8PixelFormat.RGBA8
    ):
        raise _SamplingFailure(
            Failure.SAMPLING_INVALID
        )

    try:
        check()

        width, height = _target_dimensions(
            raster.width,
            raster.height,
        )

        if (
            width == raster.width
            and height == raster.height
        ):
            check()

            return (
                width,
                height,
                raster.pixels,
            )

        output = bytearray(
            width * height * 4
        )

        source_stride = raster.stride
        destination_stride = width * 4

        for destination_y in range(height):
            check()

            source_y = _center_index(
                destination_y,
                raster.height,
                height,
            )

            source_row = (
                source_y
                * source_stride
            )

            destination_row = (
                destination_y
                * destination_stride
            )

            for destination_x in range(width):
                source_x = _center_index(
                    destination_x,
                    raster.width,
                    width,
                )

                source_offset = (
                    source_row
                    + source_x * 4
                )

                destination_offset = (
                    destination_row
                    + destination_x * 4
                )

                output[
                    destination_offset:
                    destination_offset + 4
                ] = raster.pixels[
                    source_offset:
                    source_offset + 4
                ]

        check()

        return (
            width,
            height,
            bytes(output),
        )

    except MemoryError:
        raise _SamplingFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None