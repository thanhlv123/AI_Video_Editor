"""M85 detached structured semantic vision model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.semantic_vision_observer as api

from creator_studio.png8_observer import (
    PNG8PreflightOutcome,
    PNG8PreflightRuntime,
)
from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
)
from creator_studio.visual_evidence_observer import (
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
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


class SemanticVisionModelTests(unittest.TestCase):

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
            mean_rgba=(100, 110, 120, 255),
            min_rgba=(10, 20, 30, 255),
            max_rgba=(200, 210, 220, 255),
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

        self.evidence = VisualEvidenceObservation(
            schema_version=(
                VISUAL_EVIDENCE_SCHEMA_VERSION
            ),
            method=(
                VisualEvidenceMethod
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

        self.subjects = (
            api.SemanticLabel(
                "person",
                950,
            ),
            api.SemanticLabel(
                "wooden table",
                700,
            ),
        )

        self.activities = (
            api.SemanticLabel(
                "cooking",
                900,
            ),
        )

        self.scene_tags = (
            api.SemanticLabel(
                "rural kitchen",
                850,
            ),
            api.SemanticLabel(
                "simple lifestyle",
                700,
            ),
        )

        self.observation = api.SemanticVisionObservation(
            schema_version=(
                api.SEMANTIC_VISION_SCHEMA_VERSION
            ),
            method=(
                api.SemanticVisionMethod
                .STRUCTURED_VISION_V1
            ),
            evidence=self.evidence,
            scene_setting=(
                api.SceneSetting.INDOOR
            ),
            shot_scale=(
                api.ShotScale.MEDIUM
            ),
            visual_mood=(
                api.VisualMood.CALM
            ),
            subjects=self.subjects,
            activities=self.activities,
            scene_tags=self.scene_tags,
            confidence_milli=900,
        )

    def tearDown(self):
        self.source.release(
            self.snapshot
        )

    def success_result(self):
        return api.SemanticVisionResult(
            outcome=api.SemanticVisionOutcome.SUCCESS,
            descriptor=self.descriptor,
            profile=self.profile,
            observation=self.observation,
            failure_code=None,
        )

    def test_valid_label(self):
        label = api.SemanticLabel(
            "person",
            900,
        )

        self.assertIs(
            api.validate_semantic_label(
                label
            ),
            label,
        )

    def test_invalid_label_text(self):
        variants = [
            api.SemanticLabel(
                "",
                900,
            ),
            api.SemanticLabel(
                " Person",
                900,
            ),
            api.SemanticLabel(
                "Person",
                900,
            ),
            api.SemanticLabel(
                "person!",
                900,
            ),
            api.SemanticLabel(
                "person  cooking",
                900,
            ),
            api.SemanticLabel(
                "x" * 65,
                900,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_label_invalid$",
            ):
                api.validate_semantic_label(
                    value
                )

    def test_invalid_label_confidence(self):
        variants = [
            api.SemanticLabel(
                "person",
                -1,
            ),
            api.SemanticLabel(
                "person",
                1001,
            ),
            api.SemanticLabel(
                "person",
                True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_label_invalid$",
            ):
                api.validate_semantic_label(
                    value
                )

    def test_valid_observation(self):
        self.assertIs(
            api.validate_semantic_vision_observation(
                self.observation
            ),
            self.observation,
        )

    def test_frozen(self):
        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            self.observation.confidence_milli = 1

    def test_schema_and_method_contract(self):
        variants = [
            dataclasses.replace(
                self.observation,
                schema_version=2,
            ),
            dataclasses.replace(
                self.observation,
                schema_version=True,
            ),
            dataclasses.replace(
                self.observation,
                method="STRUCTURED_VISION_V1",
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_observation_invalid$",
            ):
                api.validate_semantic_vision_observation(
                    value
                )

    def test_enum_contract(self):
        variants = [
            dataclasses.replace(
                self.observation,
                scene_setting="INDOOR",
            ),
            dataclasses.replace(
                self.observation,
                shot_scale="MEDIUM",
            ),
            dataclasses.replace(
                self.observation,
                visual_mood="CALM",
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_observation_invalid$",
            ):
                api.validate_semantic_vision_observation(
                    value
                )

    def test_label_collection_requires_tuple(self):
        value = dataclasses.replace(
            self.observation,
            subjects=list(
                self.subjects
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                value
            )

    def test_label_collection_maximum(self):
        labels = tuple(
            api.SemanticLabel(
                f"tag {index}",
                900 - index,
            )
            for index in range(9)
        )

        value = dataclasses.replace(
            self.observation,
            scene_tags=labels,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                value
            )

    def test_duplicate_labels_rejected(self):
        value = dataclasses.replace(
            self.observation,
            subjects=(
                api.SemanticLabel(
                    "person",
                    900,
                ),
                api.SemanticLabel(
                    "person",
                    800,
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                value
            )

    def test_labels_must_be_canonically_ordered(self):
        value = dataclasses.replace(
            self.observation,
            subjects=(
                api.SemanticLabel(
                    "table",
                    700,
                ),
                api.SemanticLabel(
                    "person",
                    900,
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                value
            )

    def test_equal_confidence_uses_label_order(self):
        valid = dataclasses.replace(
            self.observation,
            subjects=(
                api.SemanticLabel(
                    "person",
                    900,
                ),
                api.SemanticLabel(
                    "table",
                    900,
                ),
            ),
        )

        self.assertIs(
            api.validate_semantic_vision_observation(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            self.observation,
            subjects=(
                api.SemanticLabel(
                    "table",
                    900,
                ),
                api.SemanticLabel(
                    "person",
                    900,
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                invalid
            )

    def test_empty_label_collections_are_allowed(self):
        value = dataclasses.replace(
            self.observation,
            subjects=(),
            activities=(),
            scene_tags=(),
        )

        self.assertIs(
            api.validate_semantic_vision_observation(
                value
            ),
            value,
        )

    def test_overall_confidence_contract(self):
        variants = [
            dataclasses.replace(
                self.observation,
                confidence_milli=-1,
            ),
            dataclasses.replace(
                self.observation,
                confidence_milli=1001,
            ),
            dataclasses.replace(
                self.observation,
                confidence_milli=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_observation_invalid$",
            ):
                api.validate_semantic_vision_observation(
                    value
                )

    def test_evidence_contract(self):
        invalid_evidence = dataclasses.replace(
            self.evidence,
            luma_range=1,
        )

        value = dataclasses.replace(
            self.observation,
            evidence=invalid_evidence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_observation_invalid$",
        ):
            api.validate_semantic_vision_observation(
                value
            )

    def test_exact_observation_shape(self):
        class Subclass(
            api.SemanticVisionObservation
        ):
            pass

        subclass = Subclass(
            **self.observation.__dict__
        )

        forged = copy.copy(
            self.observation
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
                "^semantic_vision_observation_invalid$",
            ):
                api.validate_semantic_vision_observation(
                    value
                )

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            api.validate_semantic_vision_result(
                result
            ),
            result,
        )

    def test_failure_result(self):
        result = api.SemanticVisionResult(
            outcome=api.SemanticVisionOutcome.FAILURE,
            descriptor=None,
            profile=None,
            observation=None,
            failure_code=(
                api.SemanticVisionFailureCode.RESPONSE_INVALID
            ),
        )

        self.assertIs(
            api.validate_semantic_vision_result(
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

        invalid_observation = dataclasses.replace(
            self.observation,
            evidence=invalid_evidence,
        )

        result = dataclasses.replace(
            self.success_result(),
            observation=invalid_observation,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_result_invalid$",
        ):
            api.validate_semantic_vision_result(
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
                api.validate_semantic_vision_result(
                    variant
                ),
                result,
            )

    def test_invalid_result_shapes(self):
        result = self.success_result()

        class ResultSubclass(
            api.SemanticVisionResult
        ):
            pass

        forged = copy.copy(
            result
        )

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
                result.observation,
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
                observation=None,
            ),
            dataclasses.replace(
                result,
                failure_code=(
                    api.SemanticVisionFailureCode.INTERNAL_FAILURE
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_result_invalid$",
            ):
                api.validate_semantic_vision_result(
                    value
                )

    def test_public_api(self):
        self.assertEqual(
            api.SEMANTIC_VISION_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_SEMANTIC_LABELS,
            8,
        )

        self.assertEqual(
            api.MAX_SEMANTIC_LABEL_LENGTH,
            64,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_SEMANTIC_LABEL_LENGTH",
                "MAX_SEMANTIC_LABELS",
                "SEMANTIC_VISION_SCHEMA_VERSION",
                "SceneSetting",
                "SemanticLabel",
                "SemanticVisionFailureCode",
                "SemanticVisionMethod",
                "SemanticVisionObservation",
                "SemanticVisionOutcome",
                "SemanticVisionResult",
                "ShotScale",
                "VisualMood",
                "validate_semantic_label",
                "validate_semantic_vision_observation",
                "validate_semantic_vision_result",
            ),
        )

        self.assertEqual(
            {
                code.value
                for code
                in api.SemanticVisionFailureCode
            },
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "UPSTREAM_EVIDENCE_FAILED",
                "ADAPTER_UNAVAILABLE",
                "RESPONSE_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()