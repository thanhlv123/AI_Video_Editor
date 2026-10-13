"""M94 provider diagnostics presentation public facade.

This module exposes the complete stable M94 presentation surface.

Applications that want GUI/CLI-safe provider diagnostic presentation data
should import from:

    creator_studio.provider_diagnostics_presentation.public_api

Importing this module performs:
- no environment credential lookup;
- no DNS resolution;
- no network access;
- no provider API request;
- no M91 readiness execution;
- no M92 connectivity execution;
- no M93 diagnostic execution.

The presenter accepts only one validated M93 diagnostic report and converts it
into detached, secret-free presentation data.
"""

from .models import (
    MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH,
    MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH,
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
    validate_provider_diagnostic_presentation,
)
from .presenter import (
    ProviderDiagnosticPresenter,
)


PROVIDER_DIAGNOSTIC_PRESENTATION_PUBLIC_API_VERSION = 1


__all__ = (
    "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH",
    "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH",
    "PROVIDER_DIAGNOSTIC_PRESENTATION_PUBLIC_API_VERSION",
    "PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION",
    "ProviderDiagnosticPresentation",
    "ProviderDiagnosticPresentationAction",
    "ProviderDiagnosticPresentationSeverity",
    "ProviderDiagnosticPresenter",
    "validate_provider_diagnostic_presentation",
)