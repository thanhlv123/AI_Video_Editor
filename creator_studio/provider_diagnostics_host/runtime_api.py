"""Stable runtime public API for M100 provider diagnostics host integration.

The original provider_diagnostics_host.public_api remains the checkpoint-2A
credential-source API.

This separate runtime API exposes only the stateless host execution boundary.
It deliberately does not export APIKeyManager, credential-source factories,
provider/profile binding helpers, secrets, HTTP helpers or Qt worker details.
"""

from .runtime import (
    ProviderDiagnosticsHost,
)


PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION",
    "ProviderDiagnosticsHost",
)