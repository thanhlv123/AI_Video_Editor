"""M96 provider diagnostics view-model public facade.

This module exposes the complete stable M96 GUI/CLI-safe view-model surface.

Applications that want to adapt an M95 provider diagnostics application
result into display-ready data should import from:

    creator_studio.provider_diagnostics_view_model.public_api

Importing this module performs:
- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no provider API request;
- no M91/M92/M93/M94/M95 execution.

The adapter accepts only one validated M95 application result and produces
one detached M96 provider diagnostics view model.
"""

from .adapter import (
    ProviderDiagnosticsViewModelAdapter,
)
from .models import (
    MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH,
    MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH,
    MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH,
    MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH,
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
    validate_provider_diagnostics_view_model,
)


PROVIDER_DIAGNOSTICS_VIEW_MODEL_PUBLIC_API_VERSION = 1


__all__ = (
    "MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH",
    "MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH",
    "MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH",
    "MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH",
    "PROVIDER_DIAGNOSTICS_VIEW_MODEL_PUBLIC_API_VERSION",
    "PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION",
    "ProviderDiagnosticsViewAction",
    "ProviderDiagnosticsViewModel",
    "ProviderDiagnosticsViewModelAdapter",
    "ProviderDiagnosticsViewSeverity",
    "validate_provider_diagnostics_view_model",
)