"""M87 external vision provider transport interface contract."""

import inspect
import unittest

from creator_studio.external_vision_provider_transport.models import (
    ExternalVisionTransportResponse,
)
from creator_studio.external_vision_provider_transport.transport_contract import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    _invoke_transport,
)
from tests.test_external_vision_provider_transport_models import (
    request,
    response,
)


class ValidTransport(
    ExternalVisionTransport
):
    def __init__(self):
        self.requests = []
        self.checks = []

    def send(
        self,
        request_value,
        check,
    ):
        self.requests.append(
            request_value
        )

        self.checks.append(
            check
        )

        check()

        return response()


class UnavailableTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request_value,
        check,
    ):
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode.UNAVAILABLE
        )


class InvalidResponseTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request_value,
        check,
    ):
        return object()


class MemoryTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request_value,
        check,
    ):
        raise MemoryError()


class ErrorTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request_value,
        check,
    ):
        raise RuntimeError(
            "private"
        )


class InterruptTransport(
    ExternalVisionTransport
):
    def send(
        self,
        request_value,
        check,
    ):
        raise KeyboardInterrupt()


class ExternalVisionProviderTransportContractTests(
    unittest.TestCase
):

    def test_base_transport_is_abstract(self):
        with self.assertRaises(
            TypeError
        ):
            ExternalVisionTransport()

    def test_transport_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionTransport.send
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
            ),
        )

    def test_success(self):
        transport = ValidTransport()

        result = _invoke_transport(
            transport,
            request(),
            lambda: None,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertEqual(
            result,
            response(),
        )

    def test_transport_receives_request_identity(self):
        transport = ValidTransport()
        value = request()

        _invoke_transport(
            transport,
            value,
            lambda: None,
        )

        self.assertEqual(
            len(transport.requests),
            1,
        )

        self.assertIs(
            transport.requests[0],
            value,
        )

    def test_transport_receives_check_identity(self):
        transport = ValidTransport()

        def check():
            pass

        _invoke_transport(
            transport,
            request(),
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

    def test_check_is_used_before_during_and_after(self):
        transport = ValidTransport()
        calls = [0]

        def check():
            calls[0] += 1

        _invoke_transport(
            transport,
            request(),
            check,
        )

        self.assertGreaterEqual(
            calls[0],
            3,
        )

    def test_invalid_transport_is_unavailable(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                object(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode.UNAVAILABLE,
        )

    def test_invalid_request_mapping(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                ValidTransport(),
                object(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode.REQUEST_INVALID,
        )

    def test_transport_failure_is_preserved(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                UnavailableTransport(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode.UNAVAILABLE,
        )

    def test_invalid_response_mapping(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                InvalidResponseTransport(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode.RESPONSE_INVALID,
        )

    def test_memory_failure_mapping(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                MemoryTransport(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_exception_mapping(self):
        with self.assertRaises(
            ExternalVisionTransportFailure
        ) as caught:
            _invoke_transport(
                ErrorTransport(),
                request(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionTransportFailureCode.INTERNAL_FAILURE,
        )

    def test_baseexception_not_swallowed(self):
        with self.assertRaises(
            KeyboardInterrupt
        ):
            _invoke_transport(
                InterruptTransport(),
                request(),
                lambda: None,
            )

    def test_check_failure_before_transport_not_swallowed(self):
        transport = ValidTransport()

        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            _invoke_transport(
                transport,
                request(),
                check,
            )

        self.assertEqual(
            transport.requests,
            [],
        )

    def test_failure_requires_exact_code(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_transport_failure_invalid$",
        ):
            ExternalVisionTransportFailure(
                "UNAVAILABLE"
            )

    def test_failure_codes_are_stable(self):
        self.assertEqual(
            {
                code.value
                for code
                in ExternalVisionTransportFailureCode
            },
            {
                "UNAVAILABLE",
                "REQUEST_INVALID",
                "RESPONSE_INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()