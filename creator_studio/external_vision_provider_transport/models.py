"""Detached external vision provider transport models.

These objects contain bounded data only. Possession grants no source
execution authority and carries no provider credentials.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..bounded_vision_provider_payload import (
    BoundedVisionProviderPayload,
    validate_bounded_vision_provider_payload,
)
from ..semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
)


EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION = 1

MAX_EXTERNAL_VISION_RESPONSE_BYTES = 256 * 1024


class ExternalVisionTransportInstruction(str, Enum):
    STRUCTURED_SEMANTIC_VISION_V1 = (
        "STRUCTURED_SEMANTIC_VISION_V1"
    )


class ExternalVisionTransportResponseEncoding(str, Enum):
    UTF8_TEXT = "UTF8_TEXT"


@dataclass(frozen=True)
class ExternalVisionTransportRequest:
    schema_version: int
    payload: BoundedVisionProviderPayload
    instruction: ExternalVisionTransportInstruction
    response_schema_version: int
    max_response_bytes: int


@dataclass(frozen=True)
class ExternalVisionTransportResponse:
    schema_version: int
    encoding: ExternalVisionTransportResponseEncoding
    body_length: int
    body: bytes


def _validate_exact_shape(value, expected_type):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(expected_type)
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def validate_external_vision_transport_request(request):
    """
    Validate one detached bounded request for a future external transport.

    Validation does not establish source authority and performs no network
    access.
    """
    try:
        _validate_exact_shape(
            request,
            ExternalVisionTransportRequest,
        )

        if (
            type(request.schema_version) is not int
            or request.schema_version
            != EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ):
            raise ValueError()

        validate_bounded_vision_provider_payload(
            request.payload
        )

        if (
            type(request.payload)
            is not BoundedVisionProviderPayload
        ):
            raise ValueError()

        if (
            type(request.instruction)
            is not ExternalVisionTransportInstruction
            or request.instruction
            is not ExternalVisionTransportInstruction
            .STRUCTURED_SEMANTIC_VISION_V1
        ):
            raise ValueError()

        if (
            type(request.response_schema_version)
            is not int
            or request.response_schema_version
            != SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(request.max_response_bytes)
            is not int
            or request.max_response_bytes <= 0
            or request.max_response_bytes
            > MAX_EXTERNAL_VISION_RESPONSE_BYTES
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "external_vision_transport_request_invalid"
        ) from None

    return request


def validate_external_vision_transport_response(response):
    """
    Validate one detached bounded response returned by a future transport.

    The response body remains opaque UTF-8 text at this layer. Semantic
    interpretation belongs to a later parser.
    """
    try:
        _validate_exact_shape(
            response,
            ExternalVisionTransportResponse,
        )

        if (
            type(response.schema_version) is not int
            or response.schema_version
            != EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(response.encoding)
            is not ExternalVisionTransportResponseEncoding
            or response.encoding
            is not ExternalVisionTransportResponseEncoding.UTF8_TEXT
        ):
            raise ValueError()

        if type(response.body_length) is not int:
            raise ValueError()

        if (
            response.body_length <= 0
            or response.body_length
            > MAX_EXTERNAL_VISION_RESPONSE_BYTES
        ):
            raise ValueError()

        if type(response.body) is not bytes:
            raise ValueError()

        if (
            len(response.body)
            != response.body_length
        ):
            raise ValueError()

        text = response.body.decode(
            "utf-8",
            errors="strict",
        )

        if not text.strip():
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "external_vision_transport_response_invalid"
        ) from None

    return response