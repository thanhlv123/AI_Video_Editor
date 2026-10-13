"""Private deterministic feature extraction over bounded RGBA8 raster."""

from ..bounded_raster_sampling.models import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    validate_bounded_raster_observation,
)
from .models import (
    LUMA_GRID_HEIGHT,
    LUMA_GRID_SIZE,
    LUMA_GRID_WIDTH,
    RasterFeatureFailureCode as Failure,
    RasterFeatureObservation,
    validate_raster_feature_observation,
)


class _FeatureFailure(Exception):
    def __init__(self, code):
        self.code = code


def _luma(red, green, blue):
    """
    Deterministic integer BT.601-style luma.

    Coefficients sum to 256:
        77 R + 150 G + 29 B
    """
    return (
        77 * red
        + 150 * green
        + 29 * blue
        + 128
    ) >> 8


def _grid_source_index(
    grid_index,
    source_size,
    grid_size,
):
    """Map one grid-cell center to one source coordinate."""
    if (
        type(grid_index) is not int
        or type(source_size) is not int
        or type(grid_size) is not int
        or source_size <= 0
        or grid_size <= 0
        or grid_index < 0
        or grid_index >= grid_size
    ):
        raise _FeatureFailure(
            Failure.FEATURE_INVALID
        )

    return min(
        source_size - 1,
        (
            (2 * grid_index + 1)
            * source_size
        )
        // (2 * grid_size),
    )


def _extract(raster, check):
    """
    Extract deterministic numeric features from one M82 bounded raster.

    This is private computation only. Possession of a detached raster does
    not grant public execution authority. The M83 runtime must establish
    authority through the live source snapshot and M82 runtime.
    """
    try:
        validate_bounded_raster_observation(
            raster
        )

    except MemoryError:
        raise _FeatureFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _FeatureFailure(
            Failure.FEATURE_INVALID
        ) from None

    if (
        type(raster) is not BoundedRasterObservation
        or type(raster.pixel_format)
        is not BoundedRasterPixelFormat
        or raster.pixel_format
        is not BoundedRasterPixelFormat.RGBA8
    ):
        raise _FeatureFailure(
            Failure.FEATURE_INVALID
        )

    try:
        check()

        pixel_count = (
            raster.width
            * raster.height
        )

        sums = [
            0,
            0,
            0,
            0,
        ]

        minimums = [
            255,
            255,
            255,
            255,
        ]

        maximums = [
            0,
            0,
            0,
            0,
        ]

        luma_sum = 0
        min_luma = 255
        max_luma = 0

        alpha_zero = 0
        alpha_partial = 0
        alpha_opaque = 0

        pixels = raster.pixels

        for y in range(raster.height):
            check()

            row = y * raster.stride

            for x in range(raster.width):
                offset = row + x * 4

                red = pixels[offset]
                green = pixels[offset + 1]
                blue = pixels[offset + 2]
                alpha = pixels[offset + 3]

                channels = (
                    red,
                    green,
                    blue,
                    alpha,
                )

                for index in range(4):
                    value = channels[index]

                    sums[index] += value

                    if value < minimums[index]:
                        minimums[index] = value

                    if value > maximums[index]:
                        maximums[index] = value

                value_luma = _luma(
                    red,
                    green,
                    blue,
                )

                luma_sum += value_luma

                if value_luma < min_luma:
                    min_luma = value_luma

                if value_luma > max_luma:
                    max_luma = value_luma

                if alpha == 0:
                    alpha_zero += 1

                elif alpha == 255:
                    alpha_opaque += 1

                else:
                    alpha_partial += 1

        check()

        mean_rgba = tuple(
            total // pixel_count
            for total in sums
        )

        mean_luma = (
            luma_sum // pixel_count
        )

        grid = bytearray(
            LUMA_GRID_SIZE
        )

        grid_offset = 0

        for grid_y in range(
            LUMA_GRID_HEIGHT
        ):
            check()

            source_y = _grid_source_index(
                grid_y,
                raster.height,
                LUMA_GRID_HEIGHT,
            )

            source_row = (
                source_y
                * raster.stride
            )

            for grid_x in range(
                LUMA_GRID_WIDTH
            ):
                source_x = _grid_source_index(
                    grid_x,
                    raster.width,
                    LUMA_GRID_WIDTH,
                )

                offset = (
                    source_row
                    + source_x * 4
                )

                grid[grid_offset] = _luma(
                    pixels[offset],
                    pixels[offset + 1],
                    pixels[offset + 2],
                )

                grid_offset += 1

        check()

        features = RasterFeatureObservation(
            source_width=raster.source_width,
            source_height=raster.source_height,
            width=raster.width,
            height=raster.height,
            pixel_count=pixel_count,
            mean_rgba=mean_rgba,
            min_rgba=tuple(minimums),
            max_rgba=tuple(maximums),
            mean_luma=mean_luma,
            min_luma=min_luma,
            max_luma=max_luma,
            alpha_zero_pixels=alpha_zero,
            alpha_partial_pixels=alpha_partial,
            alpha_opaque_pixels=alpha_opaque,
            luma_grid=bytes(grid),
        )

        validate_raster_feature_observation(
            features
        )

        return features

    except _FeatureFailure:
        raise

    except MemoryError:
        raise _FeatureFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None