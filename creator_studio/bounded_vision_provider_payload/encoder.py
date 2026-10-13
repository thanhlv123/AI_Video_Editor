"""Deterministic bounded RGBA8 PNG encoder.

This module converts an already-bounded raster into detached PNG bytes.
It performs no filesystem access, network access, or source authority work.
"""

from enum import Enum
import struct
import zlib

from ..bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    validate_bounded_raster_observation,
)
from .models import (
    MAX_VISION_PROVIDER_IMAGE_BYTES,
    PNG_SIGNATURE,
)


class _PNGEncodingFailureCode(str, Enum):
    INPUT_INVALID = "INPUT_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class _PNGEncodingFailure(Exception):
    def __init__(self, code):
        if type(code) is not _PNGEncodingFailureCode:
            raise ValueError(
                "png_encoding_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _chunk(kind, payload):
    if (
        type(kind) is not bytes
        or len(kind) != 4
        or type(payload) is not bytes
    ):
        raise ValueError(
            "png_chunk_invalid"
        )

    body = kind + payload

    return (
        struct.pack(
            ">I",
            len(payload),
        )
        + body
        + struct.pack(
            ">I",
            zlib.crc32(body) & 0xFFFFFFFF,
        )
    )


def _encode_png_rgba8(
    raster,
    check,
):
    """
    Encode one exact bounded RGBA8 raster into deterministic PNG bytes.

    The returned bytes are detached data only and grant no execution
    authority.
    """
    try:
        validate_bounded_raster_observation(
            raster
        )

    except MemoryError:
        raise _PNGEncodingFailure(
            _PNGEncodingFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _PNGEncodingFailure(
            _PNGEncodingFailureCode.INPUT_INVALID
        ) from None

    if type(raster) is not BoundedRasterObservation:
        raise _PNGEncodingFailure(
            _PNGEncodingFailureCode.INPUT_INVALID
        )

    if (
        type(raster.pixel_format)
        is not BoundedRasterPixelFormat
        or raster.pixel_format
        is not BoundedRasterPixelFormat.RGBA8
    ):
        raise _PNGEncodingFailure(
            _PNGEncodingFailureCode.INPUT_INVALID
        )

    try:
        check()

        row_bytes = raster.width * 4

        scanlines = bytearray()

        for row in range(
            raster.height
        ):
            check()

            start = (
                row
                * raster.stride
            )

            end = (
                start
                + row_bytes
            )

            scanlines.append(
                0
            )

            scanlines.extend(
                raster.pixels[
                    start:end
                ]
            )

        check()

        compressed = zlib.compress(
            bytes(scanlines),
            level=9,
        )

        check()

        ihdr = struct.pack(
            ">IIBBBBB",
            raster.width,
            raster.height,
            8,
            6,
            0,
            0,
            0,
        )

        phys = struct.pack(
            ">IIB",
            1,
            1,
            0,
        )

        output = (
            PNG_SIGNATURE
            + _chunk(
                b"IHDR",
                ihdr,
            )
            + _chunk(
                b"pHYs",
                phys,
            )
            + _chunk(
                b"IDAT",
                compressed,
            )
            + _chunk(
                b"IEND",
                b"",
            )
        )

        if (
            len(output) <= 0
            or len(output)
            > MAX_VISION_PROVIDER_IMAGE_BYTES
        ):
            raise _PNGEncodingFailure(
                _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )

        check()

        return output

    except _PNGEncodingFailure:
        raise

    except MemoryError:
        raise _PNGEncodingFailure(
            _PNGEncodingFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None