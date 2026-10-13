"""M91 provider runtime readiness model contract.

This module defines detached readiness results for one provider runtime.

The model intentionally contains no API credential value.

A readiness report may contain only safe metadata:
- readiness outcome;
- normalized failure code;
- provider kind, when safely known;
- credential environment variable name, when safely known.

No environment access is performed here.
No credential resolution is performed here.
No DNS or network access is performed here.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..provider_runtime_assembly import (
    MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)


PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION = 1


class ProviderRuntimeReadinessOutcome(
    str,
    Enum,
):
    READY = "READY"
    NOT_READY = "NOT_READY"


class ProviderRuntimeReadinessFailureCode(
    str,
    Enum,
):
    CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
    CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
    CONFIG_INVALID = "CONFIG_INVALID"
    REMOTE_IMAGE_SOURCE_REQUIRED = (
        "REMOTE_IMAGE_SOURCE_REQUIRED"
    )
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class ProviderRuntimeReadinessReport:
    """Detached, secret-free provider readiness result."""

    schema_version: int
    outcome: ProviderRuntimeReadinessOutcome
    failure_code: object
    provider: object
    credential_environment_variable: object


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


def _validate_metadata_pair(
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


def _validate_ready_report(
    report,
):
    if report.failure_code is not None:
        raise ValueError()

    if report.provider is None:
        raise ValueError()

    if (
        report.credential_environment_variable
        is None
    ):
        raise ValueError()


def _validate_not_ready_report(
    report,
):
    if (
        type(report.failure_code)
        is not ProviderRuntimeReadinessFailureCode
    ):
        raise ValueError()

    code = report.failure_code

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .CONFIG_INVALID
    ):
        if report.provider is not None:
            raise ValueError()

        if (
            report.credential_environment_variable
            is not None
        ):
            raise ValueError()

        return

    if (
        code
        in (
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID,
            ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED,
        )
    ):
        if report.provider is None:
            raise ValueError()

        if (
            report.credential_environment_variable
            is None
        ):
            raise ValueError()

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .REMOTE_IMAGE_SOURCE_REQUIRED
    ):
        if (
            report.provider
            is not VisionProviderKind.KIE_AI
        ):
            raise ValueError()


def validate_provider_runtime_readiness_report(
    report,
):
    """Validate one detached provider runtime readiness report."""
    try:
        _validate_exact_shape(
            report,
            ProviderRuntimeReadinessReport,
        )

        if (
            type(report.schema_version)
            is not int
            or report.schema_version
            != PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(report.outcome)
            is not ProviderRuntimeReadinessOutcome
        ):
            raise ValueError()

        _validate_metadata_pair(
            report
        )

        if (
            report.outcome
            is ProviderRuntimeReadinessOutcome
            .READY
        ):
            _validate_ready_report(
                report
            )

        elif (
            report.outcome
            is ProviderRuntimeReadinessOutcome
            .NOT_READY
        ):
            _validate_not_ready_report(
                report
            )

        else:
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_readiness_report_invalid"
        ) from None

    return report