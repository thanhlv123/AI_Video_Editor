"""Deterministic external vision transport request builder.

This module converts one detached bounded provider payload into one normalized
transport request. It performs no network access and carries no credentials.
"""

from enum import Enum

from ..bounded_vision_provider_payload import (
    BoundedVisionProviderPayload,
    validate_bounded_vision_provider_payload,
)
from ..semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
)
from .models import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    MAX_EXTERNAL_VISION_RESPONSE_BYTES,
    ExternalVisionTransportInstruction,
    ExternalVisionTransportRequest,
    validate_external_vision_transport_request,
)


class _TransportRequestBuildFailureCode(str, Enum):
    PAYLOAD_INVALID = "PAYLOAD_INVALID"
    REQUEST_INVALID = "REQUEST_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class _TransportRequestBuildFailure(Exception):
    def __init__(self, code):
        if type(code) is not _TransportRequestBuildFailureCode:
            raise ValueError(
                "transport_request_build_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _build_transport_request(
    payload,
    check,
):
    """
    Build one deterministic M87 transport request.

    The detached payload grants no source execution authority.
    """
    try:
        validate_bounded_vision_provider_payload(
            payload
        )

    except MemoryError:
        raise _TransportRequestBuildFailure(
            _TransportRequestBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _TransportRequestBuildFailure(
            _TransportRequestBuildFailureCode
            .PAYLOAD_INVALID
        ) from None

    if type(payload) is not BoundedVisionProviderPayload:
        raise _TransportRequestBuildFailure(
            _TransportRequestBuildFailureCode
            .PAYLOAD_INVALID
        )

    try:
        check()

        request = ExternalVisionTransportRequest(
            schema_version=(
                EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
            ),
            payload=payload,
            instruction=(
                ExternalVisionTransportInstruction
                .STRUCTURED_SEMANTIC_VISION_V1
            ),
            response_schema_version=(
                SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
            ),
            max_response_bytes=(
                MAX_EXTERNAL_VISION_RESPONSE_BYTES
            ),
        )

        try:
            validate_external_vision_transport_request(
                request
            )

        except MemoryError:
            raise

        except Exception:
            raise _TransportRequestBuildFailure(
                _TransportRequestBuildFailureCode
                .REQUEST_INVALID
            ) from None

        check()

        return request

    except _TransportRequestBuildFailure:
        raise

    except MemoryError:
        raise _TransportRequestBuildFailure(
            _TransportRequestBuildFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None