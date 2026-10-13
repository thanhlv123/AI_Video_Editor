"""M86 deterministic bounded vision provider payload builder."""

import dataclasses
import unittest
from unittest.mock import patch

from creator_studio.bounded_raster_sampling import (
    BoundedRasterObservation,
    BoundedRasterPixelFormat,
    BoundedRasterSamplingMethod,
)
import creator_studio.bounded_vision_provider_payload.builder as builder_module
from creator_studio.bounded_vision_provider_payload.builder import (
    _PayloadBuildFailure,
    _PayloadBuildFailureCode,
    _build_payload,
)
from creator_studio.bounded_vision_provider_payload.encoder import (
    _PNGEncodingFailure,
    _PNGEncodingFailureCode,
)
from creator_studio.bounded_vision_provider_payload import (
    PNG_SIGNATURE,
    VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION,
    BoundedVisionProviderPayload,
    VisionProviderPayloadEncoding,
    validate_bounded_vision_provider_payload,
)
from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
)
from creator_studio.visual_evidence_observer import (
    VISUAL_EVIDENCE_SCHEMA_VERSION,
    VisualEvidenceMethod,
    VisualEvidenceObservation,
)


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
            10, 20, 30, 0,
            40, 50, 60, 128,
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
            159,
        ),
        min_rgba=(
            10,
            20,
            30,
            0,
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
        alpha_zero_pixels=1,
        alpha_partial_pixels=1,
        alpha_opaque_pixels=2,
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


class BoundedVisionProviderPayloadBuilderTests(
    unittest.TestCase
):

    def build(
        self,
        raster_value=None,
        evidence_value=None,
        check=None,
    ):
        if raster_value is None:
            raster_value = raster()

        if evidence_value is None:
            evidence_value = evidence()

        if check is None:
            check = lambda: None

        return _build_payload(
            raster_value,
            evidence_value,
            check,
        )

    def failure(
        self,
        raster_value,
        evidence_value,
        expected,
    ):
        with self.assertRaises(
            _PayloadBuildFailure
        ) as caught:
            _build_payload(
                raster_value,
                evidence_value,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_build_success(self):
        value = self.build()

        self.assertIs(
            type(value),
            BoundedVisionProviderPayload,
        )

        self.assertIs(
            validate_bounded_vision_provider_payload(
                value
            ),
            value,
        )

    def test_schema_and_encoding_are_exact(self):
        value = self.build()

        self.assertEqual(
            value.schema_version,
            VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION,
        )

        self.assertEqual(
            value.schema_version,
            1,
        )

        self.assertIs(
            value.encoding,
            VisionProviderPayloadEncoding.PNG_RGBA8,
        )

    def test_dimensions_are_preserved(self):
        value = self.build()

        self.assertEqual(
            value.width,
            2,
        )

        self.assertEqual(
            value.height,
            2,
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

    def test_real_png_bytes_are_created(self):
        value = self.build()

        self.assertIs(
            type(value.image_bytes),
            bytes,
        )

        self.assertTrue(
            value.image_bytes.startswith(
                PNG_SIGNATURE
            )
        )

        self.assertEqual(
            value.byte_length,
            len(
                value.image_bytes
            ),
        )

    def test_deterministic(self):
        raster_value = raster()
        evidence_value = evidence()

        first = self.build(
            raster_value,
            evidence_value,
        )

        second = self.build(
            raster_value,
            evidence_value,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_invalid_raster_rejected(self):
        invalid = dataclasses.replace(
            raster(),
            stride=7,
        )

        self.failure(
            invalid,
            evidence(),
            _PayloadBuildFailureCode.RASTER_INVALID,
        )

    def test_invalid_evidence_rejected(self):
        invalid = dataclasses.replace(
            evidence(),
            luma_range=1,
        )

        self.failure(
            raster(),
            invalid,
            _PayloadBuildFailureCode.EVIDENCE_INVALID,
        )

    def test_source_width_mismatch_rejected(self):
        changed_features = dataclasses.replace(
            features(),
            source_width=5,
        )

        changed_evidence = dataclasses.replace(
            evidence(),
            features=changed_features,
            source_aspect_numerator=5,
            source_aspect_denominator=3,
        )

        self.failure(
            raster(),
            changed_evidence,
            _PayloadBuildFailureCode.COHERENCE_INVALID,
        )

    def test_source_height_mismatch_rejected(self):
        changed_features = dataclasses.replace(
            features(),
            source_height=5,
        )

        changed_evidence = dataclasses.replace(
            evidence(),
            features=changed_features,
            source_aspect_numerator=4,
            source_aspect_denominator=5,
        )

        self.failure(
            raster(),
            changed_evidence,
            _PayloadBuildFailureCode.COHERENCE_INVALID,
        )

    def test_sample_width_mismatch_rejected(self):
        changed_raster = dataclasses.replace(
            raster(),
            width=1,
            stride=4,
            pixels=bytes([
                10, 20, 30, 0,
                70, 80, 90, 255,
            ]),
        )

        self.failure(
            changed_raster,
            evidence(),
            _PayloadBuildFailureCode.COHERENCE_INVALID,
        )

    def test_sample_height_mismatch_rejected(self):
        changed_raster = dataclasses.replace(
            raster(),
            height=1,
            pixels=bytes([
                10, 20, 30, 0,
                40, 50, 60, 128,
            ]),
        )

        self.failure(
            changed_raster,
            evidence(),
            _PayloadBuildFailureCode.COHERENCE_INVALID,
        )

    def test_encoder_resource_failure_mapping(self):
        with patch.object(
            builder_module,
            "_encode_png_rgba8",
            side_effect=_PNGEncodingFailure(
                _PNGEncodingFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ),
        ):
            with self.assertRaises(
                _PayloadBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _PayloadBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_encoder_input_failure_mapping(self):
        with patch.object(
            builder_module,
            "_encode_png_rgba8",
            side_effect=_PNGEncodingFailure(
                _PNGEncodingFailureCode
                .INPUT_INVALID
            ),
        ):
            with self.assertRaises(
                _PayloadBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _PayloadBuildFailureCode.RASTER_INVALID,
        )

    def test_output_validation_failure_mapping(self):
        with patch.object(
            builder_module,
            "validate_bounded_vision_provider_payload",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _PayloadBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _PayloadBuildFailureCode.PAYLOAD_INVALID,
        )

    def test_memory_error_mapping(self):
        with patch.object(
            builder_module,
            "validate_bounded_raster_observation",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _PayloadBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _PayloadBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_check_is_used_repeatedly(self):
        calls = [0]

        def check():
            calls[0] += 1

        value = self.build(
            check=check
        )

        self.assertIs(
            type(value),
            BoundedVisionProviderPayload,
        )

        self.assertGreaterEqual(
            calls[0],
            8,
        )

    def test_unexpected_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            self.build(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.build(
                check=check
            )


if __name__ == "__main__":
    unittest.main()