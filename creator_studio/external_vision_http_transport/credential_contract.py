"""M88 runtime-only HTTP credential boundary.

Credentials are deliberately excluded from configuration models, transport
payloads, source snapshots, logs, and persistence.

This module performs no environment lookup and no network access.
"""

from abc import ABC, abstractmethod
from enum import Enum


MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH = 4096


class ExternalVisionHTTPCredentialHeader(str, Enum):
    AUTHORIZATION = "Authorization"
    X_API_KEY = "X-API-Key"
    API_KEY = "api-key"
    X_GOOG_API_KEY = "X-Goog-Api-Key"


class ExternalVisionHTTPCredentialFailureCode(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class ExternalVisionHTTPCredentialFailure(Exception):
    def __init__(
        self,
        code,
    ):
        if (
            type(code)
            is not ExternalVisionHTTPCredentialFailureCode
        ):
            raise ValueError(
                "external_vision_http_credential_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


class ExternalVisionHTTPCredential:
    """
    Runtime-only credential value.

    The secret can be read only by the execution layer through ``value``.
    String/repr output is always redacted and the object intentionally refuses
    ordinary copy/pickle operations.
    """

    __slots__ = (
        "_header",
        "_value",
    )

    def __init__(
        self,
        header,
        value,
    ):
        if (
            type(header)
            is not ExternalVisionHTTPCredentialHeader
        ):
            raise ValueError(
                "external_vision_http_credential_invalid"
            )

        if type(value) is not str:
            raise ValueError(
                "external_vision_http_credential_invalid"
            )

        if (
            not value
            or value != value.strip()
            or len(value)
            > MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH
        ):
            raise ValueError(
                "external_vision_http_credential_invalid"
            )

        for character in value:
            code = ord(
                character
            )

            if (
                code < 32
                or code > 126
            ):
                raise ValueError(
                    "external_vision_http_credential_invalid"
                )

        self._header = header
        self._value = value

    @property
    def header(self):
        return self._header

    @property
    def value(self):
        return self._value

    def __repr__(self):
        return (
            "ExternalVisionHTTPCredential(<redacted>)"
        )

    def __str__(self):
        return "<redacted>"

    def __copy__(self):
        raise TypeError(
            "external_vision_http_credential_noncopyable"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "external_vision_http_credential_noncopyable"
        )

    def __reduce__(self):
        raise TypeError(
            "external_vision_http_credential_nonserializable"
        )


class ExternalVisionHTTPCredentialSource(ABC):
    """Runtime source of one short-lived HTTP credential."""

    @abstractmethod
    def resolve(
        self,
        check,
    ):
        raise NotImplementedError


def _resolve_http_credential(
    source,
    check,
):
    """
    Resolve one runtime-only credential through the normalized boundary.

    No credential is persisted or logged by this function.
    """
    if not isinstance(
        source,
        ExternalVisionHTTPCredentialSource,
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .UNAVAILABLE
        )

    check()

    try:
        credential = source.resolve(
            check
        )

    except ExternalVisionHTTPCredentialFailure:
        raise

    except MemoryError:
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INTERNAL_FAILURE
        ) from None

    check()

    if (
        type(credential)
        is not ExternalVisionHTTPCredential
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    if (
        type(credential.header)
        is not ExternalVisionHTTPCredentialHeader
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    if type(credential.value) is not str:
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    if (
        not credential.value
        or credential.value
        != credential.value.strip()
        or len(
            credential.value
        )
        > MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    check()

    return credential