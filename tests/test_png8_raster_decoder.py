"""M81 bounded PNG8 decoding and canonical RGBA8 conversion."""

import unittest
import zlib

from creator_studio.png8_raster_observer.decoder import (
    _RasterFailure,
    _decode,
)
from tests.test_png8_structural_preflight import (
    chunk,
    ihdr,
    png,
)


def paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)

    if pa <= pb and pa <= pc:
        return a

    if pb <= pc:
        return b

    return c


def filtered_row(row, previous, channels, filter_type):
    encoded = bytearray(len(row))

    for index, value in enumerate(row):
        left = (
            row[index - channels]
            if index >= channels
            else 0
        )

        up = previous[index] if previous else 0

        upper_left = (
            previous[index - channels]
            if previous and index >= channels
            else 0
        )

        if filter_type == 0:
            predictor = 0

        elif filter_type == 1:
            predictor = left

        elif filter_type == 2:
            predictor = up

        elif filter_type == 3:
            predictor = (left + up) // 2

        elif filter_type == 4:
            predictor = paeth(
                left,
                up,
                upper_left,
            )

        else:
            raise ValueError(filter_type)

        encoded[index] = (
            value - predictor
        ) & 0xFF

    return bytes(encoded)


def make_png(color, width, rows, filters, split=False):
    channels = {
        0: 1,
        2: 3,
        4: 2,
        6: 4,
    }[color]

    previous = bytes(width * channels)
    raw = bytearray()

    for row, filter_type in zip(rows, filters):
        raw.append(filter_type)

        raw.extend(
            filtered_row(
                row,
                previous,
                channels,
                filter_type,
            )
        )

        previous = row

    compressed = zlib.compress(bytes(raw))

    if split:
        midpoint = len(compressed) // 2

        ids = (
            chunk(
                b"IDAT",
                compressed[:midpoint],
            )
            + chunk(
                b"IDAT",
                compressed[midpoint:],
            )
        )

    else:
        ids = chunk(
            b"IDAT",
            compressed,
        )

    return png(
        header=ihdr(
            w=width,
            h=len(rows),
            color=color,
        ),
        ids=ids,
    )


def rgba_rgb(row):
    result = bytearray()

    for index in range(0, len(row), 3):
        result.extend(
            (
                row[index],
                row[index + 1],
                row[index + 2],
                255,
            )
        )

    return bytes(result)


class DecoderTests(unittest.TestCase):

    def decode(self, data, width, height, color):
        return _decode(
            data,
            width,
            height,
            color,
            lambda: None,
        )

    def failure(self, data, width, height, color):
        with self.assertRaises(
            _RasterFailure
        ) as caught:

            self.decode(
                data,
                width,
                height,
                color,
            )

        self.assertEqual(
            caught.exception.code.value,
            "RASTER_INVALID",
        )

    def test_four_color_modes_to_rgba8(self):
        cases = [
            (
                0,
                bytes([10, 20]),
                bytes([
                    10, 10, 10, 255,
                    20, 20, 20, 255,
                ]),
            ),
            (
                2,
                bytes([
                    1, 2, 3,
                    4, 5, 6,
                ]),
                bytes([
                    1, 2, 3, 255,
                    4, 5, 6, 255,
                ]),
            ),
            (
                4,
                bytes([
                    10, 11,
                    20, 21,
                ]),
                bytes([
                    10, 10, 10, 11,
                    20, 20, 20, 21,
                ]),
            ),
            (
                6,
                bytes([
                    1, 2, 3, 4,
                    5, 6, 7, 8,
                ]),
                bytes([
                    1, 2, 3, 4,
                    5, 6, 7, 8,
                ]),
            ),
        ]

        for color, row, expected in cases:
            with self.subTest(color=color):

                data = make_png(
                    color,
                    2,
                    [row],
                    [0],
                )

                self.assertEqual(
                    self.decode(
                        data,
                        2,
                        1,
                        color,
                    ),
                    expected,
                )

    def test_all_five_png_filters(self):
        first = bytes([
            10, 20, 30,
            40, 50, 60,
            70, 80, 90,
        ])

        second = bytes([
            15, 25, 35,
            45, 55, 65,
            75, 85, 95,
        ])

        expected = (
            rgba_rgb(first)
            + rgba_rgb(second)
        )

        for filter_type in range(5):
            with self.subTest(
                filter_type=filter_type
            ):

                data = make_png(
                    2,
                    3,
                    [first, second],
                    [
                        filter_type,
                        filter_type,
                    ],
                )

                self.assertEqual(
                    self.decode(
                        data,
                        3,
                        2,
                        2,
                    ),
                    expected,
                )

    def test_multiple_idat_chunks(self):
        row = bytes([
            1, 2, 3,
            4, 5, 6,
        ])

        data = make_png(
            2,
            2,
            [row],
            [0],
            split=True,
        )

        self.assertEqual(
            self.decode(
                data,
                2,
                1,
                2,
            ),
            rgba_rgb(row),
        )

    def test_invalid_filter(self):
        raw = (
            b"\x05"
            + bytes([1, 2, 3])
        )

        data = png(
            header=ihdr(
                w=1,
                h=1,
                color=2,
            ),
            ids=chunk(
                b"IDAT",
                zlib.compress(raw),
            ),
        )

        self.failure(
            data,
            1,
            1,
            2,
        )

    def test_truncated_zlib_stream(self):
        raw = b"\x00\x01\x02\x03"

        compressed = zlib.compress(raw)

        data = png(
            header=ihdr(
                w=1,
                h=1,
                color=2,
            ),
            ids=chunk(
                b"IDAT",
                compressed[:-2],
            ),
        )

        self.failure(
            data,
            1,
            1,
            2,
        )

    def test_decompressed_size_must_be_exact(self):
        cases = (
            b"\x00\x01\x02",
            b"\x00\x01\x02\x03\x04",
        )

        for raw in cases:
            with self.subTest(
                size=len(raw)
            ):

                data = png(
                    header=ihdr(
                        w=1,
                        h=1,
                        color=2,
                    ),
                    ids=chunk(
                        b"IDAT",
                        zlib.compress(raw),
                    ),
                )

                self.failure(
                    data,
                    1,
                    1,
                    2,
                )

    def test_extra_compressed_stream_rejected(self):
        first = zlib.compress(
            b"\x00\x01\x02\x03"
        )

        second = zlib.compress(
            b"extra"
        )

        data = png(
            header=ihdr(
                w=1,
                h=1,
                color=2,
            ),
            ids=(
                chunk(b"IDAT", first)
                + chunk(b"IDAT", second)
            ),
        )

        self.failure(
            data,
            1,
            1,
            2,
        )

    def test_exact_private_inputs(self):
        cases = [
            (bytearray(), 1, 1, 2),
            (b"", True, 1, 2),
            (b"", 1, True, 2),
            (b"", 1, 1, True),
            (b"", 0, 1, 2),
            (b"", 1, 0, 2),
            (b"", 4097, 1, 2),
            (b"", 1, 4097, 2),
            (b"", 1, 1, 3),
        ]

        for data, width, height, color in cases:
            with self.subTest(
                width=width,
                height=height,
                color=color,
            ):
                self.failure(
                    data,
                    width,
                    height,
                    color,
                )


if __name__ == "__main__":
    unittest.main()