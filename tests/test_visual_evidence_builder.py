"""M84 deterministic visual evidence builder."""

import dataclasses
import unittest
from unittest.mock import patch

from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
)
from creator_studio.visual_evidence_observer import (
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
    validate_visual_evidence_observation,
)
from creator_studio.visual_evidence_observer.builder import (
    _EvidenceFailure,
    _build,
    _reduced_aspect,
)


def feature_observation():
    return RasterFeatureObservation(
        source_width=1920,
        source_height=1080,
        width=640,
        height=360,
        pixel_count=230400,
        mean_rgba=(
            100,
            110,
            120,
            200,
        ),
        min_rgba=(
            0,
            10,
            20,
            0,
        ),
        max_rgba=(
            255,
            210,
            220,
            255,
        ),
        mean_luma=110,
        min_luma=20,
        max_luma=210,
        alpha_zero_pixels=10,
        alpha_partial_pixels=20,
        alpha_opaque_pixels=230370,
        luma_grid=bytes(
            [110] * 64
        ),
    )


class VisualEvidenceBuilderTests(unittest.TestCase):

    def build(self, features):
        return _build(
            features,
            lambda: None,
        )

    def failure(
        self,
        features,
        expected="EVIDENCE_INVALID",
    ):
        with self.assertRaises(
            _EvidenceFailure
        ) as caught:
            self.build(features)

        self.assertEqual(
            caught.exception.code.value,
            expected,
        )

    def test_reduced_aspect_known_values(self):
        self.assertEqual(
            _reduced_aspect(
                1920,
                1080,
            ),
            (
                16,
                9,
            ),
        )

        self.assertEqual(
            _reduced_aspect(
                1024,
                244,
            ),
            (
                256,
                61,
            ),
        )

        self.assertEqual(
            _reduced_aspect(
                1,
                4096,
            ),
            (
                1,
                4096,
            ),
        )

    def test_build_success(self):
        features = feature_observation()

        evidence = self.build(
            features
        )

        self.assertIs(
            type(evidence),
            VisualEvidenceObservation,
        )

        self.assertIs(
            validate_visual_evidence_observation(
                evidence
            ),
            evidence,
        )

    def test_features_identity_is_preserved(self):
        features = feature_observation()

        evidence = self.build(
            features
        )

        self.assertIs(
            evidence.features,
            features,
        )

    def test_schema_and_method_are_exact(self):
        evidence = self.build(
            feature_observation()
        )

        self.assertEqual(
            evidence.schema_version,
            VISUAL_EVIDENCE_SCHEMA_VERSION,
        )

        self.assertEqual(
            evidence.schema_version,
            1,
        )

        self.assertIs(
            evidence.method,
            VisualEvidenceMethod
            .DETERMINISTIC_RASTER_FEATURES_V1,
        )

    def test_exact_source_and_sample_aspects(self):
        evidence = self.build(
            feature_observation()
        )

        self.assertEqual(
            (
                evidence.source_aspect_numerator,
                evidence.source_aspect_denominator,
            ),
            (
                16,
                9,
            ),
        )

        self.assertEqual(
            (
                evidence.sample_aspect_numerator,
                evidence.sample_aspect_denominator,
            ),
            (
                16,
                9,
            ),
        )

    def test_source_and_sample_aspects_may_differ(self):
        features = dataclasses.replace(
            feature_observation(),
            source_width=2000,
            source_height=1001,
            width=1024,
            height=512,
            pixel_count=524288,
            alpha_opaque_pixels=524258,
        )

        evidence = self.build(
            features
        )

        self.assertEqual(
            (
                evidence.source_aspect_numerator,
                evidence.source_aspect_denominator,
            ),
            (
                2000,
                1001,
            ),
        )

        self.assertEqual(
            (
                evidence.sample_aspect_numerator,
                evidence.sample_aspect_denominator,
            ),
            (
                2,
                1,
            ),
        )

    def test_luma_range_and_grid_metadata(self):
        evidence = self.build(
            feature_observation()
        )

        self.assertEqual(
            evidence.luma_range,
            190,
        )

        self.assertEqual(
            evidence.luma_grid_width,
            8,
        )

        self.assertEqual(
            evidence.luma_grid_height,
            8,
        )

        self.assertEqual(
            len(evidence.features.luma_grid),
            (
                evidence.luma_grid_width
                * evidence.luma_grid_height
            ),
        )

    def test_deterministic(self):
        features = feature_observation()

        first = self.build(
            features
        )

        second = self.build(
            features
        )

        self.assertEqual(
            first,
            second,
        )

    def test_invalid_features_rejected(self):
        features = feature_observation()

        class FeatureSubclass(
            RasterFeatureObservation
        ):
            pass

        subclass = FeatureSubclass(
            **features.__dict__
        )

        variants = [
            object(),
            subclass,
            dataclasses.replace(
                features,
                pixel_count=1,
            ),
            dataclasses.replace(
                features,
                width=True,
            ),
            dataclasses.replace(
                features,
                luma_grid=bytes(63),
            ),
        ]

        for value in variants:
            with self.subTest(
                value=type(value)
            ):
                self.failure(value)

    def test_invalid_reduced_aspect_inputs(self):
        cases = [
            (
                0,
                1,
            ),
            (
                1,
                0,
            ),
            (
                -1,
                1,
            ),
            (
                1,
                -1,
            ),
            (
                True,
                1,
            ),
            (
                1,
                True,
            ),
        ]

        for width, height in cases:
            with self.subTest(
                width=width,
                height=height,
            ):
                with self.assertRaises(
                    _EvidenceFailure
                ) as caught:
                    _reduced_aspect(
                        width,
                        height,
                    )

                self.assertEqual(
                    caught.exception.code.value,
                    "EVIDENCE_INVALID",
                )

    def test_memory_failure_mapping(self):
        features = feature_observation()

        def failed_check():
            raise MemoryError()

        with self.assertRaises(
            _EvidenceFailure
        ) as caught:
            _build(
                features,
                failed_check,
            )

        self.assertEqual(
            caught.exception.code.value,
            "RESOURCE_LIMIT_EXCEEDED",
        )

    def test_check_is_used_during_build(self):
        features = feature_observation()

        calls = [0]

        def check():
            calls[0] += 1

        evidence = _build(
            features,
            check,
        )

        self.assertIs(
            type(evidence),
            VisualEvidenceObservation,
        )

        self.assertGreaterEqual(
            calls[0],
            3,
        )

    def test_baseexception_is_not_swallowed(self):
        features = feature_observation()

        def interrupted():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            _build(
                features,
                interrupted,
            )

    def test_unexpected_check_exception_is_not_reclassified(self):
        features = feature_observation()

        def failed_check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            _build(
                features,
                failed_check,
            )

    def test_output_validation_failure_mapping(self):
        features = feature_observation()

        with patch(
            "creator_studio.visual_evidence_observer.builder."
            "validate_visual_evidence_observation",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _EvidenceFailure
            ) as caught:
                self.build(
                    features
                )

        self.assertEqual(
            caught.exception.code.value,
            "EVIDENCE_INVALID",
        )


if __name__ == "__main__":
    unittest.main()