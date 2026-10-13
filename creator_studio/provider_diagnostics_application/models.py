"""M95 provider diagnostics application contract.

This module defines the detached request and result contracts used by the
provider diagnostics application service.

The request contains:
- one validated M90 ProviderRuntimeConfig;
- one M93 diagnostic mode.

The request intentionally does not contain:
- a resolved credential;
- a credential value;
- a remote image source;
- a check/cancellation callable;
- any network or execution authority.

Runtime-only dependencies such as check and remote_image_source are supplied
directly to the M95 service at execution time.

The result contains exactly one validated M94
ProviderDiagnosticPresentation.

This module performs:
- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no M91 readiness execution;
- no M92 connectivity execution;
- no M93 diagnostics execution;
- no M94 presentation execution.
"""

from dataclasses import dataclass, fields

from ..provider_diagnostics_presentation import (
    ProviderDiagnosticPresentation,
    validate_provider_diagnostic_presentation,
)
from ..provider_runtime_assembly import (
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from ..provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
)


PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProviderDiagnosticsApplicationRequest:
    """Detached M95 diagnostics application request."""

    schema_version: int
    config: ProviderRuntimeConfig
    mode: ProviderRuntimeDiagnosticMode


@dataclass(frozen=True)
class ProviderDiagnosticsApplicationResult:
    """Detached M95 diagnostics application result."""

    schema_version: int
    presentation: ProviderDiagnosticPresentation


def _validate_exact_shape(
    value,
    expected_type,
):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(
            expected_type
        )
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def validate_provider_diagnostics_application_request(
    request,
):
    """Validate one detached M95 diagnostics application request."""
    try:
        _validate_exact_shape(
            request,
            ProviderDiagnosticsApplicationRequest,
        )

        if (
            type(request.schema_version)
            is not int
            or request.schema_version
            != PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(request.config)
            is not ProviderRuntimeConfig
        ):
            raise ValueError()

        validate_provider_runtime_config(
            request.config
        )

        if (
            type(request.mode)
            is not ProviderRuntimeDiagnosticMode
        ):
            raise ValueError()

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_diagnostics_application_request_invalid"
        ) from None

    return request


def validate_provider_diagnostics_application_result(
    result,
):
    """Validate one detached M95 diagnostics application result."""
    try:
        _validate_exact_shape(
            result,
            ProviderDiagnosticsApplicationResult,
        )

        if (
            type(result.schema_version)
            is not int
            or result.schema_version
            != PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(result.presentation)
            is not ProviderDiagnosticPresentation
        ):
            raise ValueError()

        validate_provider_diagnostic_presentation(
            result.presentation
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_diagnostics_application_result_invalid"
        ) from None

    return result