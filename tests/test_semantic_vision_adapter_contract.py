"""M85 detached semantic vision adapter contract."""

import copy
import dataclasses
import pickle
import unittest

from creator_studio.bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    BoundedRasterSamplingMethod,
)
from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
)
from creator_studio.semantic_vision_observer import (
    SceneSetting,
    SemanticLabel,
    ShotScale,
    VisualMood,
)
from creator_studio.semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
    SemanticVisionAdapterRequest,
    SemanticVisionAdapterResponse,
    validate_semantic_vision_adapter_request,
    validate_semantic_vision_adapter_response,
)
from creator_studio.visual_evidence_observer import (
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
)


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError("hostile access")

    def __repr__(self):
        raise AssertionError("hostile repr")

    def __eq__(self, other):
        raise AssertionError("hostile equality")


def raster():
    return BoundedRasterObservation(
        source_width=4,
        source_height=3,
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
            10, 20, 30, 255,
            40, 50, 60, 255,
            70, 80, 90, 255,
            100, 110, 120, 255,
        ]),
    )


def features():
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
        features=features(),
        source_aspect_numerator=4,
        source_aspect_denominator=3,
        sample_aspect_numerator=1,
        sample_aspect_denominator=1,
        luma_range=90,
        luma_grid_width=8,
        luma_grid_height=8,
    )


def request():
    return SemanticVisionAdapterRequest(
        schema_version=(
            SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ),
        raster=raster(),
        evidence=evidence(),
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


class SemanticVisionAdapterContractTests(
    unittest.TestCase
):

    def test_valid_request(self):
        value = request()

        self.assertIs(
            validate_semantic_vision_adapter_request(
                value
            ),
            value,
        )

    def test_request_is_frozen(self):
        value = request()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.schema_version = 2

    def test_request_schema_version_contract(self):
        variants = [
            dataclasses.replace(
                request(),
                schema_version=0,
            ),
            dataclasses.replace(
                request(),
                schema_version=2,
            ),
            dataclasses.replace(
                request(),
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_adapter_request_invalid$",
            ):
                validate_semantic_vision_adapter_request(
                    value
                )

    def test_request_rejects_invalid_raster(self):
        invalid = dataclasses.replace(
            raster(),
            stride=7,
        )

        value = dataclasses.replace(
            request(),
            raster=invalid,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_adapter_request_invalid$",
        ):
            validate_semantic_vision_adapter_request(
                value
            )

    def test_request_rejects_invalid_evidence(self):
        invalid = dataclasses.replace(
            evidence(),
            luma_range=1,
        )

        value = dataclasses.replace(
            request(),
            evidence=invalid,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_adapter_request_invalid$",
        ):
            validate_semantic_vision_adapter_request(
                value
            )

    def test_request_source_dimensions_must_match(self):
        changed_raster = dataclasses.replace(
            raster(),
            source_width=3,
        )

        value = dataclasses.replace(
            request(),
            raster=changed_raster,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_adapter_request_invalid$",
        ):
            validate_semantic_vision_adapter_request(
                value
            )

    def test_request_sample_dimensions_must_match(self):
        changed_raster = dataclasses.replace(
            raster(),
            width=1,
            stride=4,
            pixels=bytes([
                10, 20, 30, 255,
                70, 80, 90, 255,
            ]),
        )

        value = dataclasses.replace(
            request(),
            raster=changed_raster,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_adapter_request_invalid$",
        ):
            validate_semantic_vision_adapter_request(
                value
            )

    def test_request_exact_shape(self):
        base = request()

        class Subclass(
            SemanticVisionAdapterRequest
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        forged = copy.copy(
            base
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
                "^semantic_vision_adapter_request_invalid$",
            ):
                validate_semantic_vision_adapter_request(
                    value
                )

    def test_valid_response(self):
        value = response()

        self.assertIs(
            validate_semantic_vision_adapter_response(
                value
            ),
            value,
        )

    def test_response_schema_and_enum_contract(self):
        variants = [
            dataclasses.replace(
                response(),
                schema_version=2,
            ),
            dataclasses.replace(
                response(),
                schema_version=True,
            ),
            dataclasses.replace(
                response(),
                scene_setting="INDOOR",
            ),
            dataclasses.replace(
                response(),
                shot_scale="MEDIUM",
            ),
            dataclasses.replace(
                response(),
                visual_mood="CALM",
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_adapter_response_invalid$",
            ):
                validate_semantic_vision_adapter_response(
                    value
                )

    def test_response_label_collection_contract(self):
        too_many = tuple(
            SemanticLabel(
                f"tag {index}",
                900 - index,
            )
            for index in range(9)
        )

        variants = [
            dataclasses.replace(
                response(),
                subjects=list(
                    response().subjects
                ),
            ),
            dataclasses.replace(
                response(),
                subjects=(
                    SemanticLabel(
                        "person",
                        900,
                    ),
                    SemanticLabel(
                        "person",
                        800,
                    ),
                ),
            ),
            dataclasses.replace(
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
            ),
            dataclasses.replace(
                response(),
                scene_tags=too_many,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_adapter_response_invalid$",
            ):
                validate_semantic_vision_adapter_response(
                    value
                )

    def test_response_empty_collections_are_allowed(self):
        value = dataclasses.replace(
            response(),
            subjects=(),
            activities=(),
            scene_tags=(),
        )

        self.assertIs(
            validate_semantic_vision_adapter_response(
                value
            ),
            value,
        )

    def test_response_confidence_contract(self):
        variants = [
            dataclasses.replace(
                response(),
                confidence_milli=-1,
            ),
            dataclasses.replace(
                response(),
                confidence_milli=1001,
            ),
            dataclasses.replace(
                response(),
                confidence_milli=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^semantic_vision_adapter_response_invalid$",
            ):
                validate_semantic_vision_adapter_response(
                    value
                )

    def test_response_exact_shape(self):
        base = response()

        class Subclass(
            SemanticVisionAdapterResponse
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        forged = copy.copy(
            base
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
                "^semantic_vision_adapter_response_invalid$",
            ):
                validate_semantic_vision_adapter_response(
                    value
                )

    def test_detached_roundtrips(self):
        values = [
            request(),
            response(),
        ]

        validators = [
            validate_semantic_vision_adapter_request,
            validate_semantic_vision_adapter_response,
        ]

        for value, validator in zip(
            values,
            validators,
        ):
            variants = [
                copy.copy(value),
                copy.deepcopy(value),
                pickle.loads(
                    pickle.dumps(value)
                ),
            ]

            for variant in variants:
                self.assertEqual(
                    validator(
                        variant
                    ),
                    value,
                )

    def test_contract_version(self):
        self.assertEqual(
            SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
            1,
        )


if __name__ == "__main__":
    unittest.main()