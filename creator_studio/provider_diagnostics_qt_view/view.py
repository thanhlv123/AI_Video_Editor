"""M99 Qt view for provider diagnostics.

This module renders the safe M97/M96 diagnostics state into ordinary Qt
widgets.

Architecture:

    M97 ProviderDiagnosticsGuiControllerState
        -> ProviderDiagnosticsQtView
        -> labels / buttons / user intent signals

This view does not execute diagnostics. It does not assemble provider
runtimes, access external services or resolve runtime authentication data.

The widget stores only safe presentation metadata:

- current M97 phase;
- current M96 action enum.

It intentionally does not retain the supplied M97 state or M96 view model.
"""

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)
from ..provider_diagnostics_view_model.public_api import (
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewSeverity,
    validate_provider_diagnostics_view_model,
)


class ProviderDiagnosticsQtView(
    QWidget
):
    """Render provider diagnostic state without executing diagnostics."""

    run_requested = pyqtSignal()

    cancel_requested = pyqtSignal()

    action_requested = pyqtSignal(
        object
    )

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self._phase = (
            ProviderDiagnosticsGuiControllerPhase
            .IDLE
        )

        self._current_action = (
            ProviderDiagnosticsViewAction
            .NONE
        )

        self._build_ui()

        self._render_idle()

    @property
    def phase(
        self,
    ):
        return self._phase

    @property
    def current_action(
        self,
    ):
        return self._current_action

    def _build_ui(
        self,
    ):
        self.setObjectName(
            "providerDiagnosticsView"
        )

        layout = QVBoxLayout(
            self
        )

        self.title_label = QLabel(
            "Provider Diagnostics"
        )

        self.title_label.setObjectName(
            "providerDiagnosticsTitleLabel"
        )

        self.status_label = QLabel()

        self.status_label.setObjectName(
            "providerDiagnosticsStatusLabel"
        )

        self.status_label.setWordWrap(
            True
        )

        self.detail_label = QLabel()

        self.detail_label.setObjectName(
            "providerDiagnosticsDetailLabel"
        )

        self.detail_label.setWordWrap(
            True
        )

        self.severity_label = QLabel()

        self.severity_label.setObjectName(
            "providerDiagnosticsSeverityLabel"
        )

        self.action_button = QPushButton()

        self.action_button.setObjectName(
            "providerDiagnosticsActionButton"
        )

        self.action_button.clicked.connect(
            self._emit_action_requested
        )

        button_row = QHBoxLayout()

        self.run_button = QPushButton(
            "Run Diagnostics"
        )

        self.run_button.setObjectName(
            "providerDiagnosticsRunButton"
        )

        self.run_button.clicked.connect(
            self.run_requested
        )

        self.cancel_button = QPushButton(
            "Cancel"
        )

        self.cancel_button.setObjectName(
            "providerDiagnosticsCancelButton"
        )

        self.cancel_button.clicked.connect(
            self.cancel_requested
        )

        button_row.addWidget(
            self.run_button
        )

        button_row.addWidget(
            self.cancel_button
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.status_label
        )

        layout.addWidget(
            self.detail_label
        )

        layout.addWidget(
            self.severity_label
        )

        layout.addWidget(
            self.action_button
        )

        layout.addLayout(
            button_row
        )

    def _set_phase(
        self,
        phase,
    ):
        self._phase = phase

        self.setProperty(
            "diagnosticsPhase",
            phase.value,
        )

    def _set_severity(
        self,
        text,
        property_value,
    ):
        self.severity_label.setText(
            text
        )

        self.severity_label.setProperty(
            "diagnosticsSeverity",
            property_value,
        )

    def _clear_action(
        self,
    ):
        self._current_action = (
            ProviderDiagnosticsViewAction
            .NONE
        )

        self.action_button.setText(
            ""
        )

        self.action_button.setEnabled(
            False
        )

        self.action_button.setVisible(
            False
        )

    def _set_action(
        self,
        action,
        action_text,
    ):
        self._current_action = action

        if (
            action
            is ProviderDiagnosticsViewAction
            .NONE
        ):
            self._clear_action()

            return

        self.action_button.setText(
            action_text
        )

        self.action_button.setEnabled(
            True
        )

        self.action_button.setVisible(
            True
        )

    def _render_idle(
        self,
    ):
        self._set_phase(
            ProviderDiagnosticsGuiControllerPhase
            .IDLE
        )

        self.status_label.setText(
            "Diagnostics ready"
        )

        self.detail_label.setText(
            "Run diagnostics to check provider readiness."
        )

        self._set_severity(
            "Not run",
            "IDLE",
        )

        self._clear_action()

        self.run_button.setEnabled(
            True
        )

        self.cancel_button.setEnabled(
            False
        )

    def _render_running(
        self,
    ):
        self._set_phase(
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING
        )

        self.status_label.setText(
            "Running diagnostics"
        )

        self.detail_label.setText(
            "Checking provider configuration and connectivity."
        )

        self._set_severity(
            "Running",
            "RUNNING",
        )

        self._clear_action()

        self.run_button.setEnabled(
            False
        )

        self.cancel_button.setEnabled(
            True
        )

    def _render_completed(
        self,
        view_model,
    ):
        validate_provider_diagnostics_view_model(
            view_model
        )

        self._set_phase(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED
        )

        self.status_label.setText(
            view_model.status_text
        )

        self.detail_label.setText(
            view_model.detail_text
        )

        severity = view_model.severity

        self._set_severity(
            severity.value.title(),
            severity.value,
        )

        self._set_action(
            view_model.action,
            view_model.action_text,
        )

        self.run_button.setEnabled(
            True
        )

        self.cancel_button.setEnabled(
            False
        )

    def _render_cancelled(
        self,
    ):
        self._set_phase(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        )

        self.status_label.setText(
            "Diagnostics cancelled"
        )

        self.detail_label.setText(
            "The diagnostic run was cancelled."
        )

        self._set_severity(
            "Warning",
            ProviderDiagnosticsViewSeverity
            .WARNING
            .value,
        )

        self._clear_action()

        self.run_button.setEnabled(
            True
        )

        self.cancel_button.setEnabled(
            False
        )

    def _render_failed(
        self,
        failure,
    ):
        self._set_phase(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED
        )

        if (
            failure
            is ProviderDiagnosticsGuiControllerFailure
            .INVALID_REQUEST
        ):
            status_text = (
                "Diagnostics unavailable"
            )

            detail_text = (
                "The diagnostic request is invalid."
            )

        else:
            status_text = (
                "Diagnostics failed"
            )

            detail_text = (
                "An internal failure prevented diagnostics "
                "from completing."
            )

        self.status_label.setText(
            status_text
        )

        self.detail_label.setText(
            detail_text
        )

        self._set_severity(
            "Error",
            ProviderDiagnosticsViewSeverity
            .ERROR
            .value,
        )

        self._clear_action()

        self.run_button.setEnabled(
            True
        )

        self.cancel_button.setEnabled(
            False
        )

    def bind_state(
        self,
        state,
    ):
        """Render one validated M97 controller state."""
        validate_provider_diagnostics_gui_controller_state(
            state
        )

        phase = state.phase

        if (
            phase
            is ProviderDiagnosticsGuiControllerPhase
            .IDLE
        ):
            self._render_idle()

        elif (
            phase
            is ProviderDiagnosticsGuiControllerPhase
            .RUNNING
        ):
            self._render_running()

        elif (
            phase
            is ProviderDiagnosticsGuiControllerPhase
            .COMPLETED
        ):
            self._render_completed(
                state.view_model
            )

        elif (
            phase
            is ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        ):
            self._render_cancelled()

        elif (
            phase
            is ProviderDiagnosticsGuiControllerPhase
            .FAILED
        ):
            self._render_failed(
                state.failure
            )

        return state

    def reset(
        self,
    ):
        """Return the view to its initial IDLE presentation."""
        self._render_idle()

    def _emit_action_requested(
        self,
    ):
        if (
            self._current_action
            is ProviderDiagnosticsViewAction
            .NONE
        ):
            return

        self.action_requested.emit(
            self._current_action
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_qt_view_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsQtView("
            f"phase={self._phase.value!r}, "
            f"action={self._current_action.value!r}"
            ")"
        )