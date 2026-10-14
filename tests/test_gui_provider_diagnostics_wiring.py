"""M100 3A-3 desktop GUI provider diagnostics wiring tests."""

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import (
    PropertyMock,
    patch,
)

from PyQt6.QtCore import (
    QProcess,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
)

import gui_ai_video as gui_module

from creator_studio.provider_diagnostics_host.gui_api import (
    ProviderDiagnosticsRemoteImageSource,
    ProviderDiagnosticsRequestBuilder,
)
from creator_studio.provider_diagnostics_host.runtime_api import (
    ProviderDiagnosticsHost,
)
from creator_studio.provider_diagnostics_qt_view.binding_api import (
    ProviderDiagnosticsQtViewBinder,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    ProviderDiagnosticsViewAction,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
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

        type(self).instances.append(
            self
        )

    def load_profiles(
        self,
    ):
        return []

    def get_secret(
        self,
        profile_id,
    ):
        raise AssertionError(
            "wiring construction must not read secrets"
        )


class FakeProcess:

    def __init__(
        self,
        state,
        wait_results=None,
    ):
        self._state = state
        self.wait_results = list(
            wait_results
            or []
        )
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = []

    def state(
        self,
    ):
        return self._state

    def terminate(
        self,
    ):
        self.terminate_calls += 1

    def kill(
        self,
    ):
        self.kill_calls += 1

    def waitForFinished(
        self,
        timeout,
    ):
        self.wait_calls.append(
            timeout
        )

        if self.wait_results:
            result = self.wait_results.pop(0)
        else:
            result = True

        if result:
            self._state = (
                QProcess.ProcessState.NotRunning
            )

        return result


class FakeCloseEvent:

    def __init__(
        self,
    ):
        self.accepted = False
        self.ignored = False

    def accept(
        self,
    ):
        self.accepted = True

    def ignore(
        self,
    ):
        self.ignored = True


class ProviderDiagnosticsMainWindowWiringTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        FakeAPIKeyManager.instances.clear()

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.settings_file = (
            Path(
                self.temp_dir.name
            )
            / "gui_settings.json"
        )

        self.request = object()

        self.api_manager_patch = patch.object(
            gui_module,
            "APIKeyManager",
            FakeAPIKeyManager,
        )

        self.settings_patch = patch.object(
            gui_module,
            "GUI_SETTINGS_FILE",
            self.settings_file,
        )

        self.builder_patch = patch.object(
            ProviderDiagnosticsRequestBuilder,
            "build_kie",
            return_value=self.request,
        )

        self.host_patch = patch.object(
            ProviderDiagnosticsHost,
            "start",
            return_value=object(),
        )

        self.api_manager_patch.start()
        self.settings_patch.start()

        self.build_kie = (
            self.builder_patch.start()
        )

        self.host_start = (
            self.host_patch.start()
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

        self.host_patch.stop()
        self.builder_patch.stop()
        self.settings_patch.stop()
        self.api_manager_patch.stop()

        self.temp_dir.cleanup()

    def test_run_button_builds_online_kie_request_and_starts_host(
        self,
    ):
        self.window.provider_diagnostics_view.run_button.click()

        self.build_kie.assert_called_once_with(
            self.window.api_manager,
            ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        self.host_start.assert_called_once()

        args = self.host_start.call_args.args

        self.assertIs(
            args[0],
            self.window.api_manager,
        )

        self.assertIs(
            args[1],
            self.window.provider_diagnostics_binder,
        )

        self.assertIs(
            args[2],
            self.request,
        )

        self.assertIs(
            type(args[3]),
            ProviderDiagnosticsRemoteImageSource,
        )

    def test_remote_image_source_is_transient_not_retained_by_window(
        self,
    ):
        self.window.provider_diagnostics_view.run_button.click()

        for value in self.window.__dict__.values():
            self.assertIsNot(
                type(value),
                ProviderDiagnosticsRemoteImageSource,
            )

    def test_diagnostics_start_disables_pipeline_mutation_controls(
        self,
    ):
        self.window.provider_diagnostics_view.run_button.click()

        self.assertFalse(
            self.window.start_button.isEnabled()
        )

        self.assertFalse(
            self.window.audio_button.isEnabled()
        )

        self.assertFalse(
            self.window.output_button.isEnabled()
        )

        self.assertFalse(
            self.window.api_settings_button.isEnabled()
        )

        self.assertFalse(
            self.window.pexels_check.isEnabled()
        )

        self.assertFalse(
            self.window.pixabay_check.isEnabled()
        )

        self.assertFalse(
            self.window.stop_button.isEnabled()
        )

        self.assertTrue(
            self.window.provider_diagnostics_view.isEnabled()
        )

    def test_diagnostics_finish_restores_pipeline_controls(
        self,
    ):
        self.window.provider_diagnostics_view.run_button.click()

        self.window._on_provider_diagnostics_finished(
            object()
        )

        self.assertTrue(
            self.window.start_button.isEnabled()
        )

        self.assertTrue(
            self.window.audio_button.isEnabled()
        )

        self.assertTrue(
            self.window.output_button.isEnabled()
        )

        self.assertTrue(
            self.window.api_settings_button.isEnabled()
        )

        self.assertTrue(
            self.window.provider_diagnostics_view.isEnabled()
        )

    def test_pipeline_execution_blocks_diagnostics_start(
        self,
    ):
        self.window.process = FakeProcess(
            QProcess.ProcessState.Running
        )

        with patch.object(
            QMessageBox,
            "information",
        ) as information:

            self.window.provider_diagnostics_view.run_button.click()

        self.build_kie.assert_not_called()
        self.host_start.assert_not_called()

        information.assert_called_once()

    def test_diagnostics_execution_blocks_pipeline_start_before_validation(
        self,
    ):
        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=True,
        ):
            with patch.object(
                self.window,
                "validate_inputs",
            ) as validate_inputs:
                with patch.object(
                    QMessageBox,
                    "information",
                ) as information:

                    self.window.start_pipeline()

        validate_inputs.assert_not_called()
        information.assert_called_once()

    def test_configure_credential_action_opens_existing_settings_dialog_path(
        self,
    ):
        with patch.object(
            self.window,
            "open_api_settings",
        ) as open_settings:

            self.window.provider_diagnostics_binder.action_requested.emit(
                ProviderDiagnosticsViewAction
                .CONFIGURE_CREDENTIAL
            )

        open_settings.assert_called_once_with()

    def test_none_action_does_not_open_settings(
        self,
    ):
        with patch.object(
            self.window,
            "open_api_settings",
        ) as open_settings:

            self.window.provider_diagnostics_binder.action_requested.emit(
                ProviderDiagnosticsViewAction
                .NONE
            )

        open_settings.assert_not_called()

    def test_synchronous_start_failure_restores_controls_without_raw_error(
        self,
    ):
        self.host_start.side_effect = RuntimeError(
            "private failure detail"
        )

        with patch.object(
            QMessageBox,
            "warning",
        ) as warning:

            self.window.provider_diagnostics_view.run_button.click()

        self.assertTrue(
            self.window.start_button.isEnabled()
        )

        self.assertTrue(
            self.window.api_settings_button.isEnabled()
        )

        self.assertTrue(
            self.window.provider_diagnostics_view.isEnabled()
        )

        warning.assert_called_once()

        message = warning.call_args.args[2]

        self.assertNotIn(
            "private failure detail",
            message,
        )

    def test_diagnostics_run_handler_does_not_read_legacy_secret_paths(
        self,
    ):
        source = inspect.getsource(
            gui_module.AIVideoEditorGUI
            .run_provider_diagnostics
        )

        self.assertNotIn(
            "get_secret",
            source,
        )

        self.assertNotIn(
            "runtime_environment",
            source,
        )

        self.assertNotIn(
            "runtime_provider_settings",
            source,
        )

    def test_close_running_pipeline_waits_after_force_kill_before_accept(
        self,
    ):
        event = FakeCloseEvent()

        process = FakeProcess(
            QProcess.ProcessState.Running,
            wait_results=[
                False,
                True,
            ],
        )

        self.window.process = process

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=False,
        ):
            with patch.object(
                QMessageBox,
                "question",
                return_value=(
                    QMessageBox.StandardButton
                    .Yes
                ),
            ):
                self.window.closeEvent(
                    event
                )

        self.assertEqual(
            process.terminate_calls,
            1,
        )

        self.assertEqual(
            process.kill_calls,
            1,
        )

        self.assertEqual(
            process.wait_calls,
            [
                3000,
                3000,
            ],
        )

        self.assertIs(
            process.state(),
            QProcess.ProcessState.NotRunning,
        )

        self.assertTrue(
            event.accepted
        )

        self.assertFalse(
            event.ignored
        )

    def test_close_running_pipeline_refuses_destroy_if_force_kill_not_finished(
        self,
    ):
        event = FakeCloseEvent()

        process = FakeProcess(
            QProcess.ProcessState.Running,
            wait_results=[
                False,
                False,
            ],
        )

        self.window.process = process

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=False,
        ):
            with patch.object(
                QMessageBox,
                "question",
                return_value=(
                    QMessageBox.StandardButton
                    .Yes
                ),
            ):
                with patch.object(
                    QMessageBox,
                    "warning",
                ) as warning:

                    self.window.closeEvent(
                        event
                    )

        self.assertEqual(
            process.terminate_calls,
            1,
        )

        self.assertEqual(
            process.kill_calls,
            1,
        )

        self.assertEqual(
            process.wait_calls,
            [
                3000,
                3000,
            ],
        )

        self.assertIs(
            process.state(),
            QProcess.ProcessState.Running,
        )

        self.assertTrue(
            event.ignored
        )

        self.assertFalse(
            event.accepted
        )

        warning.assert_called_once()

    def test_close_running_diagnostics_requests_cancel_and_defers_close(
        self,
    ):
        event = FakeCloseEvent()

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=True,
        ):
            with patch.object(
                QMessageBox,
                "question",
                return_value=(
                    QMessageBox.StandardButton
                    .Yes
                ),
            ):
                with patch.object(
                    self.window.provider_diagnostics_binder,
                    "request_cancel",
                    return_value=True,
                ) as request_cancel:

                    self.window.closeEvent(
                        event
                    )

        request_cancel.assert_called_once_with()

        self.assertTrue(
            event.ignored
        )

        self.assertFalse(
            event.accepted
        )

        self.assertTrue(
            self.window
            ._provider_diagnostics_close_pending
        )

    def test_close_running_diagnostics_can_be_declined(
        self,
    ):
        event = FakeCloseEvent()

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=True,
        ):
            with patch.object(
                QMessageBox,
                "question",
                return_value=(
                    QMessageBox.StandardButton
                    .No
                ),
            ):
                with patch.object(
                    self.window.provider_diagnostics_binder,
                    "request_cancel",
                ) as request_cancel:

                    self.window.closeEvent(
                        event
                    )

        request_cancel.assert_not_called()

        self.assertTrue(
            event.ignored
        )

        self.assertFalse(
            self.window
            ._provider_diagnostics_close_pending
        )

    def test_repeated_close_while_cancel_pending_does_not_prompt_again(
        self,
    ):
        self.window._provider_diagnostics_close_pending = True

        event = FakeCloseEvent()

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "is_running",
            new_callable=PropertyMock,
            return_value=True,
        ):
            with patch.object(
                QMessageBox,
                "question",
            ) as question:

                self.window.closeEvent(
                    event
                )

        question.assert_not_called()

        self.assertTrue(
            event.ignored
        )

    def test_finished_close_pending_is_deferred_to_next_event_loop_turn(
        self,
    ):
        self.window._provider_diagnostics_close_pending = True

        with patch.object(
            gui_module,
            "QTimer",
        ) as timer:

            self.window._on_provider_diagnostics_finished(
                object()
            )

        self.assertFalse(
            self.window
            ._provider_diagnostics_close_pending
        )

        timer.singleShot.assert_called_once()

        args = timer.singleShot.call_args.args

        self.assertEqual(
            args[0],
            0,
        )

        self.assertTrue(
            callable(
                args[1]
            )
        )

    def test_requested_pipeline_stop_suppresses_expected_crashed_error(
        self,
    ):
        self.window._pipeline_stop_requested = True

        with patch.object(
            self.window,
            "append_log",
        ) as append_log:
            self.window.process_error(
                QProcess.ProcessError.Crashed
            )

        append_log.assert_not_called()

    def test_unexpected_pipeline_crash_is_still_logged(
        self,
    ):
        with patch.object(
            self.window,
            "append_log",
        ) as append_log:
            self.window.process_error(
                QProcess.ProcessError.Crashed
            )

        append_log.assert_called_once_with(
            "QProcess error: "
            + str(
                QProcess.ProcessError.Crashed
            )
        )

    def test_requested_pipeline_stop_is_reported_as_user_stop_not_failure(
        self,
    ):
        self.window._pipeline_stop_requested = True
        self.window.output_path = None

        with patch.object(
            self.window,
            "read_process_output",
        ):
            with patch.object(
                QMessageBox,
                "warning",
            ) as warning:
                self.window.process_finished(
                    62097,
                    QProcess.ExitStatus.CrashExit,
                )

        warning.assert_not_called()

        self.assertEqual(
            self.window.stage_text.text(),
            "Đã dừng",
        )

        self.assertEqual(
            self.window.status_text.text(),
            "Pipeline đã được dừng theo yêu cầu.",
        )

        self.assertFalse(
            self.window._pipeline_stop_requested
        )

    def test_close_requested_pipeline_finish_does_not_show_failure_dialog(
        self,
    ):
        self.window._pipeline_close_requested = True
        self.window.output_path = None

        with patch.object(
            self.window,
            "read_process_output",
        ):
            with patch.object(
                QMessageBox,
                "warning",
            ) as warning:
                self.window.process_finished(
                    62097,
                    QProcess.ExitStatus.CrashExit,
                )

        warning.assert_not_called()

        self.assertFalse(
            self.window._pipeline_close_requested
        )



if __name__ == "__main__":
    unittest.main()
