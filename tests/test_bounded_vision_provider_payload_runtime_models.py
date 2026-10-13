"""M86 detached authority-bound runtime result contract."""

import copy
import dataclasses
import pickle
import unittest

from creator_studio.bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    BoundedRasterSamplingMethod,
)
from creator_studio.bounded_vision_provider_payload.builder import (
    _build_payload,
)
from creator_studio.bounded_vision_provider_payload.runtime_models import (
    BoundedVisionProviderPayloadFailureCode,
    BoundedVisionProviderPayloadOutcome,
    BoundedVisionProviderPayloadResult,
    validate_bounded_vision_provider_payload_result,
)
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
        raise AssertionError(
            "hostile access"
        )

    def __repr__(self):
        raise AssertionError(
            "hostile repr"
        )

    def __eq__(self, other):
        raise AssertionError(
            "hostile equality"
        )


def raster():
    return BoundedRasterObservation(
        source_width=2,
        source_height=3,
        width=2,
        height=3,
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
            130, 140, 150, 255,
            160, 170, 180, 255,
        ]),
    )


def features():
    return RasterFeatureObservation(
        source_width=2,
        source_height=3,
        width=2,
        height=3,
        pixel_count=6,
        mean_rgba=(
            85,
            95,
            105,
            255,
        ),
        min_rgba=(
            10,
            20,
            30,
            255,
        ),
        max_rgba=(
            160,
            170,
            180,
            255,
        ),
        mean_luma=95,
        min_luma=20,
        max_luma=170,
        alpha_zero_pixels=0,
        alpha_partial_pixels=0,
        alpha_opaque_pixels=6,
        luma_grid=bytes(
            [95] * 64
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
        source_aspect_numerator=2,
        source_aspect_denominator=3,
        sample_aspect_numerator=2,
        sample_aspect_denominator=3,
        luma_range=150,
        luma_grid_width=8,
        luma_grid_height=8,
    )


def payload():
    return _build_payload(
        raster(),
        evidence(),
        lambda: None,
    )


class BoundedVisionProviderPayloadRuntimeModelTests(
    unittest.TestCase
):

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

    def tearDown(self):
        self.source.release(
            self.snapshot
        )

    def success_result(self):
        return BoundedVisionProviderPayloadResult(
            outcome=(
                BoundedVisionProviderPayloadOutcome.SUCCESS
            ),
            descriptor=self.descriptor,
            profile=self.profile,
            payload=payload(),
            failure_code=None,
        )

    def test_success_result(self):
        result = self.success_result()

        self.assertIs(
            validate_bounded_vision_provider_payload_result(
                result
            ),
            result,
        )

    def test_failure_result(self):
        result = BoundedVisionProviderPayloadResult(
            outcome=(
                BoundedVisionProviderPayloadOutcome.FAILURE
            ),
            descriptor=None,
            profile=None,
            payload=None,
            failure_code=(
                BoundedVisionProviderPayloadFailureCode
                .PAYLOAD_INVALID
            ),
        )

        self.assertIs(
            validate_bounded_vision_provider_payload_result(
                result
            ),
            result,
        )

    def test_frozen(self):
        result = self.success_result()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            result.payload = None

    def test_success_requires_descriptor(self):
        result = dataclasses.replace(
            self.success_result(),
            descriptor=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_result_invalid$",
        ):
            validate_bounded_vision_provider_payload_result(
                result
            )

    def test_success_requires_profile(self):
        result = dataclasses.replace(
            self.success_result(),
            profile=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_result_invalid$",
        ):
            validate_bounded_vision_provider_payload_result(
                result
            )

    def test_success_requires_payload(self):
        result = dataclasses.replace(
            self.success_result(),
            payload=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_result_invalid$",
        ):
            validate_bounded_vision_provider_payload_result(
                result
            )

    def test_success_rejects_failure_code(self):
        result = dataclasses.replace(
            self.success_result(),
            failure_code=(
                BoundedVisionProviderPayloadFailureCode
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_result_invalid$",
        ):
            validate_bounded_vision_provider_payload_result(
                result
            )

    def test_failure_requires_empty_success_fields(self):
        base = BoundedVisionProviderPayloadResult(
            outcome=(
                BoundedVisionProviderPayloadOutcome.FAILURE
            ),
            descriptor=None,
            profile=None,
            payload=None,
            failure_code=(
                BoundedVisionProviderPayloadFailureCode
                .INTERNAL_FAILURE
            ),
        )

        variants = [
            dataclasses.replace(
                base,
                descriptor=self.descriptor,
            ),
            dataclasses.replace(
                base,
                profile=self.profile,
            ),
            dataclasses.replace(
                base,
                payload=payload(),
            ),
            dataclasses.replace(
                base,
                failure_code=None,
            ),
            dataclasses.replace(
                base,
                failure_code="INTERNAL_FAILURE",
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_result_invalid$",
            ):
                validate_bounded_vision_provider_payload_result(
                    value
                )

    def test_source_dimensions_match_profile(self):
        changed_features = dataclasses.replace(
            features(),
            source_width=3,
        )

        changed_evidence = dataclasses.replace(
            evidence(),
            features=changed_features,
            source_aspect_numerator=1,
            source_aspect_denominator=1,
        )

        changed_raster = dataclasses.replace(
            raster(),
            source_width=3,
        )

        changed_payload = _build_payload(
            changed_raster,
            changed_evidence,
            lambda: None,
        )

        result = dataclasses.replace(
            self.success_result(),
            payload=changed_payload,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_result_invalid$",
        ):
            validate_bounded_vision_provider_payload_result(
                result
            )

    def test_exact_result_shape(self):
        base = self.success_result()

        class Subclass(
            BoundedVisionProviderPayloadResult
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
                "^bounded_vision_provider_payload_result_invalid$",
            ):
                validate_bounded_vision_provider_payload_result(
                    value
                )

    def test_detached_roundtrips(self):
        result = self.success_result()

        variants = [
            copy.copy(
                result
            ),
            copy.deepcopy(
                result
            ),
            pickle.loads(
                pickle.dumps(
                    result
                )
            ),
        ]

        for variant in variants:
            self.assertEqual(
                validate_bounded_vision_provider_payload_result(
                    variant
                ),
                result,
            )

    def test_failure_codes_are_stable(self):
        self.assertEqual(
            {
                code.value
                for code
                in BoundedVisionProviderPayloadFailureCode
            },
            {
                "SNAPSHOT_AUTHORITY_INVALID",
                "UPSTREAM_RASTER_FAILED",
                "UPSTREAM_EVIDENCE_FAILED",
                "COHERENCE_INVALID",
                "PAYLOAD_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()