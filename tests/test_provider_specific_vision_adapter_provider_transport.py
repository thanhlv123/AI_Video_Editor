"""M89 provider-specific vision transport orchestration."""

import dataclasses
import inspect
import json
import unittest
from unittest.mock import patch

import creator_studio.provider_specific_vision_adapter.provider_transport as transport_module

from creator_studio.external_vision_provider_transport import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    ExternalVisionTransportResponse,
)
from creator_studio.provider_specific_vision_adapter.provider_transport import (
    ProviderSpecificVisionTransport,
    ProviderVisionHTTPExchange,
    ProviderVisionRemoteImageSource,
)
from creator_studio.provider_specific_vision_adapter.request_serializer import (
    _ProviderRequestSerializeFailure,
    _ProviderRequestSerializeFailureCode,
)
from creator_studio.provider_specific_vision_adapter.response_extractor import (
    _ProviderResponseExtractFailure,
    _ProviderResponseExtractFailureCode,
)
from tests.test_external_vision_provider_transport_models import (
    request,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    kie_profile,
    openai_profile,
)
from tests.test_provider_specific_vision_adapter_response_extractor import (
    gemini_document,
    kie_document,
    openai_document,
    raw_response,
)


REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "runtime-image.png?signature=test"
)


class FakeExchange(
    ProviderVisionHTTPExchange
):
    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = 0
        self.profiles = []
        self.bodies = []
        self.checks = []

    def send(
        self,
        profile,
        body,
        check,
    ):
        self.calls += 1

        self.profiles.append(
            profile
        )

        self.bodies.append(
            body
        )

        self.checks.append(
            check
        )

        check()

        return self.response


class FailureExchange(
    ProviderVisionHTTPExchange
):
    def __init__(
        self,
        code,
    ):
        self.code = code

    def send(
        self,
        profile,
        body,
        check,
    ):
        raise ExternalVisionTransportFailure(
            self.code
        )


class MemoryExchange(
    ProviderVisionHTTPExchange
):
    def send(
        self,
        profile,
        body,
        check,
    ):
        raise MemoryError()


class ErrorExchange(
    ProviderVisionHTTPExchange
):
    def send(
        self,
        profile,
        body,
        check,
    ):
        raise RuntimeError(
            "private"
        )


class InterruptExchange(
    ProviderVisionHTTPExchange
):
    def send(
        self,
        profile,
        body,
        check,
    ):
        raise KeyboardInterrupt()


class InvalidResponseExchange(
    ProviderVisionHTTPExchange
):
    def send(
        self,
        profile,
        body,
        check,
    ):
        return object()


class FakeRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
        value=REMOTE_IMAGE_URL,
    ):
        self.value = value
        self.calls = 0
        self.requests = []
        self.checks = []

    def resolve(
        self,
        request_value,
        check,
    ):
        self.calls += 1

        self.requests.append(
            request_value
        )

        self.checks.append(
            check
        )

        check()

        return self.value


class FailureRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
        code,
    ):
        self.code = code

    def resolve(
        self,
        request_value,
        check,
    ):
        raise ExternalVisionTransportFailure(
            self.code
        )


class InterruptRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def resolve(
        self,
        request_value,
        check,
    ):
        raise KeyboardInterrupt()


class ProviderSpecificVisionAdapterProviderTransportTests(
    unittest.TestCase
):

    def test_exchange_contract_is_abstract(self):
        with self.assertRaises(
            TypeError
        ):
            ProviderVisionHTTPExchange()

    def test_remote_image_source_contract_is_abstract(self):
        with self.assertRaises(
            TypeError
        ):
            ProviderVisionRemoteImageSource()

    def test_contract_signatures(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderVisionHTTPExchange
                    .send
                ).parameters
            ),
            (
                "self",
                "profile",
                "body",
                "check",
            ),
        )

        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderVisionRemoteImageSource
                    .resolve
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
            ),
        )

    def test_openai_constructor(self):
        value = ProviderSpecificVisionTransport(
            openai_profile(),
            FakeExchange(
                raw_response(
                    openai_document()
                )
            ),
        )

        self.assertIsInstance(
            value,
            ExternalVisionTransport,
        )

    def test_gemini_constructor(self):
        value = ProviderSpecificVisionTransport(
            gemini_profile(),
            FakeExchange(
                raw_response(
                    gemini_document()
                )
            ),
        )

        self.assertIsInstance(
            value,
            ExternalVisionTransport,
        )

    def test_kie_constructor_requires_remote_source(self):
        value = ProviderSpecificVisionTransport(
            kie_profile(),
            FakeExchange(
                raw_response(
                    kie_document()
                )
            ),
            FakeRemoteImageSource(),
        )

        self.assertIsInstance(
            value,
            ExternalVisionTransport,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_specific_vision_transport_invalid$",
        ):
            ProviderSpecificVisionTransport(
                kie_profile(),
                FakeExchange(
                    raw_response(
                        kie_document()
                    )
                ),
            )

    def test_non_kie_rejects_remote_source(self):
        for profile in (
            openai_profile(),
            gemini_profile(),
        ):
            with self.subTest(
                provider=profile.provider
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_specific_vision_transport_invalid$",
                ):
                    ProviderSpecificVisionTransport(
                        profile,
                        FakeExchange(
                            raw_response(
                                openai_document()
                            )
                        ),
                        FakeRemoteImageSource(),
                    )

    def test_constructor_rejects_invalid_profile(self):
        invalid = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://example.test/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_specific_vision_transport_invalid$",
        ):
            ProviderSpecificVisionTransport(
                invalid,
                FakeExchange(
                    raw_response(
                        openai_document()
                    )
                ),
            )

    def test_constructor_rejects_invalid_exchange(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_specific_vision_transport_invalid$",
        ):
            ProviderSpecificVisionTransport(
                openai_profile(),
                object(),
            )

    def test_openai_success(self):
        exchange = FakeExchange(
            raw_response(
                openai_document()
            )
        )

        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            exchange,
        )

        result = transport.send(
            request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertIn(
            b'"schema_version":1',
            result.body,
        )

        self.assertEqual(
            exchange.calls,
            1,
        )

    def test_gemini_success(self):
        exchange = FakeExchange(
            raw_response(
                gemini_document()
            )
        )

        transport = ProviderSpecificVisionTransport(
            gemini_profile(),
            exchange,
        )

        result = transport.send(
            request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertIn(
            b'"confidence_milli":900',
            result.body,
        )

    def test_kie_success(self):
        exchange = FakeExchange(
            raw_response(
                kie_document()
            )
        )

        remote_source = (
            FakeRemoteImageSource()
        )

        transport = ProviderSpecificVisionTransport(
            kie_profile(),
            exchange,
            remote_source,
        )

        result = transport.send(
            request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertEqual(
            remote_source.calls,
            1,
        )

        document = json.loads(
            exchange.bodies[
                0
            ].decode(
                "utf-8"
            )
        )

        image_url = document[
            "messages"
        ][
            0
        ][
            "content"
        ][
            1
        ][
            "image_url"
        ][
            "url"
        ]

        self.assertEqual(
            image_url,
            REMOTE_IMAGE_URL,
        )

    def test_exchange_receives_profile_body_and_check(self):
        profile = openai_profile()

        exchange = FakeExchange(
            raw_response(
                openai_document()
            )
        )

        transport = ProviderSpecificVisionTransport(
            profile,
            exchange,
        )

        def check():
            pass

        transport.send(
            request(),
            check,
        )

        self.assertEqual(
            exchange.calls,
            1,
        )

        self.assertIs(
            exchange.profiles[
                0
            ],
            profile,
        )

        self.assertIs(
            type(
                exchange.bodies[
                    0
                ]
            ),
            bytes,
        )

        self.assertTrue(
            exchange.bodies[
                0
            ]
        )

        self.assertIs(
            exchange.checks[
                0
            ],
            check,
        )

    def test_remote_source_receives_exact_request_and_check(self):
        request_value = request()

        remote_source = (
            FakeRemoteImageSource()
        )

        transport = ProviderSpecificVisionTransport(
            kie_profile(),
            FakeExchange(
                raw_response(
                    kie_document()
                )
            ),
            remote_source,
        )

        def check():
            pass

        transport.send(
            request_value,
            check,
        )

        self.assertEqual(
            remote_source.calls,
            1,
        )

        self.assertIs(
            remote_source.requests[
                0
            ],
            request_value,
        )

        self.assertIs(
            remote_source.checks[
                0
            ],
            check,
        )

    def test_invalid_request_prevents_dependencies(self):
        invalid = dataclasses.replace(
            request(),
            response_schema_version=2,
        )

        exchange = FakeExchange(
            raw_response(
                openai_document()
            )
        )

        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            exchange,
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                invalid,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID,
        )

        self.assertEqual(
            exchange.calls,
            0,
        )

    def test_exchange_declared_failure_is_preserved(self):
        for code in ExternalVisionTransportFailureCode:
            with self.subTest(
                code=code
            ):
                transport = (
                    ProviderSpecificVisionTransport(
                        openai_profile(),
                        FailureExchange(
                            code
                        ),
                    )
                )

                with self.assertRaises(
                    ExternalVisionTransportFailure
                ) as caught:
                    transport.send(
                        request(),
                        lambda: None,
                    )

                self.assertIs(
                    caught.exception.code,
                    code,
                )

    def test_remote_source_declared_failure_is_preserved(self):
        code = (
            ExternalVisionTransportFailureCode
            .UNAVAILABLE
        )

        transport = ProviderSpecificVisionTransport(
            kie_profile(),
            FakeExchange(
                raw_response(
                    kie_document()
                )
            ),
            FailureRemoteImageSource(
                code
            ),
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            code,
        )

    def test_exchange_memory_error_mapping(self):
        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            MemoryExchange(),
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_exchange_unexpected_exception_mapping(self):
        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            ErrorExchange(),
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

    def test_invalid_exchange_response_mapping(self):
        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            InvalidResponseExchange(),
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID,
        )

    def test_serializer_failure_mapping(self):
        cases = [
            (
                _ProviderRequestSerializeFailureCode
                .REQUEST_INVALID,
                ExternalVisionTransportFailureCode
                .REQUEST_INVALID,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .PROFILE_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .PROFILE_COHERENCE_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .REMOTE_IMAGE_REQUIRED,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .REMOTE_IMAGE_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _ProviderRequestSerializeFailureCode
                .SERIALIZATION_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        for source_code, expected in cases:
            with self.subTest(
                source_code=source_code
            ):
                transport = (
                    ProviderSpecificVisionTransport(
                        openai_profile(),
                        FakeExchange(
                            raw_response(
                                openai_document()
                            )
                        ),
                    )
                )

                with patch.object(
                    transport_module,
                    "_serialize_provider_request",
                    side_effect=(
                        _ProviderRequestSerializeFailure(
                            source_code
                        )
                    ),
                ):
                    with self.assertRaises(
                        ExternalVisionTransportFailure
                    ) as caught:
                        transport.send(
                            request(),
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_extractor_failure_mapping(self):
        cases = [
            (
                _ProviderResponseExtractFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _ProviderResponseExtractFailureCode
                .TRANSPORT_RESPONSE_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _ProviderResponseExtractFailureCode
                .JSON_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _ProviderResponseExtractFailureCode
                .OUTPUT_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _ProviderResponseExtractFailureCode
                .PROFILE_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        for source_code, expected in cases:
            with self.subTest(
                source_code=source_code
            ):
                transport = (
                    ProviderSpecificVisionTransport(
                        openai_profile(),
                        FakeExchange(
                            raw_response(
                                openai_document()
                            )
                        ),
                    )
                )

                with patch.object(
                    transport_module,
                    "_extract_provider_response",
                    side_effect=(
                        _ProviderResponseExtractFailure(
                            source_code
                        )
                    ),
                ):
                    with self.assertRaises(
                        ExternalVisionTransportFailure
                    ) as caught:
                        transport.send(
                            request(),
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_check_is_used_repeatedly(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            FakeExchange(
                raw_response(
                    openai_document()
                )
            ),
        )

        result = transport.send(
            request(),
            check,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            12,
        )

    def test_exchange_baseexception_not_swallowed(self):
        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            InterruptExchange(),
        )

        with self.assertRaises(
            KeyboardInterrupt
        ):
            transport.send(
                request(),
                lambda: None,
            )

    def test_remote_source_baseexception_not_swallowed(self):
        transport = ProviderSpecificVisionTransport(
            kie_profile(),
            FakeExchange(
                raw_response(
                    kie_document()
                )
            ),
            InterruptRemoteImageSource(),
        )

        with self.assertRaises(
            KeyboardInterrupt
        ):
            transport.send(
                request(),
                lambda: None,
            )

    def test_malformed_provider_response_maps_response_invalid(self):
        response = raw_response(
            {
                "status": "completed",
                "output": [],
            }
        )

        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            FakeExchange(
                response
            ),
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID,
        )

    def test_normalized_response_respects_request_limit(self):
        request_value = dataclasses.replace(
            request(),
            max_response_bytes=1,
        )

        exchange = FakeExchange(
            raw_response(
                openai_document()
            )
        )

        transport = ProviderSpecificVisionTransport(
            openai_profile(),
            exchange,
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            transport.send(
                request_value,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

        self.assertEqual(
            exchange.calls,
            1,
        )


if __name__ == "__main__":
    unittest.main()