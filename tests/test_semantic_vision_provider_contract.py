"""M85 semantic vision provider interface contract."""

import inspect
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
)
from creator_studio.semantic_vision_observer.provider_contract import (
    SemanticVisionProvider,
    SemanticVisionProviderFailure,
    SemanticVisionProviderFailureCode,
    _invoke_provider,
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
        ),
        confidence_milli=900,
    )


class ValidProvider(
    SemanticVisionProvider
):
    def __init__(self):
        self.requests = []
        self.checks = []

    def observe(self, request_value, check):
        self.requests.append(
            request_value
        )

        self.checks.append(
            check
        )

        check()

        return response()


class UnavailableProvider(
    SemanticVisionProvider
):
    def observe(self, request_value, check):
        raise SemanticVisionProviderFailure(
            SemanticVisionProviderFailureCode.UNAVAILABLE
        )


class InvalidResponseProvider(
    SemanticVisionProvider
):
    def observe(self, request_value, check):
        return object()


class MemoryProvider(
    SemanticVisionProvider
):
    def observe(self, request_value, check):
        raise MemoryError()


class ErrorProvider(
    SemanticVisionProvider
):
    def observe(self, request_value, check):
        raise RuntimeError(
            "private"
        )


class InterruptProvider(
    SemanticVisionProvider
):
    def observe(self, request_value, check):
        raise KeyboardInterrupt()


class SemanticVisionProviderContractTests(
    unittest.TestCase
):

    def test_base_provider_is_abstract(self):
        with self.assertRaises(
            TypeError
        ):
            SemanticVisionProvider()

    def test_provider_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    SemanticVisionProvider.observe
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
            ),
        )

    def test_success(self):
        provider = ValidProvider()

        result = _invoke_provider(
            provider,
            request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            SemanticVisionAdapterResponse,
        )

        self.assertEqual(
            result,
            response(),
        )

    def test_provider_receives_request_identity(self):
        provider = ValidProvider()
        value = request()

        _invoke_provider(
            provider,
            value,
            lambda: None,
        )

        self.assertEqual(
            len(provider.requests),
            1,
        )

        self.assertIs(
            provider.requests[0],
            value,
        )

    def test_provider_receives_check_identity(self):
        provider = ValidProvider()

        def check():
            pass

        _invoke_provider(
            provider,
            request(),
            check,
        )

        self.assertEqual(
            len(provider.checks),
            1,
        )

        self.assertIs(
            provider.checks[0],
            check,
        )

    def test_check_is_used_before_during_and_after(self):
        provider = ValidProvider()
        calls = [0]

        def check():
            calls[0] += 1

        _invoke_provider(
            provider,
            request(),
            check,
        )

        self.assertGreaterEqual(
            calls[0],
            3,
        )

    def test_invalid_provider_is_unavailable(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                object(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.UNAVAILABLE,
        )

    def test_invalid_request_is_internal_failure(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                ValidProvider(),
                object(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.INTERNAL_FAILURE,
        )

    def test_provider_failure_is_preserved(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                UnavailableProvider(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.UNAVAILABLE,
        )

    def test_invalid_response_mapping(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                InvalidResponseProvider(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.RESPONSE_INVALID,
        )

    def test_memory_failure_mapping(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                MemoryProvider(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_exception_mapping(self):
        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            _invoke_provider(
                ErrorProvider(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.INTERNAL_FAILURE,
        )

    def test_baseexception_not_swallowed(self):
        with self.assertRaises(
            KeyboardInterrupt
        ):
            _invoke_provider(
                InterruptProvider(),
                request(),
                lambda: None,
            )

    def test_check_failure_before_provider_is_not_swallowed(self):
        provider = ValidProvider()

        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            _invoke_provider(
                provider,
                request(),
                check,
            )

        self.assertEqual(
            provider.requests,
            [],
        )

    def test_failure_requires_exact_code(self):
        with self.assertRaisesRegex(
            ValueError,
            "^semantic_vision_provider_failure_invalid$",
        ):
            SemanticVisionProviderFailure(
                "UNAVAILABLE"
            )

    def test_failure_codes_are_stable(self):
        self.assertEqual(
            {
                code.value
                for code
                in SemanticVisionProviderFailureCode
            },
            {
                "UNAVAILABLE",
                "RESPONSE_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()