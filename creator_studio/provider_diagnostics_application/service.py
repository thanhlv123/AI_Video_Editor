"""M95 provider diagnostics application service.

This module provides one application-level entry point over the existing
provider diagnostics pipeline:

    M95 request
        -> M93 diagnostics coordinator
        -> M94 diagnostic presenter
        -> M95 result

The service invokes the real upstream runtimes internally. Detached reports
or presentations do not grant execution authority.

Runtime-only dependencies:
- check;
- remote_image_source.

These dependencies are never stored in the detached M95 request or result.

The service preserves caller cancellation/check authority. Exceptions raised
by the caller-owned check callable are propagated and are never reclassified
as application failures.
"""

from ..provider_diagnostics_presentation.public_api import (
    ProviderDiagnosticPresenter,
    validate_provider_diagnostic_presentation,
)
from ..provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticsCoordinator,
    validate_provider_runtime_diagnostic_report,
)
from .models import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
    ProviderDiagnosticsApplicationResult,
    validate_provider_diagnostics_application_request,
    validate_provider_diagnostics_application_result,
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


def _build_result(
    presentation,
):
    try:
        result = ProviderDiagnosticsApplicationResult(
            schema_version=(
                PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
            ),
            presentation=presentation,
        )

        validate_provider_diagnostics_application_result(
            result
        )

    except MemoryError:
        raise

    except Exception:
        raise RuntimeError(
            "provider_diagnostics_application_internal"
        ) from None

    return result


class ProviderDiagnosticsApplicationService:
    """Stateless M93-to-M94 diagnostics application service."""

    __slots__ = ()

    def run(
        self,
        request,
        check,
        remote_image_source=None,
    ):
        """
        Execute one provider diagnostics application request.

        The detached request supplies only configuration and diagnostic mode.
        Runtime-only check/cancellation and remote-image dependencies are
        supplied directly to this method.
        """
        check()

        try:
            validate_provider_diagnostics_application_request(
                request
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "provider_diagnostics_application_request_invalid"
            ) from None

        if (
            type(request)
            is not ProviderDiagnosticsApplicationRequest
        ):
            raise ValueError(
                "provider_diagnostics_application_request_invalid"
            )

        guarded_check = _guard_check(
            check
        )

        try:
            coordinator = (
                ProviderRuntimeDiagnosticsCoordinator()
            )

            diagnostic_report = (
                coordinator.diagnose(
                    request.config,
                    request.mode,
                    guarded_check,
                    remote_image_source,
                )
            )

            validate_provider_runtime_diagnostic_report(
                diagnostic_report
            )

        except _CallerCheckFailure as exc:
            raise exc.error

        except MemoryError:
            raise

        except Exception:
            raise RuntimeError(
                "provider_diagnostics_application_internal"
            ) from None

        check()

        try:
            presenter = (
                ProviderDiagnosticPresenter()
            )

            presentation = presenter.present(
                diagnostic_report
            )

            validate_provider_diagnostic_presentation(
                presentation
            )

        except MemoryError:
            raise

        except Exception:
            raise RuntimeError(
                "provider_diagnostics_application_internal"
            ) from None

        check()

        result = _build_result(
            presentation
        )

        check()

        return result