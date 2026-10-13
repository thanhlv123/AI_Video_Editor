"""M92 provider connectivity probe public facade.

This module exposes the complete stable M92 connectivity probe surface.

Applications that want to perform authenticated provider connectivity
diagnostics should import from:

    creator_studio.provider_connectivity_probe.public_api

Importing this module performs:
- no environment credential lookup;
- no DNS resolution;
- no network access;
- no provider API request.

Probe execution itself performs only one small authenticated diagnostic GET
request and sends no image or semantic prompt.
"""

from .models import (
    PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION,
    ProviderConnectivityProbeReport,
    ProviderConnectivityProbeStatus,
    validate_provider_connectivity_probe_report,
)
from .probe import (
    GEMINI_CONNECTIVITY_PROBE_ENDPOINT,
    KIE_CONNECTIVITY_PROBE_ENDPOINT,
    MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES,
    MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS,
    OPENAI_CONNECTIVITY_PROBE_ENDPOINT,
    ProviderConnectivityProbe,
)


PROVIDER_CONNECTIVITY_PROBE_PUBLIC_API_VERSION = 1


__all__ = (
    "GEMINI_CONNECTIVITY_PROBE_ENDPOINT",
    "KIE_CONNECTIVITY_PROBE_ENDPOINT",
    "MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES",
    "MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS",
    "OPENAI_CONNECTIVITY_PROBE_ENDPOINT",
    "PROVIDER_CONNECTIVITY_PROBE_PUBLIC_API_VERSION",
    "PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION",
    "ProviderConnectivityProbe",
    "ProviderConnectivityProbeReport",
    "ProviderConnectivityProbeStatus",
    "validate_provider_connectivity_probe_report",
)