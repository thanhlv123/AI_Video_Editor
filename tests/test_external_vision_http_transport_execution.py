"""M88 concrete bounded HTTPS JSON transport."""

import dataclasses
import inspect
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.external_vision_http_transport.http_transport as transport_module

from creator_studio.external_vision_http_transport.http_transport import (
    ExternalVisionHTTPSJSONTransport,
    _NoRedirectHandler,
    _map_http_status,
)
from creator_studio.external_vision_http_transport.response_reader import (
    _HTTPResponseReadFailure,
    _HTTPResponseReadFailureCode,
)
from creator_studio.external_vision_http_transport.serializer import (
    _HTTPRequestSerializeFailure,
    _HTTPRequestSerializeFailureCode,
    _serialize_http_request,
)
from creator_studio.external_vision_provider_transport import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    ExternalVisionTransportResponse,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_provider_transport_models import (
    request,
)


class FakeHeaders:
    def __init__(
        self,
        content_type="application/json",
    ):
        self._content_type = content_type

    def get(
        self,
        name,
        default=None,
    ):
        if name.lower() == "content-type":
            return self._content_type

        return default


class FakeResponse:
    def __init__(
        self,
        body=(
            b'{"schema_version":1,'
            b'"scene_setting":"INDOOR"}'
        ),
        status_code=200,
        content_type="application/json",
    ):
        self.body = body
        self.status_code = status_code
        self.headers = FakeHeaders(
            content_type
        )
        self.closed = False
        self.read_amount = None

    def getcode(self):
        return self.status_code

    def read(
        self,
        amount,
    ):
        self.read_amount = amount

        if type(self.body) is bytes:
            return self.body[
                :amount
            ]

        return self.body

    def close(self):
        self.closed = True


class ExternalVisionHTTPTransportExecutionTests(
    unittest.TestCase
):

    def make_transport(
        self,
        config_value=None,
    ):
        if config_value is None:
            config_value = config()

        return ExternalVisionHTTPSJSONTransport(
            config_value
        )

    def invoke(
        self,
        fake_response=None,
        transport=None,
        request_value=None,
        check=None,
    ):
        if fake_response is None:
            fake_response = FakeResponse()

        if transport is None:
            transport = self.make_transport()

        if request_value is None:
            request_value = request()

        if check is None:
            check = lambda: None

        with patch.object(
            transport_module,
            "_open_https",
            return_value=fake_response,
        ):
            return transport.send(
                request_value,
                check,
            )

    def test_is_m87_transport(self):
        value = self.make_transport()

        self.assertIsInstance(
            value,
            ExternalVisionTransport,
        )

    def test_constructor_rejects_invalid_config(self):
        invalid = dataclasses.replace(
            config(),
            endpoint=(
                "http://vision.example.test/v1/analyze"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_https_json_transport_invalid$",
        ):
            ExternalVisionHTTPSJSONTransport(
                invalid
            )

    def test_signatures(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionHTTPSJSONTransport.__init__
                ).parameters
            ),
            (
                "self",
                "config",
                "credential_source",
            ),
        )

        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionHTTPSJSONTransport.send
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
            ),
        )

    def test_success(self):
        result = self.invoke()

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

    def test_posts_to_exact_endpoint(self):
        response = FakeResponse()

        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            return_value=response,
        ) as opened:
            transport.send(
                request(),
                lambda: None,
            )

        http_request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            http_request.full_url,
            config().endpoint,
        )

        self.assertEqual(
            http_request.get_method(),
            "POST",
        )

    def test_fixed_headers_have_no_credentials(self):
        response = FakeResponse()

        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            return_value=response,
        ) as opened:
            transport.send(
                request(),
                lambda: None,
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

        self.assertNotIn(
            "authorization",
            headers,
        )

        self.assertNotIn(
            "cookie",
            headers,
        )

        self.assertNotIn(
            "proxy-authorization",
            headers,
        )

    def test_body_matches_serializer(self):
        request_value = request()
        config_value = config()

        expected = _serialize_http_request(
            request_value,
            config_value,
            lambda: None,
        )

        response = FakeResponse()

        transport = self.make_transport(
            config_value
        )

        with patch.object(
            transport_module,
            "_open_https",
            return_value=response,
        ) as opened:
            transport.send(
                request_value,
                lambda: None,
            )

        http_request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            http_request.data,
            expected,
        )

    def test_timeout_conversion(self):
        response = FakeResponse()

        config_value = dataclasses.replace(
            config(),
            timeout_millis=12_345,
        )

        transport = self.make_transport(
            config_value
        )

        with patch.object(
            transport_module,
            "_open_https",
            return_value=response,
        ) as opened:
            transport.send(
                request(),
                lambda: None,
            )

        timeout_seconds = opened.call_args.args[
            1
        ]

        self.assertEqual(
            timeout_seconds,
            12.345,
        )

    def test_response_is_closed(self):
        response = FakeResponse()

        self.invoke(
            fake_response=response
        )

        self.assertTrue(
            response.closed
        )

    def test_read_is_bounded(self):
        request_value = request()

        response = FakeResponse()

        self.invoke(
            fake_response=response,
            request_value=request_value,
        )

        self.assertEqual(
            response.read_amount,
            request_value.max_response_bytes
            + 1,
        )

    def test_oversized_response_mapping(self):
        request_value = request()

        response = FakeResponse(
            body=bytes(
                request_value.max_response_bytes
                + 1
            )
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            self.invoke(
                fake_response=response,
                request_value=request_value,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_non_bytes_response_mapping(self):
        response = FakeResponse(
            body=bytearray(
                b"{}"
            )
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            self.invoke(
                fake_response=response
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID,
        )

    def test_invalid_content_type_mapping(self):
        response = FakeResponse(
            content_type="text/plain"
        )

        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            self.invoke(
                fake_response=response
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
                500,
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
                    status_code=status
                )

                with self.assertRaises(
                    ExternalVisionTransportFailure
                ) as caught:
                    self.invoke(
                        fake_response=response
                    )

                self.assertIs(
                    caught.exception.code,
                    expected,
                )

    def test_http_error_mapping(self):
        cases = [
            (
                400,
                ExternalVisionTransportFailureCode
                .REQUEST_INVALID,
            ),
            (
                403,
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
                503,
                ExternalVisionTransportFailureCode
                .UNAVAILABLE,
            ),
        ]

        transport = self.make_transport()

        for status, expected in cases:
            with self.subTest(
                status=status
            ):
                error = urllib.error.HTTPError(
                    config().endpoint,
                    status,
                    "error",
                    {},
                    None,
                )

                with patch.object(
                    transport_module,
                    "_open_https",
                    side_effect=error,
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

    def test_url_timeout_mapping(self):
        transport = self.make_transport()

        error = urllib.error.URLError(
            socket.timeout(
                "timeout"
            )
        )

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=error,
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
            ExternalVisionTransportFailureCode
            .DEADLINE_EXCEEDED,
        )

    def test_url_unavailable_mapping(self):
        transport = self.make_transport()

        error = urllib.error.URLError(
            OSError(
                "offline"
            )
        )

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=error,
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
            ExternalVisionTransportFailureCode
            .UNAVAILABLE,
        )

    def test_socket_timeout_mapping(self):
        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=socket.timeout(
                "timeout"
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
            ExternalVisionTransportFailureCode
            .DEADLINE_EXCEEDED,
        )

    def test_memory_error_mapping(self):
        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=MemoryError(),
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
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_exception_mapping(self):
        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=RuntimeError(
                "private"
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
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE,
        )

    def test_serializer_failure_mapping(self):
        cases = [
            (
                _HTTPRequestSerializeFailureCode
                .REQUEST_INVALID,
                ExternalVisionTransportFailureCode
                .REQUEST_INVALID,
            ),
            (
                _HTTPRequestSerializeFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _HTTPRequestSerializeFailureCode
                .CONFIG_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _HTTPRequestSerializeFailureCode
                .COHERENCE_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
            (
                _HTTPRequestSerializeFailureCode
                .SERIALIZATION_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        transport = self.make_transport()

        for code, expected in cases:
            with self.subTest(
                code=code
            ):
                with patch.object(
                    transport_module,
                    "_serialize_http_request",
                    side_effect=(
                        _HTTPRequestSerializeFailure(
                            code
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

    def test_reader_failure_mapping(self):
        cases = [
            (
                _HTTPResponseReadFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED,
            ),
            (
                _HTTPResponseReadFailureCode
                .CONTENT_TYPE_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _HTTPResponseReadFailureCode
                .RESPONSE_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _HTTPResponseReadFailureCode
                .ENVELOPE_INVALID,
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID,
            ),
            (
                _HTTPResponseReadFailureCode
                .CONFIG_INVALID,
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE,
            ),
        ]

        transport = self.make_transport()

        for code, expected in cases:
            with self.subTest(
                code=code
            ):
                with patch.object(
                    transport_module,
                    "_read_http_response",
                    side_effect=(
                        _HTTPResponseReadFailure(
                            code
                        )
                    ),
                ):
                    with patch.object(
                        transport_module,
                        "_open_https",
                        return_value=FakeResponse(),
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

    def test_check_is_used(self):
        calls = [0]

        def check():
            calls[0] += 1

        result = self.invoke(
            check=check
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertGreaterEqual(
            calls[0],
            8,
        )

    def test_baseexception_not_swallowed(self):
        transport = self.make_transport()

        with patch.object(
            transport_module,
            "_open_https",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                transport.send(
                    request(),
                    lambda: None,
                )

    def test_redirects_are_disabled(self):
        handler = _NoRedirectHandler()

        self.assertIsNone(
            handler.redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "https://other.example.test/",
            )
        )

    def test_status_helper_requires_exact_integer(self):
        self.assertIs(
            _map_http_status(
                True
            ),
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID,
        )


if __name__ == "__main__":
    unittest.main()