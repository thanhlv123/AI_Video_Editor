"""M97 provider diagnostics GUI controller public facade.

This module exposes the complete stable M97 framework-neutral GUI controller
surface.

Applications and future PyQt worker layers should import from:

    creator_studio.provider_diagnostics_gui_controller.public_api

The controller coordinates:

    M95 ProviderDiagnosticsApplicationService
        -> M96 ProviderDiagnosticsViewModelAdapter
        -> M97 immutable controller state

Importing this module performs:

- no environment lookup;
- no credential resolution;
- no DNS resolution;
- no network access;
- no provider API request;
- no diagnostic execution;
- no PyQt import.

Runtime-only dependencies such as caller check/cancellation callbacks and
remote image sources are supplied directly to the controller and are never
stored in detached controller state.
"""

from .controller import (
    ProviderDiagnosticsGuiController,
    ProviderDiagnosticsGuiControllerCancelled,
)
from .models import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)


PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_PUBLIC_API_VERSION = 1


__all__ = (
    "PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_PUBLIC_API_VERSION",
    "PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION",
    "ProviderDiagnosticsGuiController",
    "ProviderDiagnosticsGuiControllerCancelled",
    "ProviderDiagnosticsGuiControllerFailure",
    "ProviderDiagnosticsGuiControllerPhase",
    "ProviderDiagnosticsGuiControllerState",
    "validate_provider_diagnostics_gui_controller_state",
)