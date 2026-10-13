"""M96 final provider diagnostics view-model integration.

These tests exercise the real application-to-view-model path:

    M90 provider runtime configuration
        -> M95 ProviderDiagnosticsApplicationRequest
        -> real M95 ProviderDiagnosticsApplicationService
        -> real M93 diagnostics coordinator
        -> real M91 readiness
        -> real M92 connectivity when permitted
        -> real M94 diagnostic presenter
        -> M95 ProviderDiagnosticsApplicationResult
        -> real M96 ProviderDiagnosticsViewModelAdapter
        -> M96 ProviderDiagnosticsViewModel

Only the HTTPS boundary is mocked.

No real provider network access is performed.
No image or semantic prompt is sent.
No model inference is performed.
"""

import json
import os
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_application.public_api as application_api
import creator_studio.provider_diagnostics_view_model.public_api as api
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
            "m96-image.png"
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


class ProviderDiagnosticsViewModelIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.service = (
            application_api
            .ProviderDiagnosticsApplicationService()
        )

        self.adapter = (
            api.ProviderDiagnosticsViewModelAdapter()
        )

    def run_view(
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

        application_result = (
            self.service.run(
                request,
                check,
                remote_image_source,
            )
        )

        return self.adapter.adapt(
            application_result
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH",
                "PROVIDER_DIAGNOSTICS_VIEW_MODEL_PUBLIC_API_VERSION",
                "PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION",
                "ProviderDiagnosticsViewAction",
                "ProviderDiagnosticsViewModel",
                "ProviderDiagnosticsViewModelAdapter",
                "ProviderDiagnosticsViewSeverity",
                "validate_provider_diagnostics_view_model",
            ),
        )

    def test_public_surface_access_has_no_runtime_side_effect(self):
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
                version = (
                    api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_PUBLIC_API_VERSION
                )

        self.assertEqual(
            version,
            1,
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
                    "m96-offline-openai-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertEqual(
            view.provider_label,
            "OpenAI",
        )

        self.assertEqual(
            view.status_text,
            "Ready",
        )

        self.assertEqual(
            view.detail_text,
            "Provider configuration is ready.",
        )

        self.assertIs(
            view.severity,
            api.ProviderDiagnosticsViewSeverity
            .SUCCESS,
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertEqual(
            view.action_text,
            "No action required",
        )

        self.assertIs(
            view.is_ready,
            True,
        )

        opened.assert_not_called()

    def test_offline_missing_credential_prevents_network(self):
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertEqual(
            view.provider_label,
            "OpenAI",
        )

        self.assertEqual(
            view.status_text,
            "API credential missing",
        )

        self.assertIs(
            view.severity,
            api.ProviderDiagnosticsViewSeverity
            .ERROR,
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            view.action_text,
            "Configure credential",
        )

        self.assertIs(
            view.is_ready,
            False,
        )

        opened.assert_not_called()

    def test_offline_invalid_credential_prevents_network(self):
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertEqual(
            view.status_text,
            "API credential invalid",
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            view.action_text,
            "Check credential",
        )

        self.assertIs(
            view.is_ready,
            False,
        )

        opened.assert_not_called()

    def test_offline_kie_missing_remote_source_prevents_network(self):
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
                    "m96-kie-offline-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        self.assertEqual(
            view.provider_label,
            "Kie.ai",
        )

        self.assertEqual(
            view.status_text,
            "Remote image source required",
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertEqual(
            view.action_text,
            "Add remote image source",
        )

        self.assertIs(
            view.is_ready,
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
            "m96-online-openai-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.provider_label,
            "OpenAI",
        )

        self.assertEqual(
            view.status_text,
            "Ready",
        )

        self.assertEqual(
            view.detail_text,
            (
                "Provider configuration and connectivity are ready."
            ),
        )

        self.assertIs(
            view.is_ready,
            True,
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
            "m96-online-gemini-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.provider_label,
            "Gemini",
        )

        self.assertIs(
            view.is_ready,
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
            "m96-online-kie-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                    remote_source,
                )

        self.assertEqual(
            view.provider_label,
            "Kie.ai",
        )

        self.assertEqual(
            view.status_text,
            "Ready",
        )

        self.assertIs(
            view.is_ready,
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.status_text,
            "API credential missing",
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        opened.assert_not_called()

    def test_online_authentication_failed_end_to_end(self):
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
                    "m96-auth-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.status_text,
            "Authentication failed",
        )

        self.assertIs(
            view.severity,
            api.ProviderDiagnosticsViewSeverity
            .ERROR,
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            view.action_text,
            "Check credential",
        )

        self.assertIs(
            view.is_ready,
            False,
        )

    def test_online_rate_limited_end_to_end(self):
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
                    "m96-rate-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.status_text,
            "Rate limited",
        )

        self.assertIs(
            view.severity,
            api.ProviderDiagnosticsViewSeverity
            .WARNING,
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .RETRY,
        )

        self.assertEqual(
            view.action_text,
            "Retry",
        )

    def test_online_network_unavailable_end_to_end(self):
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
                    "m96-network-secret"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.status_text,
            "Network unavailable",
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            view.action_text,
            "Check network",
        )

        self.assertIs(
            view.is_ready,
            False,
        )

    def test_online_timeout_end_to_end(self):
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
                    "m96-timeout-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            view.status_text,
            "Connection timed out",
        )

        self.assertIs(
            view.action,
            api.ProviderDiagnosticsViewAction
            .RETRY,
        )

        self.assertIs(
            view.is_ready,
            False,
        )

    def test_view_model_hides_upstream_runtime_fields(self):
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
                    "m96-fields-secret"
                ),
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertEqual(
            set(
                view.__dict__
            ),
            {
                "schema_version",
                "provider_label",
                "status_text",
                "detail_text",
                "severity",
                "action",
                "action_text",
                "is_ready",
            },
        )

        forbidden = (
            "config",
            "credential",
            "credential_environment_variable",
            "http_status",
            "provider_code",
            "diagnostic_report",
            "presentation",
            "application_result",
            "check",
            "remote_image_source",
        )

        for name in forbidden:
            self.assertFalse(
                hasattr(
                    view,
                    name,
                )
            )

    def test_secret_never_enters_view_model(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "unique-m96-final-secret-445566"
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
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .ONLINE,
                )

        self.assertNotIn(
            secret,
            repr(
                view
            ),
        )

        self.assertNotIn(
            secret,
            str(
                view
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                view.__dict__
            ),
        )

        self.assertNotIn(
            secret,
            view.provider_label,
        )

        self.assertNotIn(
            secret,
            view.status_text,
        )

        self.assertNotIn(
            secret,
            view.detail_text,
        )

        self.assertNotIn(
            secret,
            view.action_text,
        )

    def test_runtime_only_dependencies_not_stored(self):
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

        check = lambda: None

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m96-runtime-only-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                view = self.run_view(
                    runtime_config,
                    diagnostic_api.ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                    remote_source,
                    check,
                )

        self.assertIs(
            view.is_ready,
            True,
        )

        self.assertFalse(
            hasattr(
                view,
                "check",
            )
        )

        self.assertFalse(
            hasattr(
                view,
                "remote_image_source",
            )
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

        opened.assert_not_called()

    def test_caller_check_exception_propagates(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            if (
                calls[
                    0
                ]
                == 2
            ):
                raise RuntimeError(
                    "m96-caller-check"
                )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m96-check-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^m96-caller-check$",
                ):
                    self.run_view(
                        runtime_config,
                        diagnostic_api.ProviderRuntimeDiagnosticMode
                        .OFFLINE,
                        check=check,
                    )

        opened.assert_not_called()

    def test_final_view_models_validate(self):
        openai_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        gemini_config = (
            runtime_api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        views = []

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m96-validation-openai-secret"
                ),
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
                views.append(
                    self.run_view(
                        openai_config,
                        diagnostic_api.ProviderRuntimeDiagnosticMode
                        .ONLINE,
                    )
                )

        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": (
                    "m96-validation-gemini-secret"
                ),
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
                views.append(
                    self.run_view(
                        gemini_config,
                        diagnostic_api.ProviderRuntimeDiagnosticMode
                        .ONLINE,
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
                views.append(
                    self.run_view(
                        openai_config,
                        diagnostic_api.ProviderRuntimeDiagnosticMode
                        .OFFLINE,
                    )
                )

            opened.assert_not_called()

        for view in views:
            self.assertIs(
                api.validate_provider_diagnostics_view_model(
                    view
                ),
                view,
            )


if __name__ == "__main__":
    unittest.main()