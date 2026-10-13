"""M95 final provider diagnostics application integration.

These tests exercise the real provider diagnostics application path:

    M90 provider runtime configuration
        -> M95 application request
        -> M95 ProviderDiagnosticsApplicationService
        -> real M93 ProviderRuntimeDiagnosticsCoordinator
        -> real M91 readiness
        -> real M92 connectivity when permitted
        -> real M94 ProviderDiagnosticPresenter
        -> M95 ProviderDiagnosticsApplicationResult

Only the HTTPS boundary is mocked.

No real provider network access is performed.
No model inference is performed.
No image or semantic prompt is sent.
"""

import json
import os
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_application.public_api as api
import creator_studio.provider_diagnostics_presentation.public_api as presentation_api
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
            "m95-image.png"
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
    return api.ProviderDiagnosticsApplicationRequest(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=runtime_config,
        mode=mode,
    )


class ProviderDiagnosticsApplicationIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.service = (
            api.ProviderDiagnosticsApplicationService()
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_APPLICATION_PUBLIC_API_VERSION",
                "PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION",
                "ProviderDiagnosticsApplicationRequest",
                "ProviderDiagnosticsApplicationResult",
                "ProviderDiagnosticsApplicationService",
                "validate_provider_diagnostics_application_request",
                "validate_provider_diagnostics_application_result",
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
                    api.PROVIDER_DIAGNOSTICS_APPLICATION_PUBLIC_API_VERSION
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-offline-openai-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "offline diagnostics must not open network"
                ),
            ) as opened:
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            type(result),
            api.ProviderDiagnosticsApplicationResult,
        )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.presentation.severity,
            presentation_api.ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .NONE,
        )

        self.assertEqual(
            result.presentation.title,
            "Ready",
        )

        self.assertEqual(
            result.presentation.detail,
            "Provider configuration is ready.",
        )

        opened.assert_not_called()

    def test_offline_missing_credential_prevents_network(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertIn(
            "OPENAI_API_KEY",
            result.presentation.detail,
        )

        opened.assert_not_called()

    def test_offline_invalid_credential_prevents_network(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m95-offline-kie-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertEqual(
            result.presentation.title,
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        secret = (
            "m95-online-openai-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.presentation.severity,
            presentation_api.ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertEqual(
            result.presentation.detail,
            (
                "Provider configuration and connectivity are ready."
            ),
        )

        opened.assert_called_once()

        request_object = opened.call_args.args[
            0
        ]

        self.assertEqual(
            request_object.get_method(),
            "GET",
        )

        self.assertIsNone(
            request_object.data
        )

        headers = {
            name.lower(): value
            for name, value
            in request_object.header_items()
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        secret = (
            "m95-online-gemini-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        remote_source = (
            RemoteImageSource()
        )

        secret = (
            "m95-online-kie-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                    remote_source,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            result.presentation.severity,
            presentation_api.ProviderDiagnosticPresentationSeverity
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-authentication-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertIs(
            result.presentation.severity,
            presentation_api.ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.presentation.title,
            "Authentication failed",
        )

    def test_online_rate_limited_end_to_end(self):
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

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-rate-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED,
        )

        self.assertIs(
            result.presentation.severity,
            presentation_api.ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.presentation.title,
            "Rate limited",
        )

    def test_online_network_unavailable_end_to_end(self):
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

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-network-secret"
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
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            result.presentation.title,
            "Network unavailable",
        )

    def test_online_timeout_end_to_end(self):
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

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-timeout-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
        )

        self.assertIs(
            result.presentation.action,
            presentation_api.ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.presentation.title,
            "Connection timed out",
        )

    def test_secret_never_enters_application_result(self):
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

        secret = (
            "unique-m95-final-secret-112233"
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
                result = self.service.run(
                    request,
                    lambda: None,
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
            repr(
                result.presentation.__dict__
            ),
        )

        self.assertNotIn(
            secret,
            result.presentation.title,
        )

        self.assertNotIn(
            secret,
            result.presentation.detail,
        )

    def test_runtime_only_dependencies_not_stored(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_RUNTIME_ENDPOINT,
                config(),
            )
        )

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

        remote_source = (
            RemoteImageSource()
        )

        check = lambda: None

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "m95-runtime-only-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.service.run(
                    request,
                    check,
                    remote_source,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            diagnostic_api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertFalse(
            hasattr(
                request,
                "check",
            )
        )

        self.assertFalse(
            hasattr(
                request,
                "remote_image_source",
            )
        )

        self.assertFalse(
            hasattr(
                result,
                "check",
            )
        )

        self.assertFalse(
            hasattr(
                result,
                "remote_image_source",
            )
        )

        self.assertFalse(
            hasattr(
                result.presentation,
                "check",
            )
        )

        self.assertFalse(
            hasattr(
                result.presentation,
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

        request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
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
                    "m95-caller-check"
                )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-check-secret"
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
                    "^m95-caller-check$",
                ):
                    self.service.run(
                        request,
                        check,
                    )

        opened.assert_not_called()

    def test_final_results_validate(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        offline_request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

        online_request = application_request(
            runtime_config,
            diagnostic_api.ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        results = []

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "m95-validation-secret"
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
                results.append(
                    self.service.run(
                        online_request,
                        lambda: None,
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
                results.append(
                    self.service.run(
                        offline_request,
                        lambda: None,
                    )
                )

            opened.assert_not_called()

        for result in results:
            self.assertIs(
                api.validate_provider_diagnostics_application_result(
                    result
                ),
                result,
            )

            self.assertIs(
                presentation_api.validate_provider_diagnostic_presentation(
                    result.presentation
                ),
                result.presentation,
            )


if __name__ == "__main__":
    unittest.main()