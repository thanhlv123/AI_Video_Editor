"""M100 provider diagnostics detached request assembly.

This module builds one secret-free M95 provider diagnostics request from the
application's existing APIKeyManager metadata.

The current GUI pipeline uses KIE AI as its required AI provider, so this
checkpoint intentionally assembles only the KIE diagnostics request. Runtime
credential authority remains outside the request and is granted later by the
M100 host when execution starts.

Security properties:

- the builder stores no APIKeyManager authority;
- the builder stores no profile metadata;
- only APIKeyManager.get_profile("kie_ai") is consulted;
- get_secret() is never called;
- runtime_environment() is never called;
- runtime_provider_settings() is never called;
- no process environment mutation occurs;
- no DNS or network operation occurs;
- no resolved credential is inserted into the request or runtime config;
- the KIE provider endpoint is the same fixed production Responses endpoint
  used by the current application pipeline.
"""

from config.api_key_manager import (
    APIKeyManager,
)

from ..external_vision_http_transport import (
    EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION,
    MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES,
    MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES,
    ExternalVisionHTTPConfig,
    ExternalVisionHTTPHeaderPolicy,
)
from ..provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
    validate_provider_diagnostics_application_request,
)
from ..provider_runtime_assembly.public_api import (
    build_kie_runtime_config,
)
from ..provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)


KIE_AI_DIAGNOSTICS_PROFILE_ID = (
    "kie_ai"
)

KIE_AI_DIAGNOSTICS_ENDPOINT = (
    "https://api.kie.ai"
    "/openai/v1/responses"
)

PROVIDER_DIAGNOSTICS_REQUEST_TIMEOUT_MILLIS = (
    10_000
)


def _builder_invalid():
    raise ValueError(
        "provider_diagnostics_request_builder_invalid"
    )


def _builder_internal():
    raise RuntimeError(
        "provider_diagnostics_request_builder_internal"
    )


def _read_kie_profile_metadata(
    api_key_manager,
):
    try:
        profile = (
            api_key_manager.get_profile(
                KIE_AI_DIAGNOSTICS_PROFILE_ID
            )
        )

    except MemoryError:
        raise

    except Exception:
        _builder_internal()

    if type(profile) is not dict:
        _builder_invalid()

    if (
        profile.get("id")
        != KIE_AI_DIAGNOSTICS_PROFILE_ID
    ):
        _builder_invalid()

    model = profile.get(
        "model"
    )

    if (
        type(model) is not str
        or not model
        or model != model.strip()
    ):
        _builder_invalid()

    credential_environment_variable = (
        profile.get(
            "env_var"
        )
    )

    if (
        type(credential_environment_variable)
        is not str
        or not credential_environment_variable
        or credential_environment_variable
        != credential_environment_variable.strip()
    ):
        _builder_invalid()

    fields = profile.get(
        "fields",
        [],
    )

    if fields is None:
        fields = []

    if (
        type(fields) is not list
        or fields
    ):
        _builder_invalid()

    return (
        model,
        credential_environment_variable,
    )


def _build_http_config():
    try:
        return ExternalVisionHTTPConfig(
            schema_version=(
                EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION
            ),
            endpoint=(
                KIE_AI_DIAGNOSTICS_ENDPOINT
            ),
            timeout_millis=(
                PROVIDER_DIAGNOSTICS_REQUEST_TIMEOUT_MILLIS
            ),
            max_request_bytes=(
                MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
            ),
            max_response_bytes=(
                MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
            ),
            header_policy=(
                ExternalVisionHTTPHeaderPolicy
                .STRICT_JSON_V1
            ),
        )

    except MemoryError:
        raise

    except Exception:
        _builder_invalid()


def _build_kie_request(
    api_key_manager,
    mode,
):
    if (
        type(api_key_manager)
        is not APIKeyManager
    ):
        _builder_invalid()

    if (
        type(mode)
        is not ProviderRuntimeDiagnosticMode
    ):
        _builder_invalid()

    (
        model,
        credential_environment_variable,
    ) = _read_kie_profile_metadata(
        api_key_manager
    )

    try:
        config = build_kie_runtime_config(
            model=model,
            endpoint=(
                KIE_AI_DIAGNOSTICS_ENDPOINT
            ),
            http_config=(
                _build_http_config()
            ),
            credential_environment_variable=(
                credential_environment_variable
            ),
        )

        request = (
            ProviderDiagnosticsApplicationRequest(
                schema_version=(
                    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
                ),
                config=config,
                mode=mode,
            )
        )

        validate_provider_diagnostics_application_request(
            request
        )

    except MemoryError:
        raise

    except ValueError:
        _builder_invalid()

    except Exception:
        _builder_internal()

    return request


class ProviderDiagnosticsRequestBuilder:
    """Stateless builder for detached provider diagnostics requests."""

    __slots__ = ()

    def build_kie(
        self,
        api_key_manager,
        mode,
    ):
        """Build one KIE diagnostics request without resolving a secret."""
        return _build_kie_request(
            api_key_manager,
            mode,
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_request_builder_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_request_builder_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_request_builder_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsRequestBuilder()"
        )
