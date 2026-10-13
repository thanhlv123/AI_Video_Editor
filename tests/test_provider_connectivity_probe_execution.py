"""M92 provider connectivity probe execution."""

import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
)
from creator_studio.provider_connectivity_probe.models import (
    ProviderConnectivityProbeStatus,
    validate_provider_connectivity_probe_report,
)
from creator_studio.provider_connectivity_probe.probe import (
    GEMINI_CONNECTIVITY_PROBE_ENDPOINT,
    KIE_CONNECTIVITY_PROBE_ENDPOINT,
    MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES,
    MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS,
    OPENAI_CONNECTIVITY_PROBE_ENDPOINT,
    ProviderConnectivityProbe,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    gemini_runtime_config,
    kie_runtime_config,
    openai_runtime_config,
)


class FakeCredential:
    def __init__(
        self,
        header,
        value,
    ):
        self.header = header
        self.value = value


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
            "data": 100.5,
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


class ProviderConnectivityProbeExecutionTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.probe = (
            ProviderConnectivityProbe()
        )

    def credential(
        self,
        config,
        value="test-secret",
    ):
        if (
            config.profile.credential_header
            is ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ):
            value = (
                "Bearer "
                + value
            )

        return FakeCredential(
            config.profile.credential_header,
            value,
        )

    def run_with_response(
        self,
        config,
        response,
    ):
        credential = self.credential(
            config
        )

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                credential
            )

            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        return (
            result,
            opened,
        )

    def test_constants(self):
        self.assertEqual(
            OPENAI_CONNECTIVITY_PROBE_ENDPOINT,
            "https://api.openai.com/v1/models",
        )

        self.assertEqual(
            GEMINI_CONNECTIVITY_PROBE_ENDPOINT,
            (
                "https://generativelanguage.googleapis.com"
                "/v1beta/models"
            ),
        )

        self.assertEqual(
            KIE_CONNECTIVITY_PROBE_ENDPOINT,
            (
                "https://api.kie.ai"
                "/api/v1/chat/credit"
            ),
        )

        self.assertEqual(
            MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS,
            5000,
        )

        self.assertEqual(
            MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES,
            8192,
        )

    def test_probe_is_stateless(self):
        self.assertEqual(
            ProviderConnectivityProbe.__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.probe,
                "__dict__",
            )
        )

    def test_probe_signature(self):
        import inspect

        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderConnectivityProbe
                    .probe
                ).parameters
            ),
            (
                "self",
                "config",
                "check",
            ),
        )

    def test_openai_request_contract(self):
        config = openai_runtime_config()

        response = FakeResponse(
            200
        )

        result, opened = (
            self.run_with_response(
                config,
                response,
            )
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
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
            OPENAI_CONNECTIVITY_PROBE_ENDPOINT,
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
            "Bearer test-secret",
        )

    def test_gemini_request_contract(self):
        config = gemini_runtime_config()

        response = FakeResponse(
            200
        )

        result, opened = (
            self.run_with_response(
                config,
                response,
            )
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
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
            GEMINI_CONNECTIVITY_PROBE_ENDPOINT,
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
                "x-goog-api-key"
            ],
            "test-secret",
        )

    def test_kie_request_contract(self):
        config = kie_runtime_config()

        response = FakeResponse(
            200,
            kie_body(
                200
            ),
        )

        result, opened = (
            self.run_with_response(
                config,
                response,
            )
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
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
            KIE_CONNECTIVITY_PROBE_ENDPOINT,
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
            "Bearer test-secret",
        )

    def test_credential_source_receives_config_metadata(self):
        config = gemini_runtime_config()

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ):
                self.probe.probe(
                    config,
                    lambda: None,
                )

        source_type.assert_called_once_with(
            config.credential_environment_variable,
            config.profile.credential_header,
            config.credential_mode,
        )

    def test_missing_credential_mapping(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            )
        )

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.probe.probe(
                    openai_runtime_config(),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .CREDENTIAL_MISSING,
        )

        opened.assert_not_called()

    def test_invalid_credential_mapping(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            )
        )

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.probe.probe(
                    openai_runtime_config(),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .CREDENTIAL_INVALID,
        )

        opened.assert_not_called()

    def test_other_credential_failures_map_internal(self):
        codes = (
            ExternalVisionHTTPCredentialFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
            ExternalVisionHTTPCredentialFailureCode
            .DEADLINE_EXCEEDED,
            ExternalVisionHTTPCredentialFailureCode
            .INTERNAL_FAILURE,
        )

        for code in codes:
            with self.subTest(
                code=code
            ):
                failure = (
                    ExternalVisionHTTPCredentialFailure(
                        code
                    )
                )

                with patch.object(
                    probe_module,
                    "EnvironmentCredentialSource",
                ) as source_type:
                    source_type.return_value.resolve.side_effect = (
                        failure
                    )

                    result = self.probe.probe(
                        openai_runtime_config(),
                        lambda: None,
                    )

                self.assertIs(
                    result.status,
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE,
                )

    def test_invalid_config_prevents_credential_and_network(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            with patch.object(
                probe_module,
                "_open_https",
            ) as opened:
                result = self.probe.probe(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .CONFIG_INVALID,
        )

        self.assertIsNone(
            result.provider
        )

        source_type.assert_not_called()
        opened.assert_not_called()

    def test_openai_success(self):
        result, _ = self.run_with_response(
            openai_runtime_config(),
            FakeResponse(
                200
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertIsNone(
            result.provider_code
        )

    def test_gemini_success(self):
        result, _ = self.run_with_response(
            gemini_runtime_config(),
            FakeResponse(
                200
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

    def test_kie_success(self):
        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                kie_body(
                    200
                ),
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
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

    def test_kie_malformed_json(self):
        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                b"{not-json",
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .RESPONSE_INVALID,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertIsNone(
            result.provider_code
        )

    def test_kie_missing_code(self):
        body = json.dumps(
            {
                "msg": "success",
                "data": 1,
            }
        ).encode(
            "utf-8"
        )

        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                body,
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .RESPONSE_INVALID,
        )

    def test_kie_invalid_code_shape(self):
        body = json.dumps(
            {
                "code": True,
                "msg": "test",
            }
        ).encode(
            "utf-8"
        )

        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                body,
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .RESPONSE_INVALID,
        )

        self.assertIsNone(
            result.provider_code
        )

    def test_http_401(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    401
                ),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            401,
        )

    def test_http_403(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    403
                ),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .PERMISSION_DENIED,
        )

    def test_http_429(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=http_error(
                    429
                ),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .RATE_LIMITED,
        )

    def test_http_5xx(self):
        for code in (
            500,
            502,
            503,
            599,
        ):
            with self.subTest(
                code=code
            ):
                with patch.object(
                    probe_module,
                    "EnvironmentCredentialSource",
                ) as source_type:
                    config = (
                        openai_runtime_config()
                    )

                    source_type.return_value.resolve.return_value = (
                        self.credential(
                            config
                        )
                    )

                    with patch.object(
                        probe_module,
                        "_open_https",
                        side_effect=http_error(
                            code
                        ),
                    ):
                        result = (
                            self.probe.probe(
                                config,
                                lambda: None,
                            )
                        )

                self.assertIs(
                    result.status,
                    ProviderConnectivityProbeStatus
                    .PROVIDER_UNAVAILABLE,
                )

                self.assertEqual(
                    result.http_status,
                    code,
                )

    def test_other_http_status_response_invalid(self):
        for code in (
            300,
            400,
            404,
            422,
        ):
            with self.subTest(
                code=code
            ):
                with patch.object(
                    probe_module,
                    "EnvironmentCredentialSource",
                ) as source_type:
                    config = (
                        openai_runtime_config()
                    )

                    source_type.return_value.resolve.return_value = (
                        self.credential(
                            config
                        )
                    )

                    with patch.object(
                        probe_module,
                        "_open_https",
                        side_effect=http_error(
                            code
                        ),
                    ):
                        result = (
                            self.probe.probe(
                                config,
                                lambda: None,
                            )
                        )

                self.assertIs(
                    result.status,
                    ProviderConnectivityProbeStatus
                    .RESPONSE_INVALID,
                )

    def test_kie_wrapped_401(self):
        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                kie_body(
                    401
                ),
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
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

    def test_kie_wrapped_403(self):
        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                kie_body(
                    403
                ),
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .PERMISSION_DENIED,
        )

    def test_kie_wrapped_429(self):
        result, _ = self.run_with_response(
            kie_runtime_config(),
            FakeResponse(
                200,
                kie_body(
                    429
                ),
            ),
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .RATE_LIMITED,
        )

    def test_kie_wrapped_5xx(self):
        for code in (
            500,
            503,
            599,
        ):
            with self.subTest(
                code=code
            ):
                result, _ = (
                    self.run_with_response(
                        kie_runtime_config(),
                        FakeResponse(
                            200,
                            kie_body(
                                code
                            ),
                        ),
                    )
                )

                self.assertIs(
                    result.status,
                    ProviderConnectivityProbeStatus
                    .PROVIDER_UNAVAILABLE,
                )

                self.assertEqual(
                    result.provider_code,
                    code,
                )

    def test_kie_wrapped_other_code(self):
        for code in (
            201,
            400,
            402,
            422,
        ):
            with self.subTest(
                code=code
            ):
                result, _ = (
                    self.run_with_response(
                        kie_runtime_config(),
                        FakeResponse(
                            200,
                            kie_body(
                                code
                            ),
                        ),
                    )
                )

                self.assertIs(
                    result.status,
                    ProviderConnectivityProbeStatus
                    .RESPONSE_INVALID,
                )

                self.assertEqual(
                    result.provider_code,
                    code,
                )

    def test_socket_timeout(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=socket.timeout(),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .DEADLINE_EXCEEDED,
        )

    def test_url_timeout_reason(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=(
                    urllib.error.URLError(
                        socket.timeout()
                    )
                ),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .DEADLINE_EXCEEDED,
        )

    def test_url_unavailable(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

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
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .NETWORK_UNAVAILABLE,
        )

    def test_unexpected_network_exception(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=ValueError(
                    "private"
                ),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .INTERNAL_FAILURE,
        )

    def test_network_memory_error(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=MemoryError(),
            ):
                result = self.probe.probe(
                    config,
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .INTERNAL_FAILURE,
        )

    def test_kie_read_is_bounded(self):
        response = FakeResponse(
            200,
            kie_body(
                200
            ),
        )

        result, _ = self.run_with_response(
            kie_runtime_config(),
            response,
        )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            response.read_limits,
            [
                MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES
                + 1
            ],
        )

    def test_response_closed(self):
        providers = (
            (
                openai_runtime_config(),
                FakeResponse(
                    200
                ),
            ),
            (
                gemini_runtime_config(),
                FakeResponse(
                    200
                ),
            ),
            (
                kie_runtime_config(),
                FakeResponse(
                    200,
                    kie_body(
                        200
                    ),
                ),
            ),
        )

        for config, response in providers:
            with self.subTest(
                provider=(
                    config.profile.provider
                )
            ):
                self.run_with_response(
                    config,
                    response,
                )

                self.assertTrue(
                    response.closed
                )

    def test_check_is_used_repeatedly(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        config = openai_runtime_config()

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ):
                result = self.probe.probe(
                    config,
                    check,
                )

        self.assertIs(
            result.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            5,
        )

    def test_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "caller-check"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^caller-check$",
        ):
            self.probe.probe(
                openai_runtime_config(),
                check,
            )

    def test_network_baseexception_not_swallowed(self):
        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            config = openai_runtime_config()

            source_type.return_value.resolve.return_value = (
                self.credential(
                    config
                )
            )

            with patch.object(
                probe_module,
                "_open_https",
                side_effect=KeyboardInterrupt(),
            ):
                with self.assertRaises(
                    KeyboardInterrupt
                ):
                    self.probe.probe(
                        config,
                        lambda: None,
                    )

    def test_secret_never_enters_report(self):
        config = openai_runtime_config()

        secret = (
            "unique-m92-secret-887766"
        )

        credential = FakeCredential(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer "
            + secret,
        )

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                credential
            )

            with patch.object(
                probe_module,
                "_open_https",
                return_value=FakeResponse(
                    200
                ),
            ):
                result = self.probe.probe(
                    config,
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

    def test_all_returned_reports_validate(self):
        reports = []

        reports.append(
            self.run_with_response(
                openai_runtime_config(),
                FakeResponse(
                    200
                ),
            )[
                0
            ]
        )

        reports.append(
            self.run_with_response(
                kie_runtime_config(),
                FakeResponse(
                    200,
                    kie_body(
                        401
                    ),
                ),
            )[
                0
            ]
        )

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                ExternalVisionHTTPCredentialFailure(
                    ExternalVisionHTTPCredentialFailureCode
                    .UNAVAILABLE
                )
            )

            reports.append(
                self.probe.probe(
                    openai_runtime_config(),
                    lambda: None,
                )
            )

        reports.append(
            self.probe.probe(
                object(),
                lambda: None,
            )
        )

        for report in reports:
            self.assertIs(
                validate_provider_connectivity_probe_report(
                    report
                ),
                report,
            )


if __name__ == "__main__":
    unittest.main()