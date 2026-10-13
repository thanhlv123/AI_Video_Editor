"""M99 binding between the diagnostics Qt view and M98 thread bridge.

The binder coordinates Qt presentation and the existing M98 execution
bridge without constructing diagnostic jobs itself.

Architecture:

    ProviderDiagnosticsQtView
        -> ProviderDiagnosticsQtViewBinder
        -> ProviderDiagnosticsQtThreadBridge

The binder:

- forwards run intent to the integration owner;
- delegates cancellation to M98;
- starts M98 only when already-built runtime arguments are supplied;
- renders M98 controller states into the M99 view;
- forwards safe lifecycle signals.

Runtime arguments are accepted only as method arguments. The binder does not
resolve credentials, inspect credential values, or retain runtime authority
after a start method returns.

The original ``start`` path preserves the pre-M100 M98 execution path.
M100 host integration may use ``start_with_credential_source_factory`` to
transit caller-owned runtime credential authority directly into M98.
"""

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
)

from ..provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
)
from .view import (
    ProviderDiagnosticsQtView,
)


class ProviderDiagnosticsQtViewBinder(
    QObject
):
    """Bind one M99 diagnostics view to one M98 thread bridge."""

    run_requested = pyqtSignal()

    cancel_requested = pyqtSignal()

    action_requested = pyqtSignal(
        object
    )

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
        view,
        bridge,
        parent=None,
    ):
        super().__init__(
            parent
        )

        if (
            type(view)
            is not ProviderDiagnosticsQtView
        ):
            raise TypeError(
                "provider_diagnostics_qt_view_binder_view_required"
            )

        if (
            type(bridge)
            is not ProviderDiagnosticsQtThreadBridge
        ):
            raise TypeError(
                "provider_diagnostics_qt_view_binder_bridge_required"
            )

        self._view = view

        self._bridge = bridge

        self._connect()

    @property
    def phase(
        self,
    ):
        return self._view.phase

    @property
    def current_action(
        self,
    ):
        return self._view.current_action

    @property
    def is_running(
        self,
    ):
        return self._bridge.is_running

    def _connect(
        self,
    ):
        self._view.run_requested.connect(
            self._on_view_run_requested
        )

        self._view.cancel_requested.connect(
            self._on_view_cancel_requested
        )

        self._view.action_requested.connect(
            self._on_view_action_requested
        )

        self._bridge.started.connect(
            self._on_bridge_started
        )

        self._bridge.state_changed.connect(
            self._on_bridge_state_changed
        )

        self._bridge.fatal.connect(
            self._on_bridge_fatal
        )

        self._bridge.finished.connect(
            self._on_bridge_finished
        )

    def _publish_started_state(
        self,
        state,
    ):
        self._view.bind_state(
            state
        )

        self.state_changed.emit(
            state
        )

        return state

    def start(
        self,
        request,
        remote_image_source=None,
    ):
        """Start M98 using caller-supplied runtime arguments."""
        state = self._bridge.start(
            request,
            remote_image_source,
        )

        return self._publish_started_state(
            state
        )

    def start_with_credential_source_factory(
        self,
        request,
        credential_source_factory,
        remote_image_source=None,
    ):
        """
        Transit one caller-owned runtime credential-source factory into M98.

        The binder neither interprets nor stores the factory. M98 assumes
        temporary runtime ownership for the one execution.
        """
        state = (
            self._bridge
            .start_with_credential_source_factory(
                request,
                credential_source_factory,
                remote_image_source,
            )
        )

        return self._publish_started_state(
            state
        )

    def request_cancel(
        self,
    ):
        """Request cancellation through the M98 bridge."""
        return self._bridge.request_cancel()

    @pyqtSlot()
    def _on_view_run_requested(
        self,
    ):
        self.run_requested.emit()

    @pyqtSlot()
    def _on_view_cancel_requested(
        self,
    ):
        self.cancel_requested.emit()

        self.request_cancel()

    @pyqtSlot(object)
    def _on_view_action_requested(
        self,
        action,
    ):
        self.action_requested.emit(
            action
        )

    @pyqtSlot()
    def _on_bridge_started(
        self,
    ):
        self.started.emit()

    @pyqtSlot(object)
    def _on_bridge_state_changed(
        self,
        state,
    ):
        self._view.bind_state(
            state
        )

        self.state_changed.emit(
            state
        )

    @pyqtSlot()
    def _on_bridge_fatal(
        self,
    ):
        self.fatal.emit()

    @pyqtSlot(object)
    def _on_bridge_finished(
        self,
        state,
    ):
        self.finished.emit(
            state
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_binder_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_binder_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_binder_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsQtViewBinder("
            f"phase={self.phase.value!r}, "
            f"action={self.current_action.value!r}, "
            f"is_running={self.is_running!r}"
            ")"
        )