"""M94 provider diagnostics presentation model contract.

This module defines detached, secret-free presentation data derived from an
M93 ProviderRuntimeDiagnosticReport.

M94 presentation data is intended for GUI and CLI consumers. It preserves the
machine-readable M93 diagnostic state while adding stable presentation
metadata:

- severity;
- recommended user action;
- short display title;
- short display detail.

The presentation model never contains:
- credential values;
- Authorization header values;
- API key values;
- request bodies;
- response bodies.

The credential environment variable name is metadata only and may be shown to
the user, for example OPENAI_API_KEY.

This module performs:
- no environment lookup;
- no DNS resolution;
- no network access;
- no provider API request.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..provider_runtime_assembly import (
    MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
)
from ..provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)


PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION = 1

MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH = 80

MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH = 320


class ProviderDiagnosticPresentationSeverity(
    str,
    Enum,
):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProviderDiagnosticPresentationAction(
    str,
    Enum,
):
    NONE = "NONE"
    REVIEW_CONFIGURATION = "REVIEW_CONFIGURATION"
    CONFIGURE_CREDENTIAL = "CONFIGURE_CREDENTIAL"
    CHECK_CREDENTIAL = "CHECK_CREDENTIAL"
    ADD_REMOTE_SOURCE = "ADD_REMOTE_SOURCE"
    RETRY = "RETRY"
    CHECK_NETWORK = "CHECK_NETWORK"


@dataclass(frozen=True)
class ProviderDiagnosticPresentation:
    """Detached, secret-free presentation of one M93 diagnostic result."""

    schema_version: int
    mode: ProviderRuntimeDiagnosticMode
    diagnostic_status: ProviderRuntimeDiagnosticStatus
    severity: ProviderDiagnosticPresentationSeverity
    action: ProviderDiagnosticPresentationAction
    provider: object
    credential_environment_variable: object
    title: str
    detail: str


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


def _validate_metadata(
    presentation,
):
    provider_present = (
        presentation.provider is not None
    )

    environment_present = (
        presentation.credential_environment_variable
        is not None
    )

    if (
        provider_present
        != environment_present
    ):
        raise ValueError()

    if provider_present:
        if (
            type(presentation.provider)
            is not VisionProviderKind
        ):
            raise ValueError()

        _validate_environment_variable_name(
            presentation.credential_environment_variable
        )


def _validate_status_metadata(
    presentation,
):
    if (
        presentation.diagnostic_status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        if presentation.provider is not None:
            raise ValueError()

        if (
            presentation.credential_environment_variable
            is not None
        ):
            raise ValueError()

        return

    if presentation.provider is None:
        raise ValueError()

    if (
        presentation.credential_environment_variable
        is None
    ):
        raise ValueError()

    if (
        presentation.diagnostic_status
        is ProviderRuntimeDiagnosticStatus
        .REMOTE_DEPENDENCY_MISSING
        and presentation.provider
        is not VisionProviderKind.KIE_AI
    ):
        raise ValueError()


def _validate_mode_semantics(
    presentation,
):
    if (
        presentation.mode
        is ProviderRuntimeDiagnosticMode
        .ONLINE
    ):
        return

    if (
        presentation.mode
        is not ProviderRuntimeDiagnosticMode
        .OFFLINE
    ):
        raise ValueError()

    allowed = (
        ProviderRuntimeDiagnosticStatus
        .READY,
        ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID,
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
        presentation.diagnostic_status
        not in allowed
    ):
        raise ValueError()


def _validate_text(
    value,
    maximum_length,
):
    if type(value) is not str:
        raise ValueError()

    if (
        not value
        or value != value.strip()
        or len(value) > maximum_length
    ):
        raise ValueError()

    for character in value:
        if not character.isprintable():
            raise ValueError()


def validate_provider_diagnostic_presentation(
    presentation,
):
    """Validate one detached M94 provider diagnostic presentation."""
    try:
        _validate_exact_shape(
            presentation,
            ProviderDiagnosticPresentation,
        )

        if (
            type(presentation.schema_version)
            is not int
            or presentation.schema_version
            != PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(presentation.mode)
            is not ProviderRuntimeDiagnosticMode
        ):
            raise ValueError()

        if (
            type(presentation.diagnostic_status)
            is not ProviderRuntimeDiagnosticStatus
        ):
            raise ValueError()

        if (
            type(presentation.severity)
            is not ProviderDiagnosticPresentationSeverity
        ):
            raise ValueError()

        if (
            type(presentation.action)
            is not ProviderDiagnosticPresentationAction
        ):
            raise ValueError()

        _validate_metadata(
            presentation
        )

        _validate_status_metadata(
            presentation
        )

        _validate_mode_semantics(
            presentation
        )

        _validate_text(
            presentation.title,
            MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH,
        )

        _validate_text(
            presentation.detail,
            MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH,
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_diagnostic_presentation_invalid"
        ) from None

    return presentation