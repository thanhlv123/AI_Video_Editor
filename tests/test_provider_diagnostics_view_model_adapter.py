"""M96 provider diagnostics view-model adapter."""

import copy
import dataclasses
import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_view_model.adapter as adapter_module

from creator_studio.provider_diagnostics_application import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationResult,
)
from creator_studio.provider_diagnostics_presentation import (
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
)
from creator_studio.provider_diagnostics_view_model import (
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewSeverity,
    validate_provider_diagnostics_view_model,
)
from creator_studio.provider_diagnostics_view_model.adapter import (
    ProviderDiagnosticsViewModelAdapter,
)
from creator_studio.provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def environment_name(
    provider,
):
    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        return "OPENAI_API_KEY"

    if (
        provider
        is VisionProviderKind.GEMINI
    ):
        return "GEMINI_API_KEY"

    if (
        provider
        is VisionProviderKind.KIE_AI
    ):
        return "KIE_API_KEY"

    raise ValueError()


def source_result(
    *,
    status=ProviderRuntimeDiagnosticStatus.READY,
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
    provider=VisionProviderKind.OPENAI,
    severity=(
        ProviderDiagnosticPresentationSeverity
        .SUCCESS
    ),
    action=(
        ProviderDiagnosticPresentationAction
        .NONE
    ),
    title="Ready",
    detail="Provider configuration is ready.",
):
    if (
        status
        is ProviderRuntimeDiagnosticStatus
        .CONFIG_INVALID
    ):
        provider_value = None
        environment_variable = None

    else:
        provider_value = provider

        environment_variable = (
            environment_name(
                provider
            )
        )

    presentation = ProviderDiagnosticPresentation(
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

    return ProviderDiagnosticsApplicationResult(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        presentation=presentation,
    )


class ProviderDiagnosticsViewModelAdapterTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.adapter = (
            ProviderDiagnosticsViewModelAdapter()
        )

    def test_adapter_is_stateless(self):
        self.assertEqual(
            ProviderDiagnosticsViewModelAdapter
            .__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.adapter,
                "__dict__",
            )
        )

    def test_adapt_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderDiagnosticsViewModelAdapter
                    .adapt
                ).parameters
            ),
            (
                "self",
                "result",
            ),
        )

    def test_ready_openai_mapping(self):
        result = self.adapter.adapt(
            source_result()
        )

        self.assertEqual(
            result.provider_label,
            "OpenAI",
        )

        self.assertEqual(
            result.status_text,
            "Ready",
        )

        self.assertEqual(
            result.detail_text,
            "Provider configuration is ready.",
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticsViewSeverity
            .SUCCESS,
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertEqual(
            result.action_text,
            "No action required",
        )

        self.assertIs(
            result.is_ready,
            True,
        )

    def test_gemini_provider_label(self):
        result = self.adapter.adapt(
            source_result(
                provider=VisionProviderKind.GEMINI,
            )
        )

        self.assertEqual(
            result.provider_label,
            "Gemini",
        )

    def test_kie_provider_label(self):
        result = self.adapter.adapt(
            source_result(
                provider=VisionProviderKind.KIE_AI,
            )
        )

        self.assertEqual(
            result.provider_label,
            "Kie.ai",
        )

    def test_config_invalid_provider_label(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CONFIG_INVALID
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .REVIEW_CONFIGURATION
                ),
                title="Configuration invalid",
                detail=(
                    "Review the provider runtime configuration."
                ),
            )
        )

        self.assertEqual(
            result.provider_label,
            "Provider",
        )

        self.assertIs(
            result.is_ready,
            False,
        )

    def test_status_text_preserved(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_MISSING
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CONFIGURE_CREDENTIAL
                ),
                title="API credential missing",
                detail=(
                    "Configure the required credential."
                ),
            )
        )

        self.assertEqual(
            result.status_text,
            "API credential missing",
        )

    def test_detail_text_preserved(self):
        detail = (
            "Check the network connection and retry."
        )

        result = self.adapter.adapt(
            source_result(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CHECK_NETWORK
                ),
                title="Network unavailable",
                detail=detail,
            )
        )

        self.assertEqual(
            result.detail_text,
            detail,
        )

    def test_success_severity_mapping(self):
        result = self.adapter.adapt(
            source_result()
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticsViewSeverity
            .SUCCESS,
        )

    def test_warning_severity_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .INTERNAL_FAILURE
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .RETRY
                ),
                title="Retry required",
                detail="Retry the diagnostic operation.",
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticsViewSeverity
            .WARNING,
        )

    def test_error_severity_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_MISSING
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CONFIGURE_CREDENTIAL
                ),
                title="API credential missing",
                detail="Configure the credential.",
            )
        )

        self.assertIs(
            result.severity,
            ProviderDiagnosticsViewSeverity
            .ERROR,
        )

    def test_none_action_mapping(self):
        result = self.adapter.adapt(
            source_result()
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .NONE,
        )

        self.assertEqual(
            result.action_text,
            "No action required",
        )

    def test_review_configuration_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CONFIG_INVALID
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .REVIEW_CONFIGURATION
                ),
                title="Configuration invalid",
                detail="Review the configuration.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .REVIEW_CONFIGURATION,
        )

        self.assertEqual(
            result.action_text,
            "Review configuration",
        )

    def test_configure_credential_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_MISSING
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CONFIGURE_CREDENTIAL
                ),
                title="API credential missing",
                detail="Configure the credential.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
        )

        self.assertEqual(
            result.action_text,
            "Configure credential",
        )

    def test_check_credential_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_INVALID
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CHECK_CREDENTIAL
                ),
                title="API credential invalid",
                detail="Check the credential.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
        )

        self.assertEqual(
            result.action_text,
            "Check credential",
        )

    def test_add_remote_source_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .REMOTE_DEPENDENCY_MISSING
                ),
                provider=VisionProviderKind.KIE_AI,
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .ADD_REMOTE_SOURCE
                ),
                title="Remote image source required",
                detail="Configure a remote image source.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .ADD_REMOTE_SOURCE,
        )

        self.assertEqual(
            result.action_text,
            "Add remote image source",
        )

    def test_retry_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .INTERNAL_FAILURE
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .RETRY
                ),
                title="Internal diagnostic failure",
                detail="Retry the diagnostic operation.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .RETRY,
        )

        self.assertEqual(
            result.action_text,
            "Retry",
        )

    def test_check_network_action_mapping(self):
        result = self.adapter.adapt(
            source_result(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CHECK_NETWORK
                ),
                title="Network unavailable",
                detail="Check the network connection.",
            )
        )

        self.assertIs(
            result.action,
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        self.assertEqual(
            result.action_text,
            "Check network",
        )

    def test_ready_status_sets_is_ready_true(self):
        result = self.adapter.adapt(
            source_result()
        )

        self.assertIs(
            result.is_ready,
            True,
        )

    def test_nonready_status_sets_is_ready_false(self):
        result = self.adapter.adapt(
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_MISSING
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CONFIGURE_CREDENTIAL
                ),
                title="API credential missing",
                detail="Configure the credential.",
            )
        )

        self.assertIs(
            result.is_ready,
            False,
        )

    def test_credential_environment_variable_not_stored(self):
        source = source_result(
            status=(
                ProviderRuntimeDiagnosticStatus
                .CREDENTIAL_MISSING
            ),
            severity=(
                ProviderDiagnosticPresentationSeverity
                .ERROR
            ),
            action=(
                ProviderDiagnosticPresentationAction
                .CONFIGURE_CREDENTIAL
            ),
            title="API credential missing",
            detail=(
                "Configure the credential in OPENAI_API_KEY."
            ),
        )

        result = self.adapter.adapt(
            source
        )

        self.assertEqual(
            source.presentation
            .credential_environment_variable,
            "OPENAI_API_KEY",
        )

        self.assertNotIn(
            "credential_environment_variable",
            result.__dict__,
        )

    def test_source_not_mutated(self):
        source = source_result()

        before = copy.deepcopy(
            source
        )

        self.adapter.adapt(
            source
        )

        self.assertEqual(
            source,
            before,
        )

    def test_invalid_source_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_source_invalid$",
        ):
            self.adapter.adapt(
                object()
            )

    def test_subclass_source_rejected(self):
        base = source_result()

        class Subclass(
            ProviderDiagnosticsApplicationResult
        ):
            pass

        value = Subclass(
            **base.__dict__
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_source_invalid$",
        ):
            self.adapter.adapt(
                value
            )

    def test_forged_source_rejected(self):
        value = copy.copy(
            source_result()
        )

        object.__setattr__(
            value,
            "extra",
            "unexpected",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_source_invalid$",
        ):
            self.adapter.adapt(
                value
            )

    def test_source_validator_memory_error_not_swallowed(self):
        with patch.object(
            adapter_module,
            "validate_provider_diagnostics_application_result",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                self.adapter.adapt(
                    source_result()
                )

    def test_source_validator_error_is_sanitized(self):
        with patch.object(
            adapter_module,
            "validate_provider_diagnostics_application_result",
            side_effect=RuntimeError(
                "private-source-error"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_view_model_source_invalid$",
            ):
                self.adapter.adapt(
                    source_result()
                )

    def test_source_validator_baseexception_not_swallowed(self):
        with patch.object(
            adapter_module,
            "validate_provider_diagnostics_application_result",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.adapter.adapt(
                    source_result()
                )

    def test_generated_validation_failure_is_internal(self):
        with patch.object(
            adapter_module,
            "validate_provider_diagnostics_view_model",
            side_effect=ValueError(
                "private-view-error"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^provider_diagnostics_view_model_internal$",
            ):
                self.adapter.adapt(
                    source_result()
                )

    def test_generated_validation_memory_error_not_swallowed(self):
        with patch.object(
            adapter_module,
            "validate_provider_diagnostics_view_model",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                self.adapter.adapt(
                    source_result()
                )

    def test_adapter_does_not_read_environment(self):
        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ) as getenv_mock:
            result = self.adapter.adapt(
                source_result()
            )

        self.assertIs(
            result.is_ready,
            True,
        )

        getenv_mock.assert_not_called()

    def test_adapter_does_not_open_network(self):
        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "network must not open"
            ),
        ) as opened:
            result = self.adapter.adapt(
                source_result()
            )

        self.assertIs(
            result.is_ready,
            True,
        )

        opened.assert_not_called()

    def test_all_action_text_mappings(self):
        cases = (
            (
                ProviderDiagnosticPresentationAction
                .NONE,
                ProviderDiagnosticsViewAction
                .NONE,
                "No action required",
                True,
            ),
            (
                ProviderDiagnosticPresentationAction
                .REVIEW_CONFIGURATION,
                ProviderDiagnosticsViewAction
                .REVIEW_CONFIGURATION,
                "Review configuration",
                False,
            ),
            (
                ProviderDiagnosticPresentationAction
                .CONFIGURE_CREDENTIAL,
                ProviderDiagnosticsViewAction
                .CONFIGURE_CREDENTIAL,
                "Configure credential",
                False,
            ),
            (
                ProviderDiagnosticPresentationAction
                .CHECK_CREDENTIAL,
                ProviderDiagnosticsViewAction
                .CHECK_CREDENTIAL,
                "Check credential",
                False,
            ),
            (
                ProviderDiagnosticPresentationAction
                .ADD_REMOTE_SOURCE,
                ProviderDiagnosticsViewAction
                .ADD_REMOTE_SOURCE,
                "Add remote image source",
                False,
            ),
            (
                ProviderDiagnosticPresentationAction
                .RETRY,
                ProviderDiagnosticsViewAction
                .RETRY,
                "Retry",
                False,
            ),
            (
                ProviderDiagnosticPresentationAction
                .CHECK_NETWORK,
                ProviderDiagnosticsViewAction
                .CHECK_NETWORK,
                "Check network",
                False,
            ),
        )

        for (
            source_action,
            expected_action,
            expected_text,
            ready,
        ) in cases:
            if ready:
                source = source_result()

            else:
                source = source_result(
                    status=(
                        ProviderRuntimeDiagnosticStatus
                        .CREDENTIAL_MISSING
                    ),
                    severity=(
                        ProviderDiagnosticPresentationSeverity
                        .ERROR
                    ),
                    action=source_action,
                    title="Action required",
                    detail="Complete the recommended action.",
                )

            with self.subTest(
                source_action=source_action
            ):
                result = self.adapter.adapt(
                    source
                )

                self.assertIs(
                    result.action,
                    expected_action,
                )

                self.assertEqual(
                    result.action_text,
                    expected_text,
                )

    def test_all_provider_labels(self):
        cases = (
            (
                VisionProviderKind.OPENAI,
                "OpenAI",
            ),
            (
                VisionProviderKind.GEMINI,
                "Gemini",
            ),
            (
                VisionProviderKind.KIE_AI,
                "Kie.ai",
            ),
        )

        for provider, label in cases:
            with self.subTest(
                provider=provider
            ):
                result = self.adapter.adapt(
                    source_result(
                        provider=provider
                    )
                )

                self.assertEqual(
                    result.provider_label,
                    label,
                )

    def test_all_outputs_validate(self):
        sources = (
            source_result(),
            source_result(
                provider=VisionProviderKind.GEMINI,
            ),
            source_result(
                provider=VisionProviderKind.KIE_AI,
            ),
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CONFIG_INVALID
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .REVIEW_CONFIGURATION
                ),
                title="Configuration invalid",
                detail="Review the configuration.",
            ),
            source_result(
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .CREDENTIAL_MISSING
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CONFIGURE_CREDENTIAL
                ),
                title="API credential missing",
                detail="Configure the credential.",
            ),
            source_result(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .NETWORK_UNAVAILABLE
                ),
                severity=(
                    ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    ProviderDiagnosticPresentationAction
                    .CHECK_NETWORK
                ),
                title="Network unavailable",
                detail="Check the network connection.",
            ),
        )

        for source in sources:
            with self.subTest(
                status=(
                    source.presentation
                    .diagnostic_status
                )
            ):
                result = self.adapter.adapt(
                    source
                )

                self.assertIs(
                    validate_provider_diagnostics_view_model(
                        result
                    ),
                    result,
                )


if __name__ == "__main__":
    unittest.main()