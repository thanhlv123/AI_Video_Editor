"""Strict deterministic external vision transport response parser.

Opaque UTF-8 transport text is accepted only when it exactly satisfies the
M85 structured semantic response contract.
"""

from enum import Enum
import json

from ..semantic_vision_observer import (
    MAX_SEMANTIC_LABELS,
    SceneSetting,
    SemanticLabel,
    ShotScale,
    VisualMood,
)
from ..semantic_vision_observer.adapter_contract import (
    SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION,
    SemanticVisionAdapterResponse,
    validate_semantic_vision_adapter_response,
)
from .models import (
    ExternalVisionTransportResponse,
    validate_external_vision_transport_response,
)


class _TransportResponseParseFailureCode(str, Enum):
    TRANSPORT_RESPONSE_INVALID = "TRANSPORT_RESPONSE_INVALID"
    JSON_INVALID = "JSON_INVALID"
    SEMANTIC_RESPONSE_INVALID = "SEMANTIC_RESPONSE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class _TransportResponseParseFailure(Exception):
    def __init__(self, code):
        if type(code) is not _TransportResponseParseFailureCode:
            raise ValueError(
                "transport_response_parse_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


class _StrictJSONFailure(Exception):
    pass


def _reject_duplicate_object(pairs):
    result = {}

    for key, value in pairs:
        if type(key) is not str:
            raise _StrictJSONFailure()

        if key in result:
            raise _StrictJSONFailure()

        result[key] = value

    return result


def _reject_constant(value):
    raise _StrictJSONFailure()


def _require_exact_keys(
    value,
    expected,
):
    if type(value) is not dict:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID
        )

    if set(value) != expected:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID
        )


def _parse_labels(
    value,
    check,
):
    if type(value) is not list:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID
        )

    if len(value) > MAX_SEMANTIC_LABELS:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .SEMANTIC_RESPONSE_INVALID
        )

    output = []

    for item in value:
        check()

        _require_exact_keys(
            item,
            {
                "label",
                "confidence_milli",
            },
        )

        label = item["label"]
        confidence = item[
            "confidence_milli"
        ]

        if type(label) is not str:
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            )

        if type(confidence) is not int:
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            )

        output.append(
            SemanticLabel(
                label=label,
                confidence_milli=confidence,
            )
        )

    return tuple(
        output
    )


def _parse_transport_response(
    response,
    check,
):
    """
    Parse one bounded transport response into one exact M85 adapter response.

    The parser performs no network access and grants no source authority.
    """
    try:
        validate_external_vision_transport_response(
            response
        )

    except MemoryError:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .TRANSPORT_RESPONSE_INVALID
        ) from None

    if type(response) is not ExternalVisionTransportResponse:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .TRANSPORT_RESPONSE_INVALID
        )

    check()

    try:
        text = response.body.decode(
            "utf-8",
            errors="strict",
        )

        document = json.loads(
            text,
            object_pairs_hook=(
                _reject_duplicate_object
            ),
            parse_constant=(
                _reject_constant
            ),
        )

    except MemoryError:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _StrictJSONFailure,
        RecursionError,
        ValueError,
    ):
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .JSON_INVALID
        ) from None

    check()

    try:
        _require_exact_keys(
            document,
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

        schema_version = document[
            "schema_version"
        ]

        if (
            type(schema_version) is not int
            or schema_version
            != SEMANTIC_VISION_ADAPTER_SCHEMA_VERSION
        ):
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            )

        scene_setting_raw = document[
            "scene_setting"
        ]

        shot_scale_raw = document[
            "shot_scale"
        ]

        visual_mood_raw = document[
            "visual_mood"
        ]

        if (
            type(scene_setting_raw) is not str
            or type(shot_scale_raw) is not str
            or type(visual_mood_raw) is not str
        ):
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            )

        try:
            scene_setting = SceneSetting(
                scene_setting_raw
            )

            shot_scale = ShotScale(
                shot_scale_raw
            )

            visual_mood = VisualMood(
                visual_mood_raw
            )

        except ValueError:
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            ) from None

        subjects = _parse_labels(
            document[
                "subjects"
            ],
            check,
        )

        activities = _parse_labels(
            document[
                "activities"
            ],
            check,
        )

        scene_tags = _parse_labels(
            document[
                "scene_tags"
            ],
            check,
        )

        confidence = document[
            "confidence_milli"
        ]

        if type(confidence) is not int:
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            )

        check()

        parsed = SemanticVisionAdapterResponse(
            schema_version=(
                schema_version
            ),
            scene_setting=(
                scene_setting
            ),
            shot_scale=(
                shot_scale
            ),
            visual_mood=(
                visual_mood
            ),
            subjects=subjects,
            activities=activities,
            scene_tags=scene_tags,
            confidence_milli=(
                confidence
            ),
        )

        try:
            validate_semantic_vision_adapter_response(
                parsed
            )

        except MemoryError:
            raise

        except Exception:
            raise _TransportResponseParseFailure(
                _TransportResponseParseFailureCode
                .SEMANTIC_RESPONSE_INVALID
            ) from None

        check()

        return parsed

    except _TransportResponseParseFailure:
        raise

    except MemoryError:
        raise _TransportResponseParseFailure(
            _TransportResponseParseFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None