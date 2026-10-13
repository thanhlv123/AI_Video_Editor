"""M89 strict provider-specific vision response extractor.

This module unwraps one validated provider HTTP JSON response and returns only
the provider-generated semantic JSON text as a normalized M87 transport
response.

It performs no network access and handles no credentials.

The normalized semantic text is still validated later by the M87 strict
semantic response parser. This module does not grant source authority.
"""

from enum import Enum
import json

from ..external_vision_provider_transport import (
    EXTERNAL_VISION_TRANSPORT_SCHEMA_VERSION,
    MAX_EXTERNAL_VISION_RESPONSE_BYTES,
    ExternalVisionTransportResponse,
    ExternalVisionTransportResponseEncoding,
    validate_external_vision_transport_response,
)
from .models import (
    ProviderVisionProfile,
    VisionProviderResponseDialect,
    validate_provider_vision_profile,
)


MAX_PROVIDER_VISION_EXTRACTED_BYTES = (
    MAX_EXTERNAL_VISION_RESPONSE_BYTES
)


class _ProviderResponseExtractFailureCode(str, Enum):
    TRANSPORT_RESPONSE_INVALID = (
        "TRANSPORT_RESPONSE_INVALID"
    )
    PROFILE_INVALID = "PROFILE_INVALID"
    JSON_INVALID = "JSON_INVALID"
    PROVIDER_RESPONSE_INVALID = (
        "PROVIDER_RESPONSE_INVALID"
    )
    OUTPUT_INVALID = "OUTPUT_INVALID"
    RESOURCE_LIMIT_EXCEEDED = (
        "RESOURCE_LIMIT_EXCEEDED"
    )


class _ProviderResponseExtractFailure(Exception):
    def __init__(
        self,
        code,
    ):
        if (
            type(code)
            is not _ProviderResponseExtractFailureCode
        ):
            raise ValueError(
                "provider_response_extract_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


class _StrictJSONFailure(Exception):
    pass


def _reject_duplicate_object(
    pairs,
):
    result = {}

    for key, value in pairs:
        if type(key) is not str:
            raise _StrictJSONFailure()

        if key in result:
            raise _StrictJSONFailure()

        result[
            key
        ] = value

    return result


def _reject_constant(
    value,
):
    raise _StrictJSONFailure()


def _require_dict(
    value,
):
    if type(value) is not dict:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    return value


def _require_list(
    value,
):
    if type(value) is not list:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    return value


def _require_text(
    value,
):
    if (
        type(value) is not str
        or not value.strip()
    ):
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        )

    return value


def _extract_openai_text(
    document,
    check,
):
    _require_dict(
        document
    )

    if document.get(
        "status"
    ) != "completed":
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    output = _require_list(
        document.get(
            "output"
        )
    )

    if not output:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    text_parts = []
    refusal_seen = False

    for item in output:
        check()

        item = _require_dict(
            item
        )

        item_type = item.get(
            "type"
        )

        # Responses API may include non-message output items, including
        # reasoning items. They are not semantic output text.
        if item_type != "message":
            continue

        if item.get(
            "role"
        ) != "assistant":
            raise _ProviderResponseExtractFailure(
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID
            )

        if item.get(
            "status"
        ) != "completed":
            raise _ProviderResponseExtractFailure(
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID
            )

        content = _require_list(
            item.get(
                "content"
            )
        )

        for part in content:
            check()

            part = _require_dict(
                part
            )

            part_type = part.get(
                "type"
            )

            if part_type == "refusal":
                refusal_seen = True
                continue

            if part_type != "output_text":
                raise _ProviderResponseExtractFailure(
                    _ProviderResponseExtractFailureCode
                    .PROVIDER_RESPONSE_INVALID
                )

            text_parts.append(
                _require_text(
                    part.get(
                        "text"
                    )
                )
            )

    if refusal_seen:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        )

    if not text_parts:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        )

    return "".join(
        text_parts
    )


def _extract_gemini_text(
    document,
    check,
):
    _require_dict(
        document
    )

    if document.get(
        "object"
    ) != "interaction":
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    if document.get(
        "status"
    ) != "completed":
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    steps = _require_list(
        document.get(
            "steps"
        )
    )

    if not steps:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    text_parts = []

    for step in steps:
        check()

        step = _require_dict(
            step
        )

        if step.get(
            "type"
        ) != "model_output":
            raise _ProviderResponseExtractFailure(
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID
            )

        content = _require_list(
            step.get(
                "content"
            )
        )

        if not content:
            raise _ProviderResponseExtractFailure(
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID
            )

        for part in content:
            check()

            part = _require_dict(
                part
            )

            if part.get(
                "type"
            ) != "text":
                raise _ProviderResponseExtractFailure(
                    _ProviderResponseExtractFailureCode
                    .PROVIDER_RESPONSE_INVALID
                )

            text_parts.append(
                _require_text(
                    part.get(
                        "text"
                    )
                )
            )

    if not text_parts:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        )

    return "".join(
        text_parts
    )


def _extract_kie_text(
    document,
    check,
):
    _require_dict(
        document
    )

    # Kie may return an API-level error object while the HTTP layer itself
    # returned status 200.
    if "code" in document:
        code = document.get(
            "code"
        )

        if (
            type(code) is not int
            or code != 200
        ):
            raise _ProviderResponseExtractFailure(
                _ProviderResponseExtractFailureCode
                .PROVIDER_RESPONSE_INVALID
            )

    choices = _require_list(
        document.get(
            "choices"
        )
    )

    if len(
        choices
    ) != 1:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    check()

    choice = _require_dict(
        choices[
            0
        ]
    )

    if (
        type(
            choice.get(
                "index"
            )
        ) is not int
        or choice.get(
            "index"
        ) != 0
    ):
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    if choice.get(
        "finish_reason"
    ) != "stop":
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    message = _require_dict(
        choice.get(
            "message"
        )
    )

    if message.get(
        "role"
    ) != "assistant":
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROVIDER_RESPONSE_INVALID
        )

    return _require_text(
        message.get(
            "content"
        )
    )


def _build_normalized_response(
    text,
    check,
):
    text = _require_text(
        text
    )

    check()

    try:
        body = text.encode(
            "utf-8"
        )

    except MemoryError:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except UnicodeEncodeError:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        ) from None

    if (
        not body
        or len(body)
        > MAX_PROVIDER_VISION_EXTRACTED_BYTES
    ):
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    check()

    result = ExternalVisionTransportResponse(
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

    try:
        validate_external_vision_transport_response(
            result
        )

    except MemoryError:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .OUTPUT_INVALID
        ) from None

    check()

    return result


def _extract_provider_response(
    response,
    profile,
    check,
):
    """
    Extract provider-generated semantic JSON text from one raw provider
    response.

    The returned M87 response still requires M87 semantic JSON validation.
    """
    try:
        validate_external_vision_transport_response(
            response
        )

    except MemoryError:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .TRANSPORT_RESPONSE_INVALID
        ) from None

    if type(response) is not ExternalVisionTransportResponse:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .TRANSPORT_RESPONSE_INVALID
        )

    try:
        validate_provider_vision_profile(
            profile
        )

    except MemoryError:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROFILE_INVALID
        ) from None

    if type(profile) is not ProviderVisionProfile:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROFILE_INVALID
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
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _StrictJSONFailure,
        RecursionError,
        ValueError,
    ):
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .JSON_INVALID
        ) from None

    check()

    dialect = profile.response_dialect

    if (
        dialect
        is VisionProviderResponseDialect
        .OPENAI_RESPONSES_OUTPUT_TEXT_V1
    ):
        extracted = _extract_openai_text(
            document,
            check,
        )

    elif (
        dialect
        is VisionProviderResponseDialect
        .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1
    ):
        extracted = _extract_gemini_text(
            document,
            check,
        )

    elif (
        dialect
        is VisionProviderResponseDialect
        .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1
    ):
        extracted = _extract_kie_text(
            document,
            check,
        )

    else:
        raise _ProviderResponseExtractFailure(
            _ProviderResponseExtractFailureCode
            .PROFILE_INVALID
        )

    check()

    return _build_normalized_response(
        extracted,
        check,
    )