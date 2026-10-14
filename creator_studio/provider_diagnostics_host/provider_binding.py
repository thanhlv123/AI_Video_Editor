"""M100 provider diagnostics host provider/profile binding.

This module binds one validated M90 provider runtime configuration to the
single APIKeyManager profile that is allowed to supply its credential.

The binding is intentionally small and secret-free.

Canonical bindings:

    VisionProviderKind.OPENAI
        -> APIKeyManager profile "openai"

    VisionProviderKind.GEMINI
        -> APIKeyManager profile "gemini"

    VisionProviderKind.KIE_AI
        -> APIKeyManager profile "kie_ai"

Security properties:

- provider identity must use the exact VisionProviderKind enum;
- runtime config must use the exact ProviderRuntimeConfig type;
- no API secret is read here;
- runtime_environment() is never used;
- no process environment mutation occurs;
- no network access occurs;
- the returned credential-source factory still performs the final profile /
  environment metadata match when M91 or M92 actually asks it for a source.

This module is currently an internal M100 host primitive. It is deliberately
not exported through provider_diagnostics_host.public_api until the complete
host integration surface is finalized.
"""

from config.api_key_manager import (
    APIKeyManager,
)

from ..provider_runtime_assembly import (
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)
from .credential_source import (
    APIKeyManagerCredentialSourceFactory,
)


OPENAI_API_KEY_MANAGER_PROFILE_ID = (
    "openai"
)

GEMINI_API_KEY_MANAGER_PROFILE_ID = (
    "gemini"
)

KIE_AI_API_KEY_MANAGER_PROFILE_ID = (
    "kie_ai"
)


def _provider_invalid():
    raise ValueError(
        "provider_diagnostics_host_provider_invalid"
    )


def _binding_invalid():
    raise ValueError(
        "provider_diagnostics_host_binding_invalid"
    )


def api_key_manager_profile_id_for_provider(
    provider,
):
    """Return the single canonical APIKeyManager profile for one provider."""
    if (
        type(provider)
        is not VisionProviderKind
    ):
        _provider_invalid()

    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        return (
            OPENAI_API_KEY_MANAGER_PROFILE_ID
        )

    if (
        provider
        is VisionProviderKind.GEMINI
    ):
        return (
            GEMINI_API_KEY_MANAGER_PROFILE_ID
        )

    if (
        provider
        is VisionProviderKind.KIE_AI
    ):
        return (
            KIE_AI_API_KEY_MANAGER_PROFILE_ID
        )

    _provider_invalid()


def bind_api_key_manager_credential_source_factory(
    api_key_manager,
    config,
):
    """
    Bind one exact M90 runtime config to its canonical APIKeyManager profile.

    This operation grants runtime credential-store authority to the returned
    factory but performs no secret lookup itself.
    """
    if (
        type(api_key_manager)
        is not APIKeyManager
    ):
        _binding_invalid()

    try:
        validate_provider_runtime_config(
            config
        )

    except MemoryError:
        raise

    except Exception:
        _binding_invalid()

    if (
        type(config)
        is not ProviderRuntimeConfig
    ):
        _binding_invalid()

    try:
        profile_id = (
            api_key_manager_profile_id_for_provider(
                config.profile.provider
            )
        )

    except MemoryError:
        raise

    except Exception:
        _binding_invalid()

    try:
        factory = (
            APIKeyManagerCredentialSourceFactory(
                api_key_manager,
                profile_id,
            )
        )

    except MemoryError:
        raise

    except Exception:
        _binding_invalid()

    return factory