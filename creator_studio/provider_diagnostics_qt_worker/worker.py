"""M98 provider diagnostics Qt worker.

This module provides the QObject worker hosted by the M98 QThread bridge.

The worker coordinates only:

    M98 cancellation token
        -> M97 ProviderDiagnosticsGuiController
        -> immutable M97 final state
        -> Qt signals

The worker does not perform provider HTTP work itself. M97/M95/M92 retain
their existing responsibilities.

Runtime-only execution arguments may include:

- detached M95 request;
- optional remote-image source;
- optional M100 credential-source factory.

The M100 credential-source factory is retained only for the lifetime of one
worker execution. It is released together with the other runtime arguments
after execution completes.

Cancellation is intentionally not implemented as a queued Qt slot. A queued
slot on a busy worker thread might not execute until the blocking diagnostic
operation has already completed. Instead, ``request_cancel`` directly sets a
thread-safe ``threading.Event`` through the M98 cancellation token.

The worker is one-shot. A QThread bridge should create one worker for one
diagnostic execution.

Signals:

- ``started``:
  emitted immediately before M97 execution begins.

- ``state_changed``:
  emitted once with the validated terminal M97 state.

- ``fatal``:
  emitted without exception payload when an unexpected BaseException or
  malformed controller result reaches this final Qt isolation boundary.

- ``finished``:
  emitted once with the final safe M97 state.

No raw exception, credential, credential-source factory, HTTP response or
provider response is emitted.
"""

import threading

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
)

from ..provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiController,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)
from .cancellation import (
    ProviderDiagnosticsQtCancellationToken,
)


def _internal_failed_state():
    state = ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED
        ),
        view_model=None,
        failure=(
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE
        ),
    )

    validate_provider_diagnostics_gui_controller_state(
        state
    )

    return state


def _validate_terminal_state(
    state,
):
    validate_provider_diagnostics_gui_controller_state(
        state
    )

    if (
        state.phase
        not in (
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )
    ):
        raise ValueError()

    return state


class ProviderDiagnosticsQtWorker(
    QObject
):
    """One-shot QObject bridge over the framework-neutral M97 controller."""

    started = pyqtSignal()

    state_changed = pyqtSignal(
        object
    )

    fatal = pyqtSignal()

    finished = pyqtSignal(
        object
    )

    def __init__(
        self,
        request,
        remote_image_source=None,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self._request = request
        self._remote_image_source = (
            remote_image_source
        )

        self._credential_source_factory = None
        self._use_credential_source_factory = False

        self._controller = (
            ProviderDiagnosticsGuiController()
        )

        self._cancellation = (
            ProviderDiagnosticsQtCancellationToken()
        )

        self._run_gate = threading.Lock()
        self._has_run = False

    @classmethod
    def create_with_credential_source_factory(
        cls,
        request,
        credential_source_factory,
        remote_image_source=None,
        parent=None,
    ):
        """
        Create one worker carrying explicit runtime credential authority.

        The original constructor contract remains unchanged. The supplied
        factory is retained only until this one-shot worker completes.
        """
        worker = cls(
            request,
            remote_image_source,
            parent,
        )

        worker._credential_source_factory = (
            credential_source_factory
        )
        worker._use_credential_source_factory = True

        return worker

    @property
    def state(
        self,
    ):
        return self._controller.state

    @property
    def is_cancelled(
        self,
    ):
        return self._cancellation.is_cancelled

    @property
    def has_run(
        self,
    ):
        with self._run_gate:
            return self._has_run

    def request_cancel(
        self,
    ):
        """Request cancellation safely from any Python thread."""
        self._cancellation.cancel()

    def _claim_run(
        self,
    ):
        with self._run_gate:
            if self._has_run:
                return False

            self._has_run = True

            return True

    def _release_runtime_arguments(
        self,
    ):
        self._request = None
        self._remote_image_source = None
        self._credential_source_factory = None
        self._use_credential_source_factory = False

    def _recover_failed_state(
        self,
    ):
        try:
            candidate = self._controller.state

            _validate_terminal_state(
                candidate
            )

            if (
                candidate.phase
                is ProviderDiagnosticsGuiControllerPhase
                .FAILED
            ):
                return candidate

        except BaseException:
            pass

        return _internal_failed_state()

    @pyqtSlot()
    def run(
        self,
    ):
        """Run one diagnostic operation and emit only GUI-safe state."""
        if not self._claim_run():
            self.fatal.emit()

            return

        self.started.emit()

        fatal = False

        try:
            if self._use_credential_source_factory:
                state = (
                    self._controller
                    .run_with_credential_source_factory(
                        self._request,
                        self._cancellation.check,
                        self._credential_source_factory,
                        self._remote_image_source,
                    )
                )

            else:
                state = self._controller.run(
                    self._request,
                    self._cancellation.check,
                    self._remote_image_source,
                )

            try:
                state = _validate_terminal_state(
                    state
                )

            except MemoryError:
                raise

            except Exception:
                state = _internal_failed_state()
                fatal = True

        except BaseException:
            state = self._recover_failed_state()
            fatal = True

        finally:
            self._release_runtime_arguments()

        self.state_changed.emit(
            state
        )

        if fatal:
            self.fatal.emit()

        self.finished.emit(
            state
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_worker_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_qt_worker_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_worker_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsQtWorker("
            f"phase={self.state.phase.value!r}, "
            f"has_run={self.has_run!r}, "
            f"is_cancelled={self.is_cancelled!r}"
            ")"
        )