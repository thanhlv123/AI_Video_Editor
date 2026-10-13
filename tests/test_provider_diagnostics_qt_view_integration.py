"""M99 full-stack diagnostics Qt view integration tests.

These tests keep the complete internal diagnostics path real:

    M99 View
        -> M99 Binder
        -> M98 QThread Bridge
        -> M98 Worker
        -> M97 GUI Controller
        -> M95 Application Service
        -> M93 Runtime Diagnostics
        -> M91 Readiness
        -> M92 Connectivity when ONLINE
        -> M94 Presentation
        -> M96 View Model
        -> M97 terminal state
        -> M98 Bridge
        -> M99 Binder
        -> M99 View

Only the external HTTPS boundary is replaced in ONLINE tests.

The M99 view and binder do not resolve credentials, inspect environment
variables or perform provider network access themselves.
"""

import os
import threading
import unittest
import urllib.error
from unittest.mock import patch

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PyQt6.QtCore import (
    QEventLoop,
    QTimer,
)
from PyQt6.QtWidgets import (
    QApplication,
)


# Keep one GUI-capable Qt application alive for the whole test process.
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
        "provider_diagnostics_qt_view_integration_requires_qapplication"
    )


import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerPhase,
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
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewSeverity,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


class FakeResponse:
    """Minimal M92-compatible HTTPS response."""

    def __init__(
        self,
        status=200,
        body=b"",
    ):
        self.status = status
        self.body = body
        self.closed = False
        self.read_limits = []

    def read(
        self,
        limit=-1,
    ):
        self.read_limits.append(
            limit
        )

        if limit < 0:
            return self.body

        return self.body[
            :limit
        ]

    def close(
        self,
    ):
        self.closed = True


class ProviderDiagnosticsQtViewIntegrationTests(
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
                "M99 integration requires QApplication"
            )

    def setUp(
        self,
    ):
        self.view = ProviderDiagnosticsQtView()

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

    def make_request(
        self,
        mode,
        config=None,
    ):
        if config is None:
            config = openai_runtime_config()

        return ProviderDiagnosticsApplicationRequest(
            schema_version=(
                PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
            ),
            config=config,
            mode=mode,
        )

    def wait_for_finished(
        self,
        start,
        *,
        timeout_ms=3000,
    ):
        loop = QEventLoop()

        results = []

        def finished(
            state,
        ):
            results.append(
                state
            )

            loop.quit()

        self.binder.finished.connect(
            finished
        )

        timer = QTimer()

        timer.setSingleShot(
            True
        )

        timer.timeout.connect(
            loop.quit
        )

        timer.start(
            timeout_ms
        )

        start()

        if not results:
            loop.exec()

        timer.stop()

        try:
            self.binder.finished.disconnect(
                finished
            )

        except TypeError:
            pass

        self.assertEqual(
            len(
                results
            ),
            1,
            "M99 real-stack integration timed out",
        )

        QApplication.processEvents()

        return results[
            0
        ]

    def assert_ready_view(
        self,
        state,
    ):
        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            self.view.status_label.text(),
            state.view_model.status_text,
        )

        self.assertEqual(
            self.view.detail_label.text(),
            state.view_model.detail_text,
        )

        self.assertEqual(
            self.view.severity_label.property(
                "diagnosticsSeverity"
            ),
            ProviderDiagnosticsViewSeverity
            .SUCCESS
            .value,
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertTrue(
            self.view.run_button.isEnabled()
        )

        self.assertFalse(
            self.view.cancel_button.isEnabled()
        )

    def test_offline_ready_flows_through_real_stack_into_view(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
            config,
        )

        secret = (
            "m99-offline-integration-secret"
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable: secret,
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "M99 OFFLINE integration must not use network"
                ),
            ) as opened:
                state = self.wait_for_finished(
                    lambda: self.binder.start(
                        request
                    )
                )

        opened.assert_not_called()

        self.assert_ready_view(
            state
        )

    def test_online_ready_flows_through_real_stack_into_view(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        response = FakeResponse(
            200
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m99-online-integration-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                state = self.wait_for_finished(
                    lambda: self.binder.start(
                        request
                    )
                )

        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

        self.assert_ready_view(
            state
        )

    def test_online_missing_credential_stops_before_network_and_updates_view(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            os.environ.pop(
                config
                .credential_environment_variable,
                None,
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "missing credential must stop before HTTPS"
                ),
            ) as opened:
                state = self.wait_for_finished(
                    lambda: self.binder.start(
                        request
                    )
                )

        opened.assert_not_called()

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertIs(
            self.view.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            self.view.action_button.text(),
            state.view_model.action_text,
        )

        self.assertFalse(
            self.view.action_button.isHidden()
        )

    def test_online_network_failure_updates_view_with_safe_action(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m99-network-failure-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=(
                    urllib.error.URLError(
                        "offline"
                    )
                ),
            ):
                state = self.wait_for_finished(
                    lambda: self.binder.start(
                        request
                    )
                )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        self.assertIs(
            self.view.current_action,
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            self.view.action_button.text(),
            state.view_model.action_text,
        )

        self.assertEqual(
            self.view.severity_label.property(
                "diagnosticsSeverity"
            ),
            state.view_model.severity.value,
        )

    def test_cancel_button_cancels_real_online_stack(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        entered_network = threading.Event()
        release_network = threading.Event()

        def delayed_open_https(
            *args,
            **kwargs,
        ):
            entered_network.set()

            release_network.wait(
                2
            )

            return FakeResponse(
                200
            )

        loop = QEventLoop()

        results = []

        def finished(
            state,
        ):
            results.append(
                state
            )

            loop.quit()

        self.binder.finished.connect(
            finished
        )

        timer = QTimer()

        timer.setSingleShot(
            True
        )

        timer.timeout.connect(
            loop.quit
        )

        timer.start(
            3000
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m99-cancellation-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=delayed_open_https,
            ):
                self.binder.start(
                    request
                )

                self.assertIs(
                    self.view.phase,
                    ProviderDiagnosticsGuiControllerPhase
                    .RUNNING,
                )

                self.assertTrue(
                    self.view.cancel_button.isEnabled()
                )

                self.assertTrue(
                    entered_network.wait(
                        1
                    ),
                    "M99 integration did not reach M92 HTTPS boundary",
                )

                self.view.cancel_button.click()

                release_network.set()

                if not results:
                    loop.exec()

        timer.stop()

        self.assertEqual(
            len(
                results
            ),
            1,
            "cancelled M99 integration did not finish",
        )

        state = results[
            0
        ]

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
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

        self.assertFalse(
            self.binder.is_running
        )

    def test_secret_does_not_enter_view_or_binder_presentation(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        secret = (
            "unique-m99-secret-918273"
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable: secret,
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ):
                state = self.wait_for_finished(
                    lambda: self.binder.start(
                        request
                    )
                )

        self.assert_ready_view(
            state
        )

        visible_text = "\n".join(
            (
                self.view.status_label.text(),
                self.view.detail_label.text(),
                self.view.severity_label.text(),
                self.view.action_button.text(),
                repr(
                    self.view
                ),
                repr(
                    self.binder
                ),
            )
        )

        self.assertNotIn(
            secret,
            visible_text,
        )


if __name__ == "__main__":
    unittest.main()