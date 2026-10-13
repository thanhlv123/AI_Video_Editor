"""M90 provider runtime assembly public facade.

This module is the stable public facade for the complete M90 provider runtime
assembly feature.

Earlier package-level exports remain unchanged so their previously established
contracts do not need to be mutated.

Applications that want the complete M90 runtime assembly surface should import
from:

    creator_studio.provider_runtime_assembly.public_api

No API credential is resolved by importing this module.
No network access is performed by importing this module.
"""


from .credential_source import (
    MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
    EnvironmentCredentialSource,
    ProviderEnvironmentCredentialMode,
)
from .provider_presets import (
    DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE,
    DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE,
    DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE,
    GEMINI_VISION_ENDPOINT,
    OPENAI_VISION_ENDPOINT,
    build_gemini_runtime_config,
    build_kie_runtime_config,
    build_openai_runtime_config,
)
from .runtime_config import (
    PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION,
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from .runtime_factory import (
    ProviderRuntimeAssembly,
    assemble_provider_runtime,
)


PROVIDER_RUNTIME_PUBLIC_API_VERSION = 1


__all__ = (
    "DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE",
    "DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE",
    "DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE",
    "GEMINI_VISION_ENDPOINT",
    "MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH",
    "OPENAI_VISION_ENDPOINT",
    "PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION",
    "PROVIDER_RUNTIME_PUBLIC_API_VERSION",
    "EnvironmentCredentialSource",
    "ProviderEnvironmentCredentialMode",
    "ProviderRuntimeAssembly",
    "ProviderRuntimeConfig",
    "assemble_provider_runtime",
    "build_gemini_runtime_config",
    "build_kie_runtime_config",
    "build_openai_runtime_config",
    "validate_provider_runtime_config",
)