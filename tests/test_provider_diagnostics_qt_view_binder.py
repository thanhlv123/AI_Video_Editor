"""M99 provider diagnostics Qt view binder tests."""

import copy
import inspect
import os
import pickle
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PyQt6.QtCore import (
    QObject,
)
from PyQt6.QtWidgets import (
    QApplication,
)


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
        "provider_diagnostics_qt_view_binder_tests_require_qapplication"
    )


import creator_studio.provider_diagnostics_qt_view as package_api
import creator_studio.provider_diagnostics_qt_view.public_api as public_api
import creator_studio.provider_diagnostics_qt_view.binder as binder_module

from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
)
from creator_studio.provider_diagnostics_qt_view.binder import (
    ProviderDiagnosticsQtViewBinder,
)
from creator_studio.provider_diagnostics_qt_view.public_api import (
    ProviderDiagnosticsQtView,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
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


def running_state():
    return controller_state(
        ProviderDiagnosticsGuiControllerPhase
        .RUNNING
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


def credential_view_model():
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


class ProviderDiagnosticsQtViewBinderTests(
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
                "M99 binder tests require QApplication"
            )

    def setUp(
        self,
    ):
        self.view = (
            ProviderDiagnosticsQtView()
        )

        self.bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        self.binder = (
            ProviderDiagnosticsQtViewBinder(
                self.view,
                self.bridge,
            )
        )

    def tearDown(
        self,
    ):
        self.view.close()

        self.binder.deleteLater()

        self.bridge.deleteLater()

        self.view.deleteLater()

        QApplication.processEvents()

    def test_binder_is_qobject(self):
        self.assertIsInstance(
            self.binder,
            QObject,
        )

    def test_constructor_signature(self):
        parameters = inspect.signature(
            ProviderDiagnosticsQtViewBinder
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "view",
                "bridge",
                "parent",
            ),
        )

        self.assertIsNone(
            parameters[
                "parent"
            ].default
        )

    def test_start_signature(self):
        parameters = inspect.signature(
            ProviderDiagnosticsQtViewBinder
            .start
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "request",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_exact_view_is_required(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_binder_view_required$",
        ):
            ProviderDiagnosticsQtViewBinder(
                object(),
                self.bridge,
            )

    def test_exact_bridge_is_required(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_binder_bridge_required$",
        ):
            ProviderDiagnosticsQtViewBinder(
                self.view,
                object(),
            )

    def test_binder_is_not_yet_exported_from_package_api(self):
        self.assertNotIn(
            "ProviderDiagnosticsQtViewBinder",
            package_api.__all__,
        )

        self.assertFalse(
            hasattr(
                package_api,
                "ProviderDiagnosticsQtViewBinder",
            )
        )

    def test_binder_is_not_yet_exported_from_public_api(self):
        self.assertNotIn(
            "ProviderDiagnosticsQtViewBinder",
            public_api.__all__,
        )

        self.assertFalse(
            hasattr(
                public_api,
                "ProviderDiagnosticsQtViewBinder",
            )
        )

    def test_initial_phase_is_idle(self):
        self.assertIs(
            self.binder.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

    def test_initial_action_is_none(self):
        self.assertIs(
            self.binder.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

    def test_initial_is_running_is_false(self):
        self.assertIs(
            self.binder.is_running,
            False,
        )

    def test_initial_repr_contains_only_safe_metadata(self):
        self.assertEqual(
            repr(
                self.binder
            ),
            (
                "ProviderDiagnosticsQtViewBinder("
                "phase='IDLE', "
                "action='NONE', "
                "is_running=False"
                ")"
            ),
        )

    def test_run_button_forwards_run_intent(self):
        calls = []

        self.binder.run_requested.connect(
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

    def test_run_button_does_not_start_bridge_by_itself(self):
        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
        ) as start:
            self.view.run_button.click()

        start.assert_not_called()

    def test_action_signal_is_forwarded(self):
        actions = []

        self.binder.action_requested.connect(
            actions.append
        )

        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=credential_view_model(),
        )

        self.view.bind_state(
            state
        )

        self.view.action_button.click()

        self.assertEqual(
            actions,
            [
                ProviderDiagnosticsViewAction
                .CONFIGURE_CREDENTIAL,
            ],
        )

    def test_cancel_button_forwards_intent_and_calls_bridge(self):
        calls = []

        self.binder.cancel_requested.connect(
            lambda: calls.append(
                True
            )
        )

        self.view.bind_state(
            running_state()
        )

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "request_cancel",
            return_value=True,
        ) as cancel:
            self.view.cancel_button.click()

        self.assertEqual(
            calls,
            [
                True,
            ],
        )

        cancel.assert_called_once_with()

    def test_request_cancel_delegates_to_bridge(self):
        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "request_cancel",
            return_value=True,
        ) as cancel:
            result = self.binder.request_cancel()

        self.assertIs(
            result,
            True,
        )

        cancel.assert_called_once_with()

    def test_start_calls_bridge_with_runtime_arguments(self):
        request = object()

        remote_source = object()

        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            return_value=state,
        ) as start:
            returned = self.binder.start(
                request,
                remote_source,
            )

        self.assertIs(
            returned,
            state,
        )

        start.assert_called_once_with(
            request,
            remote_source,
        )

    def test_start_without_remote_source_passes_none(self):
        request = object()

        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            return_value=state,
        ) as start:
            self.binder.start(
                request
            )

        start.assert_called_once_with(
            request,
            None,
        )

    def test_start_renders_running_state(self):
        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            return_value=state,
        ):
            self.binder.start(
                object()
            )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertFalse(
            self.view.run_button.isEnabled()
        )

        self.assertTrue(
            self.view.cancel_button.isEnabled()
        )

    def test_start_emits_running_state(self):
        state = running_state()

        states = []

        self.binder.state_changed.connect(
            states.append
        )

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            return_value=state,
        ):
            self.binder.start(
                object()
            )

        self.assertEqual(
            states,
            [
                state,
            ],
        )

    def test_start_does_not_retain_runtime_arguments(self):
        request = object()

        remote_source = object()

        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            return_value=state,
        ):
            self.binder.start(
                request,
                remote_source,
            )

        for value in self.binder.__dict__.values():
            self.assertIsNot(
                value,
                request,
            )

            self.assertIsNot(
                value,
                remote_source,
            )

    def test_start_failure_does_not_render_running(self):
        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start",
            side_effect=RuntimeError(
                "bridge-start-failed"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^bridge-start-failed$",
            ):
                self.binder.start(
                    object()
                )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

    def test_bridge_completed_ready_state_updates_view(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=ready_view_model(),
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Provider ready",
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

    def test_bridge_completed_action_state_updates_view(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=credential_view_model(),
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            self.view.action_button.text(),
            "Configure credential",
        )

    def test_bridge_cancelled_state_updates_view(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics cancelled",
        )

    def test_bridge_failed_state_updates_view(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            failure=(
                ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertEqual(
            self.view.status_label.text(),
            "Diagnostics failed",
        )

    def test_bridge_state_changed_is_forwarded(self):
        states = []

        self.binder.state_changed.connect(
            states.append
        )

        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertEqual(
            states,
            [
                state,
            ],
        )

    def test_bridge_started_is_forwarded(self):
        calls = []

        self.binder.started.connect(
            lambda: calls.append(
                True
            )
        )

        self.bridge.started.emit()

        self.assertEqual(
            calls,
            [
                True,
            ],
        )

    def test_bridge_fatal_is_forwarded(self):
        calls = []

        self.binder.fatal.connect(
            lambda: calls.append(
                True
            )
        )

        self.bridge.fatal.emit()

        self.assertEqual(
            calls,
            [
                True,
            ],
        )

    def test_bridge_finished_is_forwarded(self):
        states = []

        self.binder.finished.connect(
            states.append
        )

        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        )

        self.bridge.finished.emit(
            state
        )

        self.assertEqual(
            states,
            [
                state,
            ],
        )

    def test_current_action_property_tracks_view(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=credential_view_model(),
        )

        self.bridge.state_changed.emit(
            state
        )

        self.assertIs(
            self.binder.current_action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

    def test_repr_tracks_safe_view_metadata(self):
        state = controller_state(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=credential_view_model(),
        )

        self.bridge.state_changed.emit(
            state
        )

        representation = repr(
            self.binder
        )

        self.assertIn(
            "phase='COMPLETED'",
            representation,
        )

        self.assertIn(
            "action='CONFIGURE_CREDENTIAL'",
            representation,
        )

        self.assertNotIn(
            "Credential required",
            representation,
        )

        self.assertNotIn(
            "Configure a provider credential.",
            representation,
        )

    def test_binder_not_copyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_binder_runtime_only$",
        ):
            copy.copy(
                self.binder
            )

    def test_binder_not_deepcopyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_binder_runtime_only$",
        ):
            copy.deepcopy(
                self.binder
            )

    def test_binder_not_pickleable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_view_binder_runtime_only$",
        ):
            pickle.dumps(
                self.binder
            )

    def test_binder_layer_has_no_direct_runtime_or_network_access(self):
        source = Path(
            binder_module.__file__
        ).read_text(
            encoding="utf-8"
        )

        forbidden = (
            "os.environ",
            "os.getenv",
            "urllib",
            "requests",
            "_open_https",
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

    def test_binder_does_not_import_credential_runtime_authority(self):
        source = Path(
            binder_module.__file__
        ).read_text(
            encoding="utf-8"
        )

        forbidden = (
            "EnvironmentCredentialSource",
            "ProviderRuntimeAssembly",
            "assemble_provider_runtime",
            "ProviderConnectivityProbe",
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