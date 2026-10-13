"""M95 provider diagnostics application service."""

import copy
import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_diagnostics_application.service as service_module

from creator_studio.provider_diagnostics_application import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
    ProviderDiagnosticsApplicationResult,
    validate_provider_diagnostics_application_result,
)
from creator_studio.provider_diagnostics_application.service import (
    ProviderDiagnosticsApplicationService,
)
from creator_studio.provider_diagnostics_presentation import (
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
)
from creator_studio.provider_runtime_diagnostics import (
    PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticReport,
    ProviderRuntimeDiagnosticStatus,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    kie_runtime_config,
    openai_runtime_config,
)


def application_request(
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
    config=None,
):
    if config is None:
        config = openai_runtime_config()

    return ProviderDiagnosticsApplicationRequest(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=config,
        mode=mode,
    )


def diagnostic_report(
    *,
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
    status=ProviderRuntimeDiagnosticStatus.READY,
    provider=VisionProviderKind.OPENAI,
):
    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        return ProviderRuntimeDiagnosticReport(
            schema_version=(
                PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
            ),
            mode=mode,
            status=status,
            provider=None,
            credential_environment_variable=None,
            http_status=None,
            provider_code=None,
        )

    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        environment_variable = (
            "OPENAI_API_KEY"
        )

    elif (
        provider
        is VisionProviderKind.GEMINI
    ):
        environment_variable = (
            "GEMINI_API_KEY"
        )

    elif (
        provider
        is VisionProviderKind.KIE_AI
    ):
        environment_variable = (
            "KIE_API_KEY"
        )

    else:
        raise ValueError()

    http_status = None
    provider_code = None

    if (
        mode
        is ProviderRuntimeDiagnosticMode
        .ONLINE
        and status
        is ProviderRuntimeDiagnosticStatus
        .READY
    ):
        http_status = 200

        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            provider_code = 200

    return ProviderRuntimeDiagnosticReport(
        schema_version=(
            PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=status,
        provider=provider,
        credential_environment_variable=(
            environment_variable
        ),
        http_status=http_status,
        provider_code=provider_code,
    )


def presentation(
    *,
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
    status=ProviderRuntimeDiagnosticStatus.READY,
    provider=VisionProviderKind.OPENAI,
):
    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        provider_value = None
        environment_variable = None
        severity = (
            ProviderDiagnosticPresentationSeverity
            .ERROR
        )
        action = (
            ProviderDiagnosticPresentationAction
            .REVIEW_CONFIGURATION
        )
        title = "Configuration invalid"
        detail = (
            "Review the provider runtime configuration."
        )

    else:
        provider_value = provider

        if (
            provider
            is VisionProviderKind.OPENAI
        ):
            environment_variable = (
                "OPENAI_API_KEY"
            )

        elif (
            provider
            is VisionProviderKind.GEMINI
        ):
            environment_variable = (
                "GEMINI_API_KEY"
            )

        elif (
            provider
            is VisionProviderKind.KIE_AI
        ):
            environment_variable = (
                "KIE_API_KEY"
            )

        else:
            raise ValueError()

        severity = (
            ProviderDiagnosticPresentationSeverity
            .SUCCESS
        )

        action = (
            ProviderDiagnosticPresentationAction
            .NONE
        )

        title = "Ready"

        if (
            mode
            is ProviderRuntimeDiagnosticMode
            .ONLINE
        ):
            detail = (
                "Provider configuration and connectivity are ready."
            )

        else:
            detail = (
                "Provider configuration is ready."
            )

    return ProviderDiagnosticPresentation(
        schema_version=(
            PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
        ),
        mode=mode,
        diagnostic_status=status,
        severity=severity,
        action=action,
        provider=provider_value,
        credential_environment_variable=(
            environment_variable
        ),
        title=title,
        detail=detail,
    )


class ProviderDiagnosticsApplicationServiceTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.service = (
            ProviderDiagnosticsApplicationService()
        )

    def test_service_is_stateless(self):
        self.assertEqual(
            ProviderDiagnosticsApplicationService
            .__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.service,
                "__dict__",
            )
        )

    def test_run_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderDiagnosticsApplicationService
                    .run
                ).parameters
            ),
            (
                "self",
                "request",
                "check",
                "remote_image_source",
            ),
        )

    def test_offline_request_calls_coordinator_then_presenter(self):
        request = application_request()

        report = diagnostic_report()

        rendered = presentation()

        events = []

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            def run_diagnostic(
                config,
                mode,
                check,
                remote_image_source=None,
            ):
                events.append(
                    "diagnose"
                )

                return report

            coordinator_type.return_value.diagnose.side_effect = (
                run_diagnostic
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                def run_present(
                    source,
                ):
                    events.append(
                        "present"
                    )

                    return rendered

                presenter_type.return_value.present.side_effect = (
                    run_present
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertEqual(
            events,
            [
                "diagnose",
                "present",
            ],
        )

        self.assertIs(
            result.presentation,
            rendered,
        )

    def test_online_request_calls_coordinator_and_presenter(self):
        request = application_request(
            ProviderRuntimeDiagnosticMode.ONLINE
        )

        report = diagnostic_report(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            )
        )

        rendered = presentation(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            )
        )

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                report
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    rendered
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            result.presentation,
            rendered,
        )

    def test_coordinator_receives_request_config_and_mode(self):
        request = application_request(
            ProviderRuntimeDiagnosticMode.ONLINE
        )

        report = diagnostic_report(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            )
        )

        rendered = presentation(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            )
        )

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                report
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    rendered
                )

                self.service.run(
                    request,
                    lambda: None,
                )

        call = (
            coordinator_type
            .return_value
            .diagnose
            .call_args
        )

        self.assertIs(
            call.args[
                0
            ],
            request.config,
        )

        self.assertIs(
            call.args[
                1
            ],
            request.mode,
        )

    def test_remote_source_forwarded_at_runtime_only(self):
        request = application_request(
            ProviderRuntimeDiagnosticMode.ONLINE,
            kie_runtime_config(),
        )

        report = diagnostic_report(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            provider=VisionProviderKind.KIE_AI,
        )

        rendered = presentation(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            provider=VisionProviderKind.KIE_AI,
        )

        remote_source = object()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                report
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    rendered
                )

                result = self.service.run(
                    request,
                    lambda: None,
                    remote_source,
                )

        call = (
            coordinator_type
            .return_value
            .diagnose
            .call_args
        )

        self.assertIs(
            call.args[
                3
            ],
            remote_source,
        )

        self.assertFalse(
            hasattr(
                request,
                "remote_image_source",
            )
        )

        self.assertFalse(
            hasattr(
                result,
                "remote_image_source",
            )
        )

    def test_presenter_receives_coordinator_report(self):
        request = application_request()

        report = diagnostic_report()

        rendered = presentation()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                report
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    rendered
                )

                self.service.run(
                    request,
                    lambda: None,
                )

        presenter_type.return_value.present.assert_called_once_with(
            report
        )

    def test_result_contract(self):
        request = application_request()

        report = diagnostic_report()

        rendered = presentation()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                report
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    rendered
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertIs(
            type(result),
            ProviderDiagnosticsApplicationResult,
        )

        self.assertEqual(
            result.schema_version,
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
        )

        self.assertIs(
            result.presentation,
            rendered,
        )

        self.assertIs(
            validate_provider_diagnostics_application_result(
                result
            ),
            result,
        )

    def test_result_contains_no_diagnostic_report(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    presentation()
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertNotIn(
            "diagnostic_report",
            result.__dict__,
        )

        self.assertEqual(
            set(
                result.__dict__
            ),
            {
                "schema_version",
                "presentation",
            },
        )

    def test_request_not_mutated(self):
        request = application_request()

        before = copy.deepcopy(
            request
        )

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    presentation()
                )

                self.service.run(
                    request,
                    lambda: None,
                )

        self.assertEqual(
            request,
            before,
        )

    def test_invalid_request_prevents_coordinator_and_presenter(self):
        request = object()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_request_invalid$",
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

        coordinator_type.assert_not_called()
        presenter_type.assert_not_called()

    def test_forged_request_prevents_execution(self):
        request = copy.copy(
            application_request()
        )

        object.__setattr__(
            request,
            "extra",
            "unexpected",
        )

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_request_invalid$",
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

        coordinator_type.assert_not_called()
        presenter_type.assert_not_called()

    def test_invalid_coordinator_report_is_internal_failure(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                object()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^provider_diagnostics_application_internal$",
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

        presenter_type.assert_not_called()

    def test_invalid_presenter_output_is_internal_failure(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    object()
                )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "^provider_diagnostics_application_internal$",
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

    def test_coordinator_unexpected_exception_is_sanitized(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.side_effect = (
                RuntimeError(
                    "private-coordinator-error"
                )
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "^provider_diagnostics_application_internal$",
            ):
                self.service.run(
                    request,
                    lambda: None,
                )

    def test_presenter_unexpected_exception_is_sanitized(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.side_effect = (
                    RuntimeError(
                        "private-presenter-error"
                    )
                )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "^provider_diagnostics_application_internal$",
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

    def test_coordinator_memory_error_not_swallowed(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.side_effect = (
                MemoryError()
            )

            with self.assertRaises(
                MemoryError
            ):
                self.service.run(
                    request,
                    lambda: None,
                )

    def test_presenter_memory_error_not_swallowed(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.side_effect = (
                    MemoryError()
                )

                with self.assertRaises(
                    MemoryError
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

    def test_coordinator_baseexception_not_swallowed(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.side_effect = (
                KeyboardInterrupt()
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.service.run(
                    request,
                    lambda: None,
                )

    def test_presenter_baseexception_not_swallowed(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.side_effect = (
                    KeyboardInterrupt()
                )

                with self.assertRaises(
                    KeyboardInterrupt
                ):
                    self.service.run(
                        request,
                        lambda: None,
                    )

    def test_initial_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "caller-check"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^caller-check$",
        ):
            self.service.run(
                application_request(),
                check,
            )

    def test_check_exception_inside_coordinator_not_swallowed(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            if (
                calls[
                    0
                ]
                == 2
            ):
                raise RuntimeError(
                    "nested-caller-check"
                )

        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            def run_diagnostic(
                config,
                mode,
                supplied_check,
                remote_image_source=None,
            ):
                supplied_check()

                return diagnostic_report()

            coordinator_type.return_value.diagnose.side_effect = (
                run_diagnostic
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "^nested-caller-check$",
            ):
                self.service.run(
                    request,
                    check,
                )

    def test_check_baseexception_inside_coordinator_not_swallowed(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            if (
                calls[
                    0
                ]
                == 2
            ):
                raise KeyboardInterrupt()

        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            def run_diagnostic(
                config,
                mode,
                supplied_check,
                remote_image_source=None,
            ):
                supplied_check()

                return diagnostic_report()

            coordinator_type.return_value.diagnose.side_effect = (
                run_diagnostic
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.service.run(
                    request,
                    check,
                )

    def test_check_runs_at_service_boundaries(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    presentation()
                )

                result = self.service.run(
                    request,
                    check,
                )

        self.assertIs(
            result.presentation.diagnostic_status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            4,
        )

    def test_detached_presentation_cannot_skip_coordinator(self):
        request = application_request()

        detached = presentation()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    detached
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        coordinator_type.return_value.diagnose.assert_called_once()

        self.assertIs(
            result.presentation,
            detached,
        )

    def test_result_never_contains_runtime_check(self):
        request = application_request()

        with patch.object(
            service_module,
            "ProviderRuntimeDiagnosticsCoordinator",
        ) as coordinator_type:
            coordinator_type.return_value.diagnose.return_value = (
                diagnostic_report()
            )

            with patch.object(
                service_module,
                "ProviderDiagnosticPresenter",
            ) as presenter_type:
                presenter_type.return_value.present.return_value = (
                    presentation()
                )

                result = self.service.run(
                    request,
                    lambda: None,
                )

        self.assertFalse(
            hasattr(
                result,
                "check",
            )
        )

        self.assertFalse(
            hasattr(
                request,
                "check",
            )
        )

    def test_all_outputs_validate(self):
        cases = (
            (
                application_request(),
                diagnostic_report(),
                presentation(),
            ),
            (
                application_request(
                    ProviderRuntimeDiagnosticMode.ONLINE
                ),
                diagnostic_report(
                    mode=(
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    )
                ),
                presentation(
                    mode=(
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    )
                ),
            ),
            (
                application_request(
                    ProviderRuntimeDiagnosticMode.ONLINE,
                    kie_runtime_config(),
                ),
                diagnostic_report(
                    mode=(
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    provider=VisionProviderKind.KIE_AI,
                ),
                presentation(
                    mode=(
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    provider=VisionProviderKind.KIE_AI,
                ),
            ),
        )

        for (
            request,
            report,
            rendered,
        ) in cases:
            with self.subTest(
                mode=request.mode,
                provider=report.provider,
            ):
                with patch.object(
                    service_module,
                    "ProviderRuntimeDiagnosticsCoordinator",
                ) as coordinator_type:
                    coordinator_type.return_value.diagnose.return_value = (
                        report
                    )

                    with patch.object(
                        service_module,
                        "ProviderDiagnosticPresenter",
                    ) as presenter_type:
                        presenter_type.return_value.present.return_value = (
                            rendered
                        )

                        result = self.service.run(
                            request,
                            lambda: None,
                        )

                self.assertIs(
                    validate_provider_diagnostics_application_result(
                        result
                    ),
                    result,
                )


if __name__ == "__main__":
    unittest.main()