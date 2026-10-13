"""M90 provider runtime configuration contract.

This module defines detached configuration data used to assemble one complete
provider-specific semantic vision runtime.

The configuration intentionally contains no API secret.

It contains only:
- one validated M89 provider profile;
- one validated M88 HTTP configuration;
- the name of the environment variable from which a secret will later be
  resolved;
- the credential formatting mode.

No environment lookup and no network access are performed here.
"""

from dataclasses import dataclass, fields

from ..external_vision_http_transport import (
    ExternalVisionHTTPConfig,
    ExternalVisionHTTPCredentialHeader,
    validate_external_vision_http_config,
)
from ..provider_specific_vision_adapter.models import (
    ProviderVisionProfile,
    validate_provider_vision_profile,
)
from .credential_source import (
    ProviderEnvironmentCredentialMode,
    _validate_environment_variable_name,
)


PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    """Detached, credential-free provider runtime configuration."""

    schema_version: int
    profile: ProviderVisionProfile
    http_config: ExternalVisionHTTPConfig
    credential_environment_variable: str
    credential_mode: ProviderEnvironmentCredentialMode


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


def _validate_credential_coherence(
    config,
):
    header = (
        config.profile.credential_header
    )

    mode = config.credential_mode

    if (
        header
        is ExternalVisionHTTPCredentialHeader
        .AUTHORIZATION
    ):
        if (
            mode
            is not ProviderEnvironmentCredentialMode
            .BEARER
        ):
            raise ValueError()

        return

    if (
        mode
        is not ProviderEnvironmentCredentialMode
        .RAW
    ):
        raise ValueError()


def validate_provider_runtime_config(
    config,
):
    """
    Validate one provider runtime configuration.

    Validation is deterministic and performs:
    - no environment access;
    - no DNS resolution;
    - no network access;
    - no credential resolution.
    """
    try:
        _validate_exact_shape(
            config,
            ProviderRuntimeConfig,
        )

        if (
            type(config.schema_version)
            is not int
            or config.schema_version
            != PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION
        ):
            raise ValueError()

        if (
            type(config.profile)
            is not ProviderVisionProfile
        ):
            raise ValueError()

        validate_provider_vision_profile(
            config.profile
        )

        if (
            type(config.http_config)
            is not ExternalVisionHTTPConfig
        ):
            raise ValueError()

        validate_external_vision_http_config(
            config.http_config
        )

        if (
            config.profile.endpoint
            != config.http_config.endpoint
        ):
            raise ValueError()

        _validate_environment_variable_name(
            config.credential_environment_variable
        )

        if (
            type(config.credential_mode)
            is not ProviderEnvironmentCredentialMode
        ):
            raise ValueError()

        _validate_credential_coherence(
            config
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_config_invalid"
        ) from None

    return config