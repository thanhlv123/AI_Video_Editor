"""M86 deterministic bounded RGBA8 PNG encoder."""

import dataclasses
import struct
import unittest
from unittest.mock import patch
import zlib

from creator_studio.bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    BoundedRasterSamplingMethod,
)
from creator_studio.bounded_vision_provider_payload import (
    PNG_SIGNATURE,
)
import creator_studio.bounded_vision_provider_payload.encoder as encoder_module
from creator_studio.bounded_vision_provider_payload.encoder import (
    _PNGEncodingFailure,
    _PNGEncodingFailureCode,
    _encode_png_rgba8,
)
from creator_studio.png8_raster_observer import (
    PNG8RasterObservationRuntime,
    PNG8RasterOutcome,
)
from tests.test_png8_structural_preflight import (
    capture,
)


def raster():
    return BoundedRasterObservation(
        source_width=2,
        source_height=2,
        width=2,
        height=2,
        stride=8,
        pixel_format=(
            BoundedRasterPixelFormat.RGBA8
        ),
        sampling_method=(
            BoundedRasterSamplingMethod.NEAREST_CENTER
        ),
        pixels=bytes([
            10, 20, 30, 0,
            40, 50, 60, 128,
            70, 80, 90, 255,
            100, 110, 120, 255,
        ]),
    )


def encode(
    raster_value=None,
    check=None,
):
    if raster_value is None:
        raster_value = raster()

    if check is None:
        check = lambda: None

    return _encode_png_rgba8(
        raster_value,
        check,
    )


def parse_chunks(data):
    if (
        type(data) is not bytes
        or not data.startswith(
            PNG_SIGNATURE
        )
    ):
        raise AssertionError(
            "invalid PNG fixture"
        )

    position = len(
        PNG_SIGNATURE
    )

    chunks = []

    while position < len(data):
        if position + 12 > len(data):
            raise AssertionError(
                "truncated PNG"
            )

        length = struct.unpack(
            ">I",
            data[
                position:position + 4
            ],
        )[0]

        kind_start = (
            position + 4
        )

        payload_start = (
            position + 8
        )

        payload_end = (
            payload_start
            + length
        )

        crc_end = (
            payload_end
            + 4
        )

        if crc_end > len(data):
            raise AssertionError(
                "truncated PNG chunk"
            )

        kind = data[
            kind_start:payload_start
        ]

        payload = data[
            payload_start:payload_end
        ]

        crc = struct.unpack(
            ">I",
            data[
                payload_end:crc_end
            ],
        )[0]

        chunks.append(
            (
                kind,
                payload,
                crc,
            )
        )

        position = crc_end

    if position != len(data):
        raise AssertionError(
            "PNG trailing structure invalid"
        )

    return chunks


class BoundedVisionProviderPayloadEncoderTests(
    unittest.TestCase
):

    def failure(
        self,
        callable_value,
        expected,
    ):
        with self.assertRaises(
            _PNGEncodingFailure
        ) as caught:
            callable_value()

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_returns_exact_bytes(self):
        value = encode()

        self.assertIs(
            type(value),
            bytes,
        )

        self.assertGreater(
            len(value),
            len(PNG_SIGNATURE),
        )

    def test_deterministic(self):
        value = raster()

        first = encode(
            value
        )

        second = encode(
            value
        )

        self.assertEqual(
            first,
            second,
        )

    def test_png_signature(self):
        value = encode()

        self.assertEqual(
            value[
                :len(PNG_SIGNATURE)
            ],
            PNG_SIGNATURE,
        )

    def test_chunk_order(self):
        chunks = parse_chunks(
            encode()
        )

        self.assertEqual(
            [
                kind
                for kind, _, _
                in chunks
            ],
            [
                b"IHDR",
                b"pHYs",
                b"IDAT",
                b"IEND",
            ],
        )

    def test_ihdr_contract(self):
        chunks = parse_chunks(
            encode()
        )

        kind, payload, _ = chunks[0]

        self.assertEqual(
            kind,
            b"IHDR",
        )

        self.assertEqual(
            len(payload),
            13,
        )

        (
            width,
            height,
            bit_depth,
            color_type,
            compression,
            filtering,
            interlace,
        ) = struct.unpack(
            ">IIBBBBB",
            payload,
        )

        self.assertEqual(
            width,
            2,
        )

        self.assertEqual(
            height,
            2,
        )

        self.assertEqual(
            bit_depth,
            8,
        )

        self.assertEqual(
            color_type,
            6,
        )

        self.assertEqual(
            compression,
            0,
        )

        self.assertEqual(
            filtering,
            0,
        )

        self.assertEqual(
            interlace,
            0,
        )

    def test_phys_contract(self):
        chunks = parse_chunks(
            encode()
        )

        kind, payload, _ = chunks[1]

        self.assertEqual(
            kind,
            b"pHYs",
        )

        self.assertEqual(
            len(payload),
            9,
        )

        x, y, unit = struct.unpack(
            ">IIB",
            payload,
        )

        self.assertEqual(
            x,
            1,
        )

        self.assertEqual(
            y,
            1,
        )

        self.assertEqual(
            unit,
            0,
        )

    def test_idat_decodes_to_filter_zero_rgba_rows(self):
        value = raster()

        chunks = parse_chunks(
            encode(
                value
            )
        )

        idat = chunks[2]

        self.assertEqual(
            idat[0],
            b"IDAT",
        )

        raw = zlib.decompress(
            idat[1]
        )

        expected = (
            b"\x00"
            + value.pixels[0:8]
            + b"\x00"
            + value.pixels[8:16]
        )

        self.assertEqual(
            raw,
            expected,
        )

    def test_all_chunk_crcs_are_valid(self):
        for kind, payload, crc in parse_chunks(
            encode()
        ):
            expected = (
                zlib.crc32(
                    kind + payload
                )
                & 0xFFFFFFFF
            )

            self.assertEqual(
                crc,
                expected,
            )

    def test_roundtrip_through_png8_raster_runtime(self):
        original = raster()

        data = encode(
            original
        )

        source, snapshot = capture(
            data
        )

        try:
            result = (
                PNG8RasterObservationRuntime()
                .observe(
                    source,
                    snapshot,
                )
            )

            self.assertIs(
                result.outcome,
                PNG8RasterOutcome.SUCCESS,
            )

            self.assertEqual(
                result.raster.width,
                original.width,
            )

            self.assertEqual(
                result.raster.height,
                original.height,
            )

            self.assertEqual(
                result.raster.pixels,
                original.pixels,
            )

        finally:
            source.release(
                snapshot
            )

    def test_check_is_used_repeatedly(self):
        calls = [0]

        def check():
            calls[0] += 1

        value = encode(
            check=check
        )

        self.assertIs(
            type(value),
            bytes,
        )

        self.assertGreaterEqual(
            calls[0],
            5,
        )

    def test_invalid_raster_maps_input_invalid(self):
        invalid = dataclasses.replace(
            raster(),
            stride=7,
        )

        self.failure(
            lambda: encode(
                invalid
            ),
            _PNGEncodingFailureCode.INPUT_INVALID,
        )

    def test_exact_raster_type_required(self):
        base = raster()

        class Subclass(
            BoundedRasterObservation
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        self.failure(
            lambda: encode(
                subclass
            ),
            _PNGEncodingFailureCode.INPUT_INVALID,
        )

    def test_memory_error_during_validation_mapping(self):
        with patch.object(
            encoder_module,
            "validate_bounded_raster_observation",
            side_effect=MemoryError(),
        ):
            self.failure(
                lambda: encode(),
                _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            )

    def test_memory_error_during_compression_mapping(self):
        with patch.object(
            encoder_module.zlib,
            "compress",
            side_effect=MemoryError(),
        ):
            self.failure(
                lambda: encode(),
                _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            )

    def test_output_byte_limit_mapping(self):
        with patch.object(
            encoder_module,
            "MAX_VISION_PROVIDER_IMAGE_BYTES",
            8,
        ):
            self.failure(
                lambda: encode(),
                _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            )

    def test_unexpected_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            encode(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            encode(
                check=check
            )


if __name__ == "__main__":
    unittest.main()