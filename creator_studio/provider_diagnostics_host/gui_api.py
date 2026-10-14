"""Stable GUI-support API for M100 provider diagnostics host wiring.

This API intentionally exposes only secret-free request assembly and the
runtime-only diagnostics remote-image dependency marker used by the desktop
integration owner.

Credential authority remains owned by ProviderDiagnosticsHost.start(...).
"""

from .remote_image_source import (
    ProviderDiagnosticsRemoteImageSource,
)
from .request_builder import (
    ProviderDiagnosticsRequestBuilder,
)


PROVIDER_DIAGNOSTICS_HOST_GUI_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_HOST_GUI_API_VERSION",
    "ProviderDiagnosticsRemoteImageSource",
    "ProviderDiagnosticsRequestBuilder",
)
