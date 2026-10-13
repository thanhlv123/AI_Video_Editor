"""M97 final provider diagnostics GUI controller integration.

These tests exercise the real framework-neutral controller pipeline:

    M90 provider runtime configuration
        -> M95 ProviderDiagnosticsApplicationRequest
        -> real M97 ProviderDiagnosticsGuiController
        -> real M95 ProviderDiagnosticsApplicationService
        -> real M93 diagnostics coordinator
        -> real M91 readiness
        -> real M92 connectivity when permitted
        -> real M94 presentation
        -> real M96 ProviderDiagnosticsViewModelAdapter
        -> immutable M97 controller state

Only the HTTPS boundary is mocked.

No real provider network access is performed.
No image or semantic prompt is sent.
No model inference is performed.
No PyQt dependency is required.
"""

import json
import os
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_application.public_api as application_api
import creator_studio.provider_diagnostics_gui_controller.public_api as api
import creator_studio.provider_diagnostics_view_model.public_api as view_api
import creator_studio.provider_runtime_assembly.public_api as runtime_api
import creator_studio.provider_runtime_diagnostics.public_api as diagnostic_api

from creator_studio.provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)
from tests.test_external_vision_http_transport_config import (
    config,
)


KIE_RUNTIME_ENDPOINT = (
    "https://api.kie.ai/"
    "gemini-3-flash/v1/chat/completions"
)


class FakeResponse:
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


class RemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
    ):
        self.calls = 0

    def resolve(
        self,
        request,
        check,
    ):
        self.calls += 1

        check()

        return (
            "https://media.example.test/"
            "m97-image.png"
        )


def kie_body(
    code,
):
    return json.dumps(
        {
            "code": code,
            "msg": "test",
            "data": 100.0,
        },
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )


def http_error(
    status,
):
    return urllib.error.HTTPError(
        "https://example.test",
        status,
        "test",
        None,
        None,
    )


def application_request(
    runtime_config,
    mode,
):
    return (
        application_api
        .ProviderDiagnosticsApplicationRequest(
            schema_version=(
                application_api
                .PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
            ),
            config=runtime_config,
            mode=mode,
        )
    )


class ProviderDiagnosticsGuiControllerIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.controller = (
            api.ProviderDiagnosticsGuiController()
        )

    def run_controller(
        self,
        runtime_config,
        mode,
        remote_image_source=None,
        check=None,
    ):
        if check is None:
            check = lambda: None

        request = application_request(
            runtime_config,
            mode,
        )

        return self.controller.run(
            request,
            check,
            remote_image_source,
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_PUBLIC_API_VERSION",
                "PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION",
                "ProviderDiagnosticsGuiController",
                "ProviderDiagnosticsGuiControllerCancelled",
                "ProviderDiagnosticsGuiControllerFailure",
                "ProviderDiagnosticsGuiControllerPhase",
                "ProviderDiagnosticsGuiControllerState",
                "validate_provider_diagnostics_gui_controller_state",
            ),
        )

    def test_public_surface_and_controller_construction_have_no_side_effect(self):
        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ) as getenv_mock:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not open"
                ),
            ) as opened:
                controller = (
                    api.ProviderDiagnosticsGuiController()
                )

                state = controller.state

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_offline_openai_ready_end_to_end(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-offline-openai-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "offline mode must not open network"
                ),
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertEqual(
            state.view_model.provider_label,
            "OpenAI",
        )

        self.assertEqual(
            state.view_model.status_text,
            "Ready",
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .NONE,
        )

        opened.assert_not_called()

    def test_offline_missing_credential_is_completed_not_failed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertEqual(
            state.view_model.status_text,
            "API credential missing",
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        opened.assert_not_called()

    def test_offline_invalid_credential_is_completed_not_failed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "invalid secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "API credential invalid",
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        opened.assert_not_called()

    def test_offline_kie_missing_remote_source_is_completed(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_RUNTIME_ENDPOINT,
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m97-offline-kie-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.provider_label,
            "Kie.ai",
        )

        self.assertEqual(
            state.view_model.status_text,
            "Remote image source required",
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        opened.assert_not_called()

    def test_online_openai_ready_end_to_end(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "m97-online-openai-secret"
        )

        response = FakeResponse(
            200
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertEqual(
            state.view_model.status_text,
            "Ready",
        )

        self.assertEqual(
            state.view_model.detail_text,
            (
                "Provider configuration and connectivity are ready."
            ),
        )

        opened.assert_called_once()

        request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            request.get_method(),
            "GET",
        )

        self.assertIsNone(
            request.data
        )

        headers = {
            name.lower(): value
            for name, value
            in request.header_items()
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer "
            + secret,
        )

        self.assertTrue(
            response.closed
        )

    def test_online_gemini_ready_end_to_end(self):
        runtime_config = (
            runtime_api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        secret = (
            "m97-online-gemini-secret"
        )

        response = FakeResponse(
            200
        )

        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": secret,
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.provider_label,
            "Gemini",
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        headers = {
            name.lower(): value
            for name, value
            in (
                opened.call_args.args[
                    0
                ].header_items()
            )
        }

        self.assertEqual(
            headers[
                "x-goog-api-key"
            ],
            secret,
        )

        self.assertTrue(
            response.closed
        )

    def test_online_kie_ready_end_to_end(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_RUNTIME_ENDPOINT,
                config(),
            )
        )

        remote_source = (
            RemoteImageSource()
        )

        secret = (
            "m97-online-kie-secret"
        )

        response = FakeResponse(
            200,
            kie_body(
                200
            ),
        )

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": secret,
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                    remote_source,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.provider_label,
            "Kie.ai",
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

        headers = {
            name.lower(): value
            for name, value
            in (
                opened.call_args.args[
                    0
                ].header_items()
            )
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer "
            + secret,
        )

        self.assertTrue(
            response.closed
        )

    def test_online_missing_credential_prevents_network(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "API credential missing",
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        opened.assert_not_called()

    def test_online_authentication_failure_is_completed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-auth-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    401
                ),
            ):
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "Authentication failed",
        )

        self.assertIs(
            state.view_model.severity,
            view_api.ProviderDiagnosticsViewSeverity
            .ERROR,
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

    def test_online_rate_limit_is_completed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-rate-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    429
                ),
            ):
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "Rate limited",
        )

        self.assertIs(
            state.view_model.severity,
            view_api.ProviderDiagnosticsViewSeverity
            .WARNING,
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .RETRY,
        )

    def test_online_network_unavailable_is_completed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-network-secret"
                ),
            },
            clear=True,
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
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "Network unavailable",
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

    def test_online_timeout_is_completed(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-timeout-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertEqual(
            state.view_model.status_text,
            "Connection timed out",
        )

        self.assertIs(
            state.view_model.action,
            view_api.ProviderDiagnosticsViewAction
            .RETRY,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

    def test_invalid_application_request_becomes_failed_state(self):
        with patch.object(
            probe_module,
            "_open_https",
        ) as opened:
            state = self.controller.run(
                object(),
                lambda: None,
            )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            api.ProviderDiagnosticsGuiControllerFailure
            .INVALID_REQUEST,
        )

        self.assertIsNone(
            state.view_model
        )

        opened.assert_not_called()

    def test_caller_cancellation_becomes_cancelled_state(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        def check():
            raise (
                api.ProviderDiagnosticsGuiControllerCancelled()
            )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-cancel-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.controller.run(
                    request,
                    check,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

        self.assertIsNone(
            state.view_model
        )

        self.assertIsNone(
            state.failure
        )

        opened.assert_not_called()

    def test_caller_cannot_spoof_invalid_request_failure(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        def check():
            raise ValueError(
                "provider_diagnostics_application_request_invalid"
            )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-spoof-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.controller.run(
                    request,
                    check,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            api.ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

        opened.assert_not_called()

    def test_secret_never_enters_controller_state(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "unique-m97-final-secret-778899"
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ):
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertNotIn(
            secret,
            repr(
                state
            ),
        )

        self.assertNotIn(
            secret,
            str(
                state
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                state.__dict__
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                state.view_model.__dict__
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                self.controller
            ),
        )

    def test_runtime_only_dependencies_are_not_stored(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_RUNTIME_ENDPOINT,
                config(),
            )
        )

        remote_source = (
            RemoteImageSource()
        )

        def check():
            return None

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m97-runtime-only-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                state = self.run_controller(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                    remote_source,
                    check,
                )

        self.assertIs(
            state.phase,
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model.is_ready,
            True,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

        for name in (
            "request",
            "check",
            "remote_image_source",
            "application_result",
            "credential",
            "secret",
            "api_key",
            "authorization",
            "http_status",
            "provider_code",
            "worker",
            "thread",
            "qthread",
        ):
            self.assertFalse(
                hasattr(
                    self.controller,
                    name,
                )
            )

            self.assertFalse(
                hasattr(
                    state,
                    name,
                )
            )

        opened.assert_not_called()

    def test_final_states_validate(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        states = []

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m97-validation-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                states.append(
                    self.run_controller(
                        runtime_config,
                        diagnostic_api.ProviderRuntimeDiagnosticMode
                        .OFFLINE,
                    )
                )

            opened.assert_not_called()

        second_controller = (
            api.ProviderDiagnosticsGuiController()
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                states.append(
                    second_controller.run(
                        application_request(
                            runtime_config,
                            diagnostic_api.ProviderRuntimeDiagnosticMode
                            .OFFLINE,
                        ),
                        lambda: None,
                    )
                )

            opened.assert_not_called()

        third_controller = (
            api.ProviderDiagnosticsGuiController()
        )

        states.append(
            third_controller.run(
                object(),
                lambda: None,
            )
        )

        fourth_controller = (
            api.ProviderDiagnosticsGuiController()
        )

        valid_request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        def cancel():
            raise (
                api.ProviderDiagnosticsGuiControllerCancelled()
            )

        states.append(
            fourth_controller.run(
                valid_request,
                cancel,
            )
        )

        for state in states:
            self.assertIs(
                api.validate_provider_diagnostics_gui_controller_state(
                    state
                ),
                state,
            )


if __name__ == "__main__":
    unittest.main()