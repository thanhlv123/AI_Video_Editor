"""M94 provider diagnostic presenter.

This module converts one validated M93 ProviderRuntimeDiagnosticReport into a
detached, secret-free M94 ProviderDiagnosticPresentation.

The presenter:
- validates the exact M93 report before using it;
- preserves diagnostic mode and machine-readable status;
- preserves only safe provider metadata;
- maps diagnostic state to stable severity, action, title and detail;
- validates the generated M94 presentation before returning it.

The presenter never:
- reads environment variables;
- resolves credentials;
- performs DNS resolution;
- opens a network connection;
- invokes M91 or M92;
- executes a provider API request.

Credential environment variable names are metadata only. Credential values are
never accepted by the M93 report contract and therefore cannot enter the M94
presentation through this path.
"""

from ..provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
    validate_provider_runtime_diagnostic_report,
)
from .models import (
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
    validate_provider_diagnostic_presentation,
)


def _ready_spec(
    report,
):
    if (
        report.mode
        is ProviderRuntimeDiagnosticMode
        .ONLINE
    ):
        detail = (
            "Provider configuration and connectivity are ready."
        )

    else:
        detail = (
            "Provider configuration is ready."
        )

    return (
        ProviderDiagnosticPresentationSeverity
        .SUCCESS,
        ProviderDiagnosticPresentationAction
        .NONE,
        "Ready",
        detail,
    )


def _config_invalid_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .REVIEW_CONFIGURATION,
        "Configuration invalid",
        "Review the provider runtime configuration.",
    )


def _credential_missing_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .CONFIGURE_CREDENTIAL,
        "API credential missing",
        (
            "Configure the credential in environment variable "
            + report.credential_environment_variable
            + "."
        ),
    )


def _credential_invalid_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .CHECK_CREDENTIAL,
        "API credential invalid",
        (
            "Check the credential configured in environment variable "
            + report.credential_environment_variable
            + "."
        ),
    )


def _remote_dependency_missing_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .WARNING,
        ProviderDiagnosticPresentationAction
        .ADD_REMOTE_SOURCE,
        "Remote image source required",
        (
            "Configure the required remote image source for Kie.ai."
        ),
    )


def _authentication_failed_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .CHECK_CREDENTIAL,
        "Authentication failed",
        (
            "Check the credential and provider access for "
            + report.credential_environment_variable
            + "."
        ),
    )


def _permission_denied_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .CHECK_CREDENTIAL,
        "Permission denied",
        (
            "Check the permissions associated with "
            + report.credential_environment_variable
            + "."
        ),
    )


def _rate_limited_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .WARNING,
        ProviderDiagnosticPresentationAction
        .RETRY,
        "Rate limited",
        "Wait and retry the provider connectivity check.",
    )


def _provider_unavailable_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .WARNING,
        ProviderDiagnosticPresentationAction
        .RETRY,
        "Provider unavailable",
        "The provider is temporarily unavailable. Retry later.",
    )


def _network_unavailable_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .WARNING,
        ProviderDiagnosticPresentationAction
        .CHECK_NETWORK,
        "Network unavailable",
        "Check the network connection and retry.",
    )


def _deadline_exceeded_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .WARNING,
        ProviderDiagnosticPresentationAction
        .RETRY,
        "Connection timed out",
        "The provider connectivity check timed out. Retry.",
    )


def _response_invalid_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .RETRY,
        "Invalid provider response",
        "The provider returned an unexpected response. Retry the check.",
    )


def _internal_failure_spec(
    report,
):
    return (
        ProviderDiagnosticPresentationSeverity
        .ERROR,
        ProviderDiagnosticPresentationAction
        .RETRY,
        "Internal diagnostic failure",
        "The diagnostic operation failed internally. Retry the check.",
    )


def _presentation_spec(
    report,
):
    status = report.status

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .READY
    ):
        return _ready_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        return _config_invalid_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CREDENTIAL_MISSING
    ):
        return _credential_missing_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CREDENTIAL_INVALID
    ):
        return _credential_invalid_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .REMOTE_DEPENDENCY_MISSING
    ):
        return _remote_dependency_missing_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .AUTHENTICATION_FAILED
    ):
        return _authentication_failed_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .PERMISSION_DENIED
    ):
        return _permission_denied_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .RATE_LIMITED
    ):
        return _rate_limited_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .PROVIDER_UNAVAILABLE
    ):
        return _provider_unavailable_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .NETWORK_UNAVAILABLE
    ):
        return _network_unavailable_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .DEADLINE_EXCEEDED
    ):
        return _deadline_exceeded_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .RESPONSE_INVALID
    ):
        return _response_invalid_spec(
            report
        )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .INTERNAL_FAILURE
    ):
        return _internal_failure_spec(
            report
        )

    raise ValueError()


class ProviderDiagnosticPresenter:
    """Stateless canonical M93-to-M94 presenter."""

    __slots__ = ()

    def present(
        self,
        report,
    ):
        try:
            validate_provider_runtime_diagnostic_report(
                report
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "provider_diagnostic_presentation_source_invalid"
            ) from None

        try:
            (
                severity,
                action,
                title,
                detail,
            ) = _presentation_spec(
                report
            )

            presentation = ProviderDiagnosticPresentation(
                schema_version=(
                    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
                ),
                mode=report.mode,
                diagnostic_status=report.status,
                severity=severity,
                action=action,
                provider=report.provider,
                credential_environment_variable=(
                    report.credential_environment_variable
                ),
                title=title,
                detail=detail,
            )

            validate_provider_diagnostic_presentation(
                presentation
            )

        except MemoryError:
            raise

        except Exception:
            raise RuntimeError(
                "provider_diagnostic_presentation_internal"
            ) from None

        return presentation