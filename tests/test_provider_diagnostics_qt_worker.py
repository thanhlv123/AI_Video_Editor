"""M98 provider diagnostics QObject worker contract."""

import copy
import pickle
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QObject

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_qt_worker as api
import creator_studio.provider_diagnostics_qt_worker.worker as worker_module

from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerCancelled,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)
from creator_studio.provider_diagnostics_view_model.public_api import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
)


def ready_view_model():
    return ProviderDiagnosticsViewModel(
        schema_version=(
            PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Ready",
        detail_text=(
            "Provider configuration is ready."
        ),
        severity=(
            ProviderDiagnosticsViewSeverity
            .SUCCESS
        ),
        action=(
            ProviderDiagnosticsViewAction
            .NONE
        ),
        action_text="No action required",
        is_ready=True,
    )


def completed_state():
    state = ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED
        ),
        view_model=ready_view_model(),
        failure=None,
    )

    validate_provider_diagnostics_gui_controller_state(
        state
    )

    return state


def cancelled_state():
    state = ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED
        ),
        view_model=None,
        failure=None,
    )

    validate_provider_diagnostics_gui_controller_state(
        state
    )

    return state


def failed_state():
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


class ProviderDiagnosticsQtCancellationTokenTests(
    unittest.TestCase
):

    def test_token_initially_not_cancelled(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        self.assertIs(
            token.is_cancelled,
            False,
        )

        self.assertIsNone(
            token.check()
        )

    def test_cancel_is_idempotent(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        token.cancel()
        token.cancel()

        self.assertIs(
            token.is_cancelled,
            True,
        )

    def test_check_raises_m97_cancellation_signal(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        token.cancel()

        with self.assertRaises(
            ProviderDiagnosticsGuiControllerCancelled
        ):
            token.check()

    def test_token_repr_contains_only_cancellation_metadata(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        self.assertEqual(
            repr(
                token
            ),
            (
                "ProviderDiagnosticsQtCancellationToken("
                "is_cancelled=False"
                ")"
            ),
        )

        token.cancel()

        self.assertEqual(
            repr(
                token
            ),
            (
                "ProviderDiagnosticsQtCancellationToken("
                "is_cancelled=True"
                ")"
            ),
        )

    def test_token_not_copyable(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_cancellation_token_runtime_only$",
        ):
            copy.copy(
                token
            )

    def test_token_not_deepcopyable(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_cancellation_token_runtime_only$",
        ):
            copy.deepcopy(
                token
            )

    def test_token_not_pickleable(self):
        token = (
            api.ProviderDiagnosticsQtCancellationToken()
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_cancellation_token_runtime_only$",
        ):
            pickle.dumps(
                token
            )


class ProviderDiagnosticsQtWorkerTests(
    unittest.TestCase
):

    def make_worker_with_controller(
        self,
        controller,
        request=None,
        remote_image_source=None,
    ):
        if request is None:
            request = object()

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            worker = api.ProviderDiagnosticsQtWorker(
                request,
                remote_image_source,
            )

        return worker

    def test_worker_is_qobject(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        self.assertIsInstance(
            worker,
            QObject,
        )

    def test_initial_worker_state_is_idle(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        self.assertIs(
            worker.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertIs(
            worker.has_run,
            False,
        )

        self.assertIs(
            worker.is_cancelled,
            False,
        )

    def test_worker_repr_contains_only_safe_metadata(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        self.assertEqual(
            repr(
                worker
            ),
            (
                "ProviderDiagnosticsQtWorker("
                "phase='IDLE', "
                "has_run=False, "
                "is_cancelled=False"
                ")"
            ),
        )

    def test_successful_run_signal_order(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        events = []

        worker.started.connect(
            lambda: events.append(
                (
                    "started",
                    None,
                )
            )
        )

        worker.state_changed.connect(
            lambda state: events.append(
                (
                    "state_changed",
                    state,
                )
            )
        )

        worker.fatal.connect(
            lambda: events.append(
                (
                    "fatal",
                    None,
                )
            )
        )

        worker.finished.connect(
            lambda state: events.append(
                (
                    "finished",
                    state,
                )
            )
        )

        worker.run()

        self.assertEqual(
            [
                name
                for name, _
                in events
            ],
            [
                "started",
                "state_changed",
                "finished",
            ],
        )

        self.assertIs(
            events[
                1
            ][
                1
            ],
            controller.state,
        )

        self.assertIs(
            events[
                2
            ][
                1
            ],
            controller.state,
        )

    def test_worker_passes_runtime_arguments_to_controller(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        request = object()
        remote_source = object()

        worker = self.make_worker_with_controller(
            controller,
            request,
            remote_source,
        )

        worker.run()

        call = controller.run.call_args

        self.assertIs(
            call.args[
                0
            ],
            request,
        )

        self.assertTrue(
            callable(
                call.args[
                    1
                ]
            )
        )

        self.assertIs(
            call.args[
                2
            ],
            remote_source,
        )

    def test_worker_uses_cancellation_token_check(self):
        controller = unittest.mock.Mock()

        controller.state = cancelled_state()

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            with self.assertRaises(
                ProviderDiagnosticsGuiControllerCancelled
            ):
                check()

            return controller.state

        controller.run.side_effect = run

        worker = self.make_worker_with_controller(
            controller
        )

        worker.request_cancel()

        final_states = []

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertIs(
            worker.is_cancelled,
            True,
        )

        self.assertEqual(
            len(
                final_states
            ),
            1,
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

    def test_request_cancel_is_idempotent(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        worker.request_cancel()
        worker.request_cancel()

        self.assertIs(
            worker.is_cancelled,
            True,
        )

    def test_failed_controller_state_is_normal_terminal_result(self):
        controller = unittest.mock.Mock()

        controller.state = failed_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [],
        )

        self.assertEqual(
            len(
                final_states
            ),
            1,
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_cancelled_controller_state_is_normal_terminal_result(self):
        controller = unittest.mock.Mock()

        controller.state = cancelled_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [],
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

    def test_nonterminal_controller_state_becomes_safe_failure(self):
        controller = unittest.mock.Mock()

        controller.state = (
            ProviderDiagnosticsGuiControllerState(
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
        )

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            final_states[
                0
            ].failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

    def test_malformed_controller_result_becomes_safe_failure(self):
        controller = unittest.mock.Mock()

        controller.state = failed_state()

        controller.run.return_value = (
            object()
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_unexpected_exception_at_qt_boundary_is_sanitized(self):
        controller = unittest.mock.Mock()

        controller.state = failed_state()

        controller.run.side_effect = (
            RuntimeError(
                "private-runtime-error"
            )
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertEqual(
            len(
                final_states
            ),
            1,
        )

        self.assertNotIn(
            "private-runtime-error",
            repr(
                final_states[
                    0
                ]
            ),
        )

    def test_memory_error_at_qt_boundary_is_sanitized(self):
        controller = unittest.mock.Mock()

        controller.state = failed_state()

        controller.run.side_effect = (
            MemoryError()
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_baseexception_at_qt_boundary_is_sanitized(self):
        controller = unittest.mock.Mock()

        controller.state = failed_state()

        controller.run.side_effect = (
            KeyboardInterrupt()
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []
        final_states = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.finished.connect(
            final_states.append
        )

        worker.run()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertIs(
            final_states[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_worker_releases_runtime_arguments_after_run(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller,
            object(),
            object(),
        )

        worker.run()

        self.assertIsNone(
            worker._request
        )

        self.assertIsNone(
            worker._remote_image_source
        )

    def test_worker_is_one_shot(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        fatal_calls = []

        worker.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        worker.run()
        worker.run()

        controller.run.assert_called_once()

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

    def test_worker_has_run_after_execution(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        worker = self.make_worker_with_controller(
            controller
        )

        self.assertIs(
            worker.has_run,
            False,
        )

        worker.run()

        self.assertIs(
            worker.has_run,
            True,
        )

    def test_worker_not_copyable(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_worker_runtime_only$",
        ):
            copy.copy(
                worker
            )

    def test_worker_not_deepcopyable(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_worker_runtime_only$",
        ):
            copy.deepcopy(
                worker
            )

    def test_worker_not_pickleable(self):
        worker = (
            api.ProviderDiagnosticsQtWorker(
                object()
            )
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_worker_runtime_only$",
        ):
            pickle.dumps(
                worker
            )

    def test_worker_layer_has_no_environment_or_network_access(self):
        controller = unittest.mock.Mock()

        controller.state = completed_state()

        controller.run.return_value = (
            controller.state
        )

        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "M98 worker must not read environment directly"
            ),
        ) as getenv_mock:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "M98 worker must not open network directly"
                ),
            ) as opened:
                worker = self.make_worker_with_controller(
                    controller
                )

                worker.run()

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_worker_public_api_contract(self):
        self.assertEqual(
            api.__all__,
            (
                "ProviderDiagnosticsQtCancellationToken",
                "ProviderDiagnosticsQtWorker",
            ),
        )


if __name__ == "__main__":
    unittest.main()