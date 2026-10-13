"""M98 full-stack provider diagnostics Qt integration tests.

These tests keep the complete internal diagnostics path real:

    QThread
        -> M98 bridge
        -> M98 worker
        -> M97 GUI controller
        -> M95 application service
        -> M93 runtime diagnostics
        -> M91 readiness
        -> M92 connectivity when ONLINE
        -> M94 presentation
        -> M96 view model
        -> M97 terminal state
        -> Qt main-thread signal

Only the external HTTPS boundary is replaced in ONLINE tests.
"""

import os
import threading
import unittest
import urllib.error
from unittest.mock import patch

from PyQt6.QtCore import (
    QCoreApplication,
    QEventLoop,
    QThread,
    QTimer,
)

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    validate_provider_diagnostics_gui_controller_state,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION,
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewSeverity,
    validate_provider_diagnostics_view_model,
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


def http_error(
    code,
):
    return urllib.error.HTTPError(
        url="https://provider.example.test/",
        code=code,
        msg="provider-error",
        hdrs=None,
        fp=None,
    )


class ProviderDiagnosticsQtWorkerIntegrationTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QCoreApplication.instance()
        )

        if cls.app is None:
            cls.app = QCoreApplication(
                []
            )

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
        bridge,
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

        bridge.finished.connect(
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
            bridge.finished.disconnect(
                finished
            )

        except TypeError:
            pass

        self.assertEqual(
            len(
                results
            ),
            1,
            "M98 full-stack integration timed out",
        )

        QCoreApplication.processEvents()

        return results[
            0
        ]

    def assert_completed_ready(
        self,
        state,
    ):
        self.assertIs(
            validate_provider_diagnostics_gui_controller_state(
                state
            ),
            state,
        )

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
            validate_provider_diagnostics_view_model(
                state.view_model
            ),
            state.view_model,
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertIs(
            state.view_model.severity,
            ProviderDiagnosticsViewSeverity
            .SUCCESS,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertEqual(
            state.view_model.provider_label,
            "OpenAI",
        )

    def test_public_api_version_available_to_integration(self):
        self.assertEqual(
            PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION,
            1,
        )

    def test_offline_ready_runs_real_stack_without_network(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        secret = (
            "m98-offline-integration-secret"
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
                    "OFFLINE M98 diagnostics must not use network"
                ),
            ) as opened:
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assert_completed_ready(
            state
        )

        opened.assert_not_called()

    def test_offline_missing_credential_completes_not_ready_without_network(
        self,
    ):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
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
                    "missing credential must stop before network"
                ),
            ) as opened:
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        opened.assert_not_called()

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
            False,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

    def test_online_ready_runs_real_stack_and_mocked_https(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        response = FakeResponse(
            200
        )

        secret = (
            "m98-online-integration-secret"
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
                return_value=response,
            ) as opened:
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assert_completed_ready(
            state
        )

        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

    def test_online_https_executes_outside_main_thread(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        main_thread_id = int(
            QThread.currentThreadId()
        )

        network_thread_ids = []

        def open_https(
            *args,
            **kwargs,
        ):
            network_thread_ids.append(
                int(
                    QThread.currentThreadId()
                )
            )

            return FakeResponse(
                200
            )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m98-thread-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=open_https,
            ):
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assert_completed_ready(
            state
        )

        self.assertEqual(
            len(
                network_thread_ids
            ),
            1,
        )

        self.assertNotEqual(
            network_thread_ids[
                0
            ],
            main_thread_id,
        )

    def test_finished_signal_returns_to_main_thread(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        main_thread_id = int(
            QThread.currentThreadId()
        )

        finished_thread_ids = []

        bridge.finished.connect(
            lambda state: finished_thread_ids.append(
                int(
                    QThread.currentThreadId()
                )
            )
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m98-main-signal-secret",
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
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assert_completed_ready(
            state
        )

        self.assertEqual(
            finished_thread_ids,
            [
                main_thread_id,
            ],
        )

    def test_online_missing_credential_stops_before_https(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
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
                    "ONLINE missing credential must not reach HTTPS"
                ),
            ) as opened:
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
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

    def test_online_network_failure_is_completed_gui_result(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m98-network-failure-secret",
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
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

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
            False,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

    def test_online_rate_limit_is_completed_gui_result(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m98-rate-limit-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    429
                ),
            ):
                state = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        self.assertIs(
            state.view_model.action,
            ProviderDiagnosticsViewAction
            .RETRY,
        )

    def test_invalid_application_request_becomes_failed_state_without_network(
        self,
    ):
        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "invalid application request must not use network"
            ),
        ) as opened:
            state = self.wait_for_finished(
                bridge,
                lambda: bridge.start(
                    object()
                ),
            )

        opened.assert_not_called()

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INVALID_REQUEST,
        )

        self.assertIsNone(
            state.view_model
        )

    def test_secret_does_not_enter_terminal_gui_state(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        secret = (
            "unique-m98-secret-552211"
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                secret,
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
                    bridge,
                    lambda: bridge.start(
                        request
                    ),
                )

        self.assert_completed_ready(
            state
        )

        self.assertNotIn(
            secret,
            repr(
                state
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                state.view_model
            ),
        )

    def test_main_thread_can_cancel_real_online_stack(self):
        config = openai_runtime_config()

        request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
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

        bridge.finished.connect(
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
                "m98-cancellation-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=delayed_open_https,
            ):
                bridge.start(
                    request
                )

                self.assertTrue(
                    entered_network.wait(
                        1
                    ),
                    "real ONLINE stack did not reach M92 HTTPS boundary",
                )

                self.assertIs(
                    bridge.request_cancel(),
                    True,
                )

                release_network.set()

                if not results:
                    loop.exec()

        timer.stop()

        self.assertEqual(
            len(
                results
            ),
            1,
            "cancelled M98 integration did not finish",
        )

        state = results[
            0
        ]

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIsNone(
            state.view_model
        )

        self.assertIs(
            bridge.is_running,
            False,
        )

    def test_bridge_can_run_real_stack_twice_sequentially(self):
        config = openai_runtime_config()

        offline_request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
            config,
        )

        online_request = self.make_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE,
            config,
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        with patch.dict(
            os.environ,
            {
                config
                .credential_environment_variable:
                "m98-reuse-secret",
            },
            clear=False,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ) as opened:
                first = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        offline_request
                    ),
                )

                second = self.wait_for_finished(
                    bridge,
                    lambda: bridge.start(
                        online_request
                    ),
                )

        self.assert_completed_ready(
            first
        )

        self.assert_completed_ready(
            second
        )

        opened.assert_called_once()

        self.assertIs(
            bridge.state,
            second,
        )

        self.assertIs(
            bridge.is_running,
            False,
        )


if __name__ == "__main__":
    unittest.main()