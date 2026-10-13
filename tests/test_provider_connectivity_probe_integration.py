"""M92 final public API and connectivity integration.

These tests exercise the complete connectivity path:

    M90 provider preset
        -> ProviderRuntimeConfig
        -> M92 ProviderConnectivityProbe
        -> runtime environment credential
        -> authenticated diagnostic GET
        -> normalized secret-free report

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
import creator_studio.provider_connectivity_probe.public_api as api
import creator_studio.provider_runtime_assembly.public_api as runtime_api

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


class ProviderConnectivityProbeIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.probe = (
            api.ProviderConnectivityProbe()
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_CONNECTIVITY_PROBE_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS,
            5000,
        )

        self.assertEqual(
            api.MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES,
            8192,
        )

        self.assertEqual(
            api.__all__,
            (
                "GEMINI_CONNECTIVITY_PROBE_ENDPOINT",
                "KIE_CONNECTIVITY_PROBE_ENDPOINT",
                "MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES",
                "MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS",
                "OPENAI_CONNECTIVITY_PROBE_ENDPOINT",
                "PROVIDER_CONNECTIVITY_PROBE_PUBLIC_API_VERSION",
                "PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION",
                "ProviderConnectivityProbe",
                "ProviderConnectivityProbeReport",
                "ProviderConnectivityProbeStatus",
                "validate_provider_connectivity_probe_report",
            ),
        )

    def test_import_surface_is_lazy(self):
        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "network must not open"
            ),
        ) as opened:
            value = (
                api.PROVIDER_CONNECTIVITY_PROBE_PUBLIC_API_VERSION
            )

        self.assertEqual(
            value,
            1,
        )

        opened.assert_not_called()

    def test_openai_end_to_end(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "openai-m92-integration-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertIsNone(
            result.provider_code
        )

        request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in request.header_items()
        }

        self.assertEqual(
            request.full_url,
            api.OPENAI_CONNECTIVITY_PROBE_ENDPOINT,
        )

        self.assertEqual(
            request.get_method(),
            "GET",
        )

        self.assertIsNone(
            request.data
        )

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

    def test_gemini_end_to_end(self):
        runtime_config = (
            runtime_api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        secret = (
            "gemini-m92-integration-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .READY,
        )

        request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in request.header_items()
        }

        self.assertEqual(
            request.full_url,
            api.GEMINI_CONNECTIVITY_PROBE_ENDPOINT,
        )

        self.assertEqual(
            headers[
                "x-goog-api-key"
            ],
            secret,
        )

        self.assertTrue(
            response.closed
        )

    def test_kie_end_to_end(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_RUNTIME_ENDPOINT,
                config(),
            )
        )

        secret = (
            "kie-m92-integration-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
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

        request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in request.header_items()
        }

        self.assertEqual(
            request.full_url,
            api.KIE_CONNECTIVITY_PROBE_ENDPOINT,
        )

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

    def test_missing_credential_prevents_network(self):
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .CREDENTIAL_MISSING,
        )

        self.assertIsNone(
            result.http_status
        )

        self.assertIsNone(
            result.provider_code
        )

        opened.assert_not_called()

    def test_invalid_credential_prevents_network(self):
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .CREDENTIAL_INVALID,
        )

        opened.assert_not_called()

    def test_custom_environment_variable(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
                "CUSTOM_CONNECTIVITY_KEY",
            )
        )

        secret = (
            "custom-connectivity-secret"
        )

        with patch.dict(
            os.environ,
            {
                "CUSTOM_CONNECTIVITY_KEY": secret,
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ) as opened:
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "CUSTOM_CONNECTIVITY_KEY",
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

    def test_openai_http_authentication_failure(self):
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
                    "authentication-test-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            401,
        )

        self.assertIsNone(
            result.provider_code
        )

    def test_kie_wrapped_authentication_failure(self):
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
                    "kie-auth-test-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertEqual(
            result.provider_code,
            401,
        )

    def test_rate_limit_is_normalized(self):
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
                    "rate-limit-test-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .RATE_LIMITED,
        )

        self.assertEqual(
            result.http_status,
            429,
        )

    def test_timeout_is_normalized(self):
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
                    "timeout-test-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .DEADLINE_EXCEEDED,
        )

        self.assertIsNone(
            result.http_status
        )

    def test_network_unavailable_is_normalized(self):
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
                    "network-test-secret"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
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
            "unique-m92-final-secret-112233"
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
                result = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
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

    def test_invalid_config_touches_no_environment_or_network(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
            side_effect=AssertionError(
                "credential source must not construct"
            ),
        ) as source_type:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not open"
                ),
            ) as opened:
                result = self.probe.probe(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            api.ProviderConnectivityProbeStatus
            .CONFIG_INVALID,
        )

        self.assertIsNone(
            result.provider
        )

        self.assertIsNone(
            result.credential_environment_variable
        )

        source_type.assert_not_called()
        opened.assert_not_called()

    def test_final_reports_validate(self):
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
                    "validation-test-secret"
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
                report = self.probe.probe(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                report
            ),
            report,
        )


if __name__ == "__main__":
    unittest.main()