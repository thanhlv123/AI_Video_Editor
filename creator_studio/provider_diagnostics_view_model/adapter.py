"""M96 provider diagnostics view-model adapter.

This module converts one validated M95 ProviderDiagnosticsApplicationResult
into one detached M96 ProviderDiagnosticsViewModel.

The adapter is presentation-only.

It performs:
- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no provider API request;
- no M91/M92/M93/M94/M95 execution.

The adapter preserves only data required by a GUI or CLI:

- provider label;
- status text;
- detail text;
- severity;
- recommended action;
- action text;
- ready state.

Credential metadata, diagnostic reports and transport status fields are not
copied into the M96 view model.
"""

from ..provider_diagnostics_application import (
    ProviderDiagnosticsApplicationResult,
    validate_provider_diagnostics_application_result,
)
from ..provider_diagnostics_presentation import (
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
)
from ..provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticStatus,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)
from .models import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
    validate_provider_diagnostics_view_model,
)


def _provider_label(
    provider,
):
    if provider is None:
        return "Provider"

    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        return "OpenAI"

    if (
        provider
        is VisionProviderKind.GEMINI
    ):
        return "Gemini"

    if (
        provider
        is VisionProviderKind.KIE_AI
    ):
        return "Kie.ai"

    raise ValueError()


def _severity(
    severity,
):
    if (
        severity
        is ProviderDiagnosticPresentationSeverity
        .SUCCESS
    ):
        return (
            ProviderDiagnosticsViewSeverity
            .SUCCESS
        )

    if (
        severity
        is ProviderDiagnosticPresentationSeverity
        .WARNING
    ):
        return (
            ProviderDiagnosticsViewSeverity
            .WARNING
        )

    if (
        severity
        is ProviderDiagnosticPresentationSeverity
        .ERROR
    ):
        return (
            ProviderDiagnosticsViewSeverity
            .ERROR
        )

    raise ValueError()


def _action(
    action,
):
    if (
        action
        is ProviderDiagnosticPresentationAction
        .NONE
    ):
        return (
            ProviderDiagnosticsViewAction
            .NONE
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .REVIEW_CONFIGURATION
    ):
        return (
            ProviderDiagnosticsViewAction
            .REVIEW_CONFIGURATION
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .CONFIGURE_CREDENTIAL
    ):
        return (
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .CHECK_CREDENTIAL
    ):
        return (
            ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .ADD_REMOTE_SOURCE
    ):
        return (
            ProviderDiagnosticsViewAction
            .ADD_REMOTE_SOURCE
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .RETRY
    ):
        return (
            ProviderDiagnosticsViewAction
            .RETRY
        )

    if (
        action
        is ProviderDiagnosticPresentationAction
        .CHECK_NETWORK
    ):
        return (
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK
        )

    raise ValueError()


def _action_text(
    action,
):
    if (
        action
        is ProviderDiagnosticsViewAction
        .NONE
    ):
        return "No action required"

    if (
        action
        is ProviderDiagnosticsViewAction
        .REVIEW_CONFIGURATION
    ):
        return "Review configuration"

    if (
        action
        is ProviderDiagnosticsViewAction
        .CONFIGURE_CREDENTIAL
    ):
        return "Configure credential"

    if (
        action
        is ProviderDiagnosticsViewAction
        .CHECK_CREDENTIAL
    ):
        return "Check credential"

    if (
        action
        is ProviderDiagnosticsViewAction
        .ADD_REMOTE_SOURCE
    ):
        return "Add remote image source"

    if (
        action
        is ProviderDiagnosticsViewAction
        .RETRY
    ):
        return "Retry"

    if (
        action
        is ProviderDiagnosticsViewAction
        .CHECK_NETWORK
    ):
        return "Check network"

    raise ValueError()


class ProviderDiagnosticsViewModelAdapter:
    """Stateless M95-to-M96 diagnostics view-model adapter."""

    __slots__ = ()

    def adapt(
        self,
        result,
    ):
        try:
            validate_provider_diagnostics_application_result(
                result
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "provider_diagnostics_view_model_source_invalid"
            ) from None

        if (
            type(result)
            is not ProviderDiagnosticsApplicationResult
        ):
            raise ValueError(
                "provider_diagnostics_view_model_source_invalid"
            )

        try:
            presentation = (
                result.presentation
            )

            view_severity = _severity(
                presentation.severity
            )

            view_action = _action(
                presentation.action
            )

            view_model = ProviderDiagnosticsViewModel(
                schema_version=(
                    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
                ),
                provider_label=_provider_label(
                    presentation.provider
                ),
                status_text=presentation.title,
                detail_text=presentation.detail,
                severity=view_severity,
                action=view_action,
                action_text=_action_text(
                    view_action
                ),
                is_ready=(
                    presentation.diagnostic_status
                    is ProviderRuntimeDiagnosticStatus
                    .READY
                ),
            )

            validate_provider_diagnostics_view_model(
                view_model
            )

        except MemoryError:
            raise

        except Exception:
            raise RuntimeError(
                "provider_diagnostics_view_model_internal"
            ) from None

        return view_model