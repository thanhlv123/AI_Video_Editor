"""M98 provider diagnostics QThread bridge contract."""

import copy
import pickle
import threading
import time
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import (
    QCoreApplication,
    QEventLoop,
    QThread,
    QTimer,
)

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_qt_worker.bridge as bridge_module
import creator_studio.provider_diagnostics_qt_worker.worker as worker_module

from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
    validate_provider_diagnostics_gui_controller_state,
)
from creator_studio.provider_diagnostics_qt_worker.bridge import (
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerCancelled,
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


class ProviderDiagnosticsQtThreadBridgeTests(
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

    def setUp(
        self,
    ):
        self.bridge = (
            ProviderDiagnosticsQtThreadBridge()
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

        self.bridge.finished.connect(
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
            self.bridge.finished.disconnect(
                finished
            )

        except TypeError:
            pass

        self.assertEqual(
            len(
                results
            ),
            1,
            "QThread bridge did not finish before timeout",
        )

        QCoreApplication.processEvents()

        return results[
            0
        ]

    def make_controller(
        self,
        state=None,
    ):
        if state is None:
            state = completed_state()

        controller = Mock()
        controller.state = state
        controller.run.return_value = state

        return controller

    def test_initial_state_is_idle(self):
        self.assertIs(
            self.bridge.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertIs(
            self.bridge.is_running,
            False,
        )

    def test_initial_repr_contains_only_safe_metadata(self):
        self.assertEqual(
            repr(
                self.bridge
            ),
            (
                "ProviderDiagnosticsQtThreadBridge("
                "phase='IDLE', "
                "is_running=False"
                ")"
            ),
        )

    def test_start_returns_running_state_without_waiting(self):
        entered = threading.Event()
        release = threading.Event()

        controller = self.make_controller()

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            entered.set()

            release.wait(
                2
            )

            return completed_state()

        controller.run.side_effect = run

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            running = self.bridge.start(
                object()
            )

        self.assertIs(
            running.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            self.bridge.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            self.bridge.is_running,
            True,
        )

        self.assertTrue(
            entered.wait(
                1
            )
        )

        release.set()

        loop = QEventLoop()

        self.bridge.finished.connect(
            lambda state: loop.quit()
        )

        QTimer.singleShot(
            3000,
            loop.quit,
        )

        loop.exec()

        self.assertIs(
            self.bridge.is_running,
            False,
        )

    def test_execution_occurs_on_non_main_thread(self):
        controller = self.make_controller()

        main_thread_id = int(
            QThread.currentThreadId()
        )

        worker_thread_ids = []

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            worker_thread_ids.append(
                int(
                    QThread.currentThreadId()
                )
            )

            return completed_state()

        controller.run.side_effect = run

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            len(
                worker_thread_ids
            ),
            1,
        )

        self.assertNotEqual(
            worker_thread_ids[
                0
            ],
            main_thread_id,
        )

    def test_finished_is_emitted_after_thread_cleanup(self):
        controller = self.make_controller()

        observed = []

        def finished(
            state,
        ):
            observed.append(
                (
                    state,
                    self.bridge.is_running,
                )
            )

        self.bridge.finished.connect(
            finished
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            len(
                observed
            ),
            1,
        )

        self.assertIs(
            observed[
                0
            ][
                1
            ],
            False,
        )

    def test_terminal_state_is_published(self):
        controller = self.make_controller()

        state_events = []

        self.bridge.state_changed.connect(
            state_events.append
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            final_state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertEqual(
            len(
                state_events
            ),
            1,
        )

        self.assertIs(
            state_events[
                0
            ],
            final_state,
        )

        self.assertIs(
            self.bridge.state,
            final_state,
        )

    def test_started_signal_is_forwarded(self):
        controller = self.make_controller()

        calls = []

        self.bridge.started.connect(
            lambda: calls.append(
                int(
                    QThread.currentThreadId()
                )
            )
        )

        main_thread_id = int(
            QThread.currentThreadId()
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertEqual(
            len(
                calls
            ),
            1,
        )

        self.assertEqual(
            calls[
                0
            ],
            main_thread_id,
        )

    def test_finished_signal_is_delivered_on_bridge_thread(self):
        controller = self.make_controller()

        main_thread_id = int(
            QThread.currentThreadId()
        )

        signal_thread_ids = []

        self.bridge.finished.connect(
            lambda state: signal_thread_ids.append(
                int(
                    QThread.currentThreadId()
                )
            )
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertEqual(
            signal_thread_ids,
            [
                main_thread_id,
            ],
        )

    def test_request_cancel_without_active_worker_returns_false(self):
        self.assertIs(
            self.bridge.request_cancel(),
            False,
        )

    def test_request_cancel_reaches_running_worker(self):
        entered = threading.Event()

        controller = self.make_controller(
            cancelled_state()
        )

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            entered.set()

            while True:
                try:
                    check()

                except ProviderDiagnosticsGuiControllerCancelled:
                    return cancelled_state()

                time.sleep(
                    0.001
                )

        controller.run.side_effect = run

        results = []

        self.bridge.finished.connect(
            results.append
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.bridge.start(
                object()
            )

        self.assertTrue(
            entered.wait(
                1
            )
        )

        self.assertIs(
            self.bridge.request_cancel(),
            True,
        )

        loop = QEventLoop()

        def stop_if_done(
            state,
        ):
            loop.quit()

        self.bridge.finished.connect(
            stop_if_done
        )

        QTimer.singleShot(
            3000,
            loop.quit,
        )

        if not results:
            loop.exec()

        self.assertEqual(
            len(
                results
            ),
            1,
        )

        self.assertIs(
            results[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

        self.assertIs(
            self.bridge.is_running,
            False,
        )

    def test_request_cancel_is_safe_to_repeat(self):
        entered = threading.Event()

        controller = self.make_controller(
            cancelled_state()
        )

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            entered.set()

            while True:
                try:
                    check()

                except ProviderDiagnosticsGuiControllerCancelled:
                    return cancelled_state()

                time.sleep(
                    0.001
                )

        controller.run.side_effect = run

        results = []

        self.bridge.finished.connect(
            results.append
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.bridge.start(
                object()
            )

        self.assertTrue(
            entered.wait(
                1
            )
        )

        self.assertIs(
            self.bridge.request_cancel(),
            True,
        )

        self.assertIs(
            self.bridge.request_cancel(),
            True,
        )

        loop = QEventLoop()

        self.bridge.finished.connect(
            lambda state: loop.quit()
        )

        QTimer.singleShot(
            3000,
            loop.quit,
        )

        if not results:
            loop.exec()

        self.assertEqual(
            len(
                results
            ),
            1,
        )

    def test_second_start_while_running_is_rejected(self):
        entered = threading.Event()

        controller = self.make_controller(
            cancelled_state()
        )

        def run(
            request,
            check,
            remote_image_source=None,
        ):
            entered.set()

            while True:
                try:
                    check()

                except ProviderDiagnosticsGuiControllerCancelled:
                    return cancelled_state()

                time.sleep(
                    0.001
                )

        controller.run.side_effect = run

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.bridge.start(
                object()
            )

        self.assertTrue(
            entered.wait(
                1
            )
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "^provider_diagnostics_qt_thread_bridge_busy$",
        ):
            self.bridge.start(
                object()
            )

        self.bridge.request_cancel()

        loop = QEventLoop()

        self.bridge.finished.connect(
            lambda state: loop.quit()
        )

        QTimer.singleShot(
            3000,
            loop.quit,
        )

        loop.exec()

        self.assertIs(
            self.bridge.is_running,
            False,
        )

    def test_bridge_can_be_reused_after_finished(self):
        first_controller = self.make_controller()
        second_controller = self.make_controller(
            failed_state()
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            side_effect=(
                first_controller,
                second_controller,
            ),
        ):
            first = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

            second = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            first.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            second.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            self.bridge.state,
            second,
        )

    def test_bridge_may_restart_inside_finished_handler(self):
        first_controller = self.make_controller()
        second_controller = self.make_controller()

        results = []
        second_started = []

        def finished(
            state,
        ):
            results.append(
                state
            )

            if len(
                results
            ) == 1:
                second_started.append(
                    self.bridge.start(
                        object()
                    )
                )

        self.bridge.finished.connect(
            finished
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            side_effect=(
                first_controller,
                second_controller,
            ),
        ):
            loop = QEventLoop()

            def quit_after_second(
                state,
            ):
                if len(
                    results
                ) >= 2:
                    loop.quit()

            self.bridge.finished.connect(
                quit_after_second
            )

            self.bridge.start(
                object()
            )

            QTimer.singleShot(
                3000,
                loop.quit,
            )

            loop.exec()

        self.assertEqual(
            len(
                results
            ),
            2,
        )

        self.assertEqual(
            len(
                second_started
            ),
            1,
        )

        self.assertIs(
            second_started[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            self.bridge.is_running,
            False,
        )

    def test_failed_worker_state_is_normal_terminal_state(self):
        controller = self.make_controller(
            failed_state()
        )

        fatal_calls = []

        self.bridge.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertEqual(
            fatal_calls,
            [],
        )

    def test_worker_boundary_fatal_is_forwarded(self):
        controller = self.make_controller(
            failed_state()
        )

        controller.run.side_effect = (
            RuntimeError(
                "private-worker-boundary-error"
            )
        )

        fatal_calls = []

        self.bridge.fatal.connect(
            lambda: fatal_calls.append(
                True
            )
        )

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertEqual(
            fatal_calls,
            [
                True,
            ],
        )

        self.assertNotIn(
            "private-worker-boundary-error",
            repr(
                state
            ),
        )

    def test_bridge_cleans_worker_reference_after_finish(self):
        controller = self.make_controller()

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIsNone(
            self.bridge._worker
        )

        self.assertIsNone(
            self.bridge._thread
        )

    def test_bridge_does_not_store_runtime_arguments_directly(self):
        request = object()
        remote_source = object()

        controller = self.make_controller()

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            self.wait_for_finished(
                lambda: self.bridge.start(
                    request,
                    remote_source,
                )
            )

        for name in (
            "_request",
            "_remote_image_source",
            "request",
            "remote_image_source",
            "check",
            "credential",
            "credential_value",
            "secret",
            "api_key",
            "authorization",
            "http_status",
            "provider_code",
            "application_result",
        ):
            self.assertFalse(
                hasattr(
                    self.bridge,
                    name,
                )
            )

    def test_final_state_validates(self):
        controller = self.make_controller()

        with patch.object(
            worker_module,
            "ProviderDiagnosticsGuiController",
            return_value=controller,
        ):
            state = self.wait_for_finished(
                lambda: self.bridge.start(
                    object()
                )
            )

        self.assertIs(
            validate_provider_diagnostics_gui_controller_state(
                state
            ),
            state,
        )

    def test_bridge_not_copyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_thread_bridge_runtime_only$",
        ):
            copy.copy(
                self.bridge
            )

    def test_bridge_not_deepcopyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_thread_bridge_runtime_only$",
        ):
            copy.deepcopy(
                self.bridge
            )

    def test_bridge_not_pickleable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_qt_thread_bridge_runtime_only$",
        ):
            pickle.dumps(
                self.bridge
            )

    def test_bridge_layer_has_no_direct_environment_or_network_access(self):
        controller = self.make_controller()

        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "M98 bridge must not read environment directly"
            ),
        ) as getenv_mock:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "M98 bridge must not open network directly"
                ),
            ) as opened:
                with patch.object(
                    worker_module,
                    "ProviderDiagnosticsGuiController",
                    return_value=controller,
                ):
                    state = self.wait_for_finished(
                        lambda: self.bridge.start(
                            object()
                        )
                    )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()