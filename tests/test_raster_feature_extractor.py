"""M83 deterministic bounded raster feature extraction."""

import dataclasses
import unittest

from creator_studio.bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    BoundedRasterSamplingMethod,
)
from creator_studio.raster_feature_observer import (
    LUMA_GRID_SIZE,
    RasterFeatureObservation,
    validate_raster_feature_observation,
)
from creator_studio.raster_feature_observer.features import (
    _FeatureFailure,
    _extract,
    _grid_source_index,
    _luma,
)


def raster(
    width,
    height,
    pixels,
    source_width=None,
    source_height=None,
):
    if source_width is None:
        source_width = width

    if source_height is None:
        source_height = height

    return BoundedRasterObservation(
        source_width=source_width,
        source_height=source_height,
        width=width,
        height=height,
        stride=width * 4,
        pixel_format=BoundedRasterPixelFormat.RGBA8,
        sampling_method=(
            BoundedRasterSamplingMethod.NEAREST_CENTER
        ),
        pixels=bytes(pixels),
    )


class RasterFeatureExtractorTests(unittest.TestCase):

    def extract(self, value):
        return _extract(
            value,
            lambda: None,
        )

    def failure(
        self,
        value,
        expected="FEATURE_INVALID",
    ):
        with self.assertRaises(
            _FeatureFailure
        ) as caught:
            self.extract(value)

        self.assertEqual(
            caught.exception.code.value,
            expected,
        )

    def test_luma_known_values(self):
        self.assertEqual(
            _luma(0, 0, 0),
            0,
        )

        self.assertEqual(
            _luma(255, 255, 255),
            255,
        )

        self.assertEqual(
            _luma(255, 0, 0),
            77,
        )

        self.assertEqual(
            _luma(0, 255, 0),
            149,
        )

        self.assertEqual(
            _luma(0, 0, 255),
            29,
        )

    def test_single_pixel_features(self):
        source = raster(
            1,
            1,
            [
                10,
                20,
                30,
                255,
            ],
        )

        result = self.extract(source)

        self.assertIs(
            type(result),
            RasterFeatureObservation,
        )

        self.assertEqual(
            result.source_width,
            1,
        )

        self.assertEqual(
            result.source_height,
            1,
        )

        self.assertEqual(
            result.width,
            1,
        )

        self.assertEqual(
            result.height,
            1,
        )

        self.assertEqual(
            result.pixel_count,
            1,
        )

        self.assertEqual(
            result.mean_rgba,
            (10, 20, 30, 255),
        )

        self.assertEqual(
            result.min_rgba,
            (10, 20, 30, 255),
        )

        self.assertEqual(
            result.max_rgba,
            (10, 20, 30, 255),
        )

        expected_luma = _luma(
            10,
            20,
            30,
        )

        self.assertEqual(
            result.mean_luma,
            expected_luma,
        )

        self.assertEqual(
            result.min_luma,
            expected_luma,
        )

        self.assertEqual(
            result.max_luma,
            expected_luma,
        )

        self.assertEqual(
            result.alpha_zero_pixels,
            0,
        )

        self.assertEqual(
            result.alpha_partial_pixels,
            0,
        )

        self.assertEqual(
            result.alpha_opaque_pixels,
            1,
        )

        self.assertEqual(
            result.luma_grid,
            bytes(
                [expected_luma]
                * LUMA_GRID_SIZE
            ),
        )

        validate_raster_feature_observation(
            result
        )

    def test_exact_channel_statistics(self):
        source = raster(
            2,
            2,
            [
                0, 10, 20, 0,
                100, 110, 120, 1,
                200, 210, 220, 254,
                255, 250, 240, 255,
            ],
        )

        result = self.extract(source)

        self.assertEqual(
            result.mean_rgba,
            (
                (0 + 100 + 200 + 255) // 4,
                (10 + 110 + 210 + 250) // 4,
                (20 + 120 + 220 + 240) // 4,
                (0 + 1 + 254 + 255) // 4,
            ),
        )

        self.assertEqual(
            result.min_rgba,
            (0, 10, 20, 0),
        )

        self.assertEqual(
            result.max_rgba,
            (255, 250, 240, 255),
        )

    def test_exact_luma_statistics(self):
        values = [
            (0, 0, 0),
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
        ]

        pixels = []

        for red, green, blue in values:
            pixels.extend(
                (
                    red,
                    green,
                    blue,
                    255,
                )
            )

        source = raster(
            4,
            1,
            pixels,
        )

        result = self.extract(source)

        lumas = [
            _luma(*value)
            for value in values
        ]

        self.assertEqual(
            result.mean_luma,
            sum(lumas) // len(lumas),
        )

        self.assertEqual(
            result.min_luma,
            min(lumas),
        )

        self.assertEqual(
            result.max_luma,
            max(lumas),
        )

    def test_alpha_partition(self):
        source = raster(
            4,
            1,
            [
                0, 0, 0, 0,
                0, 0, 0, 1,
                0, 0, 0, 254,
                0, 0, 0, 255,
            ],
        )

        result = self.extract(source)

        self.assertEqual(
            result.alpha_zero_pixels,
            1,
        )

        self.assertEqual(
            result.alpha_partial_pixels,
            2,
        )

        self.assertEqual(
            result.alpha_opaque_pixels,
            1,
        )

    def test_grid_source_index_mapping(self):
        self.assertEqual(
            [
                _grid_source_index(
                    index,
                    2,
                    8,
                )
                for index in range(8)
            ],
            [
                0,
                0,
                0,
                0,
                1,
                1,
                1,
                1,
            ],
        )

        self.assertEqual(
            [
                _grid_source_index(
                    index,
                    4,
                    2,
                )
                for index in range(2)
            ],
            [
                1,
                3,
            ],
        )

    def test_exact_8x8_grid(self):
        black = (
            0,
            0,
            0,
            255,
        )

        white = (
            255,
            255,
            255,
            255,
        )

        source = raster(
            2,
            2,
            [
                *black,
                *white,
                *white,
                *black,
            ],
        )

        result = self.extract(source)

        expected = bytearray()

        for grid_y in range(8):
            source_y = (
                0
                if grid_y < 4
                else 1
            )

            for grid_x in range(8):
                source_x = (
                    0
                    if grid_x < 4
                    else 1
                )

                white_cell = (
                    source_x != source_y
                )

                expected.append(
                    255
                    if white_cell
                    else 0
                )

        self.assertEqual(
            result.luma_grid,
            bytes(expected),
        )

    def test_source_and_sample_dimensions_preserved(self):
        source = raster(
            2,
            1,
            [
                1, 2, 3, 255,
                4, 5, 6, 255,
            ],
            source_width=2048,
            source_height=1000,
        )

        result = self.extract(source)

        self.assertEqual(
            (
                result.source_width,
                result.source_height,
            ),
            (
                2048,
                1000,
            ),
        )

        self.assertEqual(
            (
                result.width,
                result.height,
            ),
            (
                2,
                1,
            ),
        )

    def test_deterministic(self):
        source = raster(
            3,
            1,
            [
                10, 20, 30, 40,
                50, 60, 70, 80,
                90, 100, 110, 120,
            ],
        )

        first = self.extract(source)
        second = self.extract(source)

        self.assertEqual(
            first,
            second,
        )

    def test_grid_is_immutable_bytes(self):
        source = raster(
            1,
            1,
            [
                1,
                2,
                3,
                4,
            ],
        )

        result = self.extract(source)

        self.assertIs(
            type(result.luma_grid),
            bytes,
        )

        self.assertEqual(
            len(result.luma_grid),
            64,
        )

    def test_invalid_raster_rejected(self):
        source = raster(
            1,
            1,
            [
                1,
                2,
                3,
                4,
            ],
        )

        variants = [
            object(),
            dataclasses.replace(
                source,
                stride=3,
            ),
            dataclasses.replace(
                source,
                pixels=b"\x01\x02\x03",
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

    def test_invalid_grid_index_inputs(self):
        cases = [
            (-1, 2, 8),
            (8, 2, 8),
            (0, 0, 8),
            (0, 2, 0),
            (True, 2, 8),
            (0, True, 8),
            (0, 2, True),
        ]

        for index, source_size, grid_size in cases:
            with self.subTest(
                index=index,
                source_size=source_size,
                grid_size=grid_size,
            ):
                with self.assertRaises(
                    _FeatureFailure
                ) as caught:
                    _grid_source_index(
                        index,
                        source_size,
                        grid_size,
                    )

                self.assertEqual(
                    caught.exception.code.value,
                    "FEATURE_INVALID",
                )

    def test_memory_failure_mapping(self):
        source = raster(
            1,
            1,
            [
                1,
                2,
                3,
                255,
            ],
        )

        def failed_check():
            raise MemoryError()

        with self.assertRaises(
            _FeatureFailure
        ) as caught:
            _extract(
                source,
                failed_check,
            )

        self.assertEqual(
            caught.exception.code.value,
            "RESOURCE_LIMIT_EXCEEDED",
        )

    def test_check_is_used_during_extraction(self):
        source = raster(
            2,
            2,
            [
                1, 2, 3, 255,
                4, 5, 6, 255,
                7, 8, 9, 255,
                10, 11, 12, 255,
            ],
        )

        calls = [0]

        def check():
            calls[0] += 1

        result = _extract(
            source,
            check,
        )

        self.assertIs(
            type(result),
            RasterFeatureObservation,
        )

        self.assertGreaterEqual(
            calls[0],
            12,
        )


if __name__ == "__main__":
    unittest.main()