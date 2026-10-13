"""M89 end-to-end provider-specific vision adapter integration.

No real network access is performed.

The tests exercise the complete pipeline:

    source snapshot
        -> M85 semantic runtime
        -> M87 external semantic provider
        -> M89 provider transport
        -> M89 provider serializer
        -> M89 M88-backed exchange
        -> mocked M88 HTTPS execution
        -> provider response wrapper
        -> M89 response extractor
        -> M87 strict semantic parser
        -> M85 semantic observation

Provider credentials used here are test-only values.
"""

import dataclasses
import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.provider_specific_vision_adapter as api
import creator_studio.provider_specific_vision_adapter.provider_http_exchange as exchange_module

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)
from creator_studio.external_vision_provider_transport import (
    ExternalVisionSemanticProvider,
)
from creator_studio.semantic_vision_observer import (
    SemanticVisionFailureCode,
    SemanticVisionObservationRuntime,
    SemanticVisionOutcome,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_http_transport_execution import (
    FakeResponse,
)
from tests.test_png8_structural_preflight import (
    capture,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    kie_profile,
    openai_profile,
)
from tests.test_provider_specific_vision_adapter_response_extractor import (
    gemini_document,
    kie_document,
    openai_document,
)
from tests.test_raster_feature_runtime import (
    rgba_png,
)


REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "runtime-input.png?signature=integration-test"
)


def provider_body(
    document,
):
    return json.dumps(
        document,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )


def http_config(
    profile,
):
    return dataclasses.replace(
        config(),
        endpoint=profile.endpoint,
    )


class CredentialSource(
    ExternalVisionHTTPCredentialSource
):
    def __init__(
        self,
        header,
        value,
    ):
        self.header = header
        self.value = value
        self.calls = 0

    def resolve(
        self,
        check,
    ):
        self.calls += 1

        check()

        return ExternalVisionHTTPCredential(
            self.header,
            self.value,
        )


class RemoteImageSource(
    api.ProviderVisionRemoteImageSource
):
    def __init__(
        self,
        value=REMOTE_IMAGE_URL,
    ):
        self.value = value
        self.calls = 0

    def resolve(
        self,
        request,
        check,
    ):
        self.calls += 1

        check()

        return self.value


class ProviderSpecificVisionAdapterIntegrationTests(
    unittest.TestCase
):

    def setUp(self):
        self.data = rgba_png(
            2,
            2,
            bytes([
                10, 20, 30, 0,
                40, 50, 60, 128,
                70, 80, 90, 255,
                100, 110, 120, 255,
            ]),
        )

        self.source, self.snapshot = capture(
            self.data
        )

    def tearDown(self):
        try:
            self.source.release(
                self.snapshot
            )

        except Exception:
            pass

    def runtime(
        self,
        profile,
        credential_source,
        remote_image_source=None,
    ):
        exchange = (
            api.M88ProviderVisionHTTPExchange(
                http_config(
                    profile
                ),
                credential_source,
            )
        )

        transport = (
            api.ProviderSpecificVisionTransport(
                profile,
                exchange,
                remote_image_source,
            )
        )

        provider = ExternalVisionSemanticProvider(
            transport
        )

        runtime = SemanticVisionObservationRuntime(
            provider
        )

        return (
            runtime,
            transport,
            exchange,
        )

    def test_openai_end_to_end_success(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer openai-test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    openai_document()
                )
            ),
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            result.observation.scene_setting.value,
            "INDOOR",
        )

        self.assertEqual(
            result.observation.shot_scale.value,
            "MEDIUM",
        )

        self.assertEqual(
            result.observation.visual_mood.value,
            "CALM",
        )

        self.assertEqual(
            result.observation.confidence_milli,
            900,
        )

        self.assertEqual(
            credential.calls,
            1,
        )

    def test_gemini_end_to_end_success(self):
        profile = gemini_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
            "gemini-test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    gemini_document()
                )
            ),
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            result.observation.confidence_milli,
            900,
        )

        self.assertEqual(
            credential.calls,
            1,
        )

    def test_kie_end_to_end_success(self):
        profile = kie_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer kie-test-secret",
        )

        remote_source = RemoteImageSource()

        runtime, _, _ = self.runtime(
            profile,
            credential,
            remote_source,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    kie_document()
                )
            ),
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            result.observation.confidence_milli,
            900,
        )

        self.assertEqual(
            credential.calls,
            1,
        )

        self.assertEqual(
            remote_source.calls,
            1,
        )

    def test_openai_wire_request_contains_inline_png_and_bearer(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer openai-wire-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    openai_document()
                )
            ),
        ) as opened:
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = opened.call_args.args[
            0
        ]

        self.assertEqual(
            request_value.full_url,
            profile.endpoint,
        )

        self.assertEqual(
            request_value.get_method(),
            "POST",
        )

        headers = {
            name.lower(): value
            for name, value
            in request_value.header_items()
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer openai-wire-secret",
        )

        document = json.loads(
            request_value.data.decode(
                "utf-8"
            )
        )

        image_url = document[
            "input"
        ][
            0
        ][
            "content"
        ][
            1
        ][
            "image_url"
        ]

        self.assertTrue(
            image_url.startswith(
                "data:image/png;base64,"
            )
        )

        self.assertNotIn(
            b"openai-wire-secret",
            request_value.data,
        )

    def test_gemini_wire_request_contains_inline_png_and_api_key(self):
        profile = gemini_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
            "gemini-wire-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    gemini_document()
                )
            ),
        ) as opened:
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in request_value.header_items()
        }

        self.assertEqual(
            headers[
                "x-goog-api-key"
            ],
            "gemini-wire-secret",
        )

        document = json.loads(
            request_value.data.decode(
                "utf-8"
            )
        )

        image = document[
            "input"
        ][
            1
        ]

        self.assertEqual(
            image[
                "type"
            ],
            "image",
        )

        self.assertEqual(
            image[
                "mime_type"
            ],
            "image/png",
        )

        self.assertNotIn(
            b"gemini-wire-secret",
            request_value.data,
        )

    def test_kie_wire_request_uses_runtime_remote_url(self):
        profile = kie_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer kie-wire-secret",
        )

        remote_source = RemoteImageSource()

        runtime, _, _ = self.runtime(
            profile,
            credential,
            remote_source,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    kie_document()
                )
            ),
        ) as opened:
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = opened.call_args.args[
            0
        ]

        document = json.loads(
            request_value.data.decode(
                "utf-8"
            )
        )

        image_url = document[
            "messages"
        ][
            0
        ][
            "content"
        ][
            1
        ][
            "image_url"
        ][
            "url"
        ]

        self.assertEqual(
            image_url,
            REMOTE_IMAGE_URL,
        )

        self.assertNotIn(
            b"kie-wire-secret",
            request_value.data,
        )

    def test_invalid_provider_wrapper_maps_response_invalid(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    {
                        "status": "completed",
                        "output": [],
                    }
                )
            ),
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.FAILURE,
        )

        self.assertIs(
            result.failure_code,
            SemanticVisionFailureCode
            .RESPONSE_INVALID,
        )

    def test_http_unavailable_maps_adapter_unavailable(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        error = urllib.error.HTTPError(
            profile.endpoint,
            503,
            "unavailable",
            {},
            None,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=error,
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.FAILURE,
        )

        self.assertIs(
            result.failure_code,
            SemanticVisionFailureCode
            .ADAPTER_UNAVAILABLE,
        )

    def test_http_timeout_maps_deadline(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        error = urllib.error.URLError(
            socket.timeout(
                "timeout"
            )
        )

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=error,
        ):
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.FAILURE,
        )

        self.assertIs(
            result.failure_code,
            SemanticVisionFailureCode
            .DEADLINE_EXCEEDED,
        )

    def test_runtime_secret_never_enters_provider_json(self):
        profile = openai_profile()

        secret = (
            "Bearer uniquely-identifiable-"
            "integration-secret-998877"
        )

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            secret,
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            return_value=FakeResponse(
                body=provider_body(
                    openai_document()
                )
            ),
        ) as opened:
            result = runtime.observe(
                self.source,
                self.snapshot,
            )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = opened.call_args.args[
            0
        ]

        self.assertNotIn(
            secret.encode(
                "ascii"
            ),
            request_value.data,
        )

    def test_baseexception_from_network_is_not_swallowed(self):
        profile = openai_profile()

        credential = CredentialSource(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-secret",
        )

        runtime, _, _ = self.runtime(
            profile,
            credential,
        )

        with patch.object(
            exchange_module,
            "_open_https",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                runtime.observe(
                    self.source,
                    self.snapshot,
                )


if __name__ == "__main__":
    unittest.main()