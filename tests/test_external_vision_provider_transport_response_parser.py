"""M87 strict deterministic external vision transport response parser."""

import json
import unittest
from unittest.mock import patch

import creator_studio.external_vision_provider_transport.response_parser as parser_module

from creator_studio.external_vision_provider_transport.models import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
)
from creator_studio.external_vision_provider_transport.response_parser import (
    _TransportResponseParseFailure,
    _TransportResponseParseFailureCode,
    _parse_transport_response,
)
from creator_studio.semantic_vision_observer import (
    SceneSetting,
    SemanticVisionAdapterResponse,
    ShotScale,
    VisualMood,
    validate_semantic_vision_adapter_response,
)


def document():
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


def response_from_body(body):
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


def response_from_document(value=None):
    if value is None:
        value = document()

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

    return response_from_body(
        body
    )


class ExternalVisionTransportResponseParserTests(
    unittest.TestCase
):

    def parse(
        self,
        response_value=None,
        check=None,
    ):
        if response_value is None:
            response_value = (
                response_from_document()
            )

        if check is None:
            check = lambda: None

        return _parse_transport_response(
            response_value,
            check,
        )

    def failure(
        self,
        response_value,
        expected,
    ):
        with self.assertRaises(
            _TransportResponseParseFailure
        ) as caught:
            _parse_transport_response(
                response_value,
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            expected,
        )

    def test_parse_success(self):
        value = self.parse()

        self.assertIs(
            type(value),
            SemanticVisionAdapterResponse,
        )

        self.assertIs(
            validate_semantic_vision_adapter_response(
                value
            ),
            value,
        )

    def test_semantic_values_are_exact(self):
        value = self.parse()

        self.assertIs(
            value.scene_setting,
            SceneSetting.INDOOR,
        )

        self.assertIs(
            value.shot_scale,
            ShotScale.MEDIUM,
        )

        self.assertIs(
            value.visual_mood,
            VisualMood.CALM,
        )

        self.assertEqual(
            value.subjects[0].label,
            "person",
        )

        self.assertEqual(
            value.activities[0].label,
            "cooking",
        )

        self.assertEqual(
            value.scene_tags[0].label,
            "rural kitchen",
        )

        self.assertEqual(
            value.confidence_milli,
            900,
        )

    def test_deterministic(self):
        response_value = (
            response_from_document()
        )

        first = self.parse(
            response_value
        )

        second = self.parse(
            response_value
        )

        self.assertEqual(
            first,
            second,
        )

    def test_invalid_transport_response_rejected(self):
        invalid = response_from_body(
            b"{}"
        )

        invalid = ExternalVisionTransportResponse(
            schema_version=2,
            encoding=invalid.encoding,
            body_length=invalid.body_length,
            body=invalid.body,
        )

        self.failure(
            invalid,
            _TransportResponseParseFailureCode
            .TRANSPORT_RESPONSE_INVALID,
        )

    def test_malformed_json_rejected(self):
        self.failure(
            response_from_body(
                b'{"schema_version":1'
            ),
            _TransportResponseParseFailureCode
            .JSON_INVALID,
        )

    def test_duplicate_top_level_key_rejected(self):
        body = (
            b'{'
            b'"schema_version":1,'
            b'"schema_version":1,'
            b'"scene_setting":"INDOOR",'
            b'"shot_scale":"MEDIUM",'
            b'"visual_mood":"CALM",'
            b'"subjects":[],'
            b'"activities":[],'
            b'"scene_tags":[],'
            b'"confidence_milli":900'
            b'}'
        )

        self.failure(
            response_from_body(
                body
            ),
            _TransportResponseParseFailureCode
            .JSON_INVALID,
        )

    def test_duplicate_nested_label_key_rejected(self):
        body = (
            b'{'
            b'"schema_version":1,'
            b'"scene_setting":"INDOOR",'
            b'"shot_scale":"MEDIUM",'
            b'"visual_mood":"CALM",'
            b'"subjects":['
            b'{'
            b'"label":"person",'
            b'"label":"table",'
            b'"confidence_milli":900'
            b'}'
            b'],'
            b'"activities":[],'
            b'"scene_tags":[],'
            b'"confidence_milli":900'
            b'}'
        )

        self.failure(
            response_from_body(
                body
            ),
            _TransportResponseParseFailureCode
            .JSON_INVALID,
        )

    def test_nonfinite_json_number_rejected(self):
        body = (
            b'{'
            b'"schema_version":1,'
            b'"scene_setting":"INDOOR",'
            b'"shot_scale":"MEDIUM",'
            b'"visual_mood":"CALM",'
            b'"subjects":[],'
            b'"activities":[],'
            b'"scene_tags":[],'
            b'"confidence_milli":NaN'
            b'}'
        )

        self.failure(
            response_from_body(
                body
            ),
            _TransportResponseParseFailureCode
            .JSON_INVALID,
        )

    def test_top_level_must_be_exact_object(self):
        variants = [
            [],
            {
                **document(),
                "extra": 1,
            },
        ]

        missing = document()
        del missing[
            "visual_mood"
        ]

        variants.append(
            missing
        )

        for value in variants:
            with self.subTest(
                value_type=type(value)
            ):
                self.failure(
                    response_from_document(
                        value
                    ),
                    _TransportResponseParseFailureCode
                    .SEMANTIC_RESPONSE_INVALID,
                )

    def test_schema_version_must_be_exact_integer(self):
        for value in (
            0,
            2,
            True,
        ):
            changed = document()
            changed[
                "schema_version"
            ] = value

            with self.subTest(
                value=value
            ):
                self.failure(
                    response_from_document(
                        changed
                    ),
                    _TransportResponseParseFailureCode
                    .SEMANTIC_RESPONSE_INVALID,
                )

    def test_invalid_enum_values_rejected(self):
        cases = [
            (
                "scene_setting",
                "SPACE",
            ),
            (
                "shot_scale",
                "GIANT",
            ),
            (
                "visual_mood",
                "MAGICAL",
            ),
        ]

        for key, value in cases:
            changed = document()
            changed[
                key
            ] = value

            with self.subTest(
                key=key
            ):
                self.failure(
                    response_from_document(
                        changed
                    ),
                    _TransportResponseParseFailureCode
                    .SEMANTIC_RESPONSE_INVALID,
                )

    def test_label_collections_require_arrays(self):
        changed = document()

        changed[
            "subjects"
        ] = {
            "label": "person",
            "confidence_milli": 900,
        }

        self.failure(
            response_from_document(
                changed
            ),
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID,
        )

    def test_label_objects_require_exact_keys(self):
        variants = [
            {
                "label": "person",
            },
            {
                "label": "person",
                "confidence_milli": 900,
                "extra": 1,
            },
        ]

        for item in variants:
            changed = document()
            changed[
                "subjects"
            ] = [
                item
            ]

            self.failure(
                response_from_document(
                    changed
                ),
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID,
            )

    def test_invalid_semantic_label_rejected(self):
        cases = [
            (
                "Person",
                900,
            ),
            (
                "person!",
                900,
            ),
            (
                "person",
                1001,
            ),
            (
                "person",
                True,
            ),
        ]

        for label, confidence in cases:
            changed = document()

            changed[
                "subjects"
            ] = [
                {
                    "label": label,
                    "confidence_milli": confidence,
                }
            ]

            with self.subTest(
                label=label,
                confidence=confidence,
            ):
                self.failure(
                    response_from_document(
                        changed
                    ),
                    _TransportResponseParseFailureCode
                    .SEMANTIC_RESPONSE_INVALID,
                )

    def test_noncanonical_label_order_rejected(self):
        changed = document()

        changed[
            "subjects"
        ] = [
            {
                "label": "table",
                "confidence_milli": 700,
            },
            {
                "label": "person",
                "confidence_milli": 900,
            },
        ]

        self.failure(
            response_from_document(
                changed
            ),
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID,
        )

    def test_overall_confidence_requires_exact_integer(self):
        for value in (
            -1,
            1001,
            True,
            900.0,
        ):
            changed = document()
            changed[
                "confidence_milli"
            ] = value

            with self.subTest(
                value=value
            ):
                self.failure(
                    response_from_document(
                        changed
                    ),
                    _TransportResponseParseFailureCode
                    .SEMANTIC_RESPONSE_INVALID,
                )

    def test_memory_error_during_transport_validation_mapping(self):
        with patch.object(
            parser_module,
            "validate_external_vision_transport_response",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _TransportResponseParseFailure
            ) as caught:
                self.parse()

        self.assertIs(
            caught.exception.code,
            _TransportResponseParseFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_memory_error_during_json_parse_mapping(self):
        with patch.object(
            parser_module.json,
            "loads",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                _TransportResponseParseFailure
            ) as caught:
                self.parse()

        self.assertIs(
            caught.exception.code,
            _TransportResponseParseFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_output_validation_failure_mapping(self):
        with patch.object(
            parser_module,
            "validate_semantic_vision_adapter_response",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaises(
                _TransportResponseParseFailure
            ) as caught:
                self.parse()

        self.assertIs(
            caught.exception.code,
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID,
        )

    def test_check_is_used_repeatedly(self):
        calls = [0]

        def check():
            calls[0] += 1

        value = self.parse(
            check=check
        )

        self.assertIs(
            type(value),
            SemanticVisionAdapterResponse,
        )

        self.assertGreaterEqual(
            calls[0],
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
            self.parse(
                check=check
            )

    def test_baseexception_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            self.parse(
                check=check
            )

    def test_failure_code_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^transport_response_parse_failure_invalid$",
        ):
            _TransportResponseParseFailure(
                "JSON_INVALID"
            )


if __name__ == "__main__":
    unittest.main()