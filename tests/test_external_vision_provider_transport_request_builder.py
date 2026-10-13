"""M87 deterministic external vision transport request builder."""

import dataclasses
import unittest
from unittest.mock import patch

from creator_studio.bounded_vision_provider_payload import (
    BoundedVisionProviderPayload,
)
import creator_studio.external_vision_provider_transport.request_builder as builder_module
from creator_studio.external_vision_provider_transport.models import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    MAX_EXTERNAL_VISION_RESPONSE_BYTES,
    ExternalVisionTransportInstruction,
    ExternalVisionTransportRequest,
    validate_external_vision_transport_request,
)
from creator_studio.external_vision_provider_transport.request_builder import (
    _TransportRequestBuildFailure,
    _TransportRequestBuildFailureCode,
    _build_transport_request,
)
from creator_studio.semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
)
from tests.test_external_vision_provider_transport_models import (
    payload,
)


class ExternalVisionTransportRequestBuilderTests(
    unittest.TestCase
):

    def build(
        self,
        payload_value=None,
        check=None,
    ):
        if payload_value is None:
            payload_value = payload()

        if check is None:
            check = lambda: None

        return _build_transport_request(
            payload_value,
            check,
        )

    def failure(
        self,
        payload_value,
        expected,
    ):
        with self.assertRaises(
            _TransportRequestBuildFailure
        ) as caught:
            _build_transport_request(
                payload_value,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_build_success(self):
        value = self.build()

        self.assertIs(
            type(value),
            ExternalVisionTransportRequest,
        )

        self.assertIs(
            validate_external_vision_transport_request(
                value
            ),
            value,
        )

    def test_deterministic(self):
        payload_value = payload()

        first = self.build(
            payload_value
        )

        second = self.build(
            payload_value
        )

        self.assertEqual(
            first,
            second,
        )

    def test_schema_version_is_exact(self):
        value = self.build()

        self.assertEqual(
            value.schema_version,
            EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
        )

        self.assertEqual(
            value.schema_version,
            1,
        )

    def test_instruction_is_exact(self):
        value = self.build()

        self.assertIs(
            value.instruction,
            ExternalVisionTransportInstruction
            .STRUCTURED_SEMANTIC_VISION_V1,
        )

    def test_response_schema_version_is_exact(self):
        value = self.build()

        self.assertEqual(
            value.response_schema_version,
            SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
        )

        self.assertEqual(
            value.response_schema_version,
            1,
        )

    def test_response_byte_limit_is_exact(self):
        value = self.build()

        self.assertEqual(
            value.max_response_bytes,
            MAX_EXTERNAL_VISION_RESPONSE_BYTES,
        )

        self.assertEqual(
            value.max_response_bytes,
            256 * 1024,
        )

    def test_payload_identity_is_preserved(self):
        payload_value = payload()

        value = self.build(
            payload_value
        )

        self.assertIs(
            value.payload,
            payload_value,
        )

    def test_invalid_payload_rejected(self):
        invalid = dataclasses.replace(
            payload(),
            byte_length=1,
        )

        self.failure(
            invalid,
            _TransportRequestBuildFailureCode
            .PAYLOAD_INVALID,
        )

    def test_exact_payload_type_required(self):
        base = payload()

        class Subclass(
            BoundedVisionProviderPayload
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        self.failure(
            subclass,
            _TransportRequestBuildFailureCode
            .PAYLOAD_INVALID,
        )

    def test_memory_error_during_payload_validation_mapping(self):
        with patch.object(
            builder_module,
            "validate_bounded_vision_provider_payload",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _TransportRequestBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _TransportRequestBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_output_validation_failure_mapping(self):
        with patch.object(
            builder_module,
            "validate_external_vision_transport_request",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _TransportRequestBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _TransportRequestBuildFailureCode
            .REQUEST_INVALID,
        )

    def test_memory_error_during_output_validation_mapping(self):
        with patch.object(
            builder_module,
            "validate_external_vision_transport_request",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _TransportRequestBuildFailure
            ) as caught:
                self.build()

        self.assertIs(
            caught.exception.code,
            _TransportRequestBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_check_is_used(self):
        calls = [0]

        def check():
            calls[0] += 1

        value = self.build(
            check=check
        )

        self.assertIs(
            type(value),
            ExternalVisionTransportRequest,
        )

        self.assertGreaterEqual(
            calls[0],
            2,
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
            self.build(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.build(
                check=check
            )

    def test_failure_code_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^transport_request_build_failure_invalid$",
        ):
            _TransportRequestBuildFailure(
                "PAYLOAD_INVALID"
            )


if __name__ == "__main__":
    unittest.main()