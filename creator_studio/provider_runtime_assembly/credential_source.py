"""M90 runtime environment credential source.

This module resolves provider API credentials from environment variables only
when the runtime actually needs them.

Security properties:

- no API secret is accepted by the constructor;
- no API secret is persisted in the source object;
- environment variables are read only during resolve();
- every resolve() performs a fresh environment lookup;
- provider credentials are returned through the existing M88 runtime-only
  credential object;
- missing or invalid secrets are normalized through the M88 credential
  failure contract;
- no network access is performed here.

This module grants no source-snapshot authority.
"""

import os
from enum import Enum

from ..external_vision_http_transport import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)


MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH = 128


class ProviderEnvironmentCredentialMode(
    str,
    Enum,
):
    BEARER = "BEARER"
    RAW = "RAW"


def _validate_environment_variable_name(
    value,
):
    if type(value) is not str:
        raise ValueError()

    if (
        not value
        or value != value.strip()
        or len(value)
        > MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH
    ):
        raise ValueError()

    first = value[
        0
    ]

    if not (
        first == "_"
        or (
            "A"
            <= first
            <= "Z"
        )
    ):
        raise ValueError()

    for character in value:
        if (
            character == "_"
            or (
                "A"
                <= character
                <= "Z"
            )
            or (
                "0"
                <= character
                <= "9"
            )
        ):
            continue

        raise ValueError()


def _validate_raw_secret(
    value,
):
    if type(value) is not str:
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    if (
        not value
        or value != value.strip()
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    for character in value:
        code = ord(
            character
        )

        if (
            code <= 32
            or code > 126
        ):
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            )


class EnvironmentCredentialSource(
    ExternalVisionHTTPCredentialSource
):
    """
    Resolve one provider credential from one named environment variable.

    Only metadata is retained:
    - environment variable name;
    - HTTP credential header;
    - credential formatting mode.

    The resolved secret itself is never stored on this object.
    """

    __slots__ = (
        "_environment_variable",
        "_header",
        "_mode",
    )

    def __init__(
        self,
        environment_variable,
        header,
        mode,
    ):
        try:
            _validate_environment_variable_name(
                environment_variable
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "environment_credential_source_invalid"
            ) from None

        if (
            type(header)
            is not ExternalVisionHTTPCredentialHeader
        ):
            raise ValueError(
                "environment_credential_source_invalid"
            )

        if (
            type(mode)
            is not ProviderEnvironmentCredentialMode
        ):
            raise ValueError(
                "environment_credential_source_invalid"
            )

        if (
            mode
            is ProviderEnvironmentCredentialMode
            .BEARER
        ):
            if (
                header
                is not ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION
            ):
                raise ValueError(
                    "environment_credential_source_invalid"
                )

        elif (
            mode
            is ProviderEnvironmentCredentialMode
            .RAW
        ):
            if (
                header
                is ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION
            ):
                raise ValueError(
                    "environment_credential_source_invalid"
                )

        else:
            raise ValueError(
                "environment_credential_source_invalid"
            )

        self._environment_variable = (
            environment_variable
        )

        self._header = header
        self._mode = mode

    @property
    def environment_variable(
        self,
    ):
        return self._environment_variable

    @property
    def header(
        self,
    ):
        return self._header

    @property
    def mode(
        self,
    ):
        return self._mode

    def __repr__(
        self,
    ):
        return (
            "EnvironmentCredentialSource("
            f"environment_variable="
            f"{self._environment_variable!r}, "
            f"header={self._header.value!r}, "
            f"mode={self._mode.value!r})"
        )

    def resolve(
        self,
        check,
    ):
        check()

        try:
            raw_secret = os.getenv(
                self._environment_variable
            )

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

        if raw_secret is None:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            )

        if raw_secret == "":
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            )

        _validate_raw_secret(
            raw_secret
        )

        check()

        try:
            if (
                self._mode
                is ProviderEnvironmentCredentialMode
                .BEARER
            ):
                credential_value = (
                    "Bearer "
                    + raw_secret
                )

            elif (
                self._mode
                is ProviderEnvironmentCredentialMode
                .RAW
            ):
                credential_value = (
                    raw_secret
                )

            else:
                raise ExternalVisionHTTPCredentialFailure(
                    ExternalVisionHTTPCredentialFailureCode
                    .INTERNAL_FAILURE
                )

            credential = (
                ExternalVisionHTTPCredential(
                    self._header,
                    credential_value,
                )
            )

        except ExternalVisionHTTPCredentialFailure:
            raise

        except MemoryError:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except ValueError:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            ) from None

        except Exception:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE
            ) from None

        check()

        return credential