"""M88 external vision HTTP transport configuration contract.

Configuration is detached immutable data only. It contains no API keys,
tokens, passwords, source authority, runtime objects, file paths, or handles.

This module performs no network access.
"""

from dataclasses import dataclass, fields
from enum import Enum
from urllib.parse import urlsplit

from ..external_vision_provider_transport import (
    MAX_EXTERNAL_VISION_RESPONSE_BYTES,
)


EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION = 1

MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH = 2048

MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS = 100
MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS = 30_000

MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES = (
    10 * 1024 * 1024
)

MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES = (
    MAX_EXTERNAL_VISION_RESPONSE_BYTES
)


class ExternalVisionHTTPHeaderPolicy(str, Enum):
    STRICT_JSON_V1 = "STRICT_JSON_V1"


@dataclass(frozen=True)
class ExternalVisionHTTPConfig:
    schema_version: int
    endpoint: str
    timeout_millis: int
    max_request_bytes: int
    max_response_bytes: int
    header_policy: ExternalVisionHTTPHeaderPolicy


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


def _validate_endpoint(endpoint):
    if type(endpoint) is not str:
        raise ValueError()

    if (
        not endpoint
        or endpoint != endpoint.strip()
        or len(endpoint)
        > MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH
    ):
        raise ValueError()

    parsed = urlsplit(
        endpoint
    )

    if parsed.scheme.lower() != "https":
        raise ValueError()

    if not parsed.netloc:
        raise ValueError()

    if (
        parsed.hostname is None
        or not parsed.hostname
    ):
        raise ValueError()

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError()

    if parsed.query:
        raise ValueError()

    if parsed.fragment:
        raise ValueError()

    try:
        port = parsed.port

    except ValueError:
        raise ValueError() from None

    if (
        port is not None
        and (
            type(port) is not int
            or port <= 0
            or port > 65535
        )
    ):
        raise ValueError()


def validate_external_vision_http_config(
    config,
):
    """
    Validate one immutable bounded HTTP configuration.

    This validator performs no DNS resolution and no network access.
    """
    try:
        _validate_exact_shape(
            config,
            ExternalVisionHTTPConfig,
        )

        if (
            type(config.schema_version) is not int
            or config.schema_version
            != EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION
        ):
            raise ValueError()

        _validate_endpoint(
            config.endpoint
        )

        if (
            type(config.timeout_millis) is not int
            or config.timeout_millis
            < MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
            or config.timeout_millis
            > MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
        ):
            raise ValueError()

        if (
            type(config.max_request_bytes) is not int
            or config.max_request_bytes <= 0
            or config.max_request_bytes
            > MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
        ):
            raise ValueError()

        if (
            type(config.max_response_bytes) is not int
            or config.max_response_bytes <= 0
            or config.max_response_bytes
            > MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
        ):
            raise ValueError()

        if (
            type(config.header_policy)
            is not ExternalVisionHTTPHeaderPolicy
            or config.header_policy
            is not ExternalVisionHTTPHeaderPolicy
            .STRICT_JSON_V1
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "external_vision_http_config_invalid"
        ) from None

    return config