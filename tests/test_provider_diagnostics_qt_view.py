"""M99 provider diagnostics Qt view tests."""

import copy
import inspect
import os
import pickle
from pathlib import Path
import unittest

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
)


# Keep one real QApplication alive for the entire test process.
#
# This is intentionally created at module-import time rather than in
# setUpClass.
#
# The M98 Qt worker tests use QCoreApplication. When unittest loads all test
# modules before executing them, importing this M99 module establishes
# QApplication as the process-wide Qt application object. QApplication is also
# a QCoreApplication, so the M98 tests remain compatible, while QWidget tests
# in this module have the GUI-capable application object they require.
_TEST_APPLICATION = QApplication.instance()

if _TEST_APPLICATION is None:
    _TEST_APPLICATION = QApplication(
        []
    )

elif not isinstance(
    _TEST_APPLICATION,
    QApplication,
):
    raise RuntimeError(
        "provider_diagnostics_qt_view_tests_require_qapplication"
    )


import creator_studio.provider_diagnostics_qt_view as package_api
import creator_studio.provider_diagnostics_qt_view.public_api as public_api
import creator_studio.provider_diagnostics_qt_view.view as view_module

from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
)


EXPECTED_PUBLIC_API = (
    "PROVIDER_DIAGNOSTICS_QT_VIEW_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtView",
)


def controller_state(
    phase,
    *,
    view_model=None,
    failure=None,
):
    return ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=phase,
        view_model=view_model,
        failure=failure,
    )


def ready_view_model():
    return ProviderDiagnosticsViewModel(
        schema_version=(
            PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Provider ready",
        detail_text="OpenAI is ready for use.",
        severity=(
            ProviderDiagnosticsViewSeverity
            .SUCCESS
        ),
        action=(
            ProviderDiagnosticsViewAction
            .NONE
        ),
        action_text="No action required.",
        is_ready=True,
    )


def configure_credential_view_model():
    return ProviderDiagnosticsViewModel(
        schema_version=(
            PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Credential required",
        detail_text="Configure a provider credential.",
        severity=(
            ProviderDiagnosticsViewSeverity
            .WARNING
        ),
        action=(
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL
        ),
        action_text="Configure credential",
        is_ready=False,
    )


class ProviderDiagnosticsQtViewTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = _TEST_APPLICATION

        if not isinstance(
            cls.app,
            QApplication,
        ):
            raise AssertionError(
                "M99 Qt view tests require QApplication"
            )

    def setUp(
        self,
    ):
        self.view = (
            public_api
            .ProviderDiagnosticsQtView()
        )

    def tearDown(
        self,
    ):
        self.view.close()

        self.view.deleteLater()

        QApplication.processEvents()

    def test_public_api_version(self):
        self.assertEqual(
            public_api
            .PROVIDER_DIAGNOSTICS_QT_VIEW_PUBLIC_API_VERSION,
            1,
        )

    def test_public_api_all_is_exact(self):
        self.assertEqual(
            public_api.__all__,
            EXPECTED_PUBLIC_API,
        )

    def test_package_all_is_exact(self):
        self.assertEqual(
            package_api.__all__,
            EXPECTED_PUBLIC_API,
        )

    def test_package_and_public_view_identity(self):
        self.assertIs(
            package_api.ProviderDiagnosticsQtView,
            public_api.ProviderDiagnosticsQtView,
        )

    def test_view_is_qwidget(self):
        self.assertIsInstance(
            self.view,
            QWidget,
        )

    def test_constructor_signature(self):
        parameters = inspect.signature(
            public_api.ProviderDiagnosticsQtView
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "parent",
            ),
        )

        self.assertIsNone(
            parameters[
                "parent"
            ].default
        )

    def test_bind_state_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    public_api
                    .ProviderDiagnosticsQtView
                    .bind_state
                ).parameters
            ),
            (
                "self",
                "state",
            ),
        )

    def test_initial_state_is_idle(self):
        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics ready",
        )

        self.assertEqual(
            self.view.severity_label.text(),
            "Not run",
        )

        self.assertTrue(
            self.view.run_button.isEnabled()
        )

        self.assertFalse(
            self.view.cancel_button.isEnabled()
        )

        self.assertTrue(
            self.view.action_button.isHidden()
        )

    def test_widget_object_names_are_stable(self):
        self.assertEqual(
            self.view.objectName(),
            "providerDiagnosticsView",
        )

        self.assertEqual(
            self.view.status_label.objectName(),
            "providerDiagnosticsStatusLabel",
        )

        self.assertEqual(
            self.view.detail_label.objectName(),
            "providerDiagnosticsDetailLabel",
        )

        self.assertEqual(
            self.view.severity_label.objectName(),
            "providerDiagnosticsSeverityLabel",
        )

        self.assertEqual(
            self.view.action_button.objectName(),
            "providerDiagnosticsActionButton",
        )

        self.assertEqual(
            self.view.run_button.objectName(),
            "providerDiagnosticsRunButton",
        )

        self.assertEqual(
            self.view.cancel_button.objectName(),
            "providerDiagnosticsCancelButton",
        )

    def test_running_state_updates_controls(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING
        )

        returned = self.view.bind_state(
            state
        )

        self.assertIs(
            returned,
            state,
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Running diagnostics",
        )

        self.assertFalse(
            self.view.run_button.isEnabled()
        )

        self.assertTrue(
            self.view.cancel_button.isEnabled()
        )

        self.assertTrue(
            self.view.action_button.isHidden()
        )

    def test_completed_ready_state_uses_safe_view_model_text(self):
        model = ready_view_model()

        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=model,
        )

        self.view.bind_state(
            state
        )

        self.assertEqual(
            self.view.status_label.text(),
            model.status_text,
        )

        self.assertEqual(
            self.view.detail_label.text(),
            model.detail_text,
        )

        self.assertEqual(
            self.view.severity_label.text(),
            "Success",
        )

        self.assertEqual(
            self.view.severity_label.property(
                "diagnosticsSeverity"
            ),
            "SUCCESS",
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertTrue(
            self.view.action_button.isHidden()
        )

        self.assertTrue(
            self.view.run_button.isEnabled()
        )

        self.assertFalse(
            self.view.cancel_button.isEnabled()
        )

    def test_completed_action_state_shows_action(self):
        model = (
            configure_credential_view_model()
        )

        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=model,
        )

        self.view.bind_state(
            state
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertFalse(
            self.view.action_button.isHidden()
        )

        self.assertTrue(
            self.view.action_button.isEnabled()
        )

        self.assertEqual(
            self.view.action_button.text(),
            model.action_text,
        )

    def test_cancelled_state_is_safe_static_presentation(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        )

        self.view.bind_state(
            state
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics cancelled",
        )

        self.assertEqual(
            self.view.severity_label.text(),
            "Warning",
        )

        self.assertTrue(
            self.view.run_button.isEnabled()
        )

        self.assertFalse(
            self.view.cancel_button.isEnabled()
        )

    def test_invalid_request_failed_state(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            failure=(
                ProviderDiagnosticsGuiControllerFailure
                .INVALID_REQUEST
            ),
        )

        self.view.bind_state(
            state
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics unavailable",
        )

        self.assertEqual(
            self.view.detail_label.text(),
            "The diagnostic request is invalid.",
        )

        self.assertEqual(
            self.view.severity_label.text(),
            "Error",
        )

    def test_internal_failed_state(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            failure=(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        self.view.bind_state(
            state
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics failed",
        )

        self.assertEqual(
            self.view.severity_label.text(),
            "Error",
        )

    def test_run_signal_contains_no_runtime_argument(self):
        calls = []

        self.view.run_requested.connect(
            lambda: calls.append(
                True
            )
        )

        self.view.run_button.click()

        self.assertEqual(
            calls,
            [
                True,
            ],
        )

    def test_cancel_signal_contains_no_runtime_argument(self):
        calls = []

        self.view.cancel_requested.connect(
            lambda: calls.append(
                True
            )
        )

        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )
        )

        self.view.cancel_button.click()

        self.assertEqual(
            calls,
            [
                True,
            ],
        )

    def test_action_signal_contains_only_safe_action_enum(self):
        actions = []

        self.view.action_requested.connect(
            actions.append
        )

        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .COMPLETED,
                view_model=(
                    configure_credential_view_model()
                ),
            )
        )

        self.view.action_button.click()

        self.assertEqual(
            actions,
            [
                ProviderDiagnosticsViewAction
                .CONFIGURE_CREDENTIAL,
            ],
        )

    def test_none_action_cannot_emit_action_signal(self):
        actions = []

        self.view.action_requested.connect(
            actions.append
        )

        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .COMPLETED,
                view_model=ready_view_model(),
            )
        )

        self.view._emit_action_requested()

        self.assertEqual(
            actions,
            [],
        )

    def test_new_state_clears_previous_action(self):
        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .COMPLETED,
                view_model=(
                    configure_credential_view_model()
                ),
            )
        )

        self.assertFalse(
            self.view.action_button.isHidden()
        )

        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertTrue(
            self.view.action_button.isHidden()
        )

    def test_reset_restores_idle(self):
        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )
        )

        self.view.reset()

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertTrue(
            self.view.run_button.isEnabled()
        )

        self.assertFalse(
            self.view.cancel_button.isEnabled()
        )

    def test_invalid_state_is_rejected(self):
        with self.assertRaises(
            (
                TypeError,
                ValueError,
            )
        ):
            self.view.bind_state(
                object()
            )

    def test_view_does_not_retain_controller_state(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=ready_view_model(),
        )

        self.view.bind_state(
            state
        )

        for value in self.view.__dict__.values():
            self.assertIsNot(
                value,
                state,
            )

            self.assertNotIsInstance(
                value,
                ProviderDiagnosticsGuiControllerState,
            )

            self.assertNotIsInstance(
                value,
                ProviderDiagnosticsViewModel,
            )

    def test_repr_contains_only_safe_metadata(self):
        self.view.bind_state(
            controller_state(
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )
        )

        self.assertEqual(
            repr(
                self.view
            ),
            (
                "ProviderDiagnosticsQtView("
                "phase='RUNNING', "
                "action='NONE'"
                ")"
            ),
        )

    def test_view_not_copyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_runtime_only$",
        ):
            copy.copy(
                self.view
            )

    def test_view_not_deepcopyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_runtime_only$",
        ):
            copy.deepcopy(
                self.view
            )

    def test_view_not_pickleable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_runtime_only$",
        ):
            pickle.dumps(
                self.view
            )

    def test_view_layer_has_no_direct_runtime_or_network_access(self):
        source = Path(
            view_module.__file__
        ).read_text(
            encoding="utf-8"
        )

        forbidden = (
            "os.environ",
            "os.getenv",
            "urllib",
            "requests",
            "_open_https",
            "EnvironmentCredentialSource",
            "runtime_environment",
            "get_secret(",
            "get_field_secret(",
            "keyring",
        )

        for token in forbidden:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    source,
                )


if __name__ == "__main__":
    unittest.main()