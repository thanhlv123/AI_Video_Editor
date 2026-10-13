"""M84 detached deterministic visual evidence model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.visual_evidence_observer as api

from creator_studio.png8_observer import (
    PNG8PreflightOutcome,
    PNG8PreflightRuntime,
)
from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
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


class VisualEvidenceModelTests(unittest.TestCase):

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

        self.features = RasterFeatureObservation(
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
                [110] * 64
            ),
        )

        self.evidence = api.VisualEvidenceObservation(
            schema_version=(
                api.VISUAL_EVIDENCE_SCHEMA_VERSION
            ),
            method=(
                api.VisualEvidenceMethod
                .DETERMINISTIC_RASTER_FEATURES_V1
            ),
            features=self.features,
            source_aspect_numerator=2,
            source_aspect_denominator=3,
            sample_aspect_numerator=2,
            sample_aspect_denominator=3,
            luma_range=190,
            luma_grid_width=8,
            luma_grid_height=8,
        )

    def tearDown(self):
        self.source.release(
            self.snapshot
        )

    def success_result(self):
        return api.VisualEvidenceResult(
            outcome=api.VisualEvidenceOutcome.SUCCESS,
            descriptor=self.descriptor,
            profile=self.profile,
            evidence=self.evidence,
            failure_code=None,
        )

    def test_valid_observation(self):
        self.assertIs(
            api.validate_visual_evidence_observation(
                self.evidence
            ),
            self.evidence,
        )

        self.assertEqual(
            self.evidence.schema_version,
            1,
        )

        self.assertEqual(
            self.evidence.luma_range,
            190,
        )

    def test_frozen(self):
        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            self.evidence.luma_range = 1

    def test_schema_version_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                schema_version=2,
            ),
            dataclasses.replace(
                self.evidence,
                schema_version=0,
            ),
            dataclasses.replace(
                self.evidence,
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_method_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                method=(
                    "DETERMINISTIC_RASTER_FEATURES_V1"
                ),
            ),
            dataclasses.replace(
                self.evidence,
                method=None,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_feature_contract(self):
        invalid_features = dataclasses.replace(
            self.features,
            pixel_count=5,
        )

        variants = [
            dataclasses.replace(
                self.evidence,
                features=Hostile(),
            ),
            dataclasses.replace(
                self.evidence,
                features=invalid_features,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_source_aspect_ratio_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                source_aspect_numerator=4,
                source_aspect_denominator=6,
            ),
            dataclasses.replace(
                self.evidence,
                source_aspect_numerator=3,
                source_aspect_denominator=2,
            ),
            dataclasses.replace(
                self.evidence,
                source_aspect_numerator=0,
            ),
            dataclasses.replace(
                self.evidence,
                source_aspect_numerator=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_sample_aspect_ratio_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                sample_aspect_numerator=4,
                sample_aspect_denominator=6,
            ),
            dataclasses.replace(
                self.evidence,
                sample_aspect_numerator=3,
                sample_aspect_denominator=2,
            ),
            dataclasses.replace(
                self.evidence,
                sample_aspect_denominator=0,
            ),
            dataclasses.replace(
                self.evidence,
                sample_aspect_denominator=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_luma_range_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                luma_range=189,
            ),
            dataclasses.replace(
                self.evidence,
                luma_range=-1,
            ),
            dataclasses.replace(
                self.evidence,
                luma_range=256,
            ),
            dataclasses.replace(
                self.evidence,
                luma_range=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_grid_metadata_contract(self):
        variants = [
            dataclasses.replace(
                self.evidence,
                luma_grid_width=7,
            ),
            dataclasses.replace(
                self.evidence,
                luma_grid_height=9,
            ),
            dataclasses.replace(
                self.evidence,
                luma_grid_width=True,
            ),
            dataclasses.replace(
                self.evidence,
                luma_grid_height=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_exact_shape(self):
        class Subclass(
            api.VisualEvidenceObservation
        ):
            pass

        subclass = Subclass(
            **self.evidence.__dict__
        )

        forged = copy.copy(
            self.evidence
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
                "^visual_evidence_observation_invalid$",
            ):
                api.validate_visual_evidence_observation(
                    value
                )

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            api.validate_visual_evidence_result(
                result
            ),
            result,
        )

        self.assertIs(
            result.outcome,
            api.VisualEvidenceOutcome.SUCCESS,
        )

        self.assertIsNone(
            result.failure_code
        )

    def test_failure_result(self):
        result = api.VisualEvidenceResult(
            outcome=api.VisualEvidenceOutcome.FAILURE,
            descriptor=None,
            profile=None,
            evidence=None,
            failure_code=(
                api.VisualEvidenceFailureCode.EVIDENCE_INVALID
            ),
        )

        self.assertIs(
            api.validate_visual_evidence_result(
                result
            ),
            result,
        )

    def test_source_dimensions_match_profile(self):
        invalid_features = dataclasses.replace(
            self.features,
            source_width=1,
        )

        invalid_evidence = dataclasses.replace(
            self.evidence,
            features=invalid_features,
            source_aspect_numerator=1,
            source_aspect_denominator=3,
        )

        result = dataclasses.replace(
            self.success_result(),
            evidence=invalid_evidence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^visual_evidence_result_invalid$",
        ):
            api.validate_visual_evidence_result(
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
                api.validate_visual_evidence_result(
                    variant
                ),
                result,
            )

    def test_invalid_result_shapes(self):
        result = self.success_result()

        class ResultSubclass(
            api.VisualEvidenceResult
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
                result.evidence,
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
                evidence=None,
            ),
            dataclasses.replace(
                result,
                failure_code=(
                    api.VisualEvidenceFailureCode.INTERNAL_FAILURE
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^visual_evidence_result_invalid$",
            ):
                api.validate_visual_evidence_result(
                    value
                )

    def test_public_api(self):
        self.assertEqual(
            api.VISUAL_EVIDENCE_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "VISUAL_EVIDENCE_SCHEMA_VERSION",
                "VisualEvidenceFailureCode",
                "VisualEvidenceMethod",
                "VisualEvidenceObservation",
                "VisualEvidenceOutcome",
                "VisualEvidenceResult",
                "validate_visual_evidence_observation",
                "validate_visual_evidence_result",
            ),
        )

        self.assertEqual(
            {
                code.value
                for code
                in api.VisualEvidenceFailureCode
            },
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "UPSTREAM_FEATURE_FAILED",
                "EVIDENCE_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )

        self.assertEqual(
            {
                method.value
                for method
                in api.VisualEvidenceMethod
            },
            {
                "DETERMINISTIC_RASTER_FEATURES_V1",
            },
        )


if __name__ == "__main__":
    unittest.main()