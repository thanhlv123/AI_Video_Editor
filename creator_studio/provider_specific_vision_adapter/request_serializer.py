"""M89 deterministic provider-specific vision request serializer.

This module converts one validated M87 external vision transport request into
the wire JSON expected by one validated provider profile.

It performs no network access and handles no credentials.

OpenAI:
    bounded PNG -> base64 data URL -> Responses API request

Gemini:
    bounded PNG -> inline base64 -> Interactions API request

Kie.ai:
    requires one separately-authorized runtime HTTPS media URL. The M86 image
    bytes are never silently uploaded or exposed by this serializer.
"""

import base64
from enum import Enum
import json
from urllib.parse import urlsplit

from ..external_vision_http_transport import (
    MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES,
)
from ..external_vision_provider_transport import (
    ExternalVisionTransportRequest,
    validate_external_vision_transport_request,
)
from .models import (
    ProviderVisionProfile,
    VisionProviderImageInputMode,
    VisionProviderKind,
    VisionProviderRequestDialect,
    validate_provider_vision_profile,
)


MAX_PROVIDER_VISION_REMOTE_IMAGE_URL_LENGTH = 8192

MAX_PROVIDER_VISION_REQUEST_BYTES = (
    MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
)

SEMANTIC_VISION_PROVIDER_PROMPT = (
    "Analyze the supplied image and return only the requested JSON object. "
    "Do not use Markdown or code fences. "
    "Use concise lowercase canonical labels for subjects, activities, and "
    "scene tags. Confidence values are integers from 0 through 1000."
)


class _ProviderRequestSerializeFailureCode(str, Enum):
    REQUEST_INVALID = "REQUEST_INVALID"
    PROFILE_INVALID = "PROFILE_INVALID"
    PROFILE_COHERENCE_INVALID = "PROFILE_COHERENCE_INVALID"
    REMOTE_IMAGE_REQUIRED = "REMOTE_IMAGE_REQUIRED"
    REMOTE_IMAGE_INVALID = "REMOTE_IMAGE_INVALID"
    SERIALIZATION_INVALID = "SERIALIZATION_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class _ProviderRequestSerializeFailure(Exception):
    def __init__(
        self,
        code,
    ):
        if (
            type(code)
            is not _ProviderRequestSerializeFailureCode
        ):
            raise ValueError(
                "provider_request_serialize_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


def _semantic_label_schema():
    return {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "description": (
                    "Concise lowercase canonical semantic label."
                ),
            },
            "confidence_milli": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1000,
            },
        },
        "required": [
            "label",
            "confidence_milli",
        ],
        "additionalProperties": False,
    }


def _semantic_response_schema():
    """
    Return a fresh JSON schema matching the M85 semantic adapter response.

    M87 remains the final validator even when a provider supports structured
    output.
    """
    return {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "integer",
                "enum": [
                    1,
                ],
            },
            "scene_setting": {
                "type": "string",
                "enum": [
                    "INDOOR",
                    "OUTDOOR",
                    "MIXED",
                    "UNKNOWN",
                ],
            },
            "shot_scale": {
                "type": "string",
                "enum": [
                    "EXTREME_WIDE",
                    "WIDE",
                    "MEDIUM",
                    "CLOSE_UP",
                    "EXTREME_CLOSE_UP",
                    "UNKNOWN",
                ],
            },
            "visual_mood": {
                "type": "string",
                "enum": [
                    "CALM",
                    "POSITIVE",
                    "ENERGETIC",
                    "TENSE",
                    "SOMBER",
                    "NEUTRAL",
                    "UNKNOWN",
                ],
            },
            "subjects": {
                "type": "array",
                "items": (
                    _semantic_label_schema()
                ),
                "maxItems": 8,
            },
            "activities": {
                "type": "array",
                "items": (
                    _semantic_label_schema()
                ),
                "maxItems": 8,
            },
            "scene_tags": {
                "type": "array",
                "items": (
                    _semantic_label_schema()
                ),
                "maxItems": 8,
            },
            "confidence_milli": {
                "type": "integer",
                "minimum": 0,
                "maximum": 1000,
            },
        },
        "required": [
            "schema_version",
            "scene_setting",
            "shot_scale",
            "visual_mood",
            "subjects",
            "activities",
            "scene_tags",
            "confidence_milli",
        ],
        "additionalProperties": False,
    }


def _validate_remote_image_url(
    value,
):
    if type(value) is not str:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    if (
        not value
        or value != value.strip()
        or len(value)
        > MAX_PROVIDER_VISION_REMOTE_IMAGE_URL_LENGTH
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    try:
        parsed = urlsplit(
            value
        )

    except Exception:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        ) from None

    if parsed.scheme.lower() != "https":
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    if (
        not parsed.netloc
        or parsed.hostname is None
        or not parsed.hostname
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    try:
        port = parsed.port

    except ValueError:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        ) from None

    if (
        port is not None
        and (
            type(port) is not int
            or port <= 0
            or port > 65535
        )
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_INVALID
        )

    return value


def _serialize_openai_request(
    request,
    profile,
    image_base64,
):
    if (
        profile.request_dialect
        is not VisionProviderRequestDialect
        .OPENAI_RESPONSES_V1
        or profile.image_input_mode
        is not VisionProviderImageInputMode
        .BASE64_DATA_URL
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_COHERENCE_INVALID
        )

    image_url = (
        "data:image/png;base64,"
        + image_base64
    )

    return {
        "model": profile.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            SEMANTIC_VISION_PROVIDER_PROMPT
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": "low",
                    },
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "semantic_vision_v1",
                "strict": True,
                "schema": (
                    _semantic_response_schema()
                ),
            }
        },
        "store": False,
    }


def _serialize_gemini_request(
    request,
    profile,
    image_base64,
):
    if (
        profile.request_dialect
        is not VisionProviderRequestDialect
        .GEMINI_INTERACTIONS_V1
        or profile.image_input_mode
        is not VisionProviderImageInputMode
        .INLINE_BASE64
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_COHERENCE_INVALID
        )

    return {
        "model": profile.model,
        "input": [
            {
                "type": "text",
                "text": (
                    SEMANTIC_VISION_PROVIDER_PROMPT
                ),
            },
            {
                "type": "image",
                "data": image_base64,
                "mime_type": "image/png",
            },
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": (
                _semantic_response_schema()
            ),
        },
        "stream": False,
    }


def _serialize_kie_request(
    request,
    profile,
    remote_image_url,
):
    if (
        profile.image_input_mode
        is not VisionProviderImageInputMode
        .REMOTE_URL
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_COHERENCE_INVALID
        )

    if remote_image_url is None:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REMOTE_IMAGE_REQUIRED
        )

    remote_image_url = (
        _validate_remote_image_url(
            remote_image_url
        )
    )

    dialect = profile.request_dialect

    if (
        dialect
        is VisionProviderRequestDialect
        .KIE_OPENAI_CHAT_COMPLETIONS_V1
    ):
        return {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                SEMANTIC_VISION_PROVIDER_PROMPT
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    remote_image_url
                                ),
                            },
                        },
                    ],
                }
            ],
            "stream": False,
        }

    if (
        dialect
        is VisionProviderRequestDialect
        .KIE_OPENAI_RESPONSES_V1
    ):
        return {
            "model": profile.model,
            "stream": False,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                SEMANTIC_VISION_PROVIDER_PROMPT
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                remote_image_url
                            ),
                        },
                    ],
                }
            ],
        }

    raise _ProviderRequestSerializeFailure(
        _ProviderRequestSerializeFailureCode
        .PROFILE_COHERENCE_INVALID
    )


def _serialize_provider_request(
    request,
    profile,
    check,
    remote_image_url=None,
):
    """
    Serialize one validated M87 request into one provider-specific JSON body.

    The result contains no provider credential.

    ``remote_image_url`` is accepted only for provider profiles that explicitly
    require remote media.
    """
    try:
        validate_external_vision_transport_request(
            request
        )

    except MemoryError:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REQUEST_INVALID
        ) from None

    if type(request) is not ExternalVisionTransportRequest:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .REQUEST_INVALID
        )

    try:
        validate_provider_vision_profile(
            profile
        )

    except MemoryError:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_INVALID
        ) from None

    if type(profile) is not ProviderVisionProfile:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_INVALID
        )

    check()

    if (
        profile.provider
        is not VisionProviderKind.KIE_AI
        and remote_image_url is not None
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_COHERENCE_INVALID
        )

    try:
        image_base64 = base64.b64encode(
            request.payload.image_bytes
        ).decode(
            "ascii"
        )

    except MemoryError:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .SERIALIZATION_INVALID
        ) from None

    check()

    if (
        profile.provider
        is VisionProviderKind.OPENAI
    ):
        document = _serialize_openai_request(
            request,
            profile,
            image_base64,
        )

    elif (
        profile.provider
        is VisionProviderKind.GEMINI
    ):
        document = _serialize_gemini_request(
            request,
            profile,
            image_base64,
        )

    elif (
        profile.provider
        is VisionProviderKind.KIE_AI
    ):
        document = _serialize_kie_request(
            request,
            profile,
            remote_image_url,
        )

    else:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .PROFILE_COHERENCE_INVALID
        )

    check()

    try:
        text = json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

        body = text.encode(
            "utf-8"
        )

    except MemoryError:
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .SERIALIZATION_INVALID
        ) from None

    check()

    if (
        not body
        or len(body)
        > MAX_PROVIDER_VISION_REQUEST_BYTES
    ):
        raise _ProviderRequestSerializeFailure(
            _ProviderRequestSerializeFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    check()

    return body