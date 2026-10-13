"""M92 provider connectivity probe model contract.

This module defines detached, secret-free connectivity probe results.

The model contains only diagnostic metadata:
- one normalized connectivity status;
- provider kind, when configuration is valid;
- credential environment variable name, when configuration is valid;
- HTTP status code, when an HTTP response was actually received;
- provider application status code, when a provider wraps status inside a
  successful HTTP response.

The provider_code field exists because some providers, including the current
Kie.ai common API contract, may return HTTP 200 while reporting an application
error code inside the JSON response body.

The model never contains:
- a credential value;
- an Authorization header;
- an API key value;
- a request body;
- a response body.

No environment access is performed here.
No DNS resolution is performed here.
No network access is performed here.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..provider_runtime_assembly import (
    MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)


PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION = 1


class ProviderConnectivityProbeStatus(
    str,
    Enum,
):
    READY = "READY"
    CONFIG_INVALID = "CONFIG_INVALID"
    CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
    CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
    AUTHENTICATION_FAILED = (
        "AUTHENTICATION_FAILED"
    )
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = (
        "PROVIDER_UNAVAILABLE"
    )
    NETWORK_UNAVAILABLE = (
        "NETWORK_UNAVAILABLE"
    )
    DEADLINE_EXCEEDED = (
        "DEADLINE_EXCEEDED"
    )
    RESPONSE_INVALID = "RESPONSE_INVALID"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class ProviderConnectivityProbeReport:
    """Detached, secret-free provider connectivity result."""

    schema_version: int
    status: ProviderConnectivityProbeStatus
    provider: object
    credential_environment_variable: object
    http_status: object
    provider_code: object


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


def _validate_status_integer(
    value,
):
    if type(value) is not int:
        raise ValueError()

    if (
        value < 100
        or value > 599
    ):
        raise ValueError()


def _validate_metadata(
    report,
):
    provider_present = (
        report.provider is not None
    )

    environment_present = (
        report.credential_environment_variable
        is not None
    )

    if (
        provider_present
        != environment_present
    ):
        raise ValueError()

    if provider_present:
        if (
            type(report.provider)
            is not VisionProviderKind
        ):
            raise ValueError()

        _validate_environment_variable_name(
            report.credential_environment_variable
        )


def _validate_config_invalid(
    report,
):
    if report.provider is not None:
        raise ValueError()

    if (
        report.credential_environment_variable
        is not None
    ):
        raise ValueError()

    if report.http_status is not None:
        raise ValueError()

    if report.provider_code is not None:
        raise ValueError()


def _validate_runtime_metadata_required(
    report,
):
    if report.provider is None:
        raise ValueError()

    if (
        report.credential_environment_variable
        is None
    ):
        raise ValueError()


def _validate_no_remote_status(
    report,
):
    if report.http_status is not None:
        raise ValueError()

    if report.provider_code is not None:
        raise ValueError()


def _validate_direct_or_wrapped_status(
    report,
    expected_status,
):
    _validate_status_integer(
        report.http_status
    )

    if report.provider_code is None:
        if (
            report.http_status
            != expected_status
        ):
            raise ValueError()

        return

    _validate_status_integer(
        report.provider_code
    )

    if not (
        200
        <= report.http_status
        <= 299
    ):
        raise ValueError()

    if (
        report.provider_code
        != expected_status
    ):
        raise ValueError()


def _validate_ready(
    report,
):
    _validate_status_integer(
        report.http_status
    )

    if not (
        200
        <= report.http_status
        <= 299
    ):
        raise ValueError()

    if report.provider_code is None:
        return

    _validate_status_integer(
        report.provider_code
    )

    if not (
        200
        <= report.provider_code
        <= 299
    ):
        raise ValueError()


def _validate_provider_unavailable(
    report,
):
    _validate_status_integer(
        report.http_status
    )

    if report.provider_code is None:
        if not (
            500
            <= report.http_status
            <= 599
        ):
            raise ValueError()

        return

    _validate_status_integer(
        report.provider_code
    )

    if not (
        200
        <= report.http_status
        <= 299
    ):
        raise ValueError()

    if not (
        500
        <= report.provider_code
        <= 599
    ):
        raise ValueError()


def _validate_response_invalid(
    report,
):
    _validate_status_integer(
        report.http_status
    )

    if report.provider_code is not None:
        _validate_status_integer(
            report.provider_code
        )


def _validate_status_semantics(
    report,
):
    status = report.status

    if (
        status
        is ProviderConnectivityProbeStatus
        .READY
    ):
        _validate_ready(
            report
        )

        return

    if (
        status
        in (
            ProviderConnectivityProbeStatus
            .CREDENTIAL_MISSING,
            ProviderConnectivityProbeStatus
            .CREDENTIAL_INVALID,
            ProviderConnectivityProbeStatus
            .NETWORK_UNAVAILABLE,
            ProviderConnectivityProbeStatus
            .DEADLINE_EXCEEDED,
            ProviderConnectivityProbeStatus
            .INTERNAL_FAILURE,
        )
    ):
        _validate_no_remote_status(
            report
        )

        return

    if (
        status
        is ProviderConnectivityProbeStatus
        .AUTHENTICATION_FAILED
    ):
        _validate_direct_or_wrapped_status(
            report,
            401,
        )

        return

    if (
        status
        is ProviderConnectivityProbeStatus
        .PERMISSION_DENIED
    ):
        _validate_direct_or_wrapped_status(
            report,
            403,
        )

        return

    if (
        status
        is ProviderConnectivityProbeStatus
        .RATE_LIMITED
    ):
        _validate_direct_or_wrapped_status(
            report,
            429,
        )

        return

    if (
        status
        is ProviderConnectivityProbeStatus
        .PROVIDER_UNAVAILABLE
    ):
        _validate_provider_unavailable(
            report
        )

        return

    if (
        status
        is ProviderConnectivityProbeStatus
        .RESPONSE_INVALID
    ):
        _validate_response_invalid(
            report
        )

        return

    raise ValueError()


def validate_provider_connectivity_probe_report(
    report,
):
    """Validate one detached provider connectivity probe report."""
    try:
        _validate_exact_shape(
            report,
            ProviderConnectivityProbeReport,
        )

        if (
            type(report.schema_version)
            is not int
            or report.schema_version
            != PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(report.status)
            is not ProviderConnectivityProbeStatus
        ):
            raise ValueError()

        _validate_metadata(
            report
        )

        if (
            report.status
            is ProviderConnectivityProbeStatus
            .CONFIG_INVALID
        ):
            _validate_config_invalid(
                report
            )

            return report

        _validate_runtime_metadata_required(
            report
        )

        _validate_status_semantics(
            report
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_connectivity_probe_report_invalid"
        ) from None

    return report