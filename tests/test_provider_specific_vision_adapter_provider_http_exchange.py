"""M89 concrete provider HTTP exchange backed by M88 HTTPS primitives."""

import dataclasses
import inspect
import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_specific_vision_adapter.provider_http_exchange as exchange_module

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)
from creator_studio.external_vision_provider_transport import (
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    ExternalVisionTransportResponse,
)
from creator_studio.provider_specific_vision_adapter.provider_http_exchange import (
    M88ProviderVisionHTTPExchange,
)
from creator_studio.provider_specific_vision_adapter.provider_transport import (
    ProviderVisionHTTPExchange,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_http_transport_execution import (
    FakeResponse,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    openai_profile,
)
from tests.test_provider_specific_vision_adapter_response_extractor import (
    gemini_document,
    openai_document,
)


def provider_body(
    document,
):
    return json.dumps(
        document,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )


def http_config(
    profile=None,
):
    if profile is None:
        profile = openai_profile()

    return dataclasses.replace(
        config(),
        endpoint=profile.endpoint,
    )


class CredentialSource(
    ExternalVisionHTTPCredentialSource
):
    def __init__(
        self,
        header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        value="Bearer test-secret",
    ):
        self.credential = (
            ExternalVisionHTTPCredential(
                header,
                value,
            )
        )

        self.calls = 0
        self.checks = []

    def resolve(
        self,
        check,
    ):
        self.calls += 1

        self.checks.append(
            check
        )

        check()

        return self.credential


class FailureCredentialSource(
    ExternalVisionHTTPCredentialSource
):
    def __init__(
        self,
        code,
    ):
        self.code = code

    def resolve(
        self,
        check,
    ):
        raise ExternalVisionHTTPCredentialFailure(
            self.code
        )


class InterruptCredentialSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        raise KeyboardInterrupt()


class ProviderSpecificVisionAdapterProviderHTTPExchangeTests(
    unittest.TestCase
):

    def make_exchange(
        self,
        profile=None,
        source=None,
        config_value=None,
    ):
        if profile is None:
            profile = openai_profile()

        if source is None:
            source = CredentialSource(
                profile.credential_header
            )

        if config_value is None:
            config_value = http_config(
                profile
            )

        return M88ProviderVisionHTTPExchange(
            config_value,
            source,
        )

    def invoke(
        self,
        profile=None,
        body=None,
        response=None,
        source=None,
        config_value=None,
        check=None,
    ):
        if profile is None:
            profile = openai_profile()

        if body is None:
            body = b'{"request":"test"}'

        if response is None:
            response = FakeResponse(
                body=provider_body(
                    openai_document()
                )
            )

        if check is None:
            check = lambda: None

        exchange = self.make_exchange(
            profile=profile,
            source=source,
            config_value=config_value,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=response,
        ) as opened:
            result = exchange.send(
                profile,
                body,
                check,
            )

        return (
            result,
            opened,
            response,
        )

    def test_implements_exchange_contract(self):
        exchange = self.make_exchange()

        self.assertIsInstance(
            exchange,
            ProviderVisionHTTPExchange,
        )

    def test_constructor_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    M88ProviderVisionHTTPExchange.__init__
                ).parameters
            ),
            (
                "self",
                "config",
                "credential_source",
            ),
        )

    def test_send_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    M88ProviderVisionHTTPExchange.send
                ).parameters
            ),
            (
                "self",
                "profile",
                "body",
                "check",
            ),
        )

    def test_constructor_rejects_invalid_config(self):
        invalid = dataclasses.replace(
            http_config(),
            endpoint=(
                "http://api.openai.com/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^m88_provider_vision_http_exchange_invalid$",
        ):
            M88ProviderVisionHTTPExchange(
                invalid,
                CredentialSource(),
            )

    def test_constructor_rejects_invalid_credential_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^m88_provider_vision_http_exchange_invalid$",
        ):
            M88ProviderVisionHTTPExchange(
                http_config(),
                object(),
            )

    def test_openai_success(self):
        raw = provider_body(
            openai_document()
        )

        result, _, _ = self.invoke(
            response=FakeResponse(
                body=raw
            )
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertEqual(
            result.body,
            raw,
        )

    def test_gemini_success(self):
        profile = gemini_profile()

        raw = provider_body(
            gemini_document()
        )

        result, _, _ = self.invoke(
            profile=profile,
            source=CredentialSource(
                ExternalVisionHTTPCredentialHeader
                .X_GOOG_API_KEY,
                "test-google-key",
            ),
            config_value=http_config(
                profile
            ),
            response=FakeResponse(
                body=raw
            ),
        )

        self.assertEqual(
            result.body,
            raw,
        )

    def test_exact_endpoint_and_post_method(self):
        profile = openai_profile()

        _, opened, _ = self.invoke(
            profile=profile
        )

        http_request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            http_request.full_url,
            profile.endpoint,
        )

        self.assertEqual(
            http_request.get_method(),
            "POST",
        )

    def test_exact_serialized_body_is_sent(self):
        body = (
            b'{"provider":"body","value":123}'
        )

        _, opened, _ = self.invoke(
            body=body
        )

        http_request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            http_request.data,
            body,
        )

    def test_fixed_json_headers(self):
        _, opened, _ = self.invoke()

        http_request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in http_request.header_items()
        }

        self.assertEqual(
            headers[
                "accept"
            ],
            "application/json",
        )

        self.assertEqual(
            headers[
                "content-type"
            ],
            "application/json",
        )

    def test_authorization_credential_is_runtime_header(self):
        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer runtime-test-secret",
        )

        body = b'{"safe":"payload"}'

        _, opened, _ = self.invoke(
            body=body,
            source=source,
        )

        http_request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in http_request.header_items()
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer runtime-test-secret",
        )

        self.assertNotIn(
            b"runtime-test-secret",
            http_request.data,
        )

    def test_google_api_key_runtime_header(self):
        profile = gemini_profile()

        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
            "google-test-secret",
        )

        _, opened, _ = self.invoke(
            profile=profile,
            source=source,
            config_value=http_config(
                profile
            ),
            response=FakeResponse(
                body=provider_body(
                    gemini_document()
                )
            ),
        )

        headers = {
            name.lower(): value
            for name, value
            in opened.call_args.args[
                0
            ].header_items()
        }

        self.assertEqual(
            headers[
                "x-goog-api-key"
            ],
            "google-test-secret",
        )

    def test_profile_endpoint_must_match_config(self):
        exchange = self.make_exchange()

        profile = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://api.openai.com/v1/responses"
            ),
        )

        mismatched_config = dataclasses.replace(
            http_config(),
            endpoint=(
                "https://generativelanguage.googleapis.com"
                "/v1beta/interactions"
            ),
        )

        exchange = M88ProviderVisionHTTPExchange(
            mismatched_config,
            CredentialSource(),
        )

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    profile,
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

        opened.assert_not_called()

    def test_credential_header_must_match_profile(self):
        exchange = self.make_exchange(
            source=CredentialSource(
                ExternalVisionHTTPCredentialHeader
                .X_API_KEY,
                "wrong-header-secret",
            )
        )

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

        opened.assert_not_called()

    def test_non_bytes_body_rejected_before_network(self):
        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    bytearray(
                        b"{}"
                    ),
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

        opened.assert_not_called()

    def test_empty_body_rejected_before_network(self):
        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

        opened.assert_not_called()

    def test_request_size_bound(self):
        config_value = dataclasses.replace(
            http_config(),
            max_request_bytes=10,
        )

        exchange = self.make_exchange(
            config_value=config_value
        )

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"x" * 11,
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

        opened.assert_not_called()

    def test_response_read_is_bounded(self):
        response = FakeResponse(
            body=provider_body(
                openai_document()
            )
        )

        config_value = http_config()

        self.invoke(
            response=response,
            config_value=config_value,
        )

        self.assertEqual(
            response.read_amount,
            config_value.max_response_bytes
            + 1,
        )

    def test_oversized_response_mapping(self):
        config_value = dataclasses.replace(
            http_config(),
            max_response_bytes=100,
        )

        response = FakeResponse(
            body=bytes(
                101
            )
        )

        exchange = self.make_exchange(
            config_value=config_value
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=response,
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_response_is_closed(self):
        response = FakeResponse(
            body=provider_body(
                openai_document()
            )
        )

        self.invoke(
            response=response
        )

        self.assertTrue(
            response.closed
        )

    def test_invalid_content_type_mapping(self):
        response = FakeResponse(
            body=provider_body(
                openai_document()
            ),
            content_type="text/plain",
        )

        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=response,
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID,
        )

    def test_http_status_mapping(self):
        cases = [
            (
                400,
                ExternalVisionTransportFailureCode
                .REQUEST_INVALID,
            ),
            (
                401,
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
            ),
            (
                408,
                ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED,
            ),
            (
                413,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                429,
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
            ),
            (
                503,
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
            ),
            (
                504,
                ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED,
            ),
            (
                302,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
        ]

        for status, expected in cases:
            with self.subTest(
                status=status
            ):
                response = FakeResponse(
                    body=b"{}",
                    status_code=status,
                )

                exchange = self.make_exchange()

                with patch.object(
                    exchange_module,
                    "_open_https",
                    return_value=response,
                ):
                    with self.assertRaises(
                        ExternalVisionTransportFailure
                    ) as caught:
                        exchange.send(
                            openai_profile(),
                            b"{}",
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_url_timeout_mapping(self):
        error = urllib.error.URLError(
            socket.timeout(
                "timeout"
            )
        )

        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=error,
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .DEADLINE_EXCEEDED,
        )

    def test_url_unavailable_mapping(self):
        error = urllib.error.URLError(
            OSError(
                "offline"
            )
        )

        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=error,
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .UNAVAILABLE,
        )

    def test_credential_failure_mapping(self):
        cases = [
            (
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE,
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
            ),
            (
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                ExternalVisionHTTPCredentialFailureCode
                .DEADLINE_EXCEEDED,
                ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED,
            ),
            (
                ExternalVisionHTTPCredentialFailureCode
                .INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        for source_code, expected in cases:
            with self.subTest(
                source_code=source_code
            ):
                exchange = self.make_exchange(
                    source=(
                        FailureCredentialSource(
                            source_code
                        )
                    )
                )

                with patch.object(
                    exchange_module,
                    "_open_https",
                ) as opened:
                    with self.assertRaises(
                        ExternalVisionTransportFailure
                    ) as caught:
                        exchange.send(
                            openai_profile(),
                            b"{}",
                            lambda: None,
                        )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

                opened.assert_not_called()

    def test_network_memory_error_mapping(self):
        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_network_exception_mapping(self):
        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            with self.assertRaises(
                ExternalVisionTransportFailure
            ) as caught:
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

    def test_check_is_used_repeatedly(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        result, _, _ = self.invoke(
            check=check
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            8,
        )

    def test_network_baseexception_not_swallowed(self):
        exchange = self.make_exchange()

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

    def test_credential_baseexception_not_swallowed(self):
        exchange = self.make_exchange(
            source=(
                InterruptCredentialSource()
            )
        )

        with patch.object(
            exchange_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                KeyboardInterrupt
            ):
                exchange.send(
                    openai_profile(),
                    b"{}",
                    lambda: None,
                )

        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()