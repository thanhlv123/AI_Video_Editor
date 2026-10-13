"""M83 detached raster feature model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.raster_feature_observer as api

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


class RasterFeatureModelTests(unittest.TestCase):

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

        self.features = api.RasterFeatureObservation(
            source_width=2,
            source_height=3,
            width=2,
            height=3,
            pixel_count=6,
            mean_rgba=(
                100,
                110,
                120,
                255,
            ),
            min_rgba=(
                10,
                20,
                30,
                255,
            ),
            max_rgba=(
                200,
                210,
                220,
                255,
            ),
            mean_luma=110,
            min_luma=20,
            max_luma=210,
            alpha_zero_pixels=0,
            alpha_partial_pixels=0,
            alpha_opaque_pixels=6,
            luma_grid=bytes(
                [110] * api.LUMA_GRID_SIZE
            ),
        )

    def tearDown(self):
        self.source.release(
            self.snapshot
        )

    def success_result(self):
        return api.RasterFeatureResult(
            outcome=api.RasterFeatureOutcome.SUCCESS,
            descriptor=self.descriptor,
            profile=self.profile,
            features=self.features,
            failure_code=None,
        )

    def test_valid_observation(self):
        self.assertIs(
            api.validate_raster_feature_observation(
                self.features
            ),
            self.features,
        )

        self.assertEqual(
            self.features.pixel_count,
            6,
        )

        self.assertEqual(
            len(self.features.luma_grid),
            64,
        )

    def test_frozen_and_immutable_grid(self):
        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            self.features.width = 1

        invalid = dataclasses.replace(
            self.features,
            luma_grid=bytearray(
                self.features.luma_grid
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^raster_feature_observation_invalid$",
        ):
            api.validate_raster_feature_observation(
                invalid
            )

    def test_source_dimensions(self):
        variants = [
            dataclasses.replace(
                self.features,
                source_width=0,
            ),
            dataclasses.replace(
                self.features,
                source_height=0,
            ),
            dataclasses.replace(
                self.features,
                source_width=True,
            ),
            dataclasses.replace(
                self.features,
                source_width=4097,
            ),
        ]

        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "^raster_feature_observation_invalid$",
                ):
                    api.validate_raster_feature_observation(
                        value
                    )

    def test_sample_dimensions_and_pixel_count(self):
        variants = [
            dataclasses.replace(
                self.features,
                width=0,
            ),
            dataclasses.replace(
                self.features,
                height=0,
            ),
            dataclasses.replace(
                self.features,
                width=True,
            ),
            dataclasses.replace(
                self.features,
                pixel_count=5,
            ),
            dataclasses.replace(
                self.features,
                width=3,
                pixel_count=9,
            ),
            dataclasses.replace(
                self.features,
                height=4,
                pixel_count=8,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_rgba_tuple_contract(self):
        variants = [
            dataclasses.replace(
                self.features,
                mean_rgba=[100, 110, 120, 255],
            ),
            dataclasses.replace(
                self.features,
                mean_rgba=(100, 110, 120),
            ),
            dataclasses.replace(
                self.features,
                mean_rgba=(100, 110, True, 255),
            ),
            dataclasses.replace(
                self.features,
                mean_rgba=(100, 110, 256, 255),
            ),
            dataclasses.replace(
                self.features,
                min_rgba=(150, 20, 30, 255),
            ),
            dataclasses.replace(
                self.features,
                max_rgba=(50, 210, 220, 255),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_luma_contract(self):
        variants = [
            dataclasses.replace(
                self.features,
                mean_luma=True,
            ),
            dataclasses.replace(
                self.features,
                mean_luma=-1,
            ),
            dataclasses.replace(
                self.features,
                mean_luma=256,
            ),
            dataclasses.replace(
                self.features,
                min_luma=120,
            ),
            dataclasses.replace(
                self.features,
                max_luma=100,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_alpha_partition(self):
        variants = [
            dataclasses.replace(
                self.features,
                alpha_zero_pixels=-1,
            ),
            dataclasses.replace(
                self.features,
                alpha_partial_pixels=True,
            ),
            dataclasses.replace(
                self.features,
                alpha_opaque_pixels=5,
            ),
            dataclasses.replace(
                self.features,
                alpha_zero_pixels=1,
                alpha_opaque_pixels=6,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_grid_contract(self):
        variants = [
            dataclasses.replace(
                self.features,
                luma_grid=bytes(63),
            ),
            dataclasses.replace(
                self.features,
                luma_grid=bytes(65),
            ),
            dataclasses.replace(
                self.features,
                luma_grid=bytearray(64),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_exact_shape(self):
        class Subclass(
            api.RasterFeatureObservation
        ):
            pass

        subclass = Subclass(
            **self.features.__dict__
        )

        forged = copy.copy(
            self.features
        )

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        for value in (
            Hostile(),
            subclass,
            forged,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_observation_invalid$",
            ):
                api.validate_raster_feature_observation(
                    value
                )

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            api.validate_raster_feature_result(
                result
            ),
            result,
        )

        self.assertIs(
            result.outcome,
            api.RasterFeatureOutcome.SUCCESS,
        )

        self.assertIsNone(
            result.failure_code
        )

    def test_failure_result(self):
        result = api.RasterFeatureResult(
            outcome=api.RasterFeatureOutcome.FAILURE,
            descriptor=None,
            profile=None,
            features=None,
            failure_code=(
                api.RasterFeatureFailureCode.FEATURE_INVALID
            ),
        )

        self.assertIs(
            api.validate_raster_feature_result(
                result
            ),
            result,
        )

    def test_source_dimensions_match_profile(self):
        features = dataclasses.replace(
            self.features,
            source_width=1,
        )

        result = dataclasses.replace(
            self.success_result(),
            features=features,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^raster_feature_result_invalid$",
        ):
            api.validate_raster_feature_result(
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
                api.validate_raster_feature_result(
                    variant
                ),
                result,
            )

    def test_invalid_result_shapes(self):
        result = self.success_result()

        class ResultSubclass(
            api.RasterFeatureResult
        ):
            pass

        forged = copy.copy(result)

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        variants = [
            Hostile(),
            ResultSubclass(
                result.outcome,
                result.descriptor,
                result.profile,
                result.features,
                None,
            ),
            forged,
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
                features=None,
            ),
            dataclasses.replace(
                result,
                failure_code=(
                    api.RasterFeatureFailureCode.INTERNAL_FAILURE
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^raster_feature_result_invalid$",
            ):
                api.validate_raster_feature_result(
                    value
                )

    def test_public_api(self):
        self.assertEqual(
            api.LUMA_GRID_WIDTH,
            8,
        )

        self.assertEqual(
            api.LUMA_GRID_HEIGHT,
            8,
        )

        self.assertEqual(
            api.LUMA_GRID_SIZE,
            64,
        )

        self.assertEqual(
            api.__all__,
            (
                "LUMA_GRID_HEIGHT",
                "LUMA_GRID_SIZE",
                "LUMA_GRID_WIDTH",
                "RasterFeatureFailureCode",
                "RasterFeatureObservation",
                "RasterFeatureOutcome",
                "RasterFeatureResult",
                "validate_raster_feature_observation",
                "validate_raster_feature_result",
                "RasterFeatureObservationRuntime",
            ),
        )

        self.assertEqual(
            {
                code.value
                for code
                in api.RasterFeatureFailureCode
            },
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "UPSTREAM_RASTER_FAILED",
                "FEATURE_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()