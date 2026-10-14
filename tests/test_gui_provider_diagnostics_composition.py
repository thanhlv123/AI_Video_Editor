"""M100 3A-1 main-window provider diagnostics composition tests.

This checkpoint verifies composition only.

The main window may construct the M100/M99/M98 diagnostics objects and place
the M99 view into the existing API Providers section, but it must not start a
diagnostic run yet. Request assembly and user-intent wiring belong to later
M100 3A checkpoints.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
)

import gui_ai_video as gui_module

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


APP = (
    QApplication.instance()
    or QApplication([])
)


class FakeAPIKeyManager:

    instances = []

    def __init__(
        self,
        root,
    ):
        self.root = root
        self.load_profiles_calls = 0
        self.get_secret_calls = []
        self.runtime_environment_calls = 0

        type(self).instances.append(
            self
        )

    def load_profiles(
        self,
    ):
        self.load_profiles_calls += 1

        return []

    def get_secret(
        self,
        profile_id,
    ):
        self.get_secret_calls.append(
            profile_id
        )

        return ""

    def runtime_environment(
        self,
    ):
        self.runtime_environment_calls += 1

        raise AssertionError(
            "M100 3A-1 composition must not load runtime credentials"
        )


class ProviderDiagnosticsMainWindowCompositionTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        FakeAPIKeyManager.instances.clear()

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        settings_file = (
            Path(
                self.temp_dir.name
            )
            / "gui_settings.json"
        )

        self.api_manager_patch = patch.object(
            gui_module,
            "APIKeyManager",
            FakeAPIKeyManager,
        )

        self.settings_patch = patch.object(
            gui_module,
            "GUI_SETTINGS_FILE",
            settings_file,
        )

        self.host_start_patch = patch.object(
            ProviderDiagnosticsHost,
            "start",
            side_effect=AssertionError(
                "M100 3A-1 must not start diagnostics"
            ),
        )

        self.api_manager_patch.start()
        self.settings_patch.start()
        self.host_start = (
            self.host_start_patch.start()
        )

        self.window = (
            gui_module.AIVideoEditorGUI()
        )

    def tearDown(
        self,
    ):
        self.window.deleteLater()

        APP.processEvents()
        APP.processEvents()

        self.host_start_patch.stop()
        self.settings_patch.stop()
        self.api_manager_patch.stop()

        self.temp_dir.cleanup()

    def test_main_window_constructs_exact_diagnostics_components(
        self,
    ):
        self.assertIs(
            type(
                self.window
                .provider_diagnostics_host
            ),
            ProviderDiagnosticsHost,
        )

        self.assertIs(
            type(
                self.window
                .provider_diagnostics_view
            ),
            ProviderDiagnosticsQtView,
        )

        self.assertIs(
            type(
                self.window
                .provider_diagnostics_bridge
            ),
            ProviderDiagnosticsQtThreadBridge,
        )

        self.assertIs(
            type(
                self.window
                .provider_diagnostics_binder
            ),
            ProviderDiagnosticsQtViewBinder,
        )

    def test_composition_does_not_start_diagnostics(
        self,
    ):
        self.host_start.assert_not_called()

        self.assertFalse(
            self.window
            .provider_diagnostics_bridge
            .is_running
        )

        self.assertFalse(
            self.window
            .provider_diagnostics_binder
            .is_running
        )

        self.assertIs(
            self.window
            .provider_diagnostics_binder
            .phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

    def test_diagnostics_qobjects_are_owned_by_main_window_composition(
        self,
    ):
        self.assertIs(
            self.window
            .provider_diagnostics_view
            .parentWidget(),
            self.window.centralWidget(),
        )

        self.assertIs(
            self.window
            .provider_diagnostics_bridge
            .parent(),
            self.window,
        )

        self.assertIs(
            self.window
            .provider_diagnostics_binder
            .parent(),
            self.window,
        )

    def test_diagnostics_view_is_placed_in_main_layout(
        self,
    ):
        layout = (
            self.window
            .centralWidget()
            .layout()
        )

        self.assertGreaterEqual(
            layout.indexOf(
                self.window
                .provider_diagnostics_view
            ),
            0,
        )

    def test_checkpoint_keeps_diagnostics_view_disabled_until_request_wiring(
        self,
    ):
        self.assertFalse(
            self.window
            .provider_diagnostics_view
            .isEnabled()
        )

    def test_composition_reuses_single_existing_api_manager(
        self,
    ):
        self.assertEqual(
            len(
                FakeAPIKeyManager.instances
            ),
            1,
        )

        self.assertIs(
            self.window.api_manager,
            FakeAPIKeyManager.instances[
                0
            ],
        )

        self.assertEqual(
            self.window.api_manager.root,
            gui_module.ROOT,
        )

    def test_composition_does_not_materialize_runtime_environment(
        self,
    ):
        self.assertEqual(
            self.window
            .api_manager
            .runtime_environment_calls,
            0,
        )

        self.assertEqual(
            self.window
            .api_manager
            .get_secret_calls,
            [],
        )

        self.assertEqual(
            self.window
            .api_manager
            .load_profiles_calls,
            1,
        )

    def test_gui_does_not_import_m100_credential_factory_authority(
        self,
    ):
        self.assertFalse(
            hasattr(
                gui_module,
                "APIKeyManagerCredentialSourceFactory",
            )
        )

        self.assertFalse(
            hasattr(
                gui_module,
                "EnvironmentCredentialSource",
            )
        )


if __name__ == "__main__":
    unittest.main()
