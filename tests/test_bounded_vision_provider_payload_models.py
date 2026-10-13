"""M86 bounded vision provider payload model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.bounded_vision_provider_payload as api

from creator_studio.raster_feature_observer import (
    RasterFeatureObservation,
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


def image_bytes():
    return (
        api.PNG_SIGNATURE
        + b"deterministic-test-payload"
    )


def payload():
    data = image_bytes()

    return api.BoundedVisionProviderPayload(
        schema_version=(
            api.VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION
        ),
        encoding=(
            api.VisionProviderPayloadEncoding.PNG_RGBA8
        ),
        width=2,
        height=2,
        byte_length=len(data),
        image_bytes=data,
        evidence=evidence(),
    )


class BoundedVisionProviderPayloadModelTests(
    unittest.TestCase
):

    def test_valid_payload(self):
        value = payload()

        self.assertIs(
            api.validate_bounded_vision_provider_payload(
                value
            ),
            value,
        )

    def test_frozen(self):
        value = payload()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.width = 1

    def test_schema_version_contract(self):
        variants = [
            dataclasses.replace(
                payload(),
                schema_version=0,
            ),
            dataclasses.replace(
                payload(),
                schema_version=2,
            ),
            dataclasses.replace(
                payload(),
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_encoding_requires_exact_enum(self):
        value = dataclasses.replace(
            payload(),
            encoding="PNG_RGBA8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_dimensions_must_be_positive_integers(self):
        variants = [
            dataclasses.replace(
                payload(),
                width=0,
            ),
            dataclasses.replace(
                payload(),
                width=-1,
            ),
            dataclasses.replace(
                payload(),
                width=True,
            ),
            dataclasses.replace(
                payload(),
                height=0,
            ),
            dataclasses.replace(
                payload(),
                height=-1,
            ),
            dataclasses.replace(
                payload(),
                height=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_dimensions_are_bounded(self):
        variants = [
            dataclasses.replace(
                payload(),
                width=1025,
            ),
            dataclasses.replace(
                payload(),
                height=1025,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_pixel_count_is_bounded(self):
        changed_features = dataclasses.replace(
            features(),
            source_width=1024,
            source_height=1024,
            width=1024,
            height=1024,
            pixel_count=1024 * 1024,
            alpha_opaque_pixels=1024 * 1024,
        )

        changed_evidence = dataclasses.replace(
            evidence(),
            features=changed_features,
            source_aspect_numerator=1,
            source_aspect_denominator=1,
            sample_aspect_numerator=1,
            sample_aspect_denominator=1,
        )

        value = dataclasses.replace(
            payload(),
            width=1024,
            height=1024,
            evidence=changed_evidence,
        )

        self.assertIs(
            api.validate_bounded_vision_provider_payload(
                value
            ),
            value,
        )

    def test_byte_length_requires_exact_integer(self):
        variants = [
            dataclasses.replace(
                payload(),
                byte_length=0,
            ),
            dataclasses.replace(
                payload(),
                byte_length=-1,
            ),
            dataclasses.replace(
                payload(),
                byte_length=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_byte_length_must_match_bytes(self):
        value = dataclasses.replace(
            payload(),
            byte_length=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_image_bytes_requires_exact_bytes(self):
        value = dataclasses.replace(
            payload(),
            image_bytes=bytearray(
                image_bytes()
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_png_signature_required(self):
        data = (
            b"NOTPNG!!"
            + b"deterministic-test-payload"
        )

        value = dataclasses.replace(
            payload(),
            image_bytes=data,
            byte_length=len(data),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_image_byte_bound(self):
        data = (
            api.PNG_SIGNATURE
            + bytes(
                api.MAX_VISION_PROVIDER_IMAGE_BYTES
            )
        )

        value = dataclasses.replace(
            payload(),
            image_bytes=data,
            byte_length=len(data),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_invalid_evidence_rejected(self):
        invalid_evidence = dataclasses.replace(
            evidence(),
            luma_range=1,
        )

        value = dataclasses.replace(
            payload(),
            evidence=invalid_evidence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_sample_dimensions_match_evidence(self):
        variants = [
            dataclasses.replace(
                payload(),
                width=1,
            ),
            dataclasses.replace(
                payload(),
                height=1,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_pixel_count_matches_evidence(self):
        changed_features = dataclasses.replace(
            features(),
            pixel_count=3,
        )

        changed_evidence = dataclasses.replace(
            evidence(),
            features=changed_features,
        )

        value = dataclasses.replace(
            payload(),
            evidence=changed_evidence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^bounded_vision_provider_payload_invalid$",
        ):
            api.validate_bounded_vision_provider_payload(
                value
            )

    def test_exact_payload_shape(self):
        base = payload()

        class Subclass(
            api.BoundedVisionProviderPayload
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
                "^bounded_vision_provider_payload_invalid$",
            ):
                api.validate_bounded_vision_provider_payload(
                    value
                )

    def test_detached_roundtrips(self):
        value = payload()

        variants = [
            copy.copy(value),
            copy.deepcopy(value),
            pickle.loads(
                pickle.dumps(value)
            ),
        ]

        for variant in variants:
            self.assertEqual(
                api.validate_bounded_vision_provider_payload(
                    variant
                ),
                value,
            )

    def test_public_api(self):
        self.assertEqual(
            api.VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_VISION_PROVIDER_IMAGE_BYTES,
            6 * 1024 * 1024,
        )

        self.assertEqual(
            api.PNG_SIGNATURE,
            b"\x89PNG\r\n\x1a\n",
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_VISION_PROVIDER_IMAGE_BYTES",
                "PNG_SIGNATURE",
                "VISION_PROVIDER_PAYLOAD_SCHEMA_VERSION",
                "BoundedVisionProviderPayload",
                "VisionProviderPayloadEncoding",
                "validate_bounded_vision_provider_payload",
                "BoundedVisionProviderPayloadFailureCode",
                "BoundedVisionProviderPayloadOutcome",
                "BoundedVisionProviderPayloadResult",
                "validate_bounded_vision_provider_payload_result",
                "BoundedVisionProviderPayloadRuntime",
            ),
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.VisionProviderPayloadEncoding
            },
            {
                "PNG_RGBA8",
            },
        )


if __name__ == "__main__":
    unittest.main()