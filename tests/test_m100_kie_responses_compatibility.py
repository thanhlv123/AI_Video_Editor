"""M100 Kie.ai Responses compatibility for M89/M90."""

import dataclasses
import json
import unittest

import creator_studio.provider_runtime_assembly.provider_presets as presets
import creator_studio.provider_specific_vision_adapter as api

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialHeader,
)
from creator_studio.provider_runtime_assembly import (
    ProviderEnvironmentCredentialMode,
    validate_provider_runtime_config,
)
from creator_studio.provider_specific_vision_adapter.request_serializer import (
    SEMANTIC_VISION_PROVIDER_PROMPT,
    _ProviderRequestSerializeFailure,
    _ProviderRequestSerializeFailureCode,
    _serialize_provider_request,
)
from creator_studio.provider_specific_vision_adapter.response_extractor import (
    _ProviderResponseExtractFailure,
    _ProviderResponseExtractFailureCode,
    _extract_provider_response,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_provider_transport_models import (
    request,
)
from tests.test_provider_specific_vision_adapter_response_extractor import (
    SEMANTIC_TEXT,
    raw_response,
)


KIE_RESPONSES_ENDPOINT = (
    "https://api.kie.ai"
    "/openai/v1/responses"
)

REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "vision/input.png?signature=test"
)


def kie_responses_profile():
    return api.ProviderVisionProfile(
        schema_version=(
            api.PROVIDER_VISION_PROFILE_SCHEMA_VERSION
        ),
        provider=(
            api.VisionProviderKind.KIE_AI
        ),
        endpoint=KIE_RESPONSES_ENDPOINT,
        model="gpt-6-luna",
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        request_dialect=(
            api.VisionProviderRequestDialect
            .KIE_OPENAI_RESPONSES_V1
        ),
        response_dialect=(
            api.VisionProviderResponseDialect
            .KIE_RESPONSES_OUTPUT_TEXT_V1
        ),
        image_input_mode=(
            api.VisionProviderImageInputMode
            .REMOTE_URL
        ),
    )


def kie_responses_document(
    text=SEMANTIC_TEXT,
):
    return {
        "output": [
            {
                "type": "reasoning",
                "id": "reasoning_test",
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
            },
        ],
    }


class M100KieResponsesCompatibilityTests(
    unittest.TestCase
):

    def test_kie_responses_profile_valid(self):
        value = kie_responses_profile()

        self.assertIs(
            api.validate_provider_vision_profile(
                value
            ),
            value,
        )

    def test_kie_responses_profile_rejects_mixed_dialects(self):
        value = dataclasses.replace(
            kie_responses_profile(),
            request_dialect=(
                api.VisionProviderRequestDialect
                .KIE_OPENAI_CHAT_COMPLETIONS_V1
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_kie_responses_profile_rejects_lookalike_path(self):
        value = dataclasses.replace(
            kie_responses_profile(),
            endpoint=(
                "https://api.kie.ai"
                "/other/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_kie_responses_serializer_matches_production_shape(self):
        body = _serialize_provider_request(
            request(),
            kie_responses_profile(),
            lambda: None,
            remote_image_url=(
                REMOTE_IMAGE_URL
            ),
        )

        document = json.loads(
            body.decode(
                "utf-8"
            )
        )

        self.assertEqual(
            document[
                "model"
            ],
            "gpt-6-luna",
        )

        self.assertFalse(
            document[
                "stream"
            ]
        )

        content = document[
            "input"
        ][
            0
        ][
            "content"
        ]

        self.assertEqual(
            content[
                0
            ],
            {
                "type": "input_text",
                "text": (
                    SEMANTIC_VISION_PROVIDER_PROMPT
                ),
            },
        )

        self.assertEqual(
            content[
                1
            ],
            {
                "type": "input_image",
                "image_url": (
                    REMOTE_IMAGE_URL
                ),
            },
        )

        self.assertNotIn(
            "data:image/png;base64",
            body.decode(
                "utf-8"
            ),
        )

    def test_kie_responses_serializer_requires_remote_image(self):
        with self.assertRaises(
            _ProviderRequestSerializeFailure
        ) as caught:
            _serialize_provider_request(
                request(),
                kie_responses_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_REQUIRED,
        )

    def test_kie_responses_extractor_accepts_production_shape(self):
        result = _extract_provider_response(
            raw_response(
                kie_responses_document()
            ),
            kie_responses_profile(),
            lambda: None,
        )

        self.assertEqual(
            result.body,
            SEMANTIC_TEXT.encode(
                "utf-8"
            ),
        )

    def test_kie_responses_extractor_rejects_api_error(self):
        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                raw_response(
                    {
                        "code": 500,
                        "msg": "provider error",
                    }
                ),
                kie_responses_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
        )

    def test_kie_responses_extractor_rejects_incomplete_status(self):
        document = kie_responses_document()

        document[
            "status"
        ] = "incomplete"

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                raw_response(
                    document
                ),
                kie_responses_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
        )

    def test_kie_runtime_preset_selects_responses_dialects(self):
        result = (
            presets.build_kie_runtime_config(
                "gpt-6-luna",
                KIE_RESPONSES_ENDPOINT,
                config(),
            )
        )

        self.assertIs(
            validate_provider_runtime_config(
                result
            ),
            result,
        )

        self.assertIs(
            result.profile.request_dialect,
            api.VisionProviderRequestDialect
            .KIE_OPENAI_RESPONSES_V1,
        )

        self.assertIs(
            result.profile.response_dialect,
            api.VisionProviderResponseDialect
            .KIE_RESPONSES_OUTPUT_TEXT_V1,
        )

        self.assertIs(
            result.profile.image_input_mode,
            api.VisionProviderImageInputMode
            .REMOTE_URL,
        )

        self.assertIs(
            result.credential_mode,
            ProviderEnvironmentCredentialMode
            .BEARER,
        )

    def test_kie_runtime_preset_preserves_chat_completions(self):
        endpoint = (
            "https://api.kie.ai/"
            "gemini-3-flash/v1/chat/completions"
        )

        result = (
            presets.build_kie_runtime_config(
                "gemini-model",
                endpoint,
                config(),
            )
        )

        self.assertIs(
            result.profile.request_dialect,
            api.VisionProviderRequestDialect
            .KIE_OPENAI_CHAT_COMPLETIONS_V1,
        )

        self.assertIs(
            result.profile.response_dialect,
            api.VisionProviderResponseDialect
            .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1,
        )


if __name__ == "__main__":
    unittest.main()
