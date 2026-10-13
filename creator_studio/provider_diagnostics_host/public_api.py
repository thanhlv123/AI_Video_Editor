"""Stable public API for M100 provider diagnostics host integration."""

from .credential_source import (
    APIKeyManagerCredentialSourceFactory,
)


PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION",
    "APIKeyManagerCredentialSourceFactory",
)