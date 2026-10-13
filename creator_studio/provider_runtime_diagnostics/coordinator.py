"""M93 provider runtime diagnostics coordinator.

This module coordinates the existing M91 offline readiness checker and the
M92 online connectivity probe.

OFFLINE mode:
    M91 readiness only.
    M92 is never constructed or executed.

ONLINE mode:
    M91 readiness always runs first.
    M92 runs only when M91 reports READY.

The coordinator never treats detached diagnostic reports as execution
authority. It invokes the real upstream runtimes internally and validates
their returned reports before normalization.

The original ``diagnose`` path preserves the existing M91/M92 environment-
backed credential behavior. M100 host integration may explicitly supply one
runtime credential-source factory through
``diagnose_with_credential_source_factory``. The same factory authority is
forwarded to both M91 and M92 and is never stored in the detached diagnostic
report.

Caller check/cancellation authority is preserved even when a supplied check
callable is invoked inside M91 or M92. Caller exceptions are never
reclassified as INTERNAL_FAILURE.
"""

from ..provider_connectivity_probe.public_api import (
    ProviderConnectivityProbe,
    ProviderConnectivityProbeStatus,
    validate_provider_connectivity_probe_report,
)
from ..provider_runtime_assembly import (
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from ..provider_runtime_readiness.public_api import (
    ProviderRuntimeReadinessChecker,
    ProviderRuntimeReadinessFailureCode,
    ProviderRuntimeReadinessOutcome,
    validate_provider_runtime_readiness_report,
)
from .models import (
    PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticReport,
    ProviderRuntimeDiagnosticStatus,
    validate_provider_runtime_diagnostic_report,
)


class _CallerCheckFailure(
    BaseException
):
    """Carries one exception raised by the caller-owned check callable."""

    __slots__ = (
        "error",
    )

    def __init__(
        self,
        error,
    ):
        self.error = error


def _guard_check(
    check,
):
    def guarded():
        try:
            check()

        except _CallerCheckFailure:
            raise

        except BaseException as exc:
            raise _CallerCheckFailure(
                exc
            ) from exc

    return guarded


def _build_report(
    *,
    mode,
    status,
    provider,
    credential_environment_variable,
    http_status=None,
    provider_code=None,
):
    try:
        report = ProviderRuntimeDiagnosticReport(
            schema_version=(
                PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
            ),
            mode=mode,
            status=status,
            provider=provider,
            credential_environment_variable=(
                credential_environment_variable
            ),
            http_status=http_status,
            provider_code=provider_code,
        )

        validate_provider_runtime_diagnostic_report(
            report
        )

    except MemoryError:
        raise

    except Exception:
        raise RuntimeError(
            "provider_runtime_diagnostic_internal"
        ) from None

    return report


def _config_invalid_report(
    mode,
):
    return _build_report(
        mode=mode,
        status=(
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        ),
        provider=None,
        credential_environment_variable=None,
        http_status=None,
        provider_code=None,
    )


def _config_metadata(
    config,
):
    try:
        validate_provider_runtime_config(
            config
        )

    except MemoryError:
        raise

    except Exception:
        return None

    if type(config) is not ProviderRuntimeConfig:
        return None

    return (
        config.profile.provider,
        config.credential_environment_variable,
    )


def _internal_report_from_config(
    mode,
    config,
):
    try:
        metadata = _config_metadata(
            config
        )

    except MemoryError:
        raise

    except Exception:
        metadata = None

    if metadata is None:
        return _config_invalid_report(
            mode
        )

    provider, environment_variable = (
        metadata
    )

    return _build_report(
        mode=mode,
        status=(
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE
        ),
        provider=provider,
        credential_environment_variable=(
            environment_variable
        ),
        http_status=None,
        provider_code=None,
    )


def _readiness_status(
    report,
):
    if (
        report.outcome
        is ProviderRuntimeReadinessOutcome
        .READY
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .READY
        )

    code = report.failure_code

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .CONFIG_INVALID
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        )

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .CREDENTIAL_MISSING
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING
        )

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .CREDENTIAL_INVALID
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID
        )

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .REMOTE_IMAGE_SOURCE_REQUIRED
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING
        )

    if (
        code
        is ProviderRuntimeReadinessFailureCode
        .INTERNAL_FAILURE
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE
        )

    raise ValueError()


def _report_from_readiness(
    mode,
    report,
):
    status = _readiness_status(
        report
    )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        return _config_invalid_report(
            mode
        )

    return _build_report(
        mode=mode,
        status=status,
        provider=report.provider,
        credential_environment_variable=(
            report.credential_environment_variable
        ),
        http_status=None,
        provider_code=None,
    )


def _connectivity_status(
    report,
):
    status = report.status

    if (
        status
        is ProviderConnectivityProbeStatus
        .READY
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .READY
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .CONFIG_INVALID
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .CREDENTIAL_MISSING
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .CREDENTIAL_INVALID
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .AUTHENTICATION_FAILED
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .PERMISSION_DENIED
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .PERMISSION_DENIED
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .RATE_LIMITED
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .PROVIDER_UNAVAILABLE
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .NETWORK_UNAVAILABLE
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .DEADLINE_EXCEEDED
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .RESPONSE_INVALID
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID
        )

    if (
        status
        is ProviderConnectivityProbeStatus
        .INTERNAL_FAILURE
    ):
        return (
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE
        )

    raise ValueError()


def _report_from_connectivity(
    report,
):
    status = _connectivity_status(
        report
    )

    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        return _config_invalid_report(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

    return _build_report(
        mode=(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=status,
        provider=report.provider,
        credential_environment_variable=(
            report.credential_environment_variable
        ),
        http_status=report.http_status,
        provider_code=report.provider_code,
    )


class ProviderRuntimeDiagnosticsCoordinator:
    """Stateless M91/M92 provider diagnostics coordinator."""

    __slots__ = ()

    def diagnose(
        self,
        config,
        mode,
        check,
        remote_image_source=None,
    ):
        """
        Diagnose one provider runtime configuration using the original
        environment-backed M91/M92 credential path.

        OFFLINE performs M91 readiness only.

        ONLINE performs M91 readiness first and invokes M92 connectivity only
        when readiness reports READY.
        """
        return self._diagnose(
            config,
            mode,
            check,
            remote_image_source,
            credential_source_factory=None,
            use_credential_source_factory=False,
        )

    def diagnose_with_credential_source_factory(
        self,
        config,
        mode,
        check,
        credential_source_factory,
        remote_image_source=None,
    ):
        """
        Diagnose one provider runtime configuration using one caller-supplied
        runtime credential-source factory.

        The same runtime authority is forwarded to M91 readiness and, when
        ONLINE readiness succeeds, to M92 connectivity. The factory is never
        retained by this stateless coordinator and never enters a detached
        diagnostic report.
        """
        return self._diagnose(
            config,
            mode,
            check,
            remote_image_source,
            credential_source_factory=(
                credential_source_factory
            ),
            use_credential_source_factory=True,
        )

    def _diagnose(
        self,
        config,
        mode,
        check,
        remote_image_source,
        *,
        credential_source_factory,
        use_credential_source_factory,
    ):
        check()

        if (
            type(mode)
            is not ProviderRuntimeDiagnosticMode
        ):
            raise ValueError(
                "provider_runtime_diagnostic_mode_invalid"
            )

        guarded_check = _guard_check(
            check
        )

        try:
            readiness_checker = (
                ProviderRuntimeReadinessChecker()
            )

            if use_credential_source_factory:
                readiness_report = (
                    readiness_checker
                    .check_with_credential_source_factory(
                        config,
                        guarded_check,
                        credential_source_factory,
                        remote_image_source,
                    )
                )

            else:
                readiness_report = (
                    readiness_checker.check(
                        config,
                        guarded_check,
                        remote_image_source,
                    )
                )

            validate_provider_runtime_readiness_report(
                readiness_report
            )

        except _CallerCheckFailure as exc:
            raise exc.error

        except MemoryError:
            return _internal_report_from_config(
                mode,
                config,
            )

        except Exception:
            return _internal_report_from_config(
                mode,
                config,
            )

        if (
            readiness_report.outcome
            is not ProviderRuntimeReadinessOutcome
            .READY
        ):
            try:
                return _report_from_readiness(
                    mode,
                    readiness_report,
                )

            except MemoryError:
                return _internal_report_from_config(
                    mode,
                    config,
                )

            except Exception:
                return _internal_report_from_config(
                    mode,
                    config,
                )

        if (
            mode
            is ProviderRuntimeDiagnosticMode
            .OFFLINE
        ):
            try:
                return _report_from_readiness(
                    mode,
                    readiness_report,
                )

            except MemoryError:
                return _internal_report_from_config(
                    mode,
                    config,
                )

            except Exception:
                return _internal_report_from_config(
                    mode,
                    config,
                )

        check()

        try:
            connectivity_probe = (
                ProviderConnectivityProbe()
            )

            if use_credential_source_factory:
                connectivity_report = (
                    connectivity_probe
                    .probe_with_credential_source_factory(
                        config,
                        guarded_check,
                        credential_source_factory,
                    )
                )

            else:
                connectivity_report = (
                    connectivity_probe.probe(
                        config,
                        guarded_check,
                    )
                )

            validate_provider_connectivity_probe_report(
                connectivity_report
            )

        except _CallerCheckFailure as exc:
            raise exc.error

        except MemoryError:
            return _internal_report_from_config(
                mode,
                config,
            )

        except Exception:
            return _internal_report_from_config(
                mode,
                config,
            )

        try:
            return _report_from_connectivity(
                connectivity_report
            )

        except MemoryError:
            return _internal_report_from_config(
                mode,
                config,
            )

        except Exception:
            return _internal_report_from_config(
                mode,
                config,
            )