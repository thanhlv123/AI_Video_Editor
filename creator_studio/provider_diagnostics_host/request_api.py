"""Stable request-assembly API for M100 provider diagnostics host integration.

The existing provider_diagnostics_host.public_api and runtime_api contracts are
left unchanged. This separate API exposes only the stateless detached-request
builder used by application hosts such as the desktop GUI.
"""

from .request_builder import (
    ProviderDiagnosticsRequestBuilder,
)


PROVIDER_DIAGNOSTICS_HOST_REQUEST_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_HOST_REQUEST_API_VERSION",
    "ProviderDiagnosticsRequestBuilder",
)
