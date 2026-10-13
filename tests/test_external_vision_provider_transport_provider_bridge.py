"""M87 transport-neutral semantic vision provider bridge."""

import inspect
import json
import unittest
from unittest.mock import patch

import creator_studio.external_vision_provider_transport.provider_bridge as bridge_module

from creator_studio.external_vision_provider_transport.models import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
)
from creator_studio.external_vision_provider_transport.provider_bridge import (
    ExternalVisionSemanticProvider,
)
from creator_studio.external_vision_provider_transport.transport_contract import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
)
from creator_studio.semantic_vision_observer import (
    SceneSetting,
    SemanticVisionAdapterResponse,
    SemanticVisionProvider,
    SemanticVisionProviderFailure,
    SemanticVisionProviderFailureCode,
    ShotScale,
    VisualMood,
)
from creator_studio.semantic_vision_observer.adapter_contract import (
    SemanticVisionAdapterRequest,
)
from creator_studio.bounded_vision_provider_payload.builder import (
    _PayloadBuildFailure,
    _PayloadBuildFailureCode,
)
from creator_studio.external_vision_provider_transport.request_builder import (
    _TransportRequestBuildFailure,
    _TransportRequestBuildFailureCode,
)
from creator_studio.external_vision_provider_transport.response_parser import (
    _TransportResponseParseFailure,
    _TransportResponseParseFailureCode,
)
from tests.test_semantic_vision_adapter_contract import (
    request as semantic_request,
)


def semantic_document():
    return {
        "schema_version": 1,
        "scene_setting": "INDOOR",
        "shot_scale": "MEDIUM",
        "visual_mood": "CALM",
        "subjects": [
            {
                "label": "person",
                "confidence_milli": 950,
            },
            {
                "label": "wooden table",
                "confidence_milli": 700,
            },
        ],
        "activities": [
            {
                "label": "cooking",
                "confidence_milli": 900,
            },
        ],
        "scene_tags": [
            {
                "label": "rural kitchen",
                "confidence_milli": 850,
            },
        ],
        "confidence_milli": 900,
    }


def transport_response():
    body = json.dumps(
        semantic_document(),
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return ExternalVisionTransportResponse(
        schema_version=(
            EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=len(
            body
        ),
        body=body,
    )


class ValidTransport(
    ExternalVisionTransport
):
    def __init__(self):
        self.requests = []
        self.checks = []

    def send(
        self,
        request,
        check,
    ):
        self.requests.append(
            request
        )

        self.checks.append(
            check
        )

        check()

        return transport_response()


class FailureTransport(
    ExternalVisionTransport
):
    def __init__(self, code):
        self.code = code

    def send(
        self,
        request,
        check,
    ):
        raise ExternalVisionTransportFailure(
            self.code
        )


class InterruptTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request,
        check,
    ):
        raise KeyboardInterrupt()


class ExternalVisionSemanticProviderBridgeTests(
    unittest.TestCase
):

    def test_is_m85_provider(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        self.assertIsInstance(
            provider,
            SemanticVisionProvider,
        )

    def test_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionSemanticProvider.__init__
                ).parameters
            ),
            (
                "self",
                "transport",
            ),
        )

        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionSemanticProvider.observe
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
            ),
        )

    def test_success(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        result = provider.observe(
            semantic_request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            SemanticVisionAdapterResponse,
        )

        self.assertIs(
            result.scene_setting,
            SceneSetting.INDOOR,
        )

        self.assertIs(
            result.shot_scale,
            ShotScale.MEDIUM,
        )

        self.assertIs(
            result.visual_mood,
            VisualMood.CALM,
        )

        self.assertEqual(
            result.subjects[0].label,
            "person",
        )

        self.assertEqual(
            result.activities[0].label,
            "cooking",
        )

        self.assertEqual(
            result.confidence_milli,
            900,
        )

    def test_transport_receives_bounded_request(self):
        transport = ValidTransport()

        provider = ExternalVisionSemanticProvider(
            transport
        )

        provider.observe(
            semantic_request(),
            lambda: None,
        )

        self.assertEqual(
            len(transport.requests),
            1,
        )

        value = transport.requests[0]

        self.assertEqual(
            value.payload.width,
            2,
        )

        self.assertEqual(
            value.payload.height,
            2,
        )

        self.assertGreater(
            value.payload.byte_length,
            0,
        )

        self.assertTrue(
            value.payload.image_bytes.startswith(
                b"\x89PNG\r\n\x1a\n"
            )
        )

    def test_check_identity_reaches_transport(self):
        transport = ValidTransport()

        provider = ExternalVisionSemanticProvider(
            transport
        )

        def check():
            pass

        provider.observe(
            semantic_request(),
            check,
        )

        self.assertEqual(
            len(transport.checks),
            1,
        )

        self.assertIs(
            transport.checks[0],
            check,
        )

    def test_check_is_used_repeatedly(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        calls = [0]

        def check():
            calls[0] += 1

        provider.observe(
            semantic_request(),
            check,
        )

        self.assertGreaterEqual(
            calls[0],
            15,
        )

    def test_invalid_transport_maps_unavailable(self):
        provider = ExternalVisionSemanticProvider(
            object()
        )

        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            provider.observe(
                semantic_request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.UNAVAILABLE,
        )

    def test_invalid_semantic_request_maps_internal(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        with self.assertRaises(
            SemanticVisionProviderFailure
        ) as caught:
            provider.observe(
                object(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode.INTERNAL_FAILURE,
        )

    def test_payload_failure_mapping(self):
        mappings = [
            (
                _PayloadBuildFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _PayloadBuildFailureCode
                .RASTER_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _PayloadBuildFailureCode
                .EVIDENCE_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _PayloadBuildFailureCode
                .COHERENCE_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _PayloadBuildFailureCode
                .PAYLOAD_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                with patch.object(
                    bridge_module,
                    "_build_payload",
                    side_effect=(
                        _PayloadBuildFailure(
                            code
                        )
                    ),
                ):
                    with self.assertRaises(
                        SemanticVisionProviderFailure
                    ) as caught:
                        provider.observe(
                            semantic_request(),
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_request_builder_failure_mapping(self):
        mappings = [
            (
                _TransportRequestBuildFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _TransportRequestBuildFailureCode
                .PAYLOAD_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _TransportRequestBuildFailureCode
                .REQUEST_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                with patch.object(
                    bridge_module,
                    "_build_transport_request",
                    side_effect=(
                        _TransportRequestBuildFailure(
                            code
                        )
                    ),
                ):
                    with self.assertRaises(
                        SemanticVisionProviderFailure
                    ) as caught:
                        provider.observe(
                            semantic_request(),
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_transport_failure_mapping(self):
        mappings = [
            (
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
                SemanticVisionProviderFailureCode
                .UNAVAILABLE,
            ),
            (
                ExternalVisionTransportFailureCode
                .REQUEST_INVALID,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
                SemanticVisionProviderFailureCode
                .RESPONSE_INVALID,
            ),
            (
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED,
                SemanticVisionProviderFailureCode
                .DEADLINE_EXCEEDED,
            ),
            (
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        for code, expected in mappings:
            provider = ExternalVisionSemanticProvider(
                FailureTransport(
                    code
                )
            )

            with self.subTest(
                code=code
            ):
                with self.assertRaises(
                    SemanticVisionProviderFailure
                ) as caught:
                    provider.observe(
                        semantic_request(),
                        lambda: None,
                    )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_parser_failure_mapping(self):
        mappings = [
            (
                _TransportResponseParseFailureCode
                .TRANSPORT_RESPONSE_INVALID,
                SemanticVisionProviderFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _TransportResponseParseFailureCode
                .JSON_INVALID,
                SemanticVisionProviderFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID,
                SemanticVisionProviderFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _TransportResponseParseFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
        ]

        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        for code, expected in mappings:
            with self.subTest(
                code=code
            ):
                with patch.object(
                    bridge_module,
                    "_parse_transport_response",
                    side_effect=(
                        _TransportResponseParseFailure(
                            code
                        )
                    ),
                ):
                    with self.assertRaises(
                        SemanticVisionProviderFailure
                    ) as caught:
                        provider.observe(
                            semantic_request(),
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_memory_error_mapping(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        with patch.object(
            bridge_module,
            "_build_payload",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                SemanticVisionProviderFailure
            ) as caught:
                provider.observe(
                    semantic_request(),
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_exception_mapping(self):
        provider = ExternalVisionSemanticProvider(
            ValidTransport()
        )

        with patch.object(
            bridge_module,
            "_build_payload",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            with self.assertRaises(
                SemanticVisionProviderFailure
            ) as caught:
                provider.observe(
                    semantic_request(),
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            SemanticVisionProviderFailureCode
            .INTERNAL_FAILURE,
        )

    def test_baseexception_not_swallowed(self):
        provider = ExternalVisionSemanticProvider(
            InterruptTransport()
        )

        with self.assertRaises(
            KeyboardInterrupt
        ):
            provider.observe(
                semantic_request(),
                lambda: None,
            )

    def test_semantic_request_identity_is_not_transport_request(self):
        transport = ValidTransport()

        provider = ExternalVisionSemanticProvider(
            transport
        )

        value = semantic_request()

        self.assertIs(
            type(value),
            SemanticVisionAdapterRequest,
        )

        provider.observe(
            value,
            lambda: None,
        )

        self.assertIsNot(
            transport.requests[0],
            value,
        )


if __name__ == "__main__":
    unittest.main()