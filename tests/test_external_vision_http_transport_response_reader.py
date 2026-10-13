"""M88 bounded external vision HTTP response envelope and reader."""

import copy
import dataclasses
import pickle
import unittest
from unittest.mock import patch

import creator_studio.external_vision_http_transport.response_reader as reader_module

from creator_studio.external_vision_http_transport.response_reader import (
    ExternalVisionHTTPResponseContentType,
    ExternalVisionHTTPResponseEnvelope,
    MAX_EXTERNAL_VISION_HTTP_CONTENT_TYPE_LENGTH,
    _HTTPResponseReadFailure,
    _HTTPResponseReadFailureCode,
    _read_http_response,
    validate_external_vision_http_response_envelope,
)
from creator_studio.external_vision_provider_transport import (
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
)
from tests.test_external_vision_http_transport_config import (
    config,
)


def body():
    return (
        b'{"schema_version":1,'
        b'"scene_setting":"INDOOR"}'
    )


def envelope():
    value = body()

    return ExternalVisionHTTPResponseEnvelope(
        status_code=200,
        content_type="application/json",
        body_length=len(
            value
        ),
        body=value,
    )


class Hostile:
    def __getattribute__(
        self,
        name,
    ):
        raise AssertionError(
            "hostile access"
        )

    def __repr__(self):
        raise AssertionError(
            "hostile repr"
        )

    def __eq__(
        self,
        other,
    ):
        raise AssertionError(
            "hostile equality"
        )


class ExternalVisionHTTPTransportResponseReaderTests(
    unittest.TestCase
):

    def read(
        self,
        envelope_value=None,
        config_value=None,
        max_response_bytes=None,
        check=None,
    ):
        if envelope_value is None:
            envelope_value = envelope()

        if config_value is None:
            config_value = config()

        if max_response_bytes is None:
            max_response_bytes = (
                config_value.max_response_bytes
            )

        if check is None:
            check = lambda: None

        return _read_http_response(
            envelope_value,
            config_value,
            max_response_bytes,
            check,
        )

    def failure(
        self,
        expected,
        envelope_value=None,
        config_value=None,
        max_response_bytes=None,
    ):
        if envelope_value is None:
            envelope_value = envelope()

        if config_value is None:
            config_value = config()

        if max_response_bytes is None:
            max_response_bytes = (
                config_value.max_response_bytes
            )

        with self.assertRaises(
            _HTTPResponseReadFailure
        ) as caught:
            _read_http_response(
                envelope_value,
                config_value,
                max_response_bytes,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_valid_envelope(self):
        value = envelope()

        self.assertIs(
            validate_external_vision_http_response_envelope(
                value
            ),
            value,
        )

    def test_envelope_is_frozen(self):
        value = envelope()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.status_code = 201

    def test_status_code_shape(self):
        variants = [
            99,
            600,
            True,
            "200",
        ]

        for status in variants:
            value = dataclasses.replace(
                envelope(),
                status_code=status,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_response_envelope_invalid$",
            ):
                validate_external_vision_http_response_envelope(
                    value
                )

    def test_content_type_shape(self):
        variants = [
            "",
            " application/json",
            "application/json ",
            123,
        ]

        for content_type in variants:
            value = dataclasses.replace(
                envelope(),
                content_type=content_type,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_response_envelope_invalid$",
            ):
                validate_external_vision_http_response_envelope(
                    value
                )

    def test_content_type_length_bound(self):
        value = dataclasses.replace(
            envelope(),
            content_type=(
                "a"
                * (
                    MAX_EXTERNAL_VISION_HTTP_CONTENT_TYPE_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_response_envelope_invalid$",
        ):
            validate_external_vision_http_response_envelope(
                value
            )

    def test_body_length_shape(self):
        variants = [
            0,
            -1,
            True,
            len(
                body()
            )
            + 1,
        ]

        for length in variants:
            value = dataclasses.replace(
                envelope(),
                body_length=length,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_response_envelope_invalid$",
            ):
                validate_external_vision_http_response_envelope(
                    value
                )

    def test_body_requires_exact_bytes(self):
        value = dataclasses.replace(
            envelope(),
            body=bytearray(
                body()
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_response_envelope_invalid$",
        ):
            validate_external_vision_http_response_envelope(
                value
            )

    def test_exact_shape(self):
        base = envelope()

        class Subclass(
            ExternalVisionHTTPResponseEnvelope
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
                "^external_vision_http_response_envelope_invalid$",
            ):
                validate_external_vision_http_response_envelope(
                    value
                )

    def test_detached_roundtrips(self):
        value = envelope()

        variants = [
            copy.copy(
                value
            ),
            copy.deepcopy(
                value
            ),
            pickle.loads(
                pickle.dumps(
                    value
                )
            ),
        ]

        for variant in variants:
            self.assertEqual(
                validate_external_vision_http_response_envelope(
                    variant
                ),
                value,
            )

    def test_success(self):
        result = self.read()

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertIs(
            result.encoding,
            ExternalVisionTransportResponseEncoding
            .UTF8_TEXT,
        )

        self.assertEqual(
            result.body,
            body(),
        )

        self.assertEqual(
            result.body_length,
            len(
                body()
            ),
        )

    def test_json_utf8_content_type_accepted(self):
        value = dataclasses.replace(
            envelope(),
            content_type=(
                "application/json; charset=utf-8"
            ),
        )

        result = self.read(
            envelope_value=value
        )

        self.assertEqual(
            result.body,
            value.body,
        )

    def test_content_type_comparison_is_case_insensitive(self):
        value = dataclasses.replace(
            envelope(),
            content_type=(
                "Application/JSON; Charset=UTF-8"
            ),
        )

        result = self.read(
            envelope_value=value
        )

        self.assertEqual(
            result.body,
            value.body,
        )

    def test_invalid_content_type_mapping(self):
        value = dataclasses.replace(
            envelope(),
            content_type="text/plain",
        )

        self.failure(
            _HTTPResponseReadFailureCode
            .CONTENT_TYPE_INVALID,
            envelope_value=value,
        )

    def test_non_200_status_mapping(self):
        for status in (
            201,
            400,
            401,
            403,
            404,
            429,
            500,
            503,
        ):
            value = dataclasses.replace(
                envelope(),
                status_code=status,
            )

            with self.subTest(
                status=status
            ):
                self.failure(
                    _HTTPResponseReadFailureCode
                    .HTTP_STATUS_INVALID,
                    envelope_value=value,
                )

    def test_invalid_config_mapping(self):
        invalid = dataclasses.replace(
            config(),
            endpoint=(
                "http://vision.example.test/v1/analyze"
            ),
        )

        self.failure(
            _HTTPResponseReadFailureCode
            .CONFIG_INVALID,
            config_value=invalid,
        )

    def test_response_limit_argument_contract(self):
        for limit in (
            0,
            -1,
            True,
        ):
            with self.subTest(
                limit=limit
            ):
                self.failure(
                    _HTTPResponseReadFailureCode
                    .RESOURCE_LIMIT_EXCEEDED,
                    max_response_bytes=limit,
                )

    def test_response_limit_must_not_exceed_config(self):
        config_value = dataclasses.replace(
            config(),
            max_response_bytes=100,
        )

        self.failure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
            config_value=config_value,
            max_response_bytes=101,
        )

    def test_body_must_fit_request_response_limit(self):
        value = envelope()

        self.failure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
            envelope_value=value,
            max_response_bytes=1,
        )

    def test_invalid_utf8_mapping(self):
        raw = b"\xff\xfe\xff"

        value = dataclasses.replace(
            envelope(),
            body=raw,
            body_length=len(
                raw
            ),
        )

        self.failure(
            _HTTPResponseReadFailureCode
            .RESPONSE_INVALID,
            envelope_value=value,
        )

    def test_memory_error_during_envelope_validation_mapping(self):
        with patch.object(
            reader_module,
            "validate_external_vision_http_response_envelope",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPResponseReadFailure
            ) as caught:
                self.read()

        self.assertIs(
            caught.exception.code,
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_memory_error_during_config_validation_mapping(self):
        with patch.object(
            reader_module,
            "validate_external_vision_http_config",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPResponseReadFailure
            ) as caught:
                self.read()

        self.assertIs(
            caught.exception.code,
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_output_validation_failure_mapping(self):
        with patch.object(
            reader_module,
            "validate_external_vision_transport_response",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _HTTPResponseReadFailure
            ) as caught:
                self.read()

        self.assertIs(
            caught.exception.code,
            _HTTPResponseReadFailureCode
            .RESPONSE_INVALID,
        )

    def test_output_validation_memory_error_mapping(self):
        with patch.object(
            reader_module,
            "validate_external_vision_transport_response",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPResponseReadFailure
            ) as caught:
                self.read()

        self.assertIs(
            caught.exception.code,
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_check_is_used_repeatedly(self):
        calls = [0]

        def check():
            calls[0] += 1

        result = self.read(
            check=check
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertGreaterEqual(
            calls[0],
            4,
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
            self.read(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.read(
                check=check
            )

    def test_failure_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^http_response_read_failure_invalid$",
        ):
            _HTTPResponseReadFailure(
                "RESPONSE_INVALID"
            )

    def test_content_type_enum_is_stable(self):
        self.assertEqual(
            {
                value.value
                for value
                in ExternalVisionHTTPResponseContentType
            },
            {
                "application/json",
                "application/json; charset=utf-8",
            },
        )


if __name__ == "__main__":
    unittest.main()