"""M82 detached bounded raster model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.bounded_raster_sampling as api

from creator_studio.png8_observer import (
    PNG8PreflightOutcome,
    PNG8PreflightRuntime,
)
from tests.test_png8_structural_preflight import (
    capture,
    png,
)


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


class BoundedRasterModelTests(unittest.TestCase):

    def setUp(self):
        self.source, self.snapshot = capture(
            png()
        )

        preflight = PNG8PreflightRuntime().preflight(
            self.source,
            self.snapshot,
        )

        self.assertIs(
            preflight.outcome,
            PNG8PreflightOutcome.SUCCESS,
        )

        self.descriptor = preflight.descriptor
        self.profile = preflight.profile

        self.raster = api.BoundedRasterObservation(
            source_width=2,
            source_height=3,
            width=2,
            height=3,
            stride=8,
            pixel_format=(
                api.BoundedRasterPixelFormat.RGBA8
            ),
            sampling_method=(
                api.BoundedRasterSamplingMethod.NEAREST_CENTER
            ),
            pixels=bytes(range(24)),
        )

    def tearDown(self):
        self.source.release(
            self.snapshot
        )

    def success_result(self):
        return api.BoundedRasterResult(
            outcome=api.BoundedRasterOutcome.SUCCESS,
            descriptor=self.descriptor,
            profile=self.profile,
            raster=self.raster,
            failure_code=None,
        )

    def test_valid_observation(self):
        self.assertIs(
            api.validate_bounded_raster_observation(
                self.raster
            ),
            self.raster,
        )

        self.assertEqual(
            self.raster.source_width,
            2,
        )

        self.assertEqual(
            self.raster.source_height,
            3,
        )

        self.assertEqual(
            self.raster.stride,
            8,
        )

        self.assertEqual(
            len(self.raster.pixels),
            24,
        )

    def test_frozen_and_immutable_pixels(self):
        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            self.raster.width = 1

        invalid = dataclasses.replace(
            self.raster,
            pixels=bytearray(
                self.raster.pixels
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_raster_observation_invalid$",
        ):
            api.validate_bounded_raster_observation(
                invalid
            )

    def test_source_dimension_limits(self):
        variants = [
            dataclasses.replace(
                self.raster,
                source_width=0,
            ),
            dataclasses.replace(
                self.raster,
                source_height=0,
            ),
            dataclasses.replace(
                self.raster,
                source_width=True,
            ),
            dataclasses.replace(
                self.raster,
                source_width=4097,
            ),
        ]

        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "^bounded_raster_observation_invalid$",
                ):
                    api.validate_bounded_raster_observation(
                        value
                    )

    def test_sample_dimension_limits(self):
        variants = [
            dataclasses.replace(
                self.raster,
                width=0,
            ),
            dataclasses.replace(
                self.raster,
                height=0,
            ),
            dataclasses.replace(
                self.raster,
                width=True,
            ),
            dataclasses.replace(
                self.raster,
                width=1025,
                stride=4100,
                pixels=bytes(4100 * 3),
            ),
        ]

        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "^bounded_raster_observation_invalid$",
                ):
                    api.validate_bounded_raster_observation(
                        value
                    )

    def test_no_upscale(self):
        variants = [
            dataclasses.replace(
                self.raster,
                width=3,
                stride=12,
                pixels=bytes(36),
            ),
            dataclasses.replace(
                self.raster,
                height=4,
                pixels=bytes(32),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_raster_observation_invalid$",
            ):
                api.validate_bounded_raster_observation(
                    value
                )

    def test_stride_and_pixel_length_exact(self):
        variants = [
            dataclasses.replace(
                self.raster,
                stride=7,
            ),
            dataclasses.replace(
                self.raster,
                pixels=self.raster.pixels[:-1],
            ),
            dataclasses.replace(
                self.raster,
                pixels=self.raster.pixels + b"\x00",
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_raster_observation_invalid$",
            ):
                api.validate_bounded_raster_observation(
                    value
                )

    def test_exact_shape_and_enums(self):
        class Subclass(
            api.BoundedRasterObservation
        ):
            pass

        subclass = Subclass(
            2,
            3,
            2,
            3,
            8,
            api.BoundedRasterPixelFormat.RGBA8,
            api.BoundedRasterSamplingMethod.NEAREST_CENTER,
            bytes(24),
        )

        forged = copy.copy(
            self.raster
        )

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        fake_format = str.__new__(
            api.BoundedRasterPixelFormat,
            "RGBA8",
        )

        fake_method = str.__new__(
            api.BoundedRasterSamplingMethod,
            "NEAREST_CENTER",
        )

        variants = [
            Hostile(),
            subclass,
            forged,
            dataclasses.replace(
                self.raster,
                pixel_format=fake_format,
            ),
            dataclasses.replace(
                self.raster,
                sampling_method=fake_method,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_raster_observation_invalid$",
            ):
                api.validate_bounded_raster_observation(
                    value
                )

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            api.validate_bounded_raster_result(
                result
            ),
            result,
        )

        self.assertIs(
            result.outcome,
            api.BoundedRasterOutcome.SUCCESS,
        )

        self.assertIsNone(
            result.failure_code
        )

    def test_failure_result(self):
        result = api.BoundedRasterResult(
            outcome=api.BoundedRasterOutcome.FAILURE,
            descriptor=None,
            profile=None,
            raster=None,
            failure_code=(
                api.BoundedRasterFailureCode.SAMPLING_INVALID
            ),
        )

        self.assertIs(
            api.validate_bounded_raster_result(
                result
            ),
            result,
        )

    def test_source_dimensions_match_profile(self):
        raster = dataclasses.replace(
            self.raster,
            source_width=1,
        )

        result = dataclasses.replace(
            self.success_result(),
            raster=raster,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_raster_result_invalid$",
        ):
            api.validate_bounded_raster_result(
                result
            )

    def test_detached_roundtrips(self):
        result = self.success_result()

        variants = [
            copy.copy(result),
            copy.deepcopy(result),
            pickle.loads(
                pickle.dumps(result)
            ),
        ]

        for variant in variants:
            self.assertEqual(
                api.validate_bounded_raster_result(
                    variant
                ),
                result,
            )

    def test_invalid_result_shapes(self):
        result = self.success_result()

        class ResultSubclass(
            api.BoundedRasterResult
        ):
            pass

        forged = copy.copy(result)

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        fake_outcome = str.__new__(
            api.BoundedRasterOutcome,
            "SUCCESS",
        )

        fake_failure = str.__new__(
            api.BoundedRasterFailureCode,
            "SAMPLING_INVALID",
        )

        variants = [
            Hostile(),
            ResultSubclass(
                result.outcome,
                result.descriptor,
                result.profile,
                result.raster,
                None,
            ),
            forged,
            dataclasses.replace(
                result,
                outcome=fake_outcome,
            ),
            dataclasses.replace(
                result,
                descriptor=None,
            ),
            dataclasses.replace(
                result,
                profile=None,
            ),
            dataclasses.replace(
                result,
                raster=None,
            ),
            dataclasses.replace(
                result,
                failure_code=(
                    api.BoundedRasterFailureCode.INTERNAL_FAILURE
                ),
            ),
            api.BoundedRasterResult(
                api.BoundedRasterOutcome.FAILURE,
                None,
                None,
                None,
                fake_failure,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_raster_result_invalid$",
            ):
                api.validate_bounded_raster_result(
                    value
                )

    def test_public_api(self):
        self.assertEqual(
            api.MAX_SAMPLE_AXIS,
            1024,
        )

        self.assertEqual(
            api.MAX_SAMPLE_PIXELS,
            1_048_576,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_SAMPLE_AXIS",
                "MAX_SAMPLE_PIXELS",
                "BoundedRasterFailureCode",
                "BoundedRasterObservation",
                "BoundedRasterOutcome",
                "BoundedRasterPixelFormat",
                "BoundedRasterResult",
                "BoundedRasterSamplingMethod",
                "validate_bounded_raster_observation",
                "validate_bounded_raster_result",
                "BoundedRasterSamplingRuntime",
            ),
        )

        self.assertEqual(
            {
                code.value
                for code
                in api.BoundedRasterFailureCode
            },
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "UPSTREAM_RASTER_FAILED",
                "SAMPLING_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()