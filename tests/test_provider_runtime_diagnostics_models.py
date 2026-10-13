"""M93 provider runtime diagnostics model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_runtime_diagnostics as api

from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def offline_ready_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .OFFLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .READY
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def online_ready_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .READY
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=200,
        provider_code=None,
    )


def kie_online_ready_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .READY
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=200,
    )


def config_invalid_report(
    mode=api.ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        ),
        provider=None,
        credential_environment_variable=None,
        http_status=None,
        provider_code=None,
    )


def credential_missing_report(
    mode=api.ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def credential_invalid_report(
    mode=api.ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def remote_dependency_missing_report(
    mode=api.ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def authentication_failed_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=401,
        provider_code=None,
    )


def kie_authentication_failed_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=401,
    )


def permission_denied_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .PERMISSION_DENIED
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=403,
        provider_code=None,
    )


def rate_limited_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=429,
        provider_code=None,
    )


def provider_unavailable_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=503,
        provider_code=None,
    )


def kie_provider_unavailable_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=503,
    )


def network_unavailable_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def deadline_exceeded_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def response_invalid_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=422,
        provider_code=None,
    )


def kie_response_invalid_report():
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=(
            api.ProviderRuntimeDiagnosticMode
            .ONLINE
        ),
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=422,
    )


def internal_failure_report(
    mode=api.ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderRuntimeDiagnosticReport(
        schema_version=(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION
        ),
        mode=mode,
        status=(
            api.ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


class Hostile:
    def __getattribute__(
        self,
        name,
    ):
        raise AssertionError(
            "hostile access"
        )

    def __repr__(
        self,
    ):
        raise AssertionError(
            "hostile repr"
        )


class ProviderRuntimeDiagnosticsModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
            1,
        )

    def test_mode_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderRuntimeDiagnosticMode
            },
            {
                "OFFLINE",
                "ONLINE",
            },
        )

    def test_status_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderRuntimeDiagnosticStatus
            },
            {
                "READY",
                "CONFIG_INVALID",
                "CREDENTIAL_MISSING",
                "CREDENTIAL_INVALID",
                "REMOTE_DEPENDENCY_MISSING",
                "AUTHENTICATION_FAILED",
                "PERMISSION_DENIED",
                "RATE_LIMITED",
                "PROVIDER_UNAVAILABLE",
                "NETWORK_UNAVAILABLE",
                "DEADLINE_EXCEEDED",
                "RESPONSE_INVALID",
                "INTERNAL_FAILURE",
            },
        )

    def test_offline_ready_valid(self):
        value = offline_ready_report()

        self.assertIs(
            api.validate_provider_runtime_diagnostic_report(
                value
            ),
            value,
        )

    def test_online_ready_valid(self):
        for value in (
            online_ready_report(),
            kie_online_ready_report(),
        ):
            with self.subTest(
                provider=value.provider
            ):
                self.assertIs(
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    ),
                    value,
                )

    def test_config_invalid_valid(self):
        for mode in (
            api.ProviderRuntimeDiagnosticMode.OFFLINE,
            api.ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = config_invalid_report(
                mode
            )

            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_credential_missing_valid(self):
        for mode in (
            api.ProviderRuntimeDiagnosticMode.OFFLINE,
            api.ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = credential_missing_report(
                mode
            )

            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_credential_invalid_valid(self):
        for mode in (
            api.ProviderRuntimeDiagnosticMode.OFFLINE,
            api.ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = credential_invalid_report(
                mode
            )

            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_remote_dependency_missing_valid(self):
        for mode in (
            api.ProviderRuntimeDiagnosticMode.OFFLINE,
            api.ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = remote_dependency_missing_report(
                mode
            )

            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_authentication_failed_valid(self):
        for value in (
            authentication_failed_report(),
            kie_authentication_failed_report(),
        ):
            with self.subTest(
                provider=value.provider
            ):
                self.assertIs(
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    ),
                    value,
                )

    def test_permission_denied_valid(self):
        direct = permission_denied_report()

        wrapped = dataclasses.replace(
            direct,
            provider=VisionProviderKind.KIE_AI,
            credential_environment_variable=(
                "KIE_API_KEY"
            ),
            http_status=200,
            provider_code=403,
        )

        for value in (
            direct,
            wrapped,
        ):
            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_rate_limited_valid(self):
        direct = rate_limited_report()

        wrapped = dataclasses.replace(
            direct,
            provider=VisionProviderKind.KIE_AI,
            credential_environment_variable=(
                "KIE_API_KEY"
            ),
            http_status=200,
            provider_code=429,
        )

        for value in (
            direct,
            wrapped,
        ):
            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_provider_unavailable_valid(self):
        for value in (
            provider_unavailable_report(),
            kie_provider_unavailable_report(),
        ):
            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_network_unavailable_valid(self):
        value = network_unavailable_report()

        self.assertIs(
            api.validate_provider_runtime_diagnostic_report(
                value
            ),
            value,
        )

    def test_deadline_exceeded_valid(self):
        value = deadline_exceeded_report()

        self.assertIs(
            api.validate_provider_runtime_diagnostic_report(
                value
            ),
            value,
        )

    def test_response_invalid_valid(self):
        for value in (
            response_invalid_report(),
            kie_response_invalid_report(),
        ):
            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_internal_failure_valid(self):
        for mode in (
            api.ProviderRuntimeDiagnosticMode.OFFLINE,
            api.ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = internal_failure_report(
                mode
            )

            self.assertIs(
                api.validate_provider_runtime_diagnostic_report(
                    value
                ),
                value,
            )

    def test_report_is_frozen(self):
        value = offline_ready_report()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.status = (
                api.ProviderRuntimeDiagnosticStatus
                .INTERNAL_FAILURE
            )

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                offline_ready_report(),
                schema_version=version,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_diagnostic_report_invalid$",
            ):
                api.validate_provider_runtime_diagnostic_report(
                    value
                )

    def test_exact_shape_contract(self):
        base = offline_ready_report()

        class Subclass(
            api.ProviderRuntimeDiagnosticReport
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        forged = copy.copy(
            base
        )

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        for value in (
            Hostile(),
            subclass,
            forged,
        ):
            with self.subTest(
                value_type=type(
                    value
                ).__name__
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_mode_requires_exact_enum(self):
        value = dataclasses.replace(
            offline_ready_report(),
            mode="OFFLINE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_status_requires_exact_enum(self):
        value = dataclasses.replace(
            offline_ready_report(),
            status="READY",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_provider_requires_exact_enum(self):
        value = dataclasses.replace(
            offline_ready_report(),
            provider="OPENAI",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_metadata_must_be_paired(self):
        variants = (
            dataclasses.replace(
                offline_ready_report(),
                provider=None,
            ),
            dataclasses.replace(
                offline_ready_report(),
                credential_environment_variable=None,
            ),
        )

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_diagnostic_report_invalid$",
            ):
                api.validate_provider_runtime_diagnostic_report(
                    value
                )

    def test_config_invalid_requires_empty_metadata(self):
        variants = (
            dataclasses.replace(
                config_invalid_report(),
                provider=VisionProviderKind.OPENAI,
                credential_environment_variable=(
                    "OPENAI_API_KEY"
                ),
            ),
            dataclasses.replace(
                config_invalid_report(),
                http_status=400,
            ),
            dataclasses.replace(
                config_invalid_report(),
                provider_code=400,
            ),
        )

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_diagnostic_report_invalid$",
            ):
                api.validate_provider_runtime_diagnostic_report(
                    value
                )

    def test_non_config_status_requires_metadata(self):
        value = dataclasses.replace(
            credential_missing_report(),
            provider=None,
            credential_environment_variable=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_environment_variable_contract(self):
        invalid = (
            "",
            " OPENAI_API_KEY",
            "OPENAI_API_KEY ",
            "openai_api_key",
            "9OPENAI_API_KEY",
            "OPENAI-API-KEY",
            "OPENAI API KEY",
        )

        for name in invalid:
            value = dataclasses.replace(
                offline_ready_report(),
                credential_environment_variable=name,
            )

            with self.subTest(
                name=name
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_offline_rejects_connectivity_statuses(self):
        values = (
            authentication_failed_report(),
            permission_denied_report(),
            rate_limited_report(),
            provider_unavailable_report(),
            network_unavailable_report(),
            deadline_exceeded_report(),
            response_invalid_report(),
        )

        for base in values:
            value = dataclasses.replace(
                base,
                mode=(
                    api.ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
            )

            with self.subTest(
                status=value.status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_offline_ready_rejects_remote_status(self):
        variants = (
            dataclasses.replace(
                offline_ready_report(),
                http_status=200,
            ),
            dataclasses.replace(
                offline_ready_report(),
                provider=VisionProviderKind.KIE_AI,
                credential_environment_variable=(
                    "KIE_API_KEY"
                ),
                provider_code=200,
            ),
        )

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_diagnostic_report_invalid$",
            ):
                api.validate_provider_runtime_diagnostic_report(
                    value
                )

    def test_offline_failures_reject_remote_status(self):
        values = (
            credential_missing_report(),
            credential_invalid_report(),
            remote_dependency_missing_report(),
            internal_failure_report(),
        )

        for base in values:
            variants = (
                dataclasses.replace(
                    base,
                    http_status=500,
                ),
                dataclasses.replace(
                    base,
                    provider_code=500,
                ),
            )

            for value in variants:
                with self.subTest(
                    status=base.status
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "^provider_runtime_diagnostic_report_invalid$",
                    ):
                        api.validate_provider_runtime_diagnostic_report(
                            value
                        )

    def test_online_ready_requires_success(self):
        for status in (
            None,
            199,
            300,
            401,
            500,
        ):
            value = dataclasses.replace(
                online_ready_report(),
                http_status=status,
            )

            with self.subTest(
                http_status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

        for provider_code in (
            199,
            300,
            401,
            500,
        ):
            value = dataclasses.replace(
                kie_online_ready_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                provider_code=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_wrapped_provider_code_requires_kie(self):
        values = (
            dataclasses.replace(
                online_ready_report(),
                provider_code=200,
            ),
            dataclasses.replace(
                authentication_failed_report(),
                http_status=200,
                provider_code=401,
            ),
            dataclasses.replace(
                response_invalid_report(),
                http_status=200,
                provider_code=422,
            ),
        )

        for value in values:
            with self.subTest(
                status=value.status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_remote_dependency_requires_kie(self):
        value = dataclasses.replace(
            remote_dependency_missing_report(),
            provider=VisionProviderKind.OPENAI,
            credential_environment_variable=(
                "OPENAI_API_KEY"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_authentication_semantics(self):
        for status in (
            None,
            400,
            403,
            429,
            500,
        ):
            value = dataclasses.replace(
                authentication_failed_report(),
                http_status=status,
            )

            with self.subTest(
                direct=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

        for provider_code in (
            400,
            403,
            429,
            500,
        ):
            value = dataclasses.replace(
                kie_authentication_failed_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                wrapped=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_provider_unavailable_semantics(self):
        for status in (
            None,
            200,
            400,
            499,
            600,
        ):
            value = dataclasses.replace(
                provider_unavailable_report(),
                http_status=status,
            )

            with self.subTest(
                direct=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

        for provider_code in (
            200,
            400,
            499,
            600,
        ):
            value = dataclasses.replace(
                kie_provider_unavailable_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                wrapped=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_diagnostic_report_invalid$",
                ):
                    api.validate_provider_runtime_diagnostic_report(
                        value
                    )

    def test_response_invalid_requires_http_status(self):
        value = dataclasses.replace(
            response_invalid_report(),
            http_status=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_report_invalid$",
        ):
            api.validate_provider_runtime_diagnostic_report(
                value
            )

    def test_non_http_statuses_reject_remote_status(self):
        values = (
            credential_missing_report(
                api.ProviderRuntimeDiagnosticMode.ONLINE
            ),
            credential_invalid_report(
                api.ProviderRuntimeDiagnosticMode.ONLINE
            ),
            network_unavailable_report(),
            deadline_exceeded_report(),
            internal_failure_report(
                api.ProviderRuntimeDiagnosticMode.ONLINE
            ),
        )

        for base in values:
            variants = (
                dataclasses.replace(
                    base,
                    http_status=500,
                ),
                dataclasses.replace(
                    base,
                    provider_code=500,
                ),
            )

            for value in variants:
                with self.subTest(
                    status=base.status
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "^provider_runtime_diagnostic_report_invalid$",
                    ):
                        api.validate_provider_runtime_diagnostic_report(
                            value
                        )

    def test_detached_roundtrips(self):
        values = (
            offline_ready_report(),
            online_ready_report(),
            kie_online_ready_report(),
            config_invalid_report(),
            credential_missing_report(),
            credential_invalid_report(),
            remote_dependency_missing_report(),
            authentication_failed_report(),
            kie_authentication_failed_report(),
            permission_denied_report(),
            rate_limited_report(),
            provider_unavailable_report(),
            kie_provider_unavailable_report(),
            network_unavailable_report(),
            deadline_exceeded_report(),
            response_invalid_report(),
            kie_response_invalid_report(),
            internal_failure_report(),
        )

        for value in values:
            variants = (
                copy.copy(
                    value
                ),
                copy.deepcopy(
                    value
                ),
                pickle.loads(
                    pickle.dumps(
                        value
                    )
                ),
            )

            for variant in variants:
                self.assertEqual(
                    api.validate_provider_runtime_diagnostic_report(
                        variant
                    ),
                    value,
                )

    def test_report_contains_no_secret_fields(self):
        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                api.ProviderRuntimeDiagnosticReport
            )
        }

        forbidden = {
            "secret",
            "password",
            "token",
            "api_key",
            "credential",
            "credential_value",
            "authorization",
            "request_body",
            "response_body",
        }

        self.assertTrue(
            names.isdisjoint(
                forbidden
            )
        )

        self.assertEqual(
            names,
            {
                "schema_version",
                "mode",
                "status",
                "provider",
                "credential_environment_variable",
                "http_status",
                "provider_code",
            },
        )

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_RUNTIME_DIAGNOSTIC_SCHEMA_VERSION",
                "ProviderRuntimeDiagnosticMode",
                "ProviderRuntimeDiagnosticReport",
                "ProviderRuntimeDiagnosticStatus",
                "validate_provider_runtime_diagnostic_report",
            ),
        )


if __name__ == "__main__":
    unittest.main()