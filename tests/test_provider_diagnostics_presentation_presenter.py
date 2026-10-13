"""M94 provider diagnostic presenter."""

import copy
import dataclasses
import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_presentation.presenter as presenter_module

from creator_studio.provider_diagnostics_presentation import (
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
    validate_provider_diagnostic_presentation,
)
from creator_studio.provider_diagnostics_presentation.presenter import (
    ProviderDiagnosticPresenter,
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


def source_report(
    status=ProviderRuntimeDiagnosticStatus.READY,
    *,
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
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
    ):
        if (
            status
            is ProviderRuntimeDiagnosticStatus
            .READY
        ):
            http_status = 200

            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                provider_code = 200

        elif (
            status
            is ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED
        ):
            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                http_status = 200
                provider_code = 401

            else:
                http_status = 401

        elif (
            status
            is ProviderRuntimeDiagnosticStatus
            .PERMISSION_DENIED
        ):
            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                http_status = 200
                provider_code = 403

            else:
                http_status = 403

        elif (
            status
            is ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED
        ):
            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                http_status = 200
                provider_code = 429

            else:
                http_status = 429

        elif (
            status
            is ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE
        ):
            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                http_status = 200
                provider_code = 503

            else:
                http_status = 503

        elif (
            status
            is ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID
        ):
            if (
                provider
                is VisionProviderKind.KIE_AI
            ):
                http_status = 200
                provider_code = 422

            else:
                http_status = 422

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


class ProviderDiagnosticPresenterTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.presenter = (
            ProviderDiagnosticPresenter()
        )

    def test_presenter_is_stateless(self):
        self.assertEqual(
            ProviderDiagnosticPresenter.__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.presenter,
                "__dict__",
            )
        )

    def test_present_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderDiagnosticPresenter
                    .present
                ).parameters
            ),
            (
                "self",
                "report",
            ),
        )

    def test_offline_ready_mapping(self):
        result = self.presenter.present(
            source_report()
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .NONE,
        )

        self.assertEqual(
            result.title,
            "Ready",
        )

        self.assertEqual(
            result.detail,
            "Provider configuration is ready.",
        )

    def test_online_ready_mapping(self):
        result = self.presenter.present(
            source_report(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                )
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .SUCCESS,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .NONE,
        )

        self.assertEqual(
            result.title,
            "Ready",
        )

        self.assertEqual(
            result.detail,
            (
                "Provider configuration and connectivity are ready."
            ),
        )

    def test_config_invalid_mapping(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CONFIG_INVALID
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .REVIEW_CONFIGURATION,
        )

        self.assertEqual(
            result.title,
            "Configuration invalid",
        )

    def test_credential_missing_mapping(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_MISSING
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "API credential missing",
        )

    def test_credential_invalid_mapping(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_INVALID
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "API credential invalid",
        )

    def test_remote_dependency_missing_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .REMOTE_DEPENDENCY_MISSING
                ),
                provider=VisionProviderKind.KIE_AI,
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertEqual(
            result.title,
            "Remote image source required",
        )

    def test_authentication_failed_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .AUTHENTICATION_FAILED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "Authentication failed",
        )

    def test_permission_denied_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PERMISSION_DENIED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.title,
            "Permission denied",
        )

    def test_rate_limited_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RATE_LIMITED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Rate limited",
        )

    def test_provider_unavailable_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PROVIDER_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Provider unavailable",
        )

    def test_network_unavailable_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            result.title,
            "Network unavailable",
        )

    def test_deadline_exceeded_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .DEADLINE_EXCEEDED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .WARNING,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Connection timed out",
        )

    def test_response_invalid_mapping(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RESPONSE_INVALID
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Invalid provider response",
        )

    def test_internal_failure_mapping(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .INTERNAL_FAILURE
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticPresentationSeverity
            .ERROR,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticPresentationAction
            .RETRY,
        )

        self.assertEqual(
            result.title,
            "Internal diagnostic failure",
        )

    def test_preserves_mode_status_provider_metadata(self):
        source = source_report(
            (
                ProviderRuntimeDiagnosticStatus
                .AUTHENTICATION_FAILED
            ),
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            provider=VisionProviderKind.GEMINI,
        )

        result = self.presenter.present(
            source
        )

        self.assertIs(
            result.mode,
            source.mode,
        )

        self.assertIs(
            result.diagnostic_status,
            source.status,
        )

        self.assertIs(
            result.provider,
            source.provider,
        )

        self.assertEqual(
            result.credential_environment_variable,
            source.credential_environment_variable,
        )

    def test_config_invalid_preserves_empty_metadata(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CONFIG_INVALID,
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            )
        )

        self.assertIsNone(
            result.provider
        )

        self.assertIsNone(
            result.credential_environment_variable
        )

    def test_environment_name_appears_for_missing_credential(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_MISSING,
                provider=VisionProviderKind.GEMINI,
            )
        )

        self.assertIn(
            "GEMINI_API_KEY",
            result.detail,
        )

    def test_environment_name_appears_for_invalid_credential(self):
        result = self.presenter.present(
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_INVALID,
                provider=VisionProviderKind.OPENAI,
            )
        )

        self.assertIn(
            "OPENAI_API_KEY",
            result.detail,
        )

    def test_environment_name_appears_for_authentication_failure(self):
        result = self.presenter.present(
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .AUTHENTICATION_FAILED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                provider=VisionProviderKind.KIE_AI,
            )
        )

        self.assertIn(
            "KIE_API_KEY",
            result.detail,
        )

    def test_connectivity_codes_are_not_exposed(self):
        source = source_report(
            (
                ProviderRuntimeDiagnosticStatus
                .AUTHENTICATION_FAILED
            ),
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            provider=VisionProviderKind.KIE_AI,
        )

        self.assertEqual(
            source.http_status,
            200,
        )

        self.assertEqual(
            source.provider_code,
            401,
        )

        result = self.presenter.present(
            source
        )

        self.assertNotIn(
            "http_status",
            result.__dict__,
        )

        self.assertNotIn(
            "provider_code",
            result.__dict__,
        )

    def test_all_outputs_validate(self):
        cases = (
            source_report(),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CONFIG_INVALID
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_MISSING
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_INVALID
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .REMOTE_DEPENDENCY_MISSING
                ),
                provider=VisionProviderKind.KIE_AI,
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .AUTHENTICATION_FAILED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PERMISSION_DENIED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RATE_LIMITED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PROVIDER_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .DEADLINE_EXCEEDED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RESPONSE_INVALID
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .INTERNAL_FAILURE
            ),
        )

        for source in cases:
            with self.subTest(
                status=source.status
            ):
                result = self.presenter.present(
                    source
                )

                self.assertIs(
                    validate_provider_diagnostic_presentation(
                        result
                    ),
                    result,
                )

    def test_source_report_not_mutated(self):
        source = source_report(
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING
        )

        before = copy.deepcopy(
            source
        )

        self.presenter.present(
            source
        )

        self.assertEqual(
            source,
            before,
        )

    def test_invalid_source_report_rejected(self):
        invalid = dataclasses.replace(
            source_report(),
            mode="OFFLINE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_source_invalid$",
        ):
            self.presenter.present(
                invalid
            )

    def test_subclass_source_report_rejected(self):
        base = source_report()

        class Subclass(
            ProviderRuntimeDiagnosticReport
        ):
            pass

        value = Subclass(
            **base.__dict__
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_source_invalid$",
        ):
            self.presenter.present(
                value
            )

    def test_forged_source_report_rejected(self):
        value = copy.copy(
            source_report()
        )

        object.__setattr__(
            value,
            "extra",
            "unexpected",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_source_invalid$",
        ):
            self.presenter.present(
                value
            )

    def test_presenter_does_not_read_environment(self):
        source = source_report(
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING
        )

        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ) as getenv_mock:
            result = self.presenter.present(
                source
            )

        self.assertIs(
            result.diagnostic_status,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

        getenv_mock.assert_not_called()

    def test_presenter_does_not_open_network(self):
        source = source_report(
            (
                ProviderRuntimeDiagnosticStatus
                .NETWORK_UNAVAILABLE
            ),
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "network must not open"
            ),
        ) as opened:
            result = self.presenter.present(
                source
            )

        self.assertIs(
            result.diagnostic_status,
            ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
        )

        opened.assert_not_called()

    def test_validator_baseexception_not_swallowed(self):
        with patch.object(
            presenter_module,
            "validate_provider_runtime_diagnostic_report",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.presenter.present(
                    source_report()
                )

    def test_validator_memory_error_not_swallowed(self):
        with patch.object(
            presenter_module,
            "validate_provider_runtime_diagnostic_report",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                self.presenter.present(
                    source_report()
                )

    def test_generated_presentation_validation_failure_is_internal(self):
        with patch.object(
            presenter_module,
            "validate_provider_diagnostic_presentation",
            side_effect=ValueError(
                "private"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^provider_diagnostic_presentation_internal$",
            ):
                self.presenter.present(
                    source_report()
                )

    def test_all_diagnostic_statuses_have_canonical_mapping(self):
        sources = (
            source_report(),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CONFIG_INVALID
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_MISSING
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_INVALID
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .REMOTE_DEPENDENCY_MISSING
                ),
                provider=VisionProviderKind.KIE_AI,
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .AUTHENTICATION_FAILED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PERMISSION_DENIED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RATE_LIMITED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .PROVIDER_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .DEADLINE_EXCEEDED
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                (
                    ProviderRuntimeDiagnosticStatus
                    .RESPONSE_INVALID
                ),
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
            ),
            source_report(
                ProviderRuntimeDiagnosticStatus
                .INTERNAL_FAILURE
            ),
        )

        self.assertEqual(
            {
                source.status
                for source in sources
            },
            set(
                ProviderRuntimeDiagnosticStatus
            ),
        )

        for source in sources:
            with self.subTest(
                status=source.status
            ):
                result = self.presenter.present(
                    source
                )

                self.assertIs(
                    result.diagnostic_status,
                    source.status,
                )

    def test_ready_detail_distinguishes_offline_and_online(self):
        offline = self.presenter.present(
            source_report()
        )

        online = self.presenter.present(
            source_report(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                )
            )
        )

        self.assertNotEqual(
            offline.detail,
            online.detail,
        )

        self.assertEqual(
            offline.title,
            online.title,
        )


if __name__ == "__main__":
    unittest.main()