"""M91 provider runtime readiness checker.

This module determines whether one M90 provider runtime configuration is ready
for execution without contacting the provider.

Readiness checks may:
- validate detached provider runtime configuration;
- verify the required runtime remote-image dependency is present;
- resolve and validate the configured environment credential.

Readiness checks never:
- open a network connection;
- perform DNS resolution;
- upload media;
- invoke the provider API;
- return the resolved credential;
- persist the resolved credential in a readiness report.

The credential is resolved only to prove that the configured runtime secret is
currently present and structurally valid.
"""

from ..external_vision_http_transport import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
)
from ..provider_runtime_assembly import (
    EnvironmentCredentialSource,
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from ..provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
    VisionProviderKind,
)
from .models import (
    PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION,
    ProviderRuntimeReadinessFailureCode,
    ProviderRuntimeReadinessOutcome,
    ProviderRuntimeReadinessReport,
    validate_provider_runtime_readiness_report,
)


def _build_report(
    *,
    outcome,
    failure_code,
    provider,
    credential_environment_variable,
):
    try:
        report = ProviderRuntimeReadinessReport(
            schema_version=(
                PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
            ),
            outcome=outcome,
            failure_code=failure_code,
            provider=provider,
            credential_environment_variable=(
                credential_environment_variable
            ),
        )

        validate_provider_runtime_readiness_report(
            report
        )

    except MemoryError:
        raise

    except Exception:
        raise RuntimeError(
            "provider_runtime_readiness_internal"
        ) from None

    return report


def _config_invalid_report():
    return _build_report(
        outcome=(
            ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            ProviderRuntimeReadinessFailureCode
            .CONFIG_INVALID
        ),
        provider=None,
        credential_environment_variable=None,
    )


def _metadata_failure_report(
    config,
    failure_code,
):
    return _build_report(
        outcome=(
            ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=failure_code,
        provider=config.profile.provider,
        credential_environment_variable=(
            config.credential_environment_variable
        ),
    )


def _ready_report(
    config,
):
    return _build_report(
        outcome=(
            ProviderRuntimeReadinessOutcome
            .READY
        ),
        failure_code=None,
        provider=config.profile.provider,
        credential_environment_variable=(
            config.credential_environment_variable
        ),
    )


def _map_credential_failure(
    code,
):
    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .UNAVAILABLE
    ):
        return (
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING
        )

    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .INVALID
    ):
        return (
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID
        )

    return (
        ProviderRuntimeReadinessFailureCode
        .INTERNAL_FAILURE
    )


class ProviderRuntimeReadinessChecker:
    """Stateless provider runtime readiness checker."""

    __slots__ = ()

    def check(
        self,
        config,
        check,
        remote_image_source=None,
    ):
        """
        Check one provider runtime configuration without provider network I/O.

        The supplied check callable is intentionally allowed to propagate its
        own exceptions and BaseException subclasses. This preserves caller
        cancellation and deadline authority.
        """
        check()

        try:
            validate_provider_runtime_config(
                config
            )

        except MemoryError:
            return _config_invalid_report()

        except Exception:
            return _config_invalid_report()

        if type(config) is not ProviderRuntimeConfig:
            return _config_invalid_report()

        check()

        if (
            config.profile.provider
            is VisionProviderKind.KIE_AI
        ):
            if not isinstance(
                remote_image_source,
                ProviderVisionRemoteImageSource,
            ):
                return _metadata_failure_report(
                    config,
                    (
                        ProviderRuntimeReadinessFailureCode
                        .REMOTE_IMAGE_SOURCE_REQUIRED
                    ),
                )

        check()

        try:
            credential_source = (
                EnvironmentCredentialSource(
                    config.credential_environment_variable,
                    config.profile.credential_header,
                    config.credential_mode,
                )
            )

        except MemoryError:
            return _metadata_failure_report(
                config,
                (
                    ProviderRuntimeReadinessFailureCode
                    .INTERNAL_FAILURE
                ),
            )

        except Exception:
            return _metadata_failure_report(
                config,
                (
                    ProviderRuntimeReadinessFailureCode
                    .INTERNAL_FAILURE
                ),
            )

        check()

        try:
            credential = credential_source.resolve(
                check
            )

        except ExternalVisionHTTPCredentialFailure as exc:
            return _metadata_failure_report(
                config,
                _map_credential_failure(
                    exc.code
                ),
            )

        except MemoryError:
            return _metadata_failure_report(
                config,
                (
                    ProviderRuntimeReadinessFailureCode
                    .INTERNAL_FAILURE
                ),
            )

        except Exception:
            return _metadata_failure_report(
                config,
                (
                    ProviderRuntimeReadinessFailureCode
                    .INTERNAL_FAILURE
                ),
            )

        check()

        del credential

        check()

        return _ready_report(
            config
        )