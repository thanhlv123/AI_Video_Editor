"""M88 HTTPS transport runtime credential integration."""

import unittest
from unittest.mock import patch

import creator_studio.external_vision_http_transport.http_transport as transport_module

from creator_studio.external_vision_http_transport.credential_contract import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)
from creator_studio.external_vision_http_transport.http_transport import (
    ExternalVisionHTTPSJSONTransport,
)
from creator_studio.external_vision_provider_transport import (
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    ExternalVisionTransportResponse,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_http_transport_execution import (
    FakeResponse,
)
from tests.test_external_vision_provider_transport_models import (
    request,
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
        value="Bearer test-secret-123",
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


class FailureSource(
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


class InvalidSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        return object()


class InterruptSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        raise KeyboardInterrupt()


class ExternalVisionHTTPTransportCredentialIntegrationTests(
    unittest.TestCase
):

    def send(
        self,
        source=None,
        response=None,
        check=None,
    ):
        if response is None:
            response = FakeResponse()

        if check is None:
            check = lambda: None

        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            source,
        )

        with patch.object(
            transport_module,
            "_open_https",
            return_value=response,
        ) as opened:
            result = transport.send(
                request(),
                check,
            )

        return (
            result,
            opened,
        )

    def test_constructor_accepts_credential_source(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            CredentialSource(),
        )

        self.assertIsInstance(
            transport,
            ExternalVisionHTTPSJSONTransport,
        )

    def test_constructor_rejects_invalid_credential_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_https_json_transport_invalid$",
        ):
            ExternalVisionHTTPSJSONTransport(
                config(),
                object(),
            )

    def test_authorization_header_is_injected(self):
        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-secret-123",
        )

        result, opened = self.send(
            source
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
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
            "Bearer test-secret-123",
        )

    def test_x_api_key_header_is_injected(self):
        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .X_API_KEY,
            "test-key-123",
        )

        _, opened = self.send(
            source
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
                "x-api-key"
            ],
            "test-key-123",
        )

    def test_api_key_header_is_injected(self):
        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .API_KEY,
            "test-key-123",
        )

        _, opened = self.send(
            source
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
                "api-key"
            ],
            "test-key-123",
        )

    def test_x_goog_api_key_header_is_injected(self):
        source = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
            "test-google-key",
        )

        _, opened = self.send(
            source
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
            "test-google-key",
        )

    def test_fixed_headers_are_preserved(self):
        _, opened = self.send(
            CredentialSource()
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

    def test_secret_is_not_in_serialized_body(self):
        source = CredentialSource(
            value="Bearer unique-test-secret-987654",
        )

        _, opened = self.send(
            source
        )

        http_request = opened.call_args.args[
            0
        ]

        self.assertNotIn(
            b"unique-test-secret-987654",
            http_request.data,
        )

    def test_source_is_resolved_once_per_send(self):
        source = CredentialSource()

        self.send(
            source
        )

        self.assertEqual(
            source.calls,
            1,
        )

    def test_check_identity_reaches_source(self):
        source = CredentialSource()

        def check():
            pass

        self.send(
            source,
            check=check,
        )

        self.assertEqual(
            len(
                source.checks
            ),
            1,
        )

        self.assertIs(
            source.checks[
                0
            ],
            check,
        )

    def test_unavailable_failure_mapping(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            FailureSource(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
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
            .UNAVAILABLE,
        )

    def test_invalid_credential_mapping(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            InvalidSource(),
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

    def test_resource_failure_mapping(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            FailureSource(
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED
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
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_deadline_failure_mapping(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            FailureSource(
                ExternalVisionHTTPCredentialFailureCode
                .DEADLINE_EXCEEDED
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
            .DEADLINE_EXCEEDED,
        )

    def test_internal_failure_mapping(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            FailureSource(
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE
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
            .INTERNAL_FAILURE,
        )

    def test_network_not_opened_when_resolution_fails(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            FailureSource(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            ),
        )

        with patch.object(
            transport_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                ExternalVisionTransportFailure
            ):
                transport.send(
                    request(),
                    lambda: None,
                )

        opened.assert_not_called()

    def test_baseexception_not_swallowed(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config(),
            InterruptSource(),
        )

        with patch.object(
            transport_module,
            "_open_https",
        ) as opened:
            with self.assertRaises(
                KeyboardInterrupt
            ):
                transport.send(
                    request(),
                    lambda: None,
                )

        opened.assert_not_called()

    def test_no_credential_source_keeps_existing_behavior(self):
        transport = ExternalVisionHTTPSJSONTransport(
            config()
        )

        with patch.object(
            transport_module,
            "_open_https",
            return_value=FakeResponse(),
        ) as opened:
            result = transport.send(
                request(),
                lambda: None,
            )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        headers = {
            name.lower(): value
            for name, value
            in opened.call_args.args[
                0
            ].header_items()
        }

        self.assertNotIn(
            "authorization",
            headers,
        )

        self.assertNotIn(
            "x-api-key",
            headers,
        )

        self.assertNotIn(
            "api-key",
            headers,
        )

        self.assertNotIn(
            "x-goog-api-key",
            headers,
        )


if __name__ == "__main__":
    unittest.main()