"""M95 provider diagnostics application public facade.

This module exposes the complete stable M95 application surface.

Applications that want one provider diagnostics application entry point
should import from:

    creator_studio.provider_diagnostics_application.public_api

The public service accepts:
- one detached M95 request;
- one runtime-only check callable;
- one optional runtime-only remote image source.

It returns one detached M95 result containing a validated M94 provider
diagnostic presentation.

Importing this module performs:
- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no provider API request;
- no M91 readiness execution;
- no M92 connectivity execution;
- no M93 diagnostic execution;
- no M94 presentation execution.
"""

from .models import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
    ProviderDiagnosticsApplicationResult,
    validate_provider_diagnostics_application_request,
    validate_provider_diagnostics_application_result,
)
from .service import (
    ProviderDiagnosticsApplicationService,
)


PROVIDER_DIAGNOSTICS_APPLICATION_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_APPLICATION_PUBLIC_API_VERSION",
    "PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION",
    "ProviderDiagnosticsApplicationRequest",
    "ProviderDiagnosticsApplicationResult",
    "ProviderDiagnosticsApplicationService",
    "validate_provider_diagnostics_application_request",
    "validate_provider_diagnostics_application_result",
)