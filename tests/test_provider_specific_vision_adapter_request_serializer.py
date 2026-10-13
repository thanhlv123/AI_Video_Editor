"""M89 deterministic provider-specific vision request serializer."""

import base64
import dataclasses
import json
import unittest
from unittest.mock import patch

import creator_studio.provider_specific_vision_adapter.request_serializer as serializer_module

from creator_studio.provider_specific_vision_adapter.request_serializer import (
    MAX_PROVIDER_VISION_REQUEST_BYTES,
    SEMANTIC_VISION_PROVIDER_PROMPT,
    _ProviderRequestSerializeFailure,
    _ProviderRequestSerializeFailureCode,
    _serialize_provider_request,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    kie_profile,
    openai_profile,
)
from tests.test_external_vision_provider_transport_models import (
    request,
)


REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "vision/input.png?signature=test"
)


class ProviderSpecificVisionAdapterRequestSerializerTests(
    unittest.TestCase
):

    def serialize(
        self,
        profile_value,
        request_value=None,
        remote_image_url=None,
        check=None,
    ):
        if request_value is None:
            request_value = request()

        if check is None:
            check = lambda: None

        return _serialize_provider_request(
            request_value,
            profile_value,
            check,
            remote_image_url=(
                remote_image_url
            ),
        )

    def failure(
        self,
        expected,
        profile_value,
        request_value=None,
        remote_image_url=None,
    ):
        with self.assertRaises(
            _ProviderRequestSerializeFailure
        ) as caught:
            self.serialize(
                profile_value,
                request_value=request_value,
                remote_image_url=(
                    remote_image_url
                ),
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_openai_success(self):
        body = self.serialize(
            openai_profile()
        )

        self.assertIs(
            type(body),
            bytes,
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
            openai_profile().model,
        )

    def test_gemini_success(self):
        body = self.serialize(
            gemini_profile()
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
            gemini_profile().model,
        )

        self.assertFalse(
            document[
                "stream"
            ]
        )

    def test_kie_success_with_remote_url(self):
        body = self.serialize(
            kie_profile(),
            remote_image_url=(
                REMOTE_IMAGE_URL
            ),
        )

        document = json.loads(
            body.decode(
                "utf-8"
            )
        )

        self.assertFalse(
            document[
                "stream"
            ]
        )

        media = document[
            "messages"
        ][
            0
        ][
            "content"
        ][
            1
        ]

        self.assertEqual(
            media[
                "type"
            ],
            "image_url",
        )

        self.assertEqual(
            media[
                "image_url"
            ][
                "url"
            ],
            REMOTE_IMAGE_URL,
        )

    def test_openai_is_deterministic(self):
        value = request()
        profile = openai_profile()

        first = self.serialize(
            profile,
            request_value=value,
        )

        second = self.serialize(
            profile,
            request_value=value,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_gemini_is_deterministic(self):
        value = request()
        profile = gemini_profile()

        first = self.serialize(
            profile,
            request_value=value,
        )

        second = self.serialize(
            profile,
            request_value=value,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_openai_image_roundtrip(self):
        value = request()

        document = json.loads(
            self.serialize(
                openai_profile(),
                request_value=value,
            ).decode(
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

        prefix = (
            "data:image/png;base64,"
        )

        self.assertTrue(
            image_url.startswith(
                prefix
            )
        )

        recovered = base64.b64decode(
            image_url[
                len(prefix):
            ],
            validate=True,
        )

        self.assertEqual(
            recovered,
            value.payload.image_bytes,
        )

    def test_openai_structured_output_contract(self):
        document = json.loads(
            self.serialize(
                openai_profile()
            ).decode(
                "utf-8"
            )
        )

        format_value = document[
            "text"
        ][
            "format"
        ]

        self.assertEqual(
            format_value[
                "type"
            ],
            "json_schema",
        )

        self.assertTrue(
            format_value[
                "strict"
            ]
        )

        schema = format_value[
            "schema"
        ]

        self.assertFalse(
            schema[
                "additionalProperties"
            ]
        )

        self.assertEqual(
            set(
                schema[
                    "required"
                ]
            ),
            {
                "schema_version",
                "scene_setting",
                "shot_scale",
                "visual_mood",
                "subjects",
                "activities",
                "scene_tags",
                "confidence_milli",
            },
        )

    def test_gemini_inline_image_roundtrip(self):
        value = request()

        document = json.loads(
            self.serialize(
                gemini_profile(),
                request_value=value,
            ).decode(
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

        recovered = base64.b64decode(
            image[
                "data"
            ],
            validate=True,
        )

        self.assertEqual(
            recovered,
            value.payload.image_bytes,
        )

    def test_gemini_response_format_contract(self):
        document = json.loads(
            self.serialize(
                gemini_profile()
            ).decode(
                "utf-8"
            )
        )

        response_format = document[
            "response_format"
        ]

        self.assertEqual(
            response_format[
                "type"
            ],
            "text",
        )

        self.assertEqual(
            response_format[
                "mime_type"
            ],
            "application/json",
        )

        self.assertFalse(
            response_format[
                "schema"
            ][
                "additionalProperties"
            ]
        )

    def test_provider_prompt_is_present(self):
        openai_document = json.loads(
            self.serialize(
                openai_profile()
            ).decode(
                "utf-8"
            )
        )

        gemini_document = json.loads(
            self.serialize(
                gemini_profile()
            ).decode(
                "utf-8"
            )
        )

        self.assertEqual(
            openai_document[
                "input"
            ][
                0
            ][
                "content"
            ][
                0
            ][
                "text"
            ],
            SEMANTIC_VISION_PROVIDER_PROMPT,
        )

        self.assertEqual(
            gemini_document[
                "input"
            ][
                0
            ][
                "text"
            ],
            SEMANTIC_VISION_PROVIDER_PROMPT,
        )

    def test_kie_requires_remote_image(self):
        self.failure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_REQUIRED,
            kie_profile(),
        )

    def test_kie_rejects_invalid_remote_image_url(self):
        variants = [
            "",
            "http://media.example.test/input.png",
            " https://media.example.test/input.png",
            "https://user:secret@media.example.test/input.png",
            "https://media.example.test/input.png#fragment",
            123,
        ]

        for value in variants:
            with self.subTest(
                value=value
            ):
                self.failure(
                    _ProviderRequestSerializeFailureCode
                    .REMOTE_IMAGE_INVALID,
                    kie_profile(),
                    remote_image_url=value,
                )

    def test_non_kie_rejects_remote_image_argument(self):
        for profile in (
            openai_profile(),
            gemini_profile(),
        ):
            with self.subTest(
                provider=profile.provider
            ):
                self.failure(
                    _ProviderRequestSerializeFailureCode
                    .PROFILE_COHERENCE_INVALID,
                    profile,
                    remote_image_url=(
                        REMOTE_IMAGE_URL
                    ),
                )

    def test_invalid_request_mapping(self):
        invalid = dataclasses.replace(
            request(),
            response_schema_version=2,
        )

        self.failure(
            _ProviderRequestSerializeFailureCode
            .REQUEST_INVALID,
            openai_profile(),
            request_value=invalid,
        )

    def test_invalid_profile_mapping(self):
        invalid = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://example.test/v1/responses"
            ),
        )

        self.failure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_INVALID,
            invalid,
        )

    def test_request_body_limit_mapping(self):
        with patch.object(
            serializer_module,
            "MAX_PROVIDER_VISION_REQUEST_BYTES",
            1,
        ):
            with self.assertRaises(
                _ProviderRequestSerializeFailure
            ) as caught:
                self.serialize(
                    openai_profile()
                )

        self.assertIs(
            caught.exception.code,
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_json_failure_mapping(self):
        with patch.object(
            serializer_module.json,
            "dumps",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _ProviderRequestSerializeFailure
            ) as caught:
                self.serialize(
                    openai_profile()
                )

        self.assertIs(
            caught.exception.code,
            _ProviderRequestSerializeFailureCode
            .SERIALIZATION_INVALID,
        )

    def test_json_memory_error_mapping(self):
        with patch.object(
            serializer_module.json,
            "dumps",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _ProviderRequestSerializeFailure
            ) as caught:
                self.serialize(
                    openai_profile()
                )

        self.assertIs(
            caught.exception.code,
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_check_is_used_repeatedly(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        body = self.serialize(
            openai_profile(),
            check=check,
        )

        self.assertIs(
            type(body),
            bytes,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            5,
        )

    def test_unexpected_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            self.serialize(
                openai_profile(),
                check=check,
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.serialize(
                openai_profile(),
                check=check,
            )

    def test_failure_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_request_serialize_failure_invalid$",
        ):
            _ProviderRequestSerializeFailure(
                "REQUEST_INVALID"
            )


if __name__ == "__main__":
    unittest.main()