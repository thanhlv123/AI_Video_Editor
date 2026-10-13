"""M88 end-to-end external vision HTTPS transport integration.

No real network access is performed. The HTTPS execution boundary is replaced
with deterministic test responses.
"""

import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

import creator_studio.external_vision_http_transport as http_api
import creator_studio.external_vision_http_transport.http_transport as http_module

from creator_studio.external_vision_provider_transport import (
    ExternalVisionSemanticProvider,
    ExternalVisionTransport,
)
from creator_studio.semantic_vision_observer import (
    SemanticVisionFailureCode,
    SemanticVisionObservationRuntime,
    SemanticVisionOutcome,
)
from tests.test_external_vision_http_transport_execution import (
    FakeResponse,
)
from tests.test_png8_structural_preflight import (
    capture,
)
from tests.test_raster_feature_runtime import (
    rgba_png,
)


def semantic_document():
    return {
        "schema_version": 1,
        "scene_setting": "INDOOR",
        "shot_scale": "MEDIUM",
        "visual_mood": "CALM",
        "subjects": [
            {
                "label": "person",
                "confidence_milli": 950,
            },
            {
                "label": "wooden table",
                "confidence_milli": 700,
            },
        ],
        "activities": [
            {
                "label": "cooking",
                "confidence_milli": 900,
            },
        ],
        "scene_tags": [
            {
                "label": "rural kitchen",
                "confidence_milli": 850,
            },
        ],
        "confidence_milli": 900,
    }


def semantic_body():
    return json.dumps(
        semantic_document(),
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )


def http_config():
    return http_api.ExternalVisionHTTPConfig(
        schema_version=(
            http_api.EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION
        ),
        endpoint=(
            "https://vision.example.test/v1/analyze"
        ),
        timeout_millis=10_000,
        max_request_bytes=(
            http_api.MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
        ),
        max_response_bytes=(
            http_api.MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
        ),
        header_policy=(
            http_api.ExternalVisionHTTPHeaderPolicy
            .STRICT_JSON_V1
        ),
    )


class CredentialSource(
    http_api.ExternalVisionHTTPCredentialSource
):
    def __init__(self):
        self.calls = 0

    def resolve(
        self,
        check,
    ):
        self.calls += 1

        check()

        return http_api.ExternalVisionHTTPCredential(
            http_api.ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer integration-test-secret",
        )


class ExternalVisionHTTPTransportIntegrationTests(
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
        credential_source=None,
    ):
        transport = (
            http_api.ExternalVisionHTTPSJSONTransport(
                http_config(),
                credential_source,
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
        )

    def test_public_transport_implements_m87_contract(self):
        _, transport = self.runtime()

        self.assertIsInstance(
            transport,
            ExternalVisionTransport,
        )

    def test_end_to_end_success_without_credential(self):
        runtime, _ = self.runtime()

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=semantic_body()
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
            result.descriptor,
            self.snapshot.descriptor,
        )

        self.assertEqual(
            result.observation.subjects[0].label,
            "person",
        )

        self.assertEqual(
            result.observation.activities[0].label,
            "cooking",
        )

        self.assertEqual(
            result.observation.scene_tags[0].label,
            "rural kitchen",
        )

        self.assertEqual(
            result.observation.confidence_milli,
            900,
        )

    def test_end_to_end_success_with_runtime_credential(self):
        source = CredentialSource()

        runtime, _ = self.runtime(
            source
        )

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=semantic_body()
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
            source.calls,
            1,
        )

    def test_https_request_contains_bounded_json_payload(self):
        runtime, _ = self.runtime()

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=semantic_body()
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

        http_request = opened.call_args.args[
            0
        ]

        self.assertEqual(
            http_request.full_url,
            http_config().endpoint,
        )

        self.assertEqual(
            http_request.get_method(),
            "POST",
        )

        document = json.loads(
            http_request.data.decode(
                "utf-8"
            )
        )

        self.assertEqual(
            document[
                "instruction"
            ],
            "STRUCTURED_SEMANTIC_VISION_V1",
        )

        self.assertEqual(
            document[
                "payload"
            ][
                "width"
            ],
            2,
        )

        self.assertEqual(
            document[
                "payload"
            ][
                "height"
            ],
            2,
        )

        self.assertIn(
            "image_base64",
            document[
                "payload"
            ],
        )

    def test_runtime_secret_is_header_only(self):
        source = CredentialSource()

        runtime, _ = self.runtime(
            source
        )

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=semantic_body()
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

        http_request = opened.call_args.args[
            0
        ]

        headers = {
            name.lower(): value
            for name, value
            in http_request.header_items()
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer integration-test-secret",
        )

        self.assertNotIn(
            b"integration-test-secret",
            http_request.data,
        )

    def test_invalid_provider_json_maps_response_invalid(self):
        runtime, _ = self.runtime()

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=b'{"schema_version":1'
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
        runtime, _ = self.runtime()

        error = urllib.error.HTTPError(
            http_config().endpoint,
            503,
            "unavailable",
            {},
            None,
        )

        with patch.object(
            http_module,
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
        runtime, _ = self.runtime()

        error = urllib.error.URLError(
            socket.timeout(
                "timeout"
            )
        )

        with patch.object(
            http_module,
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

    def test_oversized_http_response_maps_resource_limit(self):
        runtime, _ = self.runtime()

        body = bytes(
            http_api.MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
            + 1
        )

        with patch.object(
            http_module,
            "_open_https",
            return_value=FakeResponse(
                body=body
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
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_baseexception_from_execution_is_not_swallowed(self):
        runtime, _ = self.runtime()

        with patch.object(
            http_module,
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