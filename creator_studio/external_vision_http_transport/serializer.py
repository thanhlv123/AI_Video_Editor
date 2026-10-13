"""M88 deterministic external vision HTTP request serializer.

This module converts one validated M87 transport request into one canonical
bounded UTF-8 JSON body suitable for a future HTTP implementation.

It performs no network access and handles no provider credentials.
"""

import base64
from dataclasses import fields, is_dataclass
from enum import Enum
import json

from ..external_vision_provider_transport import (
    ExternalVisionTransportRequest,
    validate_external_vision_transport_request,
)
from .config import (
    ExternalVisionHTTPConfig,
    validate_external_vision_http_config,
)


class _HTTPRequestSerializeFailureCode(str, Enum):
    REQUEST_INVALID = "REQUEST_INVALID"
    CONFIG_INVALID = "CONFIG_INVALID"
    COHERENCE_INVALID = "COHERENCE_INVALID"
    SERIALIZATION_INVALID = "SERIALIZATION_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class _HTTPRequestSerializeFailure(Exception):
    def __init__(
        self,
        code,
    ):
        if (
            type(code)
            is not _HTTPRequestSerializeFailureCode
        ):
            raise ValueError(
                "http_request_serialize_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _to_json_value(
    value,
    check,
):
    """
    Convert one already-validated detached evidence value into a JSON-safe
    deterministic structure.

    Validated byte sequences are represented as arrays of unsigned integers.
    Arbitrary unsupported objects are intentionally rejected.
    """
    check()

    if value is None:
        return None

    if type(value) is bool:
        return value

    if type(value) is int:
        return value

    if type(value) is str:
        return value

    if isinstance(
        value,
        Enum,
    ):
        enum_value = value.value

        if type(enum_value) is not str:
            raise _HTTPRequestSerializeFailure(
                _HTTPRequestSerializeFailureCode
                .SERIALIZATION_INVALID
            )

        return enum_value

    if type(value) is bytes:
        output = []

        for item in value:
            check()

            output.append(
                item
            )

        return output

    if type(value) is tuple:
        output = []

        for item in value:
            check()

            output.append(
                _to_json_value(
                    item,
                    check,
                )
            )

        return output

    if (
        is_dataclass(value)
        and not isinstance(
            value,
            type,
        )
    ):
        output = {}

        for field in fields(
            type(value)
        ):
            check()

            field_value = getattr(
                value,
                field.name,
            )

            output[
                field.name
            ] = _to_json_value(
                field_value,
                check,
            )

        return output

    raise _HTTPRequestSerializeFailure(
        _HTTPRequestSerializeFailureCode
        .SERIALIZATION_INVALID
    )


def _serialize_http_request(
    request,
    config,
    check,
):
    """
    Serialize one M87 request to one deterministic bounded JSON byte body.

    The resulting body grants no source execution authority.
    """
    try:
        validate_external_vision_transport_request(
            request
        )

    except MemoryError:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .REQUEST_INVALID
        ) from None

    if type(request) is not ExternalVisionTransportRequest:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .REQUEST_INVALID
        )

    try:
        validate_external_vision_http_config(
            config
        )

    except MemoryError:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .CONFIG_INVALID
        ) from None

    if type(config) is not ExternalVisionHTTPConfig:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .CONFIG_INVALID
        )

    check()

    if (
        request.max_response_bytes
        > config.max_response_bytes
    ):
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .COHERENCE_INVALID
        )

    try:
        image_base64 = base64.b64encode(
            request.payload.image_bytes
        ).decode(
            "ascii"
        )

    except MemoryError:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    check()

    evidence = _to_json_value(
        request.payload.evidence,
        check,
    )

    document = {
        "schema_version": (
            request.schema_version
        ),
        "instruction": (
            request.instruction.value
        ),
        "response_schema_version": (
            request.response_schema_version
        ),
        "max_response_bytes": (
            request.max_response_bytes
        ),
        "payload": {
            "schema_version": (
                request.payload.schema_version
            ),
            "encoding": (
                request.payload.encoding.value
            ),
            "width": (
                request.payload.width
            ),
            "height": (
                request.payload.height
            ),
            "byte_length": (
                request.payload.byte_length
            ),
            "image_base64": (
                image_base64
            ),
            "evidence": (
                evidence
            ),
        },
    }

    check()

    try:
        text = json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

        body = text.encode(
            "utf-8"
        )

    except MemoryError:
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .SERIALIZATION_INVALID
        ) from None

    check()

    if (
        not body
        or len(body)
        > config.max_request_bytes
    ):
        raise _HTTPRequestSerializeFailure(
            _HTTPRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    check()

    return body