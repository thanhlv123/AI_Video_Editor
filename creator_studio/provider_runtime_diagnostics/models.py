"""M93 provider runtime diagnostics result contract.

This module defines the detached, secret-free result returned by the M93
provider runtime diagnostics coordinator.

M93 coordinates two existing diagnostic layers:

OFFLINE:
    M91 provider runtime readiness only.

ONLINE:
    M91 provider runtime readiness first, followed by M92 provider
    connectivity only when readiness succeeds.

The result contains only diagnostic metadata:
- requested diagnostic mode;
- normalized diagnostic status;
- provider kind, when configuration is valid;
- credential environment variable name, when configuration is valid;
- HTTP status, when online connectivity reached an HTTP response;
- provider application code, when a provider wraps status inside HTTP 2xx.

The result never contains:
- credential values;
- Authorization header values;
- API key values;
- request bodies;
- response bodies.

This module performs no environment access and no network access.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..provider_runtime_assembly import (
    MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)


PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION = 1


class ProviderRuntimeDiagnosticMode(
    str,
    Enum,
):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class ProviderRuntimeDiagnosticStatus(
    str,
    Enum,
):
    READY = "READY"
    CONFIG_INVALID = "CONFIG_INVALID"
    CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
    CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
    REMOTE_DEPENDENCY_MISSING = (
        "REMOTE_DEPENDENCY_MISSING"
    )
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
class ProviderRuntimeDiagnosticReport:
    """Detached, secret-free provider runtime diagnostic result."""

    schema_version: int
    mode: ProviderRuntimeDiagnosticMode
    status: ProviderRuntimeDiagnosticStatus
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


def _validate_provider_code_owner(
    report,
):
    if report.provider_code is None:
        return

    if (
        report.provider
        is not VisionProviderKind.KIE_AI
    ):
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

    _validate_provider_code_owner(
        report
    )

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


def _validate_online_ready(
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

    _validate_provider_code_owner(
        report
    )

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

    _validate_provider_code_owner(
        report
    )

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

    if report.provider_code is None:
        return

    _validate_provider_code_owner(
        report
    )

    _validate_status_integer(
        report.provider_code
    )

    if not (
        200
        <= report.http_status
        <= 299
    ):
        raise ValueError()


def _validate_remote_dependency_missing(
    report,
):
    _validate_no_remote_status(
        report
    )

    if (
        report.provider
        is not VisionProviderKind.KIE_AI
    ):
        raise ValueError()


def _validate_offline_semantics(
    report,
):
    allowed = (
        ProviderRuntimeDiagnosticStatus
        .READY,
        ProviderRuntimeDiagnosticStatus
        .CREDENTIAL_MISSING,
        ProviderRuntimeDiagnosticStatus
        .CREDENTIAL_INVALID,
        ProviderRuntimeDiagnosticStatus
        .REMOTE_DEPENDENCY_MISSING,
        ProviderRuntimeDiagnosticStatus
        .INTERNAL_FAILURE,
    )

    if (
        report.status
        not in allowed
    ):
        raise ValueError()

    if (
        report.status
        is ProviderRuntimeDiagnosticStatus
        .REMOTE_DEPENDENCY_MISSING
    ):
        _validate_remote_dependency_missing(
            report
        )

        return

    _validate_no_remote_status(
        report
    )


def _validate_online_semantics(
    report,
):
    status = report.status

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .READY
    ):
        _validate_online_ready(
            report
        )

        return

    if (
        status
        in (
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
            ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
            ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )
    ):
        _validate_no_remote_status(
            report
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .REMOTE_DEPENDENCY_MISSING
    ):
        _validate_remote_dependency_missing(
            report
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .AUTHENTICATION_FAILED
    ):
        _validate_direct_or_wrapped_status(
            report,
            401,
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .PERMISSION_DENIED
    ):
        _validate_direct_or_wrapped_status(
            report,
            403,
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .RATE_LIMITED
    ):
        _validate_direct_or_wrapped_status(
            report,
            429,
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .PROVIDER_UNAVAILABLE
    ):
        _validate_provider_unavailable(
            report
        )

        return

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .RESPONSE_INVALID
    ):
        _validate_response_invalid(
            report
        )

        return

    raise ValueError()


def validate_provider_runtime_diagnostic_report(
    report,
):
    """Validate one detached M93 provider runtime diagnostic report."""
    try:
        _validate_exact_shape(
            report,
            ProviderRuntimeDiagnosticReport,
        )

        if (
            type(report.schema_version)
            is not int
            or report.schema_version
            != PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(report.mode)
            is not ProviderRuntimeDiagnosticMode
        ):
            raise ValueError()

        if (
            type(report.status)
            is not ProviderRuntimeDiagnosticStatus
        ):
            raise ValueError()

        _validate_metadata(
            report
        )

        if (
            report.status
            is ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        ):
            _validate_config_invalid(
                report
            )

            return report

        _validate_runtime_metadata_required(
            report
        )

        if (
            report.mode
            is ProviderRuntimeDiagnosticMode
            .OFFLINE
        ):
            _validate_offline_semantics(
                report
            )

        elif (
            report.mode
            is ProviderRuntimeDiagnosticMode
            .ONLINE
        ):
            _validate_online_semantics(
                report
            )

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_diagnostic_report_invalid"
        ) from None

    return report