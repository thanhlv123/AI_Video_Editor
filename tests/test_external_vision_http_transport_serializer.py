"""M88 deterministic external vision HTTP request serializer."""

import base64
import dataclasses
import json
import unittest
from unittest.mock import patch

import creator_studio.external_vision_http_transport.serializer as serializer_module

from creator_studio.external_vision_http_transport.serializer import (
    _HTTPRequestSerializeFailure,
    _HTTPRequestSerializeFailureCode,
    _serialize_http_request,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_provider_transport_models import (
    request,
)


class ExternalVisionHTTPTransportSerializerTests(
    unittest.TestCase
):

    def serialize(
        self,
        request_value=None,
        config_value=None,
        check=None,
    ):
        if request_value is None:
            request_value = request()

        if config_value is None:
            config_value = config()

        if check is None:
            check = lambda: None

        return _serialize_http_request(
            request_value,
            config_value,
            check,
        )

    def failure(
        self,
        expected,
        request_value=None,
        config_value=None,
    ):
        if request_value is None:
            request_value = request()

        if config_value is None:
            config_value = config()

        with self.assertRaises(
            _HTTPRequestSerializeFailure
        ) as caught:
            _serialize_http_request(
                request_value,
                config_value,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_success_returns_exact_bytes(self):
        body = self.serialize()

        self.assertIs(
            type(body),
            bytes,
        )

        self.assertGreater(
            len(body),
            0,
        )

    def test_deterministic(self):
        request_value = request()
        config_value = config()

        first = self.serialize(
            request_value,
            config_value,
        )

        second = self.serialize(
            request_value,
            config_value,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_json_is_canonical(self):
        body = self.serialize()

        document = json.loads(
            body.decode(
                "utf-8"
            )
        )

        canonical = json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        self.assertEqual(
            body,
            canonical,
        )

    def test_image_roundtrip(self):
        request_value = request()

        body = self.serialize(
            request_value
        )

        document = json.loads(
            body.decode(
                "utf-8"
            )
        )

        encoded = document[
            "payload"
        ][
            "image_base64"
        ]

        recovered = base64.b64decode(
            encoded,
            validate=True,
        )

        self.assertEqual(
            recovered,
            request_value.payload.image_bytes,
        )

    def test_payload_metadata_is_preserved(self):
        request_value = request()

        body = self.serialize(
            request_value
        )

        document = json.loads(
            body.decode(
                "utf-8"
            )
        )

        payload = document[
            "payload"
        ]

        self.assertEqual(
            payload[
                "schema_version"
            ],
            request_value.payload.schema_version,
        )

        self.assertEqual(
            payload[
                "encoding"
            ],
            request_value.payload.encoding.value,
        )

        self.assertEqual(
            payload[
                "width"
            ],
            request_value.payload.width,
        )

        self.assertEqual(
            payload[
                "height"
            ],
            request_value.payload.height,
        )

        self.assertEqual(
            payload[
                "byte_length"
            ],
            request_value.payload.byte_length,
        )

        self.assertNotIn(
            "image_bytes",
            payload,
        )

    def test_transport_metadata_is_preserved(self):
        request_value = request()

        document = json.loads(
            self.serialize(
                request_value
            ).decode(
                "utf-8"
            )
        )

        self.assertEqual(
            document[
                "schema_version"
            ],
            request_value.schema_version,
        )

        self.assertEqual(
            document[
                "instruction"
            ],
            request_value.instruction.value,
        )

        self.assertEqual(
            document[
                "response_schema_version"
            ],
            request_value.response_schema_version,
        )

        self.assertEqual(
            document[
                "max_response_bytes"
            ],
            request_value.max_response_bytes,
        )

    def test_evidence_is_serialized(self):
        request_value = request()

        document = json.loads(
            self.serialize(
                request_value
            ).decode(
                "utf-8"
            )
        )

        evidence = document[
            "payload"
        ][
            "evidence"
        ]

        self.assertIs(
            type(evidence),
            dict,
        )

        self.assertEqual(
            evidence[
                "schema_version"
            ],
            request_value.payload.evidence.schema_version,
        )

        luma_grid = evidence[
            "features"
        ][
            "luma_grid"
        ]

        self.assertIs(
            type(luma_grid),
            list,
        )

        self.assertEqual(
            luma_grid,
            list(
                request_value
                .payload
                .evidence
                .features
                .luma_grid
            ),
        )

        self.assertTrue(
            all(
                type(value) is int
                and 0 <= value <= 255
                for value in luma_grid
            )
        )

    def test_invalid_request_mapping(self):
        invalid = dataclasses.replace(
            request(),
            response_schema_version=2,
        )

        self.failure(
            _HTTPRequestSerializeFailureCode
            .REQUEST_INVALID,
            request_value=invalid,
        )

    def test_invalid_config_mapping(self):
        invalid = dataclasses.replace(
            config(),
            endpoint=(
                "http://vision.example.test/v1/analyze"
            ),
        )

        self.failure(
            _HTTPRequestSerializeFailureCode
            .CONFIG_INVALID,
            config_value=invalid,
        )

    def test_response_limit_coherence(self):
        config_value = dataclasses.replace(
            config(),
            max_response_bytes=1,
        )

        self.failure(
            _HTTPRequestSerializeFailureCode
            .COHERENCE_INVALID,
            config_value=config_value,
        )

    def test_request_body_limit(self):
        config_value = dataclasses.replace(
            config(),
            max_request_bytes=1,
        )

        self.failure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
            config_value=config_value,
        )

    def test_memory_error_during_request_validation_mapping(self):
        with patch.object(
            serializer_module,
            "validate_external_vision_transport_request",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPRequestSerializeFailure
            ) as caught:
                self.serialize()

        self.assertIs(
            caught.exception.code,
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_memory_error_during_config_validation_mapping(self):
        with patch.object(
            serializer_module,
            "validate_external_vision_http_config",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPRequestSerializeFailure
            ) as caught:
                self.serialize()

        self.assertIs(
            caught.exception.code,
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_json_serialization_failure_mapping(self):
        with patch.object(
            serializer_module.json,
            "dumps",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _HTTPRequestSerializeFailure
            ) as caught:
                self.serialize()

        self.assertIs(
            caught.exception.code,
            _HTTPRequestSerializeFailureCode
            .SERIALIZATION_INVALID,
        )

    def test_json_memory_error_mapping(self):
        with patch.object(
            serializer_module.json,
            "dumps",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _HTTPRequestSerializeFailure
            ) as caught:
                self.serialize()

        self.assertIs(
            caught.exception.code,
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_check_is_used_repeatedly(self):
        calls = [0]

        def check():
            calls[0] += 1

        body = self.serialize(
            check=check
        )

        self.assertIs(
            type(body),
            bytes,
        )

        self.assertGreater(
            calls[0],
            5,
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
            self.serialize(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.serialize(
                check=check
            )

    def test_failure_code_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^http_request_serialize_failure_invalid$",
        ):
            _HTTPRequestSerializeFailure(
                "REQUEST_INVALID"
            )


if __name__ == "__main__":
    unittest.main()