"""M89 provider-specific vision profile model contract.

Profiles describe provider wire-format requirements only.

They contain:
- no API keys;
- no source authority;
- no runtime objects;
- no image bytes;
- no file handles;
- no network execution capability.

Provider-specific request/response serializers are implemented separately.
"""

from dataclasses import dataclass, fields
from enum import Enum
from urllib.parse import urlsplit

from ..external_vision_http_transport import (
    MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH,
    ExternalVisionHTTPCredentialHeader,
)


PROVIDER_VISION_PROFILE_SCHEMA_VERSION = 1

MAX_PROVIDER_VISION_MODEL_LENGTH = 256


class VisionProviderKind(str, Enum):
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    KIE_AI = "KIE_AI"


class VisionProviderRequestDialect(str, Enum):
    OPENAI_RESPONSES_V1 = "OPENAI_RESPONSES_V1"
    GEMINI_INTERACTIONS_V1 = "GEMINI_INTERACTIONS_V1"
    KIE_OPENAI_CHAT_COMPLETIONS_V1 = (
        "KIE_OPENAI_CHAT_COMPLETIONS_V1"
    )
    KIE_OPENAI_RESPONSES_V1 = (
        "KIE_OPENAI_RESPONSES_V1"
    )


class VisionProviderResponseDialect(str, Enum):
    OPENAI_RESPONSES_OUTPUT_TEXT_V1 = (
        "OPENAI_RESPONSES_OUTPUT_TEXT_V1"
    )
    GEMINI_INTERACTIONS_OUTPUT_TEXT_V1 = (
        "GEMINI_INTERACTIONS_OUTPUT_TEXT_V1"
    )
    KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1 = (
        "KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1"
    )
    KIE_RESPONSES_OUTPUT_TEXT_V1 = (
        "KIE_RESPONSES_OUTPUT_TEXT_V1"
    )


class VisionProviderImageInputMode(str, Enum):
    BASE64_DATA_URL = "BASE64_DATA_URL"
    INLINE_BASE64 = "INLINE_BASE64"
    REMOTE_URL = "REMOTE_URL"


@dataclass(frozen=True)
class ProviderVisionProfile:
    schema_version: int
    provider: VisionProviderKind
    endpoint: str
    model: str
    credential_header: ExternalVisionHTTPCredentialHeader
    request_dialect: VisionProviderRequestDialect
    response_dialect: VisionProviderResponseDialect
    image_input_mode: VisionProviderImageInputMode


def _validate_exact_shape(
    value,
    expected_type,
):
    if type(value) is not expected_type:
        raise ValueError()

    members = object.__getattribute__(
        value,
        "__dict__",
    )

    names = {
        field.name
        for field in fields(
            expected_type
        )
    }

    if (
        type(members) is not dict
        or len(members) != len(names)
        or any(
            type(key) is not str
            for key in members
        )
        or set(members) != names
    ):
        raise ValueError()


def _validate_endpoint(
    endpoint,
):
    if type(endpoint) is not str:
        raise ValueError()

    if (
        not endpoint
        or endpoint != endpoint.strip()
        or len(endpoint)
        > MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH
    ):
        raise ValueError()

    parsed = urlsplit(
        endpoint
    )

    if parsed.scheme.lower() != "https":
        raise ValueError()

    if (
        not parsed.netloc
        or parsed.hostname is None
        or not parsed.hostname
    ):
        raise ValueError()

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError()

    try:
        port = parsed.port

    except ValueError:
        raise ValueError() from None

    if (
        port is not None
        and (
            type(port) is not int
            or port <= 0
            or port > 65535
        )
    ):
        raise ValueError()

    return parsed


def _validate_model(
    model,
):
    if type(model) is not str:
        raise ValueError()

    if (
        not model
        or model != model.strip()
        or len(model)
        > MAX_PROVIDER_VISION_MODEL_LENGTH
    ):
        raise ValueError()

    for character in model:
        code = ord(
            character
        )

        if (
            code < 33
            or code > 126
        ):
            raise ValueError()


def _validate_provider_coherence(
    profile,
    parsed_endpoint,
):
    provider = profile.provider

    if provider is VisionProviderKind.OPENAI:
        if (
            parsed_endpoint.hostname.lower()
            != "api.openai.com"
        ):
            raise ValueError()

        if parsed_endpoint.path != "/v1/responses":
            raise ValueError()

        if (
            profile.credential_header
            is not ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ):
            raise ValueError()

        if (
            profile.request_dialect
            is not VisionProviderRequestDialect
            .OPENAI_RESPONSES_V1
        ):
            raise ValueError()

        if (
            profile.response_dialect
            is not VisionProviderResponseDialect
            .OPENAI_RESPONSES_OUTPUT_TEXT_V1
        ):
            raise ValueError()

        if (
            profile.image_input_mode
            is not VisionProviderImageInputMode
            .BASE64_DATA_URL
        ):
            raise ValueError()

        return

    if provider is VisionProviderKind.GEMINI:
        if (
            parsed_endpoint.hostname.lower()
            != "generativelanguage.googleapis.com"
        ):
            raise ValueError()

        if parsed_endpoint.path != "/v1beta/interactions":
            raise ValueError()

        if (
            profile.credential_header
            is not ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY
        ):
            raise ValueError()

        if (
            profile.request_dialect
            is not VisionProviderRequestDialect
            .GEMINI_INTERACTIONS_V1
        ):
            raise ValueError()

        if (
            profile.response_dialect
            is not VisionProviderResponseDialect
            .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1
        ):
            raise ValueError()

        if (
            profile.image_input_mode
            is not VisionProviderImageInputMode
            .INLINE_BASE64
        ):
            raise ValueError()

        return

    if provider is VisionProviderKind.KIE_AI:
        if (
            parsed_endpoint.hostname.lower()
            != "api.kie.ai"
        ):
            raise ValueError()

        if (
            profile.credential_header
            is not ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ):
            raise ValueError()

        if (
            profile.image_input_mode
            is not VisionProviderImageInputMode
            .REMOTE_URL
        ):
            raise ValueError()

        path = parsed_endpoint.path

        if (
            path.startswith(
                "/"
            )
            and path.endswith(
                "/v1/chat/completions"
            )
        ):
            if (
                profile.request_dialect
                is not VisionProviderRequestDialect
                .KIE_OPENAI_CHAT_COMPLETIONS_V1
            ):
                raise ValueError()

            if (
                profile.response_dialect
                is not VisionProviderResponseDialect
                .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1
            ):
                raise ValueError()

            return

        if path == "/openai/v1/responses":
            if (
                profile.request_dialect
                is not VisionProviderRequestDialect
                .KIE_OPENAI_RESPONSES_V1
            ):
                raise ValueError()

            if (
                profile.response_dialect
                is not VisionProviderResponseDialect
                .KIE_RESPONSES_OUTPUT_TEXT_V1
            ):
                raise ValueError()

            return

        raise ValueError()

    raise ValueError()


def validate_provider_vision_profile(
    profile,
):
    """
    Validate one immutable provider-specific vision profile.

    Validation performs no DNS lookup and no network access.
    """
    try:
        _validate_exact_shape(
            profile,
            ProviderVisionProfile,
        )

        if (
            type(profile.schema_version) is not int
            or profile.schema_version
            != PROVIDER_VISION_PROFILE_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(profile.provider)
            is not VisionProviderKind
        ):
            raise ValueError()

        parsed_endpoint = _validate_endpoint(
            profile.endpoint
        )

        _validate_model(
            profile.model
        )

        if (
            type(profile.credential_header)
            is not ExternalVisionHTTPCredentialHeader
        ):
            raise ValueError()

        if (
            type(profile.request_dialect)
            is not VisionProviderRequestDialect
        ):
            raise ValueError()

        if (
            type(profile.response_dialect)
            is not VisionProviderResponseDialect
        ):
            raise ValueError()

        if (
            type(profile.image_input_mode)
            is not VisionProviderImageInputMode
        ):
            raise ValueError()

        _validate_provider_coherence(
            profile,
            parsed_endpoint,
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_vision_profile_invalid"
        ) from None

    return profile