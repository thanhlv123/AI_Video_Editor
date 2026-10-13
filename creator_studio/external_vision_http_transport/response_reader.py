"""M88 bounded external vision HTTP response envelope and reader.

This module normalizes already-received HTTP response metadata and bytes into
the M87 transport response contract.

It performs no DNS resolution, socket operations, HTTP requests, or credential
handling.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..external_vision_provider_transport import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
    validate_external_vision_transport_response,
)
from .config import (
    ExternalVisionHTTPConfig,
    validate_external_vision_http_config,
)


MAX_EXTERNAL_VISION_HTTP_CONTENT_TYPE_LENGTH = 128


class ExternalVisionHTTPResponseContentType(str, Enum):
    APPLICATION_JSON = "application/json"
    APPLICATION_JSON_UTF8 = "application/json; charset=utf-8"


@dataclass(frozen=True)
class ExternalVisionHTTPResponseEnvelope:
    status_code: int
    content_type: str
    body_length: int
    body: bytes


class _HTTPResponseReadFailureCode(str, Enum):
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    CONFIG_INVALID = "CONFIG_INVALID"
    HTTP_STATUS_INVALID = "HTTP_STATUS_INVALID"
    CONTENT_TYPE_INVALID = "CONTENT_TYPE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    RESPONSE_INVALID = "RESPONSE_INVALID"


class _HTTPResponseReadFailure(Exception):
    def __init__(
        self,
        code,
    ):
        if type(code) is not _HTTPResponseReadFailureCode:
            raise ValueError(
                "http_response_read_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _validate_exact_shape(
    value,
    expected_type,
):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(
            expected_type
        )
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


def validate_external_vision_http_response_envelope(
    envelope,
):
    try:
        _validate_exact_shape(
            envelope,
            ExternalVisionHTTPResponseEnvelope,
        )

        if (
            type(envelope.status_code) is not int
            or envelope.status_code < 100
            or envelope.status_code > 599
        ):
            raise ValueError()

        if type(envelope.content_type) is not str:
            raise ValueError()

        if (
            not envelope.content_type
            or envelope.content_type
            != envelope.content_type.strip()
            or len(envelope.content_type)
            > MAX_EXTERNAL_VISION_HTTP_CONTENT_TYPE_LENGTH
        ):
            raise ValueError()

        if type(envelope.body_length) is not int:
            raise ValueError()

        if envelope.body_length <= 0:
            raise ValueError()

        if type(envelope.body) is not bytes:
            raise ValueError()

        if (
            len(envelope.body)
            != envelope.body_length
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "external_vision_http_response_envelope_invalid"
        ) from None

    return envelope


def _normalize_content_type(
    content_type,
):
    if type(content_type) is not str:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .CONTENT_TYPE_INVALID
        )

    lowered = content_type.lower()

    if (
        lowered
        == ExternalVisionHTTPResponseContentType
        .APPLICATION_JSON.value
    ):
        return (
            ExternalVisionHTTPResponseContentType
            .APPLICATION_JSON
        )

    if (
        lowered
        == ExternalVisionHTTPResponseContentType
        .APPLICATION_JSON_UTF8.value
    ):
        return (
            ExternalVisionHTTPResponseContentType
            .APPLICATION_JSON_UTF8
        )

    raise _HTTPResponseReadFailure(
        _HTTPResponseReadFailureCode
        .CONTENT_TYPE_INVALID
    )


def _read_http_response(
    envelope,
    config,
    max_response_bytes,
    check,
):
    """
    Normalize one already-received bounded HTTP response into the M87
    transport response model.
    """
    try:
        validate_external_vision_http_response_envelope(
            envelope
        )

    except MemoryError:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .ENVELOPE_INVALID
        ) from None

    if type(envelope) is not ExternalVisionHTTPResponseEnvelope:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .ENVELOPE_INVALID
        )

    try:
        validate_external_vision_http_config(
            config
        )

    except MemoryError:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .CONFIG_INVALID
        ) from None

    if type(config) is not ExternalVisionHTTPConfig:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .CONFIG_INVALID
        )

    if (
        type(max_response_bytes) is not int
        or max_response_bytes <= 0
        or max_response_bytes
        > config.max_response_bytes
    ):
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    check()

    if envelope.status_code != 200:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .HTTP_STATUS_INVALID
        )

    _normalize_content_type(
        envelope.content_type
    )

    check()

    if (
        envelope.body_length
        > max_response_bytes
        or envelope.body_length
        > config.max_response_bytes
    ):
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    try:
        envelope.body.decode(
            "utf-8",
            errors="strict",
        )

    except MemoryError:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except UnicodeDecodeError:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESPONSE_INVALID
        ) from None

    check()

    response = ExternalVisionTransportResponse(
        schema_version=(
            EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=(
            envelope.body_length
        ),
        body=(
            envelope.body
        ),
    )

    try:
        validate_external_vision_transport_response(
            response
        )

    except MemoryError:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _HTTPResponseReadFailure(
            _HTTPResponseReadFailureCode
            .RESPONSE_INVALID
        ) from None

    check()

    return response