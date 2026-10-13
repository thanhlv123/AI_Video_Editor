"""M87 external vision provider transport model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.external_vision_provider_transport as api

from creator_studio.bounded_vision_provider_payload.builder import (
    _build_payload,
)
from creator_studio.semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
)
from tests.test_bounded_vision_provider_payload_builder import (
    evidence,
    raster,
)


class Hostile:
    def __getattribute__(self, name):
        raise AssertionError(
            "hostile access"
        )

    def __repr__(self):
        raise AssertionError(
            "hostile repr"
        )

    def __eq__(self, other):
        raise AssertionError(
            "hostile equality"
        )


def payload():
    return _build_payload(
        raster(),
        evidence(),
        lambda: None,
    )


def request():
    return api.ExternalVisionTransportRequest(
        schema_version=(
            api.EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        payload=payload(),
        instruction=(
            api.ExternalVisionTransportInstruction
            .STRUCTURED_SEMANTIC_VISION_V1
        ),
        response_schema_version=(
            SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ),
        max_response_bytes=(
            api.MAX_EXTERNAL_VISION_RESPONSE_BYTES
        ),
    )


def response():
    body = (
        b'{"scene_setting":"INDOOR"}'
    )

    return api.ExternalVisionTransportResponse(
        schema_version=(
            api.EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            api.ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=len(
            body
        ),
        body=body,
    )


class ExternalVisionProviderTransportModelTests(
    unittest.TestCase
):

    def test_valid_request(self):
        value = request()

        self.assertIs(
            api.validate_external_vision_transport_request(
                value
            ),
            value,
        )

    def test_request_is_frozen(self):
        value = request()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.max_response_bytes = 1

    def test_request_schema_version_contract(self):
        variants = [
            dataclasses.replace(
                request(),
                schema_version=0,
            ),
            dataclasses.replace(
                request(),
                schema_version=2,
            ),
            dataclasses.replace(
                request(),
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_transport_request_invalid$",
            ):
                api.validate_external_vision_transport_request(
                    value
                )

    def test_request_requires_valid_payload(self):
        invalid_payload = dataclasses.replace(
            payload(),
            byte_length=1,
        )

        value = dataclasses.replace(
            request(),
            payload=invalid_payload,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_request_invalid$",
        ):
            api.validate_external_vision_transport_request(
                value
            )

    def test_request_requires_exact_instruction_enum(self):
        value = dataclasses.replace(
            request(),
            instruction=(
                "STRUCTURED_SEMANTIC_VISION_V1"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_request_invalid$",
        ):
            api.validate_external_vision_transport_request(
                value
            )

    def test_response_schema_version_is_semantic_adapter_version(self):
        variants = [
            dataclasses.replace(
                request(),
                response_schema_version=0,
            ),
            dataclasses.replace(
                request(),
                response_schema_version=2,
            ),
            dataclasses.replace(
                request(),
                response_schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_transport_request_invalid$",
            ):
                api.validate_external_vision_transport_request(
                    value
                )

    def test_request_response_limit_contract(self):
        valid = dataclasses.replace(
            request(),
            max_response_bytes=1,
        )

        self.assertIs(
            api.validate_external_vision_transport_request(
                valid
            ),
            valid,
        )

        variants = [
            dataclasses.replace(
                request(),
                max_response_bytes=0,
            ),
            dataclasses.replace(
                request(),
                max_response_bytes=-1,
            ),
            dataclasses.replace(
                request(),
                max_response_bytes=True,
            ),
            dataclasses.replace(
                request(),
                max_response_bytes=(
                    api.MAX_EXTERNAL_VISION_RESPONSE_BYTES
                    + 1
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_transport_request_invalid$",
            ):
                api.validate_external_vision_transport_request(
                    value
                )

    def test_request_exact_shape(self):
        base = request()

        class Subclass(
            api.ExternalVisionTransportRequest
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
                "^external_vision_transport_request_invalid$",
            ):
                api.validate_external_vision_transport_request(
                    value
                )

    def test_valid_response(self):
        value = response()

        self.assertIs(
            api.validate_external_vision_transport_response(
                value
            ),
            value,
        )

    def test_response_is_frozen(self):
        value = response()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.body = b"x"

    def test_response_schema_contract(self):
        variants = [
            dataclasses.replace(
                response(),
                schema_version=0,
            ),
            dataclasses.replace(
                response(),
                schema_version=2,
            ),
            dataclasses.replace(
                response(),
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_transport_response_invalid$",
            ):
                api.validate_external_vision_transport_response(
                    value
                )

    def test_response_requires_exact_encoding_enum(self):
        value = dataclasses.replace(
            response(),
            encoding="UTF8_TEXT",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_response_invalid$",
        ):
            api.validate_external_vision_transport_response(
                value
            )

    def test_response_body_length_contract(self):
        variants = [
            dataclasses.replace(
                response(),
                body_length=0,
            ),
            dataclasses.replace(
                response(),
                body_length=-1,
            ),
            dataclasses.replace(
                response(),
                body_length=True,
            ),
            dataclasses.replace(
                response(),
                body_length=1,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_transport_response_invalid$",
            ):
                api.validate_external_vision_transport_response(
                    value
                )

    def test_response_requires_exact_bytes(self):
        value = dataclasses.replace(
            response(),
            body=bytearray(
                response().body
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_response_invalid$",
        ):
            api.validate_external_vision_transport_response(
                value
            )

    def test_response_requires_valid_utf8(self):
        body = b"\xff\xfe\xff"

        value = dataclasses.replace(
            response(),
            body=body,
            body_length=len(
                body
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_response_invalid$",
        ):
            api.validate_external_vision_transport_response(
                value
            )

    def test_response_rejects_whitespace_only_text(self):
        body = b" \r\n\t "

        value = dataclasses.replace(
            response(),
            body=body,
            body_length=len(
                body
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_response_invalid$",
        ):
            api.validate_external_vision_transport_response(
                value
            )

    def test_response_byte_limit(self):
        body = bytes(
            api.MAX_EXTERNAL_VISION_RESPONSE_BYTES
            + 1
        )

        value = dataclasses.replace(
            response(),
            body=body,
            body_length=len(
                body
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_response_invalid$",
        ):
            api.validate_external_vision_transport_response(
                value
            )

    def test_response_exact_shape(self):
        base = response()

        class Subclass(
            api.ExternalVisionTransportResponse
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
                "^external_vision_transport_response_invalid$",
            ):
                api.validate_external_vision_transport_response(
                    value
                )

    def test_detached_roundtrips(self):
        pairs = [
            (
                request(),
                api.validate_external_vision_transport_request,
            ),
            (
                response(),
                api.validate_external_vision_transport_response,
            ),
        ]

        for value, validator in pairs:
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
                    validator(
                        variant
                    ),
                    value,
                )

    def test_public_api(self):
        self.assertEqual(
            api.EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_EXTERNAL_VISION_RESPONSE_BYTES,
            256 * 1024,
        )

        self.assertEqual(
            api.__all__,
            (
                "EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION",
                "MAX_EXTERNAL_VISION_RESPONSE_BYTES",
                "ExternalVisionTransportInstruction",
                "ExternalVisionTransportRequest",
                "ExternalVisionTransportResponse",
                "ExternalVisionTransportResponseEncoding",
                "validate_external_vision_transport_request",
                "validate_external_vision_transport_response",
                "ExternalVisionTransport",
                "ExternalVisionTransportFailure",
                "ExternalVisionTransportFailureCode",
                "ExternalVisionSemanticProvider",
            ),
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.ExternalVisionTransportInstruction
            },
            {
                "STRUCTURED_SEMANTIC_VISION_V1",
            },
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.ExternalVisionTransportResponseEncoding
            },
            {
                "UTF8_TEXT",
            },
        )


if __name__ == "__main__":
    unittest.main()