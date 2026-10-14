"""M90 provider runtime configuration presets.

This module builds credential-free ProviderRuntimeConfig objects for the
provider contracts introduced in M89.

The builders:
- accept one validated M88 HTTP configuration as a transport-policy template;
- replace only its endpoint with the provider endpoint;
- create one coherent M89 provider profile;
- create one coherent M90 runtime configuration;
- store only the name of the environment variable that will later contain the
  credential;
- perform no environment lookup;
- perform no DNS lookup;
- perform no network access.

No API secret is accepted by any preset builder.
"""

import dataclasses
from urllib.parse import urlsplit

from ..external_vision_http_transport import (
    ExternalVisionHTTPConfig,
    ExternalVisionHTTPCredentialHeader,
    validate_external_vision_http_config,
)
from ..provider_specific_vision_adapter import (
    PROVIDER_VISION_PROFILE_SCHEMA_VERSION,
    ProviderVisionProfile,
    VisionProviderImageInputMode,
    VisionProviderKind,
    VisionProviderRequestDialect,
    VisionProviderResponseDialect,
)
from .credential_source import (
    ProviderEnvironmentCredentialMode,
)
from .runtime_config import (
    PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION,
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)


OPENAI_VISION_ENDPOINT = (
    "https://api.openai.com/v1/responses"
)

GEMINI_VISION_ENDPOINT = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/interactions"
)

DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE = (
    "OPENAI_API_KEY"
)

DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE = (
    "GEMINI_API_KEY"
)

DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE = (
    "KIE_API_KEY"
)


def _validate_http_template(
    http_config,
):
    if type(http_config) is not ExternalVisionHTTPConfig:
        raise ValueError()

    validate_external_vision_http_config(
        http_config
    )


def _build_runtime_config(
    *,
    provider,
    endpoint,
    model,
    credential_header,
    request_dialect,
    response_dialect,
    image_input_mode,
    credential_environment_variable,
    credential_mode,
    http_config,
):
    try:
        _validate_http_template(
            http_config
        )

        profile = ProviderVisionProfile(
            schema_version=(
                PROVIDER_VISION_PROFILE_SCHEMA_VERSION
            ),
            provider=provider,
            endpoint=endpoint,
            model=model,
            credential_header=credential_header,
            request_dialect=request_dialect,
            response_dialect=response_dialect,
            image_input_mode=image_input_mode,
        )

        provider_http_config = (
            dataclasses.replace(
                http_config,
                endpoint=endpoint,
            )
        )

        result = ProviderRuntimeConfig(
            schema_version=(
                PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION
            ),
            profile=profile,
            http_config=provider_http_config,
            credential_environment_variable=(
                credential_environment_variable
            ),
            credential_mode=credential_mode,
        )

        validate_provider_runtime_config(
            result
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_preset_invalid"
        ) from None

    return result


def build_openai_runtime_config(
    model,
    http_config,
    credential_environment_variable=(
        DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE
    ),
):
    """Build one OpenAI runtime configuration."""
    return _build_runtime_config(
        provider=(
            VisionProviderKind.OPENAI
        ),
        endpoint=(
            OPENAI_VISION_ENDPOINT
        ),
        model=model,
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        request_dialect=(
            VisionProviderRequestDialect
            .OPENAI_RESPONSES_V1
        ),
        response_dialect=(
            VisionProviderResponseDialect
            .OPENAI_RESPONSES_OUTPUT_TEXT_V1
        ),
        image_input_mode=(
            VisionProviderImageInputMode
            .BASE64_DATA_URL
        ),
        credential_environment_variable=(
            credential_environment_variable
        ),
        credential_mode=(
            ProviderEnvironmentCredentialMode
            .BEARER
        ),
        http_config=http_config,
    )


def build_gemini_runtime_config(
    model,
    http_config,
    credential_environment_variable=(
        DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE
    ),
):
    """Build one Gemini runtime configuration."""
    return _build_runtime_config(
        provider=(
            VisionProviderKind.GEMINI
        ),
        endpoint=(
            GEMINI_VISION_ENDPOINT
        ),
        model=model,
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY
        ),
        request_dialect=(
            VisionProviderRequestDialect
            .GEMINI_INTERACTIONS_V1
        ),
        response_dialect=(
            VisionProviderResponseDialect
            .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1
        ),
        image_input_mode=(
            VisionProviderImageInputMode
            .INLINE_BASE64
        ),
        credential_environment_variable=(
            credential_environment_variable
        ),
        credential_mode=(
            ProviderEnvironmentCredentialMode
            .RAW
        ),
        http_config=http_config,
    )


def build_kie_runtime_config(
    model,
    endpoint,
    http_config,
    credential_environment_variable=(
        DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE
    ),
):
    """
    Build one Kie.ai runtime configuration.

    The endpoint is explicit because Kie supports more than one compatible
    provider route. Existing Chat Completions routes remain supported, while
    the production OpenAI-compatible Responses route receives its matching
    M89 request/response dialect pair.
    """
    try:
        parsed_endpoint = urlsplit(
            endpoint
        )

        if (
            type(endpoint) is str
            and parsed_endpoint.path
            == "/openai/v1/responses"
        ):
            request_dialect = (
                VisionProviderRequestDialect
                .KIE_OPENAI_RESPONSES_V1
            )
            response_dialect = (
                VisionProviderResponseDialect
                .KIE_RESPONSES_OUTPUT_TEXT_V1
            )

        else:
            request_dialect = (
                VisionProviderRequestDialect
                .KIE_OPENAI_CHAT_COMPLETIONS_V1
            )
            response_dialect = (
                VisionProviderResponseDialect
                .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1
            )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_preset_invalid"
        ) from None

    return _build_runtime_config(
        provider=(
            VisionProviderKind.KIE_AI
        ),
        endpoint=endpoint,
        model=model,
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        request_dialect=request_dialect,
        response_dialect=response_dialect,
        image_input_mode=(
            VisionProviderImageInputMode
            .REMOTE_URL
        ),
        credential_environment_variable=(
            credential_environment_variable
        ),
        credential_mode=(
            ProviderEnvironmentCredentialMode
            .BEARER
        ),
        http_config=http_config,
    )
