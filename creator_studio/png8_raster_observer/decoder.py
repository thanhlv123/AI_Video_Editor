"""Private bounded PNG8 raster decoder. No execution authority."""

import zlib

from ..still_image_observation_method import (
    MAX_CODED_AXIS,
    MAX_DECODED_PIXELS,
)
from .models import PNG8RasterFailureCode as Failure


class _RasterFailure(Exception):
    def __init__(self, code):
        self.code = code


_CHANNELS = {
    0: 1,  # grayscale
    2: 3,  # RGB
    4: 2,  # grayscale + alpha
    6: 4,  # RGBA
}


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)

    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, width, height, color, check):
    channels = _CHANNELS.get(color)

    if channels is None:
        raise _RasterFailure(Failure.RASTER_INVALID)

    source_stride = width * channels
    expected_size = height * (source_stride + 1)

    if len(raw) != expected_size:
        raise _RasterFailure(Failure.RASTER_INVALID)

    rgba = bytearray(width * height * 4)
    previous = bytearray(source_stride)

    source_offset = 0
    output_offset = 0

    for _row_index in range(height):
        check()

        filter_type = raw[source_offset]
        source_offset += 1

        row = bytearray(
            raw[source_offset:source_offset + source_stride]
        )
        source_offset += source_stride

        if filter_type == 0:
            pass

        elif filter_type == 1:
            for index in range(source_stride):
                left = row[index - channels] if index >= channels else 0
                row[index] = (row[index] + left) & 0xFF

        elif filter_type == 2:
            for index in range(source_stride):
                row[index] = (
                    row[index] + previous[index]
                ) & 0xFF

        elif filter_type == 3:
            for index in range(source_stride):
                left = row[index - channels] if index >= channels else 0
                up = previous[index]

                row[index] = (
                    row[index] + ((left + up) // 2)
                ) & 0xFF

        elif filter_type == 4:
            for index in range(source_stride):
                left = row[index - channels] if index >= channels else 0
                up = previous[index]

                upper_left = (
                    previous[index - channels]
                    if index >= channels
                    else 0
                )

                row[index] = (
                    row[index]
                    + _paeth(left, up, upper_left)
                ) & 0xFF

        else:
            raise _RasterFailure(Failure.RASTER_INVALID)

        if color == 0:
            for gray in row:
                rgba[output_offset:output_offset + 4] = (
                    gray,
                    gray,
                    gray,
                    255,
                )
                output_offset += 4

        elif color == 2:
            for index in range(0, source_stride, 3):
                rgba[output_offset:output_offset + 4] = (
                    row[index],
                    row[index + 1],
                    row[index + 2],
                    255,
                )
                output_offset += 4

        elif color == 4:
            for index in range(0, source_stride, 2):
                gray = row[index]
                alpha = row[index + 1]

                rgba[output_offset:output_offset + 4] = (
                    gray,
                    gray,
                    gray,
                    alpha,
                )
                output_offset += 4

        else:
            rgba[
                output_offset:output_offset + source_stride
            ] = row

            output_offset += source_stride

        previous = row

    return bytes(rgba)


def _decode(data, width, height, color, check):
    """
    Decode an already-preflighted PNG8 source into canonical RGBA8.

    Private function only. Possession of bytes or a detached report does not
    grant authority to call the public raster observation runtime.
    """

    if (
        type(data) is not bytes
        or type(width) is not int
        or type(height) is not int
        or type(color) is not int
        or width <= 0
        or height <= 0
        or width > MAX_CODED_AXIS
        or height > MAX_CODED_AXIS
        or width * height > MAX_DECODED_PIXELS
        or color not in _CHANNELS
    ):
        raise _RasterFailure(Failure.RASTER_INVALID)

    channels = _CHANNELS[color]
    source_stride = width * channels
    expected_raw_size = height * (source_stride + 1)

    decompressor = zlib.decompressobj()
    raw = bytearray()

    offset = 8
    saw_idat = False

    view = memoryview(data)
    payload = None

    try:
        while offset < len(data):
            check()

            remaining_file = len(data) - offset

            if remaining_file < 12:
                raise _RasterFailure(
                    Failure.RASTER_INVALID
                )

            length = int.from_bytes(
                data[offset:offset + 4],
                "big",
            )

            payload_start = offset + 8
            payload_end = payload_start + length
            next_offset = payload_end + 4

            if next_offset > len(data):
                raise _RasterFailure(
                    Failure.RASTER_INVALID
                )

            kind = data[offset + 4:offset + 8]

            if kind == b"IDAT":
                saw_idat = True
                payload = view[payload_start:payload_end]

                try:
                    if decompressor.eof:
                        if len(payload):
                            raise _RasterFailure(
                                Failure.RASTER_INVALID
                            )

                    else:
                        remaining_output = (
                            expected_raw_size - len(raw)
                        )

                        try:
                            piece = decompressor.decompress(
                                payload,
                                remaining_output + 1,
                            )

                        except zlib.error:
                            raise _RasterFailure(
                                Failure.RASTER_INVALID
                            ) from None

                        if len(piece) > remaining_output:
                            raise _RasterFailure(
                                Failure.RASTER_INVALID
                            )

                        raw.extend(piece)

                        if decompressor.unconsumed_tail:
                            raise _RasterFailure(
                                Failure.RASTER_INVALID
                            )

                        if decompressor.unused_data:
                            raise _RasterFailure(
                                Failure.RASTER_INVALID
                            )

                finally:
                    payload.release()
                    payload = None

            offset = next_offset

        if not saw_idat:
            raise _RasterFailure(
                Failure.RASTER_INVALID
            )

        remaining_output = expected_raw_size - len(raw)

        try:
            tail = decompressor.flush(
                remaining_output + 1
            )

        except zlib.error:
            raise _RasterFailure(
                Failure.RASTER_INVALID
            ) from None

        if len(tail) > remaining_output:
            raise _RasterFailure(
                Failure.RASTER_INVALID
            )

        raw.extend(tail)

        if (
            not decompressor.eof
            or decompressor.unused_data
            or decompressor.unconsumed_tail
            or len(raw) != expected_raw_size
        ):
            raise _RasterFailure(
                Failure.RASTER_INVALID
            )

        check()

        return _unfilter(
            raw,
            width,
            height,
            color,
            check,
        )

    except MemoryError:
        raise _RasterFailure(
            Failure.RESOURCE_LIMIT_EXCEEDED
        ) from None

    finally:
        if payload is not None:
            payload.release()

        view.release()