"""M100 M98 runtime credential-source handoff tests.

These tests establish runtime-only credential-source propagation through the
M98 QObject worker and QThread bridge without changing their original public
constructor/start contracts.

The seam must:

- preserve the original worker constructor;
- preserve the original bridge start signature;
- provide explicit injected runtime paths;
- carry the same factory into the real M97/M95/M93/M91/M92 stack;
- release factory authority after worker execution;
- keep credential material out of terminal GUI state and Qt signals;
- preserve normal provider diagnostic outcomes as COMPLETED states.
"""

import inspect
import time
import unittest
from unittest.mock import patch

from PyQt6.QtCore import (
    QCoreApplication,
)

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiControllerPhase,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
    ProviderDiagnosticsQtWorker,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


APP = (
    QCoreApplication.instance()
    or QCoreApplication([])
)


class FakeCredential:
    def __init__(
        self,
        header,
        value,
    ):
        self.header = header
        self.value = value


class FakeCredentialSource:
    def __init__(
        self,
        credential,
    ):
        self.credential = credential

    def resolve(
        self,
        check,
    ):
        check()

        return self.credential


class RecordingCredentialSourceFactory:
    def __init__(
        self,
        secret,
    ):
        self.secret = secret
        self.calls = []

    def __call__(
        self,
        environment_variable,
        header,
        mode,
    ):
        self.calls.append(
            (
                environment_variable,
                header,
                mode,
            )
        )

        return FakeCredentialSource(
            FakeCredential(
                header,
                self.secret,
            )
        )


class FakeResponse:
    def __init__(
        self,
        status=200,
    ):
        self.status = status
        self.closed = False

    def close(
        self,
    ):
        self.closed = True


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


def wait_for(
    predicate,
    timeout_seconds=3.0,
):
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while (
        time.monotonic()
        < deadline
    ):
        APP.processEvents()

        if predicate():
            return True

        time.sleep(
            0.001
        )

    APP.processEvents()

    return bool(
        predicate()
    )


class ProviderDiagnosticsQtWorkerCredentialSourceInjectionTests(
    unittest.TestCase
):

    def test_original_worker_and_bridge_signatures_are_unchanged(
        self,
    ):
        worker_parameters = inspect.signature(
            ProviderDiagnosticsQtWorker
        ).parameters

        self.assertEqual(
            tuple(
                worker_parameters
            ),
            (
                "request",
                "remote_image_source",
                "parent",
            ),
        )

        self.assertIsNone(
            worker_parameters[
                "remote_image_source"
            ].default
        )

        self.assertIsNone(
            worker_parameters[
                "parent"
            ].default
        )

        bridge_parameters = inspect.signature(
            ProviderDiagnosticsQtThreadBridge.start
        ).parameters

        self.assertEqual(
            tuple(
                bridge_parameters
            ),
            (
                "self",
                "request",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            bridge_parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_worker_and_bridge_signatures_are_explicit(
        self,
    ):
        worker_parameters = inspect.signature(
            ProviderDiagnosticsQtWorker
            .create_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                worker_parameters
            ),
            (
                "request",
                "credential_source_factory",
                "remote_image_source",
                "parent",
            ),
        )

        self.assertIsNone(
            worker_parameters[
                "remote_image_source"
            ].default
        )

        self.assertIsNone(
            worker_parameters[
                "parent"
            ].default
        )

        bridge_parameters = inspect.signature(
            ProviderDiagnosticsQtThreadBridge
            .start_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                bridge_parameters
            ),
            (
                "self",
                "request",
                "credential_source_factory",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            bridge_parameters[
                "remote_image_source"
            ].default
        )

    def test_worker_offline_uses_factory_and_releases_runtime_authority(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        config = request.config

        secret = (
            "unique-m100-m98-worker-secret-244948"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        worker = (
            ProviderDiagnosticsQtWorker
            .create_with_credential_source_factory(
                request,
                factory,
            )
        )

        finished = []

        worker.finished.connect(
            finished.append
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "OFFLINE worker diagnostics must not open HTTPS"
            ),
        ) as opened:
            worker.run()

        opened.assert_not_called()

        self.assertEqual(
            len(
                finished
            ),
            1,
        )

        state = finished[
            0
        ]

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertTrue(
            state.view_model.is_ready
        )

        self.assertEqual(
            factory.calls,
            [
                (
                    config.credential_environment_variable,
                    config.profile.credential_header,
                    config.credential_mode,
                )
            ],
        )

        self.assertIsNone(
            worker._request
        )

        self.assertIsNone(
            worker._remote_image_source
        )

        self.assertIsNone(
            worker._credential_source_factory
        )

        self.assertFalse(
            worker._use_credential_source_factory
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
                worker
            ),
        )

    def test_bridge_online_uses_same_factory_and_finishes_completed(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        config = request.config

        secret = (
            "unique-m100-m98-bridge-secret-264575"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        response = FakeResponse(
            200
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        finished = []

        bridge.finished.connect(
            finished.append
        )

        with patch.object(
            probe_module,
            "_open_https",
            return_value=response,
        ) as opened:
            running_state = (
                bridge
                .start_with_credential_source_factory(
                    request,
                    factory,
                )
            )

            self.assertIs(
                running_state.phase,
                ProviderDiagnosticsGuiControllerPhase
                .RUNNING,
            )

            self.assertTrue(
                wait_for(
                    lambda: bool(
                        finished
                    )
                )
            )

        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

        self.assertFalse(
            bridge.is_running
        )

        self.assertEqual(
            len(
                finished
            ),
            1,
        )

        state = finished[
            0
        ]

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertTrue(
            state.view_model.is_ready
        )

        expected_metadata = (
            config.credential_environment_variable,
            config.profile.credential_header,
            config.credential_mode,
        )

        self.assertEqual(
            factory.calls,
            [
                expected_metadata,
                expected_metadata,
            ],
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
                bridge
            ),
        )

    def test_factory_failure_is_completed_not_ready_without_https(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        private_message = (
            "private-m100-m98-factory-failure"
        )

        calls = []

        def factory(
            environment_variable,
            header,
            mode,
        ):
            calls.append(
                (
                    environment_variable,
                    header,
                    mode,
                )
            )

            raise RuntimeError(
                private_message
            )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        finished = []

        bridge.finished.connect(
            finished.append
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "failed readiness must stop before HTTPS"
            ),
        ) as opened:
            bridge.start_with_credential_source_factory(
                request,
                factory,
            )

            self.assertTrue(
                wait_for(
                    lambda: bool(
                        finished
                    )
                )
            )

        opened.assert_not_called()

        self.assertEqual(
            len(
                calls
            ),
            1,
        )

        state = finished[
            0
        ]

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertFalse(
            state.view_model.is_ready
        )

        self.assertNotIn(
            private_message,
            repr(
                state
            ),
        )

        self.assertFalse(
            bridge.is_running
        )

    def test_terminal_qt_surface_contains_no_runtime_authority(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        secret = (
            "unique-m100-m98-terminal-secret-282842"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        state_events = []
        finished_events = []

        bridge.state_changed.connect(
            state_events.append
        )

        bridge.finished.connect(
            finished_events.append
        )

        bridge.start_with_credential_source_factory(
            request,
            factory,
        )

        self.assertTrue(
            wait_for(
                lambda: bool(
                    finished_events
                )
            )
        )

        self.assertEqual(
            len(
                state_events
            ),
            1,
        )

        self.assertEqual(
            len(
                finished_events
            ),
            1,
        )

        terminal_state = (
            finished_events[
                0
            ]
        )

        self.assertIs(
            terminal_state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertNotIn(
            secret,
            repr(
                terminal_state
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                state_events
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                finished_events
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                bridge
            ),
        )


if __name__ == "__main__":
    unittest.main()