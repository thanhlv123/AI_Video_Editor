"""M97 framework-neutral provider diagnostics GUI controller.

The controller coordinates the already-existing application and view-model
layers:

    M95 ProviderDiagnosticsApplicationService
        -> M96 ProviderDiagnosticsViewModelAdapter
        -> immutable M97 controller state

The controller itself contains no PyQt dependency.

Runtime-only dependencies such as:

- check/cancellation callback;
- remote image source;

are passed directly to ``run`` and are never stored in detached controller
state.

Caller-owned check exceptions are wrapped internally so they cannot be
mistaken for errors emitted by M95 itself.

A caller may request normal GUI cancellation by raising
``ProviderDiagnosticsGuiControllerCancelled`` from the supplied check
callable.

Ordinary provider diagnostic outcomes are not controller failures. They are
returned by M95/M96 as valid view models and therefore produce COMPLETED
states even when ``view_model.is_ready`` is False.
"""

import threading

from ..provider_diagnostics_application.public_api import (
    ProviderDiagnosticsApplicationService,
)
from ..provider_diagnostics_view_model.public_api import (
    ProviderDiagnosticsViewModelAdapter,
)
from .models import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)


class ProviderDiagnosticsGuiControllerCancelled(
    Exception
):
    """Runtime-only signal used by caller-owned cancellation checks."""

    __slots__ = ()


class _CallerCheckFailure(
    BaseException
):
    """Carries one BaseException raised by the caller-owned check."""

    __slots__ = (
        "error",
    )

    def __init__(
        self,
        error,
    ):
        self.error = error


def _guard_check(
    check,
):
    def guarded():
        try:
            check()

        except _CallerCheckFailure:
            raise

        except BaseException as exc:
            raise _CallerCheckFailure(
                exc
            ) from exc

    return guarded


def _build_state(
    phase,
    *,
    view_model=None,
    failure=None,
):
    try:
        state = ProviderDiagnosticsGuiControllerState(
            schema_version=(
                PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
            ),
            phase=phase,
            view_model=view_model,
            failure=failure,
        )

        validate_provider_diagnostics_gui_controller_state(
            state
        )

    except MemoryError:
        raise

    except Exception:
        raise RuntimeError(
            "provider_diagnostics_gui_controller_internal"
        ) from None

    return state


class ProviderDiagnosticsGuiController:
    """Thread-aware, framework-neutral M97 diagnostics controller."""

    __slots__ = (
        "_gate",
        "_state",
    )

    def __init__(
        self,
    ):
        self._gate = threading.Lock()

        self._state = _build_state(
            ProviderDiagnosticsGuiControllerPhase
            .IDLE
        )

    @property
    def state(
        self,
    ):
        with self._gate:
            return self._state

    def reset(
        self,
    ):
        with self._gate:
            if (
                self._state.phase
                is ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            ):
                raise RuntimeError(
                    "provider_diagnostics_gui_controller_busy"
                )

            new_state = _build_state(
                ProviderDiagnosticsGuiControllerPhase
                .IDLE
            )

            self._state = new_state

            return new_state

    def _begin(
        self,
    ):
        with self._gate:
            if (
                self._state.phase
                is ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            ):
                raise RuntimeError(
                    "provider_diagnostics_gui_controller_busy"
                )

            new_state = _build_state(
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )

            self._state = new_state

            return new_state

    def _finish(
        self,
        phase,
        *,
        view_model=None,
        failure=None,
    ):
        new_state = _build_state(
            phase,
            view_model=view_model,
            failure=failure,
        )

        with self._gate:
            self._state = new_state

        return new_state

    def _failed(
        self,
        failure,
    ):
        return self._finish(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            failure=failure,
        )

    def _handle_caller_check_failure(
        self,
        carrier,
    ):
        error = carrier.error

        if (
            isinstance(
                error,
                ProviderDiagnosticsGuiControllerCancelled,
            )
        ):
            return self._finish(
                ProviderDiagnosticsGuiControllerPhase
                .CANCELLED
            )

        if isinstance(
            error,
            MemoryError,
        ):
            self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

            raise error

        if isinstance(
            error,
            Exception,
        ):
            return self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

        self._failed(
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE
        )

        raise error

    def run(
        self,
        request,
        check,
        remote_image_source=None,
    ):
        """Execute one M95 request and publish one final M97 state."""
        self._begin()

        guarded_check = _guard_check(
            check
        )

        try:
            application_service = (
                ProviderDiagnosticsApplicationService()
            )

            application_result = (
                application_service.run(
                    request,
                    guarded_check,
                    remote_image_source,
                )
            )

        except _CallerCheckFailure as exc:
            return self._handle_caller_check_failure(
                exc
            )

        except MemoryError:
            self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

            raise

        except Exception as exc:
            if (
                type(exc) is ValueError
                and exc.args
                == (
                    "provider_diagnostics_application_request_invalid",
                )
            ):
                return self._failed(
                    ProviderDiagnosticsGuiControllerFailure
                    .INVALID_REQUEST
                )

            return self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

        except BaseException:
            self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

            raise

        try:
            adapter = (
                ProviderDiagnosticsViewModelAdapter()
            )

            view_model = adapter.adapt(
                application_result
            )

        except MemoryError:
            self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

            raise

        except Exception:
            return self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

        except BaseException:
            self._failed(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            )

            raise

        return self._finish(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=view_model,
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_gui_controller_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_gui_controller_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_gui_controller_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsGuiController("
            f"phase={self.state.phase.value!r}"
            ")"
        )