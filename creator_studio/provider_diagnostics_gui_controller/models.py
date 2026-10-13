"""M97 provider diagnostics GUI controller state contract.

This module defines the detached immutable state published by the provider
diagnostics GUI controller.

The state is framework-neutral. PyQt is intentionally not imported here.

Controller phases:

- IDLE:
  no diagnostic operation is running and no result is attached.

- RUNNING:
  one diagnostic operation is in progress.

- COMPLETED:
  execution completed normally and contains one validated M96 GUI-safe
  ProviderDiagnosticsViewModel. The contained view model may represent either
  a ready provider or a valid non-ready diagnostic outcome.

- CANCELLED:
  execution was cancelled before publishing a diagnostic result.

- FAILED:
  the controller could not complete the application operation because of an
  invalid request or an internal controller/application failure.

Provider diagnostic outcomes such as missing credentials, invalid credentials,
network failures, rate limits, provider unavailability and timeouts are not
controller failures. Those outcomes belong in a COMPLETED state containing an
M96 view model with is_ready=False.

This module contains no:

- API credential value;
- credential environment access;
- HTTP request or response;
- provider response code;
- runtime configuration;
- application request;
- M93 diagnostic report;
- M94 presentation;
- runtime check callable;
- remote image source;
- PyQt object;
- execution authority.

Validation performs no environment lookup and no network access.
"""

from dataclasses import dataclass, fields
from enum import Enum

from ..provider_diagnostics_view_model import (
    ProviderDiagnosticsViewModel,
    validate_provider_diagnostics_view_model,
)


PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION = 1


class ProviderDiagnosticsGuiControllerPhase(
    str,
    Enum,
):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ProviderDiagnosticsGuiControllerFailure(
    str,
    Enum,
):
    INVALID_REQUEST = "INVALID_REQUEST"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


@dataclass(frozen=True)
class ProviderDiagnosticsGuiControllerState:
    """Detached GUI-safe snapshot of one controller state."""

    schema_version: int
    phase: ProviderDiagnosticsGuiControllerPhase
    view_model: ProviderDiagnosticsViewModel | None
    failure: ProviderDiagnosticsGuiControllerFailure | None


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


def _validate_semantics(
    state,
):
    phase = state.phase

    if (
        phase
        is ProviderDiagnosticsGuiControllerPhase
        .COMPLETED
    ):
        if (
            type(state.view_model)
            is not ProviderDiagnosticsViewModel
        ):
            raise ValueError()

        validate_provider_diagnostics_view_model(
            state.view_model
        )

        if state.failure is not None:
            raise ValueError()

        return

    if state.view_model is not None:
        raise ValueError()

    if (
        phase
        is ProviderDiagnosticsGuiControllerPhase
        .FAILED
    ):
        if (
            type(state.failure)
            is not ProviderDiagnosticsGuiControllerFailure
        ):
            raise ValueError()

        return

    if state.failure is not None:
        raise ValueError()


def validate_provider_diagnostics_gui_controller_state(
    state,
):
    """Validate one detached M97 GUI controller state."""
    try:
        _validate_exact_shape(
            state,
            ProviderDiagnosticsGuiControllerState,
        )

        if (
            type(state.schema_version)
            is not int
            or state.schema_version
            != PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(state.phase)
            is not ProviderDiagnosticsGuiControllerPhase
        ):
            raise ValueError()

        _validate_semantics(
            state
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_diagnostics_gui_controller_state_invalid"
        ) from None

    return state