"""M98 provider diagnostics QThread bridge.

This module owns the Qt thread lifecycle around the one-shot M98 QObject
worker.

Architecture:

    GUI/main thread
        -> ProviderDiagnosticsQtThreadBridge.start(...)
        -> QThread
        -> ProviderDiagnosticsQtWorker
        -> M97 controller
        -> M95/M96 diagnostics pipeline

Cancellation does not rely on the worker thread's Qt event loop. The bridge
calls the worker's thread-safe ``request_cancel`` method directly, which sets
the M98 threading.Event cancellation token.

The bridge publishes terminal state only after the worker thread has actually
finished.

A critical Qt lifecycle rule is enforced here:

The Python reference to the completed QThread is not released from inside the
QThread.finished signal callback itself. Final lifecycle cleanup is deferred
to the next GUI event-loop turn with QTimer.singleShot(0, ...).

This prevents the PyQt wrapper / underlying QThread object from being released
while Qt is still dispatching that same thread's ``finished`` signal.

Two different locks intentionally protect two different concerns:

- ``_gate`` protects bridge lifecycle ownership observed by the GUI thread.
- ``_result_gate`` protects terminal-result handoff from the worker thread.

The bridge never creates an unused worker or QThread when a second ``start``
call is rejected as busy.

The bridge does not:

- read environment variables;
- resolve credentials;
- perform HTTP requests;
- store detached credentials;
- expose raw exceptions;
- expose HTTP/provider response metadata;
- block waiting for the worker thread during normal execution.

The request and optional remote-image source are owned temporarily by the
worker and are released by that worker after execution.
"""

import threading

from PyQt6.QtCore import (
    QObject,
    QThread,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)

from ..provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)
from .worker import (
    ProviderDiagnosticsQtWorker,
)


def _idle_state():
    state = ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .IDLE
        ),
        view_model=None,
        failure=None,
    )

    validate_provider_diagnostics_gui_controller_state(
        state
    )

    return state


def _running_state():
    state = ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING
        ),
        view_model=None,
        failure=None,
    )

    validate_provider_diagnostics_gui_controller_state(
        state
    )

    return state


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


class ProviderDiagnosticsQtThreadBridge(
    QObject
):
    """Reusable non-blocking QThread lifecycle bridge for M98 workers."""

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
        parent=None,
    ):
        super().__init__(
            parent
        )

        self._gate = threading.Lock()
        self._result_gate = threading.Lock()

        self._starting = False
        self._finalize_scheduled = False

        self._thread = None
        self._worker = None

        self._state = _idle_state()

        self._pending_state = None
        self._pending_fatal = False

    @property
    def state(
        self,
    ):
        with self._gate:
            return self._state

    @property
    def is_running(
        self,
    ):
        with self._gate:
            return (
                self._starting
                or self._thread is not None
            )

    def _reserve_start(
        self,
        running_state,
    ):
        """Reserve one execution before constructing any Qt runtime object."""
        with self._gate:
            if (
                self._starting
                or self._thread is not None
                or self._finalize_scheduled
            ):
                raise RuntimeError(
                    "provider_diagnostics_qt_thread_bridge_busy"
                )

            self._starting = True
            self._state = running_state

    def _clear_pending_result(
        self,
    ):
        with self._result_gate:
            self._pending_state = None
            self._pending_fatal = False

    def _release_start_reservation_as_failure(
        self,
    ):
        failed_state = _internal_failed_state()

        with self._gate:
            self._starting = False
            self._finalize_scheduled = False
            self._thread = None
            self._worker = None
            self._state = failed_state

        self._clear_pending_result()

        return failed_state

    def start(
        self,
        request,
        remote_image_source=None,
    ):
        """Start one diagnostic execution without blocking the caller."""
        running_state = _running_state()

        # Reserve first.
        #
        # A rejected second start therefore creates no temporary QThread and
        # no QObject moved to a thread whose event loop will never run.
        self._reserve_start(
            running_state
        )

        thread = None
        worker = None

        try:
            thread = QThread()

            worker = ProviderDiagnosticsQtWorker(
                request,
                remote_image_source,
            )

            worker.state_changed.connect(
                self._capture_state,
                type=(
                    Qt.ConnectionType
                    .DirectConnection
                ),
            )

            worker.fatal.connect(
                self._capture_fatal,
                type=(
                    Qt.ConnectionType
                    .DirectConnection
                ),
            )

            worker.finished.connect(
                self._capture_finished,
                type=(
                    Qt.ConnectionType
                    .DirectConnection
                ),
            )

            worker.finished.connect(
                thread.quit,
                type=(
                    Qt.ConnectionType
                    .DirectConnection
                ),
            )

            worker.finished.connect(
                worker.deleteLater,
                type=(
                    Qt.ConnectionType
                    .DirectConnection
                ),
            )

            thread.started.connect(
                worker.run
            )

            thread.started.connect(
                self._on_thread_started
            )

            thread.finished.connect(
                self._on_thread_finished
            )

            worker.moveToThread(
                thread
            )

        except BaseException:
            self._release_start_reservation_as_failure()

            if worker is not None:
                try:
                    worker.deleteLater()

                except BaseException:
                    pass

            if thread is not None:
                try:
                    thread.deleteLater()

                except BaseException:
                    pass

            raise

        self._clear_pending_result()

        with self._gate:
            self._thread = thread
            self._worker = worker
            self._starting = False
            self._finalize_scheduled = False
            self._state = running_state

        try:
            thread.start()

        except BaseException:
            self._release_start_reservation_as_failure()

            try:
                thread.deleteLater()

            except BaseException:
                pass

            raise

        return running_state

    def request_cancel(
        self,
    ):
        """Request cancellation safely from the GUI/main thread."""
        with self._gate:
            worker = self._worker

        if worker is None:
            return False

        worker.request_cancel()

        return True

    @pyqtSlot()
    def _on_thread_started(
        self,
    ):
        self.started.emit()

    @pyqtSlot(object)
    def _capture_state(
        self,
        state,
    ):
        fatal = False

        try:
            state = _validate_terminal_state(
                state
            )

        except BaseException:
            state = _internal_failed_state()
            fatal = True

        with self._result_gate:
            self._pending_state = state

            if fatal:
                self._pending_fatal = True

    @pyqtSlot()
    def _capture_fatal(
        self,
    ):
        with self._result_gate:
            self._pending_fatal = True

    @pyqtSlot(object)
    def _capture_finished(
        self,
        state,
    ):
        fatal = False

        try:
            state = _validate_terminal_state(
                state
            )

        except BaseException:
            state = _internal_failed_state()
            fatal = True

        with self._result_gate:
            self._pending_state = state

            if fatal:
                self._pending_fatal = True

    @pyqtSlot()
    def _on_thread_finished(
        self,
    ):
        """Schedule final cleanup after Qt finishes dispatching this signal."""
        with self._gate:
            if self._finalize_scheduled:
                return

            self._finalize_scheduled = True

        # Do not release self._thread here.
        #
        # We are currently inside delivery of QThread.finished. Releasing the
        # last Python reference to that QThread from this callback can cause
        # PyQt/Qt object destruction while Qt is still dispatching the same
        # signal.
        #
        # Defer finalization by one GUI event-loop turn.
        QTimer.singleShot(
            0,
            self._finalize_thread_finished,
        )

    @pyqtSlot()
    def _finalize_thread_finished(
        self,
    ):
        """Finalize one completed thread outside QThread.finished dispatch."""
        with self._result_gate:
            state = self._pending_state
            fatal = self._pending_fatal

            self._pending_state = None
            self._pending_fatal = False

        if state is None:
            state = _internal_failed_state()
            fatal = True

        # Keep a local reference alive throughout finalization.
        #
        # This guarantees that clearing self._thread cannot destroy the
        # QThread wrapper until this method itself is done using it.
        with self._gate:
            thread = self._thread

            self._state = state
            self._worker = None
            self._thread = None
            self._starting = False
            self._finalize_scheduled = False

        # We are now outside QThread.finished signal dispatch. It is safe to
        # schedule destruction of the QThread QObject.
        if thread is not None:
            try:
                thread.deleteLater()

            except RuntimeError:
                # The underlying Qt object may already have been deleted by
                # external ownership. There is no runtime data to expose and
                # the diagnostic state has already been finalized safely.
                pass

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
            "provider_diagnostics_qt_thread_bridge_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_qt_thread_bridge_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_thread_bridge_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsQtThreadBridge("
            f"phase={self.state.phase.value!r}, "
            f"is_running={self.is_running!r}"
            ")"
        )