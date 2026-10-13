"""M87 end-to-end transport-neutral semantic vision integration."""

import ast
import json
from pathlib import Path
import unittest

import creator_studio.external_vision_provider_transport as api

from creator_studio.semantic_vision_observer import (
    SemanticVisionFailureCode,
    SemanticVisionObservationRuntime,
    SemanticVisionOutcome,
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


def response_from_document(value):
    body = json.dumps(
        value,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return api.ExternalVisionTransportResponse(
        schema_version=(
            api.EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            api.ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=len(
            body
        ),
        body=body,
    )


class ValidTransport(
    api.ExternalVisionTransport
):
    def __init__(self):
        self.requests = []

    def send(
        self,
        request,
        check,
    ):
        self.requests.append(
            request
        )

        check()

        return response_from_document(
            semantic_document()
        )


class RawBodyTransport(
    api.ExternalVisionTransport
):
    def __init__(self, body):
        self.body = body

    def send(
        self,
        request,
        check,
    ):
        check()

        return api.ExternalVisionTransportResponse(
            schema_version=(
                api.EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
            ),
            encoding=(
                api.ExternalVisionTransportResponseEncoding
                .UTF8_TEXT
            ),
            body_length=len(
                self.body
            ),
            body=self.body,
        )


class FailureTransport(
    api.ExternalVisionTransport
):
    def __init__(self, code):
        self.code = code

    def send(
        self,
        request,
        check,
    ):
        raise api.ExternalVisionTransportFailure(
            self.code
        )


class ExternalVisionProviderTransportIntegrationTests(
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

    def runtime_for_transport(
        self,
        transport,
    ):
        provider = (
            api.ExternalVisionSemanticProvider(
                transport
            )
        )

        return SemanticVisionObservationRuntime(
            provider
        )

    def test_success_end_to_end(self):
        transport = ValidTransport()

        runtime = self.runtime_for_transport(
            transport
        )

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

    def test_transport_receives_bounded_png_request(self):
        transport = ValidTransport()

        runtime = self.runtime_for_transport(
            transport
        )

        result = runtime.observe(
            self.source,
            self.snapshot,
        )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            len(transport.requests),
            1,
        )

        request = transport.requests[0]

        self.assertIs(
            type(request),
            api.ExternalVisionTransportRequest,
        )

        self.assertIs(
            request.instruction,
            api.ExternalVisionTransportInstruction
            .STRUCTURED_SEMANTIC_VISION_V1,
        )

        self.assertEqual(
            request.payload.width,
            2,
        )

        self.assertEqual(
            request.payload.height,
            2,
        )

        self.assertTrue(
            request.payload.image_bytes.startswith(
                b"\x89PNG\r\n\x1a\n"
            )
        )

        self.assertEqual(
            request.payload.byte_length,
            len(
                request.payload.image_bytes
            ),
        )

    def test_semantic_response_is_normalized(self):
        transport = ValidTransport()

        runtime = self.runtime_for_transport(
            transport
        )

        result = runtime.observe(
            self.source,
            self.snapshot,
        )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        observation = result.observation

        self.assertEqual(
            observation.schema_version,
            1,
        )

        self.assertEqual(
            observation.scene_setting.value,
            "INDOOR",
        )

        self.assertEqual(
            observation.shot_scale.value,
            "MEDIUM",
        )

        self.assertEqual(
            observation.visual_mood.value,
            "CALM",
        )

    def test_unavailable_transport_mapping(self):
        runtime = self.runtime_for_transport(
            FailureTransport(
                api.ExternalVisionTransportFailureCode
                .UNAVAILABLE
            )
        )

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

    def test_invalid_json_mapping(self):
        runtime = self.runtime_for_transport(
            RawBodyTransport(
                b'{"schema_version":1'
            )
        )

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

    def test_invalid_semantic_response_mapping(self):
        body = json.dumps(
            {
                "schema_version": 1,
                "scene_setting": "SPACE",
                "shot_scale": "MEDIUM",
                "visual_mood": "CALM",
                "subjects": [],
                "activities": [],
                "scene_tags": [],
                "confidence_milli": 900,
            },
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        runtime = self.runtime_for_transport(
            RawBodyTransport(
                body
            )
        )

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

    def test_deadline_transport_mapping(self):
        runtime = self.runtime_for_transport(
            FailureTransport(
                api.ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED
            )
        )

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

    def test_resource_limit_transport_mapping(self):
        runtime = self.runtime_for_transport(
            FailureTransport(
                api.ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )
        )

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

    def test_m87_has_no_network_implementation(self):
        package = Path(
            api.__file__
        ).parent

        forbidden_imports = {
            "requests",
            "httpx",
            "aiohttp",
            "urllib",
            "socket",
            "openai",
            "anthropic",
            "google",
            "subprocess",
        }

        for path in package.glob(
            "*.py"
        ):
            tree = ast.parse(
                path.read_text(
                    encoding="utf-8"
                )
            )

            for node in ast.walk(
                tree
            ):
                if isinstance(
                    node,
                    ast.Import,
                ):
                    self.assertFalse(
                        any(
                            alias.name.split(".")[0]
                            in forbidden_imports
                            for alias in node.names
                        )
                    )

                if isinstance(
                    node,
                    ast.ImportFrom,
                ):
                    self.assertFalse(
                        any(
                            part
                            in forbidden_imports
                            for part in (
                                node.module or ""
                            ).split(".")
                        )
                    )


if __name__ == "__main__":
    unittest.main()