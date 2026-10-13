"""M85 deterministic semantic vision observation builder."""

import dataclasses
import unittest
from unittest.mock import patch

from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
)
from creator_studio.semantic_vision_observer import (
    SEMANTIC_VISION_SCHEMA_VERSION,
    SceneSetting,
    SemanticLabel,
    SemanticVisionMethod,
    SemanticVisionObservation,
    ShotScale,
    VisualMood,
    validate_semantic_vision_observation,
)
from creator_studio.semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
    SemanticVisionAdapterResponse,
)
from creator_studio.semantic_vision_observer.builder import (
    _SemanticBuildFailure,
    _build_semantic_observation,
)
from creator_studio.visual_evidence_observer import (
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
)


def feature_observation():
    return RasterFeatureObservation(
        source_width=4,
        source_height=3,
        width=2,
        height=2,
        pixel_count=4,
        mean_rgba=(
            55,
            65,
            75,
            255,
        ),
        min_rgba=(
            10,
            20,
            30,
            255,
        ),
        max_rgba=(
            100,
            110,
            120,
            255,
        ),
        mean_luma=65,
        min_luma=20,
        max_luma=110,
        alpha_zero_pixels=0,
        alpha_partial_pixels=0,
        alpha_opaque_pixels=4,
        luma_grid=bytes(
            [65] * 64
        ),
    )


def evidence():
    return VisualEvidenceObservation(
        schema_version=(
            VISUAL_EVIDENCE_SCHEMA_VERSION
        ),
        method=(
            VisualEvidenceMethod
            .DETERMINISTIC_RASTER_FEATURES_V1
        ),
        features=feature_observation(),
        source_aspect_numerator=4,
        source_aspect_denominator=3,
        sample_aspect_numerator=1,
        sample_aspect_denominator=1,
        luma_range=90,
        luma_grid_width=8,
        luma_grid_height=8,
    )


def response():
    return SemanticVisionAdapterResponse(
        schema_version=(
            SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ),
        scene_setting=(
            SceneSetting.INDOOR
        ),
        shot_scale=(
            ShotScale.MEDIUM
        ),
        visual_mood=(
            VisualMood.CALM
        ),
        subjects=(
            SemanticLabel(
                "person",
                950,
            ),
            SemanticLabel(
                "wooden table",
                700,
            ),
        ),
        activities=(
            SemanticLabel(
                "cooking",
                900,
            ),
        ),
        scene_tags=(
            SemanticLabel(
                "rural kitchen",
                850,
            ),
            SemanticLabel(
                "simple lifestyle",
                700,
            ),
        ),
        confidence_milli=900,
    )


class SemanticVisionBuilderTests(
    unittest.TestCase
):

    def build(
        self,
        evidence_value=None,
        response_value=None,
    ):
        if evidence_value is None:
            evidence_value = evidence()

        if response_value is None:
            response_value = response()

        return _build_semantic_observation(
            evidence_value,
            response_value,
            lambda: None,
        )

    def failure(
        self,
        evidence_value,
        response_value,
        expected,
    ):
        with self.assertRaises(
            _SemanticBuildFailure
        ) as caught:
            _build_semantic_observation(
                evidence_value,
                response_value,
                lambda: None,
            )

        self.assertEqual(
            caught.exception.code.value,
            expected,
        )

    def test_build_success(self):
        value = self.build()

        self.assertIs(
            type(value),
            SemanticVisionObservation,
        )

        self.assertIs(
            validate_semantic_vision_observation(
                value
            ),
            value,
        )

    def test_schema_and_method_are_exact(self):
        value = self.build()

        self.assertEqual(
            value.schema_version,
            SEMANTIC_VISION_SCHEMA_VERSION,
        )

        self.assertEqual(
            value.schema_version,
            1,
        )

        self.assertIs(
            value.method,
            SemanticVisionMethod
            .STRUCTURED_VISION_V1,
        )

    def test_evidence_identity_is_preserved(self):
        evidence_value = evidence()

        value = self.build(
            evidence_value=evidence_value
        )

        self.assertIs(
            value.evidence,
            evidence_value,
        )

    def test_response_fields_are_preserved(self):
        response_value = response()

        value = self.build(
            response_value=response_value
        )

        self.assertIs(
            value.scene_setting,
            response_value.scene_setting,
        )

        self.assertIs(
            value.shot_scale,
            response_value.shot_scale,
        )

        self.assertIs(
            value.visual_mood,
            response_value.visual_mood,
        )

        self.assertIs(
            value.subjects,
            response_value.subjects,
        )

        self.assertIs(
            value.activities,
            response_value.activities,
        )

        self.assertIs(
            value.scene_tags,
            response_value.scene_tags,
        )

        self.assertEqual(
            value.confidence_milli,
            response_value.confidence_milli,
        )

    def test_deterministic(self):
        evidence_value = evidence()
        response_value = response()

        first = self.build(
            evidence_value,
            response_value,
        )

        second = self.build(
            evidence_value,
            response_value,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_invalid_evidence_rejected(self):
        invalid = dataclasses.replace(
            evidence(),
            luma_range=1,
        )

        self.failure(
            invalid,
            response(),
            "UPSTREAM_EVIDENCE_FAILED",
        )

    def test_invalid_response_rejected(self):
        invalid = dataclasses.replace(
            response(),
            confidence_milli=1001,
        )

        self.failure(
            evidence(),
            invalid,
            "RESPONSE_INVALID",
        )

    def test_response_schema_rejected(self):
        invalid = dataclasses.replace(
            response(),
            schema_version=2,
        )

        self.failure(
            evidence(),
            invalid,
            "RESPONSE_INVALID",
        )

    def test_response_enum_rejected(self):
        invalid = dataclasses.replace(
            response(),
            scene_setting="INDOOR",
        )

        self.failure(
            evidence(),
            invalid,
            "RESPONSE_INVALID",
        )

    def test_response_label_order_rejected(self):
        invalid = dataclasses.replace(
            response(),
            subjects=(
                SemanticLabel(
                    "table",
                    700,
                ),
                SemanticLabel(
                    "person",
                    900,
                ),
            ),
        )

        self.failure(
            evidence(),
            invalid,
            "RESPONSE_INVALID",
        )

    def test_memory_failure_mapping(self):
        def failed_check():
            raise MemoryError()

        with self.assertRaises(
            _SemanticBuildFailure
        ) as caught:
            _build_semantic_observation(
                evidence(),
                response(),
                failed_check,
            )

        self.assertEqual(
            caught.exception.code.value,
            "RESOURCE_LIMIT_EXCEEDED",
        )

    def test_check_is_used(self):
        calls = [0]

        def check():
            calls[0] += 1

        value = _build_semantic_observation(
            evidence(),
            response(),
            check,
        )

        self.assertIs(
            type(value),
            SemanticVisionObservation,
        )

        self.assertGreaterEqual(
            calls[0],
            2,
        )

    def test_baseexception_is_not_swallowed(self):
        def interrupted():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            _build_semantic_observation(
                evidence(),
                response(),
                interrupted,
            )

    def test_unexpected_check_exception_is_not_reclassified(self):
        def failed_check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            _build_semantic_observation(
                evidence(),
                response(),
                failed_check,
            )

    def test_output_validation_failure_mapping(self):
        with patch(
            "creator_studio.semantic_vision_observer.builder."
            "validate_semantic_vision_observation",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _SemanticBuildFailure
            ) as caught:
                self.build()

        self.assertEqual(
            caught.exception.code.value,
            "RESPONSE_INVALID",
        )

    def test_empty_semantic_collections_are_preserved(self):
        response_value = dataclasses.replace(
            response(),
            subjects=(),
            activities=(),
            scene_tags=(),
        )

        value = self.build(
            response_value=response_value
        )

        self.assertEqual(
            value.subjects,
            (),
        )

        self.assertEqual(
            value.activities,
            (),
        )

        self.assertEqual(
            value.scene_tags,
            (),
        )


if __name__ == "__main__":
    unittest.main()