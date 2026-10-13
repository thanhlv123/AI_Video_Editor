"""M82 deterministic bounded nearest-center RGBA8 sampling."""

import dataclasses
import unittest

from creator_studio.bounded_raster_sampling.sampler import (
    _SamplingFailure,
    _center_index,
    _sample,
    _target_dimensions,
)
from creator_studio.png8_raster_observer import (
    PNG8PixelFormat,
    PNG8RasterObservation,
)


def raster(width, height, pixels=None):
    if pixels is None:
        data = bytearray()

        for y in range(height):
            for x in range(width):
                data.extend(
                    (
                        x & 0xFF,
                        y & 0xFF,
                        (x + y) & 0xFF,
                        255,
                    )
                )

        pixels = bytes(data)

    return PNG8RasterObservation(
        width=width,
        height=height,
        stride=width * 4,
        pixel_format=PNG8PixelFormat.RGBA8,
        pixels=pixels,
    )


class SamplerTests(unittest.TestCase):

    def sample(self, value):
        return _sample(
            value,
            lambda: None,
        )

    def failure(self, value, code="SAMPLING_INVALID"):
        with self.assertRaises(
            _SamplingFailure
        ) as caught:
            self.sample(value)

        self.assertEqual(
            caught.exception.code.value,
            code,
        )

    def test_small_raster_is_not_upscaled(self):
        source = raster(
            4,
            3,
        )

        width, height, pixels = self.sample(
            source
        )

        self.assertEqual(
            (width, height),
            (4, 3),
        )

        self.assertEqual(
            pixels,
            source.pixels,
        )

        self.assertIs(
            pixels,
            source.pixels,
        )

    def test_square_target_dimensions(self):
        self.assertEqual(
            _target_dimensions(
                2000,
                2000,
            ),
            (1024, 1024),
        )

    def test_landscape_target_dimensions(self):
        self.assertEqual(
            _target_dimensions(
                4096,
                976,
            ),
            (1024, 244),
        )

    def test_portrait_target_dimensions(self):
        self.assertEqual(
            _target_dimensions(
                976,
                4096,
            ),
            (244, 1024),
        )

    def test_thin_dimensions_never_reach_zero(self):
        self.assertEqual(
            _target_dimensions(
                4096,
                1,
            ),
            (1024, 1),
        )

        self.assertEqual(
            _target_dimensions(
                1,
                4096,
            ),
            (1, 1024),
        )

    def test_axis_boundary_is_unchanged(self):
        self.assertEqual(
            _target_dimensions(
                1024,
                1024,
            ),
            (1024, 1024),
        )

        self.assertEqual(
            _target_dimensions(
                1024,
                500,
            ),
            (1024, 500),
        )

    def test_center_index_mapping(self):
        self.assertEqual(
            [
                _center_index(
                    index,
                    4,
                    2,
                )
                for index in range(2)
            ],
            [1, 3],
        )

        self.assertEqual(
            [
                _center_index(
                    index,
                    5,
                    3,
                )
                for index in range(3)
            ],
            [0, 2, 4],
        )

    def test_exact_nearest_center_pixels(self):
        source = raster(
            4,
            2,
            bytes([
                10, 0, 0, 255,
                20, 0, 0, 255,
                30, 0, 0, 255,
                40, 0, 0, 255,

                50, 0, 0, 255,
                60, 0, 0, 255,
                70, 0, 0, 255,
                80, 0, 0, 255,
            ]),
        )

        # Exercise the private sampling mechanics at 2x1 without changing
        # the public M82 dimension policy.
        import creator_studio.bounded_raster_sampling.sampler as module

        original = module._target_dimensions

        module._target_dimensions = (
            lambda width, height: (2, 1)
        )

        try:
            width, height, pixels = self.sample(
                source
            )

        finally:
            module._target_dimensions = original

        self.assertEqual(
            (width, height),
            (2, 1),
        )

        self.assertEqual(
            pixels,
            bytes([
                60, 0, 0, 255,
                80, 0, 0, 255,
            ]),
        )

    def test_output_is_immutable_bytes(self):
        source = raster(
            2048,
            1,
        )

        width, height, pixels = self.sample(
            source
        )

        self.assertEqual(
            (width, height),
            (1024, 1),
        )

        self.assertIs(
            type(pixels),
            bytes,
        )

        self.assertEqual(
            len(pixels),
            1024 * 4,
        )

    def test_sampling_is_deterministic(self):
        source = raster(
            1200,
            3,
        )

        first = self.sample(source)
        second = self.sample(source)

        self.assertEqual(
            first,
            second,
        )

    def test_invalid_raster_rejected(self):
        source = raster(
            2,
            2,
        )

        variants = [
            object(),
            dataclasses.replace(
                source,
                stride=7,
            ),
            dataclasses.replace(
                source,
                pixels=source.pixels[:-1],
            ),
            dataclasses.replace(
                source,
                width=True,
            ),
        ]

        for value in variants:
            with self.subTest(
                value=type(value)
            ):
                self.failure(value)

    def test_invalid_target_dimension_inputs(self):
        cases = [
            (0, 1),
            (1, 0),
            (-1, 1),
            (1, -1),
            (True, 1),
            (1, True),
        ]

        for width, height in cases:
            with self.subTest(
                width=width,
                height=height,
            ):
                with self.assertRaises(
                    _SamplingFailure
                ) as caught:
                    _target_dimensions(
                        width,
                        height,
                    )

                self.assertEqual(
                    caught.exception.code.value,
                    "SAMPLING_INVALID",
                )

    def test_memory_failure_mapping(self):
        source = raster(
            2048,
            1,
        )

        def failed_check():
            raise MemoryError()

        with self.assertRaises(
            _SamplingFailure
        ) as caught:
            _sample(
                source,
                failed_check,
            )

        self.assertEqual(
            caught.exception.code.value,
            "RESOURCE_LIMIT_EXCEEDED",
        )

    def test_check_is_used_during_sampling(self):
        source = raster(
            2048,
            2,
        )

        calls = [0]

        def check():
            calls[0] += 1

        self.sample_with_check = _sample

        self.sample_with_check(
            source,
            check,
        )

        self.assertGreaterEqual(
            calls[0],
            3,
        )


if __name__ == "__main__":
    unittest.main()