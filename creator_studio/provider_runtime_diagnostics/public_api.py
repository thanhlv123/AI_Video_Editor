"""M93 provider runtime diagnostics public facade.

This module exposes the complete stable M93 diagnostics surface.

Applications that want one normalized provider runtime diagnostic interface
should import from:

    creator_studio.provider_runtime_diagnostics.public_api

Importing this module performs:
- no environment credential lookup;
- no DNS resolution;
- no network access;
- no provider API request.

OFFLINE diagnostics execute M91 readiness only.

ONLINE diagnostics execute M91 readiness first and execute M92 connectivity
only when readiness succeeds.

Diagnostic reports never contain resolved credential values.
"""

from .coordinator import (
    ProviderRuntimeDiagnosticsCoordinator,
)
from .models import (
    PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticReport,
    ProviderRuntimeDiagnosticStatus,
    validate_provider_runtime_diagnostic_report,
)


PROVIDER_RUNTIME_DIAGNOSTIC_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_RUNTIME_DIAGNOSTIC_PUBLIC_API_VERSION",
    "PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION",
    "ProviderRuntimeDiagnosticMode",
    "ProviderRuntimeDiagnosticReport",
    "ProviderRuntimeDiagnosticStatus",
    "ProviderRuntimeDiagnosticsCoordinator",
    "validate_provider_runtime_diagnostic_report",
)