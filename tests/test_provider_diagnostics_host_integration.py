"""M100 provider diagnostics host real-stack integration tests.

These tests exercise:

    APIKeyManager boundary
        -> M100 ProviderDiagnosticsHost
        -> M99 Qt view binder
        -> M98 QThread bridge / worker
        -> M97 GUI controller
        -> M95 application service
        -> M93 coordinator
        -> M91 readiness
        -> optional M92 connectivity

Only two external boundaries are substituted:

- APIKeyManager storage methods are patched instead of touching the real
  Windows Credential Manager;
- M92 HTTPS opening is patched for ONLINE diagnostics.

No M91-M99 execution layer is mocked.
"""

import unittest
from unittest.mock import patch

from PyQt6.QtCore import (
    QEventLoop,
    QTimer,
)
from PyQt6.QtWidgets import (
    QApplication,
)

from config.api_key_manager import (
    APIKeyManager,
)

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerPhase,
)
from creator_studio.provider_diagnostics_host.runtime_api import (
    ProviderDiagnosticsHost,
)
from creator_studio.provider_diagnostics_qt_view.binding_api import (
    ProviderDiagnosticsQtViewBinder,
)
from creator_studio.provider_diagnostics_qt_view.public_api import (
    ProviderDiagnosticsQtView,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


APP = (
    QApplication.instance()
    or QApplication([])
)


def new_manager():
    return object.__new__(
        APIKeyManager
    )


def openai_profile(
    environment_variable="OPENAI_API_KEY",
):
    return {
        "id": "openai",
        "name": "OpenAI",
        "env_var": environment_variable,
        "base_url": "",
        "model": "",
        "enabled": True,
    }


def build_request(
    mode,
):
    return ProviderDiagnosticsApplicationRequest(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=openai_runtime_config(),
        mode=mode,
    )


class FakeResponse:

    def __init__(
        self,
        status,
    ):
        self.status = status
        self.closed = False

    def close(
        self,
    ):
        self.closed = True


class ProviderDiagnosticsHostIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.host = (
            ProviderDiagnosticsHost()
        )

        self.manager = (
            new_manager()
        )

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
        if self.bridge.is_running:
            self.bridge.request_cancel()

        APP.processEvents()
        APP.processEvents()
        APP.processEvents()

        self.binder.deleteLater()
        self.bridge.deleteLater()
        self.view.deleteLater()

        APP.processEvents()
        APP.processEvents()

    def _run_host(
        self,
        request,
        remote_image_source=None,
    ):
        terminal = []

        loop = QEventLoop()

        timeout = QTimer()
        timeout.setSingleShot(
            True
        )

        def finished(
            state,
        ):
            terminal.append(
                state
            )

            loop.quit()

        def timed_out():
            loop.quit()

        self.binder.finished.connect(
            finished
        )

        timeout.timeout.connect(
            timed_out
        )

        try:
            initial = self.host.start(
                self.manager,
                self.binder,
                request,
                remote_image_source,
            )

            if not terminal:
                timeout.start(
                    5000
                )

                loop.exec()

        finally:
            timeout.stop()

            try:
                self.binder.finished.disconnect(
                    finished
                )

            except Exception:
                pass

        APP.processEvents()
        APP.processEvents()
        APP.processEvents()

        if not terminal:
            self.fail(
                "provider diagnostics host integration timed out"
            )

        return (
            initial,
            terminal[
                -1
            ],
        )

    def test_offline_real_stack_reads_only_bound_secret_and_never_opens_https(
        self,
    ):
        secret = (
            "unique-m100-host-offline-secret-314159"
        )

        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=openai_profile(),
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value=secret,
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host diagnostics must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                probe_module,
                "_open_https",
            ) as opened,
        ):
            initial, final = (
                self._run_host(
                    request
                )
            )

        self.assertIs(
            initial.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            final.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            final.view_model
        )

        self.assertTrue(
            final.view_model.is_ready
        )

        get_profile.assert_called_once_with(
            "openai"
        )

        get_secret.assert_called_once_with(
            "openai"
        )

        runtime_environment.assert_not_called()

        opened.assert_not_called()

        self.assertNotIn(
            secret,
            repr(
                final
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.host
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.binder
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.bridge
            ),
        )

    def test_online_real_stack_runs_readiness_then_authenticated_connectivity(
        self,
    ):
        secret = (
            "unique-m100-host-online-secret-271828"
        )

        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        response = FakeResponse(
            200
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=openai_profile(),
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value=secret,
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host diagnostics must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened,
        ):
            initial, final = (
                self._run_host(
                    request
                )
            )

        self.assertIs(
            initial.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            final.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            final.view_model
        )

        self.assertTrue(
            final.view_model.is_ready
        )

        self.assertEqual(
            get_profile.call_count,
            2,
        )

        self.assertEqual(
            get_secret.call_count,
            2,
        )

        runtime_environment.assert_not_called()

        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

        http_request = (
            opened.call_args.args[
                0
            ]
        )

        self.assertEqual(
            http_request.get_header(
                "Authorization"
            ),
            (
                "Bearer "
                + secret
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                final
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.host
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.binder
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.bridge
            ),
        )

    def test_offline_missing_secret_completes_not_ready_without_network(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=openai_profile(),
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value="",
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host diagnostics must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                probe_module,
                "_open_https",
            ) as opened,
        ):
            _, final = (
                self._run_host(
                    request
                )
            )

        self.assertIs(
            final.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            final.view_model
        )

        self.assertFalse(
            final.view_model.is_ready
        )

        get_profile.assert_called_once_with(
            "openai"
        )

        get_secret.assert_called_once_with(
            "openai"
        )

        runtime_environment.assert_not_called()

        opened.assert_not_called()

    def test_profile_environment_mismatch_stops_before_secret_and_network(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=openai_profile(
                    "KIE_API_KEY"
                ),
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                side_effect=AssertionError(
                    "mismatched profile must not read secret"
                ),
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host diagnostics must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                probe_module,
                "_open_https",
            ) as opened,
        ):
            _, final = (
                self._run_host(
                    request
                )
            )

        self.assertIs(
            final.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            final.view_model
        )

        self.assertFalse(
            final.view_model.is_ready
        )

        get_profile.assert_called_once_with(
            "openai"
        )

        get_secret.assert_not_called()

        runtime_environment.assert_not_called()

        opened.assert_not_called()

    def test_completed_execution_releases_bridge_runtime_work(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=openai_profile(),
            ),
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value=(
                    "unique-m100-host-release-secret-161803"
                ),
            ),
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host diagnostics must not load all secrets"
                ),
            ),
            patch.object(
                probe_module,
                "_open_https",
            ) as opened,
        ):
            _, final = (
                self._run_host(
                    request
                )
            )

        self.assertIs(
            final.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        opened.assert_not_called()

        APP.processEvents()
        APP.processEvents()

        self.assertFalse(
            self.bridge.is_running
        )


if __name__ == "__main__":
    unittest.main()