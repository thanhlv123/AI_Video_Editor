"""M94 final provider diagnostics presentation integration.

These tests exercise the real application path:

    M90 provider preset
        -> ProviderRuntimeConfig
        -> M93 ProviderRuntimeDiagnosticsCoordinator
        -> real M91 readiness
        -> real M92 connectivity when permitted
        -> M93 ProviderRuntimeDiagnosticReport
        -> M94 ProviderDiagnosticPresenter
        -> GUI/CLI-safe ProviderDiagnosticPresentation

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
import creator_studio.provider_diagnostics_presentation.public_api as api
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
            "m94-image.png"
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


class ProviderDiagnosticsPresentationIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.coordinator = (
            diagnostic_api
            .ProviderRuntimeDiagnosticsCoordinator()
        )

        self.presenter = (
            api.ProviderDiagnosticPresenter()
        )

    def diagnose_and_present(
        self,
        runtime_config,
        mode,
        remote_image_source=None,
    ):
        report = self.coordinator.diagnose(
            runtime_config,
            mode,
            lambda: None,
            remote_image_source,
        )

        return self.presenter.present(
            report
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTIC_PRESENTATION_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH,
            80,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH,
            320,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH",
                "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH",
                "PROVIDER_DIAGNOSTIC_PRESENTATION_PUBLIC_API_VERSION",
                "PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION",
                "ProviderDiagnosticPresentation",
                "ProviderDiagnosticPresentationAction",
                "ProviderDiagnosticPresentationSeverity",
                "ProviderDiagnosticPresenter",
                "validate_provider_diagnostic_presentation",
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
                    api.PROVIDER_DIAGNOSTIC_PRESENTATION_PUBLIC_API_VERSION
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
                    "m94-offline-openai-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .NONE,
        )

        self.assertEqual(
            result.title,
            "Ready",
        )

        self.assertEqual(
            result.detail,
            "Provider configuration is ready.",
        )

        opened.assert_not_called()

    def test_offline_missing_credential_end_to_end(self):
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "API credential missing",
        )

        self.assertIn(
            "OPENAI_API_KEY",
            result.detail,
        )

        opened.assert_not_called()

    def test_offline_invalid_credential_end_to_end(self):
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "API credential invalid",
        )

        opened.assert_not_called()

    def test_offline_kie_missing_remote_source_end_to_end(self):
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
                    "m94-kie-offline-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertEqual(
            result.title,
            "Remote image source required",
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
            "m94-online-openai-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertEqual(
            result.title,
            "Ready",
        )

        self.assertEqual(
            result.detail,
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
            "m94-online-gemini-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
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
            "m94-online-kie-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    remote_source,
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .SUCCESS,
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
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
                    "m94-authentication-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "Authentication failed",
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
                    "m94-rate-limit-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Rate limited",
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
                    "m94-network-secret"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
        )

        self.assertIs(
            result.severity,
            api.ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            result.title,
            "Network unavailable",
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
                    "m94-timeout-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
        )

        self.assertIs(
            result.action,
            api.ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Connection timed out",
        )

    def test_secret_never_enters_final_presentation(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "unique-m94-final-secret-778899"
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
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                )

        self.assertNotIn(
            secret,
            repr(
                result
            ),
        )

        self.assertNotIn(
            secret,
            str(
                result
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                result.__dict__
            ),
        )

        self.assertNotIn(
            secret,
            result.title,
        )

        self.assertNotIn(
            secret,
            result.detail,
        )

    def test_presentation_hides_transport_status_fields(self):
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

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m94-kie-auth-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200,
                    kie_body(
                        401
                    ),
                ),
            ):
                result = self.diagnose_and_present(
                    runtime_config,
                    (
                        diagnostic_api
                        .ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    remote_source,
                )

        self.assertIs(
            result.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertNotIn(
            "http_status",
            result.__dict__,
        )

        self.assertNotIn(
            "provider_code",
            result.__dict__,
        )

    def test_final_presentations_validate(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        presentations = []

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m94-validation-secret"
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
                presentations.append(
                    self.diagnose_and_present(
                        runtime_config,
                        (
                            diagnostic_api
                            .ProviderRuntimeDiagnosticMode
                            .ONLINE
                        ),
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
                presentations.append(
                    self.diagnose_and_present(
                        runtime_config,
                        (
                            diagnostic_api
                            .ProviderRuntimeDiagnosticMode
                            .OFFLINE
                        ),
                    )
                )

            opened.assert_not_called()

        for presentation in presentations:
            self.assertIs(
                api.validate_provider_diagnostic_presentation(
                    presentation
                ),
                presentation,
            )


if __name__ == "__main__":
    unittest.main()