"""M89 strict provider-specific vision response extractor."""

import dataclasses
import json
import unittest
from unittest.mock import patch

import creator_studio.provider_specific_vision_adapter.response_extractor as extractor_module

from creator_studio.external_vision_provider_transport import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
)
from creator_studio.provider_specific_vision_adapter.response_extractor import (
    _ProviderResponseExtractFailure,
    _ProviderResponseExtractFailureCode,
    _extract_provider_response,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    kie_profile,
    openai_profile,
)


SEMANTIC_TEXT = (
    '{"schema_version":1,'
    '"scene_setting":"INDOOR",'
    '"shot_scale":"MEDIUM",'
    '"visual_mood":"CALM",'
    '"subjects":[],'
    '"activities":[],'
    '"scene_tags":[],'
    '"confidence_milli":900}'
)


def raw_response(
    document,
):
    body = json.dumps(
        document,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return ExternalVisionTransportResponse(
        schema_version=(
            EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=len(
            body
        ),
        body=body,
    )


def raw_body_response(
    body,
):
    return ExternalVisionTransportResponse(
        schema_version=(
            EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION
        ),
        encoding=(
            ExternalVisionTransportResponseEncoding
            .UTF8_TEXT
        ),
        body_length=len(
            body
        ),
        body=body,
    )


def openai_document(
    text=SEMANTIC_TEXT,
):
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
            }
        ],
    }


def gemini_document(
    text=SEMANTIC_TEXT,
):
    return {
        "id": "interaction_test",
        "object": "interaction",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        ],
    }


def kie_document(
    text=SEMANTIC_TEXT,
):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
    }


class ProviderSpecificVisionAdapterResponseExtractorTests(
    unittest.TestCase
):

    def extract(
        self,
        document,
        profile,
        check=None,
    ):
        if check is None:
            check = lambda: None

        return _extract_provider_response(
            raw_response(
                document
            ),
            profile,
            check,
        )

    def failure(
        self,
        expected,
        document,
        profile,
    ):
        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            self.extract(
                document,
                profile,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_openai_success(self):
        result = self.extract(
            openai_document(),
            openai_profile(),
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertEqual(
            result.body,
            SEMANTIC_TEXT.encode(
                "utf-8"
            ),
        )

    def test_openai_concatenates_output_text(self):
        document = openai_document()

        document[
            "output"
        ][
            0
        ][
            "content"
        ] = [
            {
                "type": "output_text",
                "text": '{"schema_',
            },
            {
                "type": "output_text",
                "text": 'version":1}',
            },
        ]

        result = self.extract(
            document,
            openai_profile(),
        )

        self.assertEqual(
            result.body,
            b'{"schema_version":1}',
        )

    def test_openai_requires_completed_status(self):
        document = openai_document()

        document[
            "status"
        ] = "incomplete"

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            openai_profile(),
        )

    def test_openai_refusal_rejected(self):
        document = openai_document()

        document[
            "output"
        ][
            0
        ][
            "content"
        ] = [
            {
                "type": "refusal",
                "refusal": "No",
            }
        ]

        self.failure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID,
            document,
            openai_profile(),
        )

    def test_openai_requires_output_text(self):
        document = openai_document()

        document[
            "output"
        ] = [
            {
                "type": "reasoning",
                "id": "reasoning_test",
            }
        ]

        self.failure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID,
            document,
            openai_profile(),
        )

    def test_gemini_success(self):
        result = self.extract(
            gemini_document(),
            gemini_profile(),
        )

        self.assertEqual(
            result.body,
            SEMANTIC_TEXT.encode(
                "utf-8"
            ),
        )

    def test_gemini_concatenates_text_blocks(self):
        document = gemini_document()

        document[
            "steps"
        ][
            0
        ][
            "content"
        ] = [
            {
                "type": "text",
                "text": '{"schema_',
            },
            {
                "type": "text",
                "text": 'version":1}',
            },
        ]

        result = self.extract(
            document,
            gemini_profile(),
        )

        self.assertEqual(
            result.body,
            b'{"schema_version":1}',
        )

    def test_gemini_requires_completed_status(self):
        document = gemini_document()

        document[
            "status"
        ] = "incomplete"

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            gemini_profile(),
        )

    def test_gemini_rejects_unexpected_step(self):
        document = gemini_document()

        document[
            "steps"
        ] = [
            {
                "type": "function_call",
                "name": "unexpected",
            }
        ]

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            gemini_profile(),
        )

    def test_gemini_rejects_non_text_content(self):
        document = gemini_document()

        document[
            "steps"
        ][
            0
        ][
            "content"
        ] = [
            {
                "type": "image",
                "data": "abc",
            }
        ]

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            gemini_profile(),
        )

    def test_kie_success(self):
        result = self.extract(
            kie_document(),
            kie_profile(),
        )

        self.assertEqual(
            result.body,
            SEMANTIC_TEXT.encode(
                "utf-8"
            ),
        )

    def test_kie_http_200_error_body_rejected(self):
        document = {
            "code": 500,
            "msg": "provider error",
        }

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            kie_profile(),
        )

    def test_kie_requires_single_choice(self):
        document = kie_document()

        document[
            "choices"
        ].append(
            document[
                "choices"
            ][
                0
            ].copy()
        )

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            kie_profile(),
        )

    def test_kie_requires_stop_finish_reason(self):
        document = kie_document()

        document[
            "choices"
        ][
            0
        ][
            "finish_reason"
        ] = "length"

        self.failure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID,
            document,
            kie_profile(),
        )

    def test_kie_requires_string_content(self):
        document = kie_document()

        document[
            "choices"
        ][
            0
        ][
            "message"
        ][
            "content"
        ] = {
            "value": SEMANTIC_TEXT,
        }

        self.failure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID,
            document,
            kie_profile(),
        )

    def test_invalid_transport_response_mapping(self):
        response = raw_response(
            openai_document()
        )

        invalid = dataclasses.replace(
            response,
            body_length=1,
        )

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                invalid,
                openai_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .TRANSPORT_RESPONSE_INVALID,
        )

    def test_invalid_profile_mapping(self):
        invalid = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://example.test/v1/responses"
            ),
        )

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                raw_response(
                    openai_document()
                ),
                invalid,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .PROFILE_INVALID,
        )

    def test_malformed_json_mapping(self):
        response = raw_body_response(
            b'{"status":"completed"'
        )

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                response,
                openai_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .JSON_INVALID,
        )

    def test_duplicate_json_key_rejected(self):
        body = (
            b'{'
            b'"status":"completed",'
            b'"status":"completed",'
            b'"output":[]'
            b'}'
        )

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                raw_body_response(
                    body
                ),
                openai_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .JSON_INVALID,
        )

    def test_nonfinite_json_rejected(self):
        body = (
            b'{'
            b'"status":"completed",'
            b'"value":NaN,'
            b'"output":[]'
            b'}'
        )

        with self.assertRaises(
            _ProviderResponseExtractFailure
        ) as caught:
            _extract_provider_response(
                raw_body_response(
                    body
                ),
                openai_profile(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .JSON_INVALID,
        )

    def test_extracted_output_limit(self):
        document = openai_document(
            text="x" * 100
        )

        with patch.object(
            extractor_module,
            "MAX_PROVIDER_VISION_EXTRACTED_BYTES",
            1,
        ):
            with self.assertRaises(
                _ProviderResponseExtractFailure
            ) as caught:
                self.extract(
                    document,
                    openai_profile(),
                )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_output_validation_failure_mapping(self):
        with patch.object(
            extractor_module,
            "validate_external_vision_transport_response",
            side_effect=[
                raw_response(
                    openai_document()
                ),
                ValueError(
                    "private"
                ),
            ],
        ):
            with self.assertRaises(
                _ProviderResponseExtractFailure
            ) as caught:
                _extract_provider_response(
                    raw_response(
                        openai_document()
                    ),
                    openai_profile(),
                    lambda: None,
                )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID,
        )

    def test_memory_error_during_json_parse_mapping(self):
        with patch.object(
            extractor_module.json,
            "loads",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _ProviderResponseExtractFailure
            ) as caught:
                self.extract(
                    openai_document(),
                    openai_profile(),
                )

        self.assertIs(
            caught.exception.code,
            _ProviderResponseExtractFailureCode
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

        result = self.extract(
            openai_document(),
            openai_profile(),
            check=check,
        )

        self.assertIs(
            type(result),
            ExternalVisionTransportResponse,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            7,
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
            self.extract(
                openai_document(),
                openai_profile(),
                check=check,
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.extract(
                openai_document(),
                openai_profile(),
                check=check,
            )

    def test_failure_code_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_response_extract_failure_invalid$",
        ):
            _ProviderResponseExtractFailure(
                "JSON_INVALID"
            )


if __name__ == "__main__":
    unittest.main()