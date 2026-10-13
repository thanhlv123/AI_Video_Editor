"""M90 provider runtime factory.

This module assembles one complete provider-specific semantic vision runtime
from one validated, credential-free ProviderRuntimeConfig.

Assembly performs:
- no environment credential lookup;
- no DNS lookup;
- no network access;
- no image upload;
- no source snapshot acquisition.

The environment credential source is constructed during assembly, but the
secret itself is resolved only later when the HTTPS exchange executes.

For providers requiring a remotely reachable image URL, such as the current
Kie.ai profile, a ProviderVisionRemoteImageSource must be supplied explicitly.
"""

import copy

from ..external_vision_provider_transport import (
    ExternalVisionSemanticProvider,
)
from ..provider_specific_vision_adapter import (
    M88ProviderVisionHTTPExchange,
    ProviderSpecificVisionTransport,
    ProviderVisionRemoteImageSource,
    VisionProviderKind,
)
from ..semantic_vision_observer import (
    SemanticVisionObservationRuntime,
)
from .credential_source import (
    EnvironmentCredentialSource,
)
from .runtime_config import (
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)


class ProviderRuntimeAssembly:
    """
    Non-serializable runtime assembly.

    This object owns references to the runtime components created from one
    validated ProviderRuntimeConfig.

    It intentionally contains no resolved API secret.
    """

    __slots__ = (
        "_config",
        "_credential_source",
        "_exchange",
        "_transport",
        "_provider",
        "_runtime",
    )

    def __init__(
        self,
        config,
        credential_source,
        exchange,
        transport,
        provider,
        runtime,
    ):
        if type(config) is not ProviderRuntimeConfig:
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        if (
            type(credential_source)
            is not EnvironmentCredentialSource
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        if (
            type(exchange)
            is not M88ProviderVisionHTTPExchange
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        if (
            type(transport)
            is not ProviderSpecificVisionTransport
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        if (
            type(provider)
            is not ExternalVisionSemanticProvider
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        if (
            type(runtime)
            is not SemanticVisionObservationRuntime
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

        self._config = config
        self._credential_source = (
            credential_source
        )
        self._exchange = exchange
        self._transport = transport
        self._provider = provider
        self._runtime = runtime

    @property
    def config(
        self,
    ):
        return self._config

    @property
    def credential_source(
        self,
    ):
        return self._credential_source

    @property
    def exchange(
        self,
    ):
        return self._exchange

    @property
    def transport(
        self,
    ):
        return self._transport

    @property
    def provider(
        self,
    ):
        return self._provider

    @property
    def runtime(
        self,
    ):
        return self._runtime

    def __repr__(
        self,
    ):
        return (
            "ProviderRuntimeAssembly("
            f"provider={self._config.profile.provider.value!r}, "
            f"model={self._config.profile.model!r}, "
            f"environment_variable="
            f"{self._config.credential_environment_variable!r})"
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_runtime_assembly_noncopyable"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_runtime_assembly_noncopyable"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_runtime_assembly_nonserializable"
        )


def assemble_provider_runtime(
    config,
    remote_image_source=None,
):
    """
    Assemble one complete semantic vision runtime.

    No provider credential is resolved here.

    OpenAI and Gemini configurations reject a remote image source because their
    current M89 profiles use inline image data.

    Kie.ai requires a ProviderVisionRemoteImageSource because its current M89
    profile uses REMOTE_URL media.
    """
    try:
        validate_provider_runtime_config(
            config
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_assembly_invalid"
        ) from None

    if type(config) is not ProviderRuntimeConfig:
        raise ValueError(
            "provider_runtime_assembly_invalid"
        )

    if (
        config.profile.provider
        is VisionProviderKind.KIE_AI
    ):
        if not isinstance(
            remote_image_source,
            ProviderVisionRemoteImageSource,
        ):
            raise ValueError(
                "provider_runtime_assembly_invalid"
            )

    elif remote_image_source is not None:
        raise ValueError(
            "provider_runtime_assembly_invalid"
        )

    try:
        credential_source = (
            EnvironmentCredentialSource(
                config.credential_environment_variable,
                config.profile.credential_header,
                config.credential_mode,
            )
        )

        exchange = (
            M88ProviderVisionHTTPExchange(
                config.http_config,
                credential_source,
            )
        )

        transport = (
            ProviderSpecificVisionTransport(
                config.profile,
                exchange,
                remote_image_source,
            )
        )

        provider = ExternalVisionSemanticProvider(
            transport
        )

        runtime = SemanticVisionObservationRuntime(
            provider
        )

        result = ProviderRuntimeAssembly(
            config,
            credential_source,
            exchange,
            transport,
            provider,
            runtime,
        )

    except MemoryError:
        raise

    except Exception:
        raise ValueError(
            "provider_runtime_assembly_invalid"
        ) from None

    return result