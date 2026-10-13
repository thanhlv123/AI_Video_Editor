"""M99 stable public API for diagnostics Qt view binding.

The original M99 ``public_api`` remains the stable presentation-only
interface for ``ProviderDiagnosticsQtView``.

This module publishes the separate execution-binding surface without
expanding or breaking that checkpoint-1 public API contract.

The binding surface exposes only:

- its public API version;
- the M99 Qt view binder.

It does not export requests, credentials, runtime assemblies, provider
transport objects, environment values or HTTP response objects.
"""

from .binder import (
    ProviderDiagnosticsQtViewBinder,
)


PROVIDER_DIAGNOSTICS_QT_VIEW_BINDING_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_QT_VIEW_BINDING_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtViewBinder",
)