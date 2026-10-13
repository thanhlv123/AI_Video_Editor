"""M93 final public API and diagnostics integration.

These tests exercise the real M93 -> M91 -> M92 diagnostic chain:

    M90 provider preset
        -> ProviderRuntimeConfig
        -> M93 ProviderRuntimeDiagnosticsCoordinator
        -> real M91 readiness
        -> real M92 connectivity when permitted
        -> normalized M93 diagnostic report

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
import creator_studio.provider_runtime_diagnostics.public_api as api
import creator_studio.provider_runtime_assembly.public_api as runtime_api

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
            "m93-image.png"
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


class ProviderRuntimeDiagnosticsIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.coordinator = (
            api.ProviderRuntimeDiagnosticsCoordinator()
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_RUNTIME_DIAGNOSTIC_PUBLIC_API_VERSION",
                "PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION",
                "ProviderRuntimeDiagnosticMode",
                "ProviderRuntimeDiagnosticReport",
                "ProviderRuntimeDiagnosticStatus",
                "ProviderRuntimeDiagnosticsCoordinator",
                "validate_provider_runtime_diagnostic_report",
            ),
        )

    def test_public_surface_access_opens_no_network(self):
        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "network must not open"
            ),
        ) as opened:
            version = (
                api.PROVIDER_RUNTIME_DIAGNOSTIC_PUBLIC_API_VERSION
            )

        self.assertEqual(
            version,
            1,
        )

        opened.assert_not_called()

    def test_offline_openai_ready_without_network(self):
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
                    "offline-openai-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIsNone(
            result.http_status
        )

        self.assertIsNone(
            result.provider_code
        )

        opened.assert_not_called()

    def test_offline_missing_credential_without_network(self):
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        opened.assert_not_called()

    def test_offline_invalid_credential_without_network(self):
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

        opened.assert_not_called()

    def test_offline_kie_missing_remote_dependency_without_network(self):
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
                    "kie-offline-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING,
        )

        opened.assert_not_called()

    def test_offline_kie_ready_does_not_resolve_remote_source(self):
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
                    "kie-offline-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                    remote_source,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

        opened.assert_not_called()

    def test_online_openai_ready(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "openai-m93-online-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertIsNone(
            result.provider_code
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

    def test_online_gemini_ready(self):
        runtime_config = (
            runtime_api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        secret = (
            "gemini-m93-online-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
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

    def test_online_kie_ready(self):
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
            "kie-m93-online-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                    remote_source,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertEqual(
            result.provider_code,
            200,
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        opened.assert_not_called()

    def test_online_invalid_credential_prevents_network(self):
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

        opened.assert_not_called()

    def test_online_missing_remote_dependency_prevents_network(self):
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
                    "kie-missing-source-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING,
        )

        opened.assert_not_called()

    def test_online_authentication_failure(self):
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
                    "authentication-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            401,
        )

    def test_online_rate_limit(self):
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
                    "rate-limit-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED,
        )

        self.assertEqual(
            result.http_status,
            429,
        )

    def test_online_provider_unavailable(self):
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
                    "provider-failure-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    503
                ),
            ):
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE,
        )

        self.assertEqual(
            result.http_status,
            503,
        )

    def test_online_timeout(self):
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
                    "timeout-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
        )

        self.assertIsNone(
            result.http_status
        )

    def test_online_network_unavailable(self):
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
                    "network-secret"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
        )

        self.assertIsNone(
            result.http_status
        )

    def test_secret_never_enters_report(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "unique-m93-secret-445566"
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
                result = self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderRuntimeDiagnosticStatus
            .READY,
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

    def test_nested_check_exception_not_swallowed(self):
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
                    "m93-caller-check"
                )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "check-test-secret"
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
                    "^m93-caller-check$",
                ):
                    self.coordinator.diagnose(
                        runtime_config,
                        (
                            api.ProviderRuntimeDiagnosticMode
                            .OFFLINE
                        ),
                        check,
                    )

        opened.assert_not_called()

    def test_returned_reports_validate(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        reports = []

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "validation-secret"
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
                reports.append(
                    self.coordinator.diagnose(
                        runtime_config,
                        (
                            api.ProviderRuntimeDiagnosticMode
                            .ONLINE
                        ),
                        lambda: None,
                    )
                )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            reports.append(
                self.coordinator.diagnose(
                    runtime_config,
                    (
                        api.ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )
            )

        for report in reports:
            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    report
                ),
                report,
            )


if __name__ == "__main__":
    unittest.main()