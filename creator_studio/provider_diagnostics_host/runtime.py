"""M100 provider diagnostics host runtime assembly.

This module is the narrow application-host boundary between the existing
APIKeyManager-backed credential authority and the M99 diagnostics Qt binder.

Architecture:

    APIKeyManager
        +
    ProviderDiagnosticsApplicationRequest
        +
    ProviderDiagnosticsQtViewBinder
        |
        v
    ProviderDiagnosticsHost.start(...)
        |
        +-> bind_api_key_manager_credential_source_factory(...)
        |
        +-> binder.start_with_credential_source_factory(...)
        |
        v
    M99 -> M98 -> M97 -> M95 -> M93 -> M91/M92

Security properties:

- the host stores no APIKeyManager authority;
- the host stores no binder;
- the host stores no diagnostic request;
- the host stores no credential-source factory;
- the host reads no secret;
- the host does not call APIKeyManager.runtime_environment();
- the host does not modify process environment variables;
- the host performs no network operation itself;
- the credential-source factory exists only as one runtime handoff;
- detached request/config objects remain secret-free.

The runtime host is deliberately stateless.
"""

from config.api_key_manager import (
    APIKeyManager,
)

from ..provider_diagnostics_application.public_api import (
    ProviderDiagnosticsApplicationRequest,
)
from ..provider_diagnostics_qt_view.binding_api import (
    ProviderDiagnosticsQtViewBinder,
)
from .provider_binding import (
    bind_api_key_manager_credential_source_factory,
)


def _host_invalid():
    raise ValueError(
        "provider_diagnostics_host_invalid"
    )


class ProviderDiagnosticsHost:
    """Stateless runtime assembler for provider diagnostics."""

    __slots__ = ()

    def start(
        self,
        api_key_manager,
        binder,
        request,
        remote_image_source=None,
    ):
        """
        Start one provider diagnostic execution through the M100 host path.

        All authority-bearing objects are supplied by the caller for this
        invocation only. Nothing is retained on the host instance.
        """
        if (
            type(api_key_manager)
            is not APIKeyManager
        ):
            _host_invalid()

        if (
            type(binder)
            is not ProviderDiagnosticsQtViewBinder
        ):
            _host_invalid()

        if (
            type(request)
            is not ProviderDiagnosticsApplicationRequest
        ):
            _host_invalid()

        try:
            credential_source_factory = (
                bind_api_key_manager_credential_source_factory(
                    api_key_manager,
                    request.config,
                )
            )

        except MemoryError:
            raise

        except ValueError:
            raise

        except Exception:
            raise RuntimeError(
                "provider_diagnostics_host_internal"
            ) from None

        try:
            state = (
                binder
                .start_with_credential_source_factory(
                    request,
                    credential_source_factory,
                    remote_image_source,
                )
            )

        except MemoryError:
            raise

        finally:
            del credential_source_factory

        return state

    def __copy__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_host_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "provider_diagnostics_host_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "provider_diagnostics_host_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "ProviderDiagnosticsHost()"
        )