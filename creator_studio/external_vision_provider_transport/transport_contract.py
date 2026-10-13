"""Implementation-neutral external vision transport contract.

This module defines the boundary that future HTTP/API implementations must
obey. It performs no network access and carries no credentials.
"""

from abc import ABC, abstractmethod
from enum import Enum

from .models import (
    ExternalVisionTransportRequest,
    ExternalVisionTransportResponse,
    validate_external_vision_transport_request,
    validate_external_vision_transport_response,
)


class ExternalVisionTransportFailureCode(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    REQUEST_INVALID = "REQUEST_INVALID"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class ExternalVisionTransportFailure(Exception):
    """Normalized failure crossing the transport boundary."""

    def __init__(self, code):
        if type(code) is not ExternalVisionTransportFailureCode:
            raise ValueError(
                "external_vision_transport_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


class ExternalVisionTransport(ABC):
    """Implementation-neutral external vision transport."""

    @abstractmethod
    def send(self, request, check):
        """
        Send one bounded detached request.

        A concrete implementation may later use HTTP or another protocol.
        The request itself grants no source authority.
        """
        raise NotImplementedError


def _invoke_transport(
    transport,
    request,
    check,
):
    """
    Invoke one transport through the normalized contract.

    Source authority must already have been established before this boundary.
    """
    if not isinstance(
        transport,
        ExternalVisionTransport,
    ):
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode.UNAVAILABLE
        )

    try:
        validate_external_vision_transport_request(
            request
        )

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        ) from None

    if type(request) is not ExternalVisionTransportRequest:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        )

    check()

    try:
        response = transport.send(
            request,
            check,
        )

    except ExternalVisionTransportFailure:
        raise

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        ) from None

    check()

    try:
        validate_external_vision_transport_response(
            response
        )

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        ) from None

    if type(response) is not ExternalVisionTransportResponse:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        )

    return response