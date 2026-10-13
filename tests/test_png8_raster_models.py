"""M81 detached canonical PNG8 raster model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.png8_raster_observer as api
from creator_studio.png8_observer import (
    PNG8PreflightOutcome,
    PNG8PreflightRuntime,
)
from tests.test_png8_structural_preflight import capture, png


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


class RasterModelTests(unittest.TestCase):
    def setUp(self):
        self.source, self.snapshot = capture(png())
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

        self.raster = api.PNG8RasterObservation(
            width=2,
            height=3,
            stride=8,
            pixel_format=api.PNG8PixelFormat.RGBA8,
            pixels=bytes(range(24)),
        )

    def tearDown(self):
        self.source.release(self.snapshot)

    def success_result(self):
        return api.PNG8RasterResult(
            outcome=api.PNG8RasterOutcome.SUCCESS,
            descriptor=self.descriptor,
            profile=self.profile,
            raster=self.raster,
            failure_code=None,
        )

    def test_valid_raster(self):
        self.assertIs(
            api.validate_raster_observation(self.raster),
            self.raster,
        )

        self.assertEqual(self.raster.width, 2)
        self.assertEqual(self.raster.height, 3)
        self.assertEqual(self.raster.stride, 8)
        self.assertEqual(len(self.raster.pixels), 24)
        self.assertIs(
            self.raster.pixel_format,
            api.PNG8PixelFormat.RGBA8,
        )

    def test_raster_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.raster.width = 10

    def test_pixels_are_immutable_bytes(self):
        self.assertIs(type(self.raster.pixels), bytes)

        invalid = dataclasses.replace(
            self.raster,
            pixels=bytearray(self.raster.pixels),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^png8_raster_observation_invalid$",
        ):
            api.validate_raster_observation(invalid)

    def test_dimensions_and_stride(self):
        variants = [
            dataclasses.replace(self.raster, width=0),
            dataclasses.replace(self.raster, width=-1),
            dataclasses.replace(self.raster, height=0),
            dataclasses.replace(self.raster, height=-1),
            dataclasses.replace(self.raster, width=True),
            dataclasses.replace(self.raster, height=True),
            dataclasses.replace(self.raster, stride=True),
            dataclasses.replace(self.raster, stride=7),
            dataclasses.replace(self.raster, width=4097),
        ]

        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "^png8_raster_observation_invalid$",
                ):
                    api.validate_raster_observation(value)

    def test_pixel_length_exact(self):
        for pixels in (
            self.raster.pixels[:-1],
            self.raster.pixels + b"\x00",
        ):
            with self.subTest(size=len(pixels)):
                value = dataclasses.replace(
                    self.raster,
                    pixels=pixels,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^png8_raster_observation_invalid$",
                ):
                    api.validate_raster_observation(value)

    def test_exact_raster_shape_and_enum(self):
        class RasterSubclass(api.PNG8RasterObservation):
            pass

        subclass = RasterSubclass(
            2,
            3,
            8,
            api.PNG8PixelFormat.RGBA8,
            bytes(24),
        )

        forged = copy.copy(self.raster)
        object.__setattr__(forged, "extra", Hostile())

        fake_format = str.__new__(
            api.PNG8PixelFormat,
            "RGBA8",
        )

        variants = [
            Hostile(),
            subclass,
            forged,
            dataclasses.replace(
                self.raster,
                pixel_format=fake_format,
            ),
        ]

        for value in variants:
            with self.subTest(type=type(value)):
                with self.assertRaisesRegex(
                    ValueError,
                    "^png8_raster_observation_invalid$",
                ):
                    api.validate_raster_observation(value)

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            api.validate_raster_result(result),
            result,
        )

        self.assertIs(
            result.outcome,
            api.PNG8RasterOutcome.SUCCESS,
        )

        self.assertIsNone(result.failure_code)

    def test_failure_result(self):
        result = api.PNG8RasterResult(
            outcome=api.PNG8RasterOutcome.FAILURE,
            descriptor=None,
            profile=None,
            raster=None,
            failure_code=api.PNG8RasterFailureCode.RASTER_INVALID,
        )

        self.assertIs(
            api.validate_raster_result(result),
            result,
        )

    def test_success_dimensions_match_profile(self):
        wrong_width = dataclasses.replace(
            self.raster,
            width=1,
            stride=4,
            pixels=bytes(12),
        )

        result = dataclasses.replace(
            self.success_result(),
            raster=wrong_width,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^png8_raster_result_invalid$",
        ):
            api.validate_raster_result(result)

    def test_detached_roundtrips(self):
        result = self.success_result()

        variants = [
            copy.copy(result),
            copy.deepcopy(result),
            pickle.loads(pickle.dumps(result)),
        ]

        for variant in variants:
            self.assertEqual(
                api.validate_raster_result(variant),
                result,
            )

    def test_invalid_result_shapes(self):
        result = self.success_result()

        class ResultSubclass(api.PNG8RasterResult):
            pass

        forged = copy.copy(result)
        object.__setattr__(forged, "extra", Hostile())

        fake_outcome = str.__new__(
            api.PNG8RasterOutcome,
            "SUCCESS",
        )

        fake_failure = str.__new__(
            api.PNG8RasterFailureCode,
            "RASTER_INVALID",
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
                failure_code=api.PNG8RasterFailureCode.INTERNAL_FAILURE,
            ),
            api.PNG8RasterResult(
                api.PNG8RasterOutcome.FAILURE,
                None,
                None,
                None,
                fake_failure,
            ),
        ]

        for value in variants:
            with self.subTest(type=type(value)):
                with self.assertRaisesRegex(
                    ValueError,
                    "^png8_raster_result_invalid$",
                ):
                    api.validate_raster_result(value)

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "PNG8PixelFormat",
                "PNG8RasterFailureCode",
                "PNG8RasterObservation",
                "PNG8RasterOutcome",
                "PNG8RasterResult",
                "validate_raster_observation",
                "validate_raster_result",
            ),
        )

        self.assertEqual(
            {code.value for code in api.PNG8RasterFailureCode},
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "PREFLIGHT_FAILED",
                "RASTER_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()