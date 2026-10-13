"""M94 provider diagnostics presentation model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_diagnostics_presentation as api

from creator_studio.provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def presentation(
    *,
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
    status=ProviderRuntimeDiagnosticStatus.READY,
    severity=(
        api.ProviderDiagnosticPresentationSeverity
        .SUCCESS
    ),
    action=(
        api.ProviderDiagnosticPresentationAction
        .NONE
    ),
    provider=VisionProviderKind.OPENAI,
    environment_variable="OPENAI_API_KEY",
    title="Ready",
    detail="Provider configuration is ready.",
):
    return api.ProviderDiagnosticPresentation(
        schema_version=(
            api.PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
        ),
        mode=mode,
        diagnostic_status=status,
        severity=severity,
        action=action,
        provider=provider,
        credential_environment_variable=(
            environment_variable
        ),
        title=title,
        detail=detail,
    )


def config_invalid_presentation(
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return presentation(
        mode=mode,
        status=(
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID
        ),
        severity=(
            api.ProviderDiagnosticPresentationSeverity
            .ERROR
        ),
        action=(
            api.ProviderDiagnosticPresentationAction
            .REVIEW_CONFIGURATION
        ),
        provider=None,
        environment_variable=None,
        title="Configuration invalid",
        detail=(
            "Review the provider configuration."
        ),
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


class ProviderDiagnosticsPresentationModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
            1,
        )

    def test_text_limits(self):
        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH,
            80,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH,
            320,
        )

    def test_severity_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderDiagnosticPresentationSeverity
            },
            {
                "SUCCESS",
                "WARNING",
                "ERROR",
            },
        )

    def test_action_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderDiagnosticPresentationAction
            },
            {
                "NONE",
                "REVIEW_CONFIGURATION",
                "CONFIGURE_CREDENTIAL",
                "CHECK_CREDENTIAL",
                "ADD_REMOTE_SOURCE",
                "RETRY",
                "CHECK_NETWORK",
            },
        )

    def test_ready_presentation_valid(self):
        value = presentation()

        self.assertIs(
            api.validate_provider_diagnostic_presentation(
                value
            ),
            value,
        )

    def test_config_invalid_presentation_valid(self):
        for mode in (
            ProviderRuntimeDiagnosticMode.OFFLINE,
            ProviderRuntimeDiagnosticMode.ONLINE,
        ):
            value = config_invalid_presentation(
                mode
            )

            self.assertIs(
                api.validate_provider_diagnostic_presentation(
                    value
                ),
                value,
            )

    def test_all_non_config_statuses_structurally_valid_online(self):
        statuses = (
            ProviderRuntimeDiagnosticStatus.READY,
            ProviderRuntimeDiagnosticStatus.CREDENTIAL_MISSING,
            ProviderRuntimeDiagnosticStatus.CREDENTIAL_INVALID,
            ProviderRuntimeDiagnosticStatus.AUTHENTICATION_FAILED,
            ProviderRuntimeDiagnosticStatus.PERMISSION_DENIED,
            ProviderRuntimeDiagnosticStatus.RATE_LIMITED,
            ProviderRuntimeDiagnosticStatus.PROVIDER_UNAVAILABLE,
            ProviderRuntimeDiagnosticStatus.NETWORK_UNAVAILABLE,
            ProviderRuntimeDiagnosticStatus.DEADLINE_EXCEEDED,
            ProviderRuntimeDiagnosticStatus.RESPONSE_INVALID,
            ProviderRuntimeDiagnosticStatus.INTERNAL_FAILURE,
        )

        for status in statuses:
            value = presentation(
                mode=ProviderRuntimeDiagnosticMode.ONLINE,
                status=status,
            )

            with self.subTest(
                status=status
            ):
                self.assertIs(
                    api.validate_provider_diagnostic_presentation(
                        value
                    ),
                    value,
                )

        remote = presentation(
            mode=ProviderRuntimeDiagnosticMode.ONLINE,
            status=(
                ProviderRuntimeDiagnosticStatus
                .REMOTE_DEPENDENCY_MISSING
            ),
            provider=VisionProviderKind.KIE_AI,
            environment_variable="KIE_API_KEY",
        )

        self.assertIs(
            api.validate_provider_diagnostic_presentation(
                remote
            ),
            remote,
        )

    def test_offline_allowed_statuses_valid(self):
        statuses = (
            ProviderRuntimeDiagnosticStatus.READY,
            ProviderRuntimeDiagnosticStatus.CREDENTIAL_MISSING,
            ProviderRuntimeDiagnosticStatus.CREDENTIAL_INVALID,
            ProviderRuntimeDiagnosticStatus.INTERNAL_FAILURE,
        )

        for status in statuses:
            value = presentation(
                status=status,
            )

            with self.subTest(
                status=status
            ):
                self.assertIs(
                    api.validate_provider_diagnostic_presentation(
                        value
                    ),
                    value,
                )

        remote = presentation(
            status=(
                ProviderRuntimeDiagnosticStatus
                .REMOTE_DEPENDENCY_MISSING
            ),
            provider=VisionProviderKind.KIE_AI,
            environment_variable="KIE_API_KEY",
        )

        self.assertIs(
            api.validate_provider_diagnostic_presentation(
                remote
            ),
            remote,
        )

    def test_report_is_frozen(self):
        value = presentation()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.title = "Changed"

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                presentation(),
                schema_version=version,
            )

            with self.subTest(
                version=version
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_exact_shape_contract(self):
        base = presentation()

        class Subclass(
            api.ProviderDiagnosticPresentation
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
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_mode_requires_exact_enum(self):
        value = dataclasses.replace(
            presentation(),
            mode="OFFLINE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_diagnostic_status_requires_exact_enum(self):
        value = dataclasses.replace(
            presentation(),
            diagnostic_status="READY",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_severity_requires_exact_enum(self):
        value = dataclasses.replace(
            presentation(),
            severity="SUCCESS",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_action_requires_exact_enum(self):
        value = dataclasses.replace(
            presentation(),
            action="NONE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_provider_requires_exact_enum(self):
        value = dataclasses.replace(
            presentation(),
            provider="OPENAI",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_metadata_must_be_paired(self):
        variants = (
            dataclasses.replace(
                presentation(),
                provider=None,
            ),
            dataclasses.replace(
                presentation(),
                credential_environment_variable=None,
            ),
        )

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostic_presentation_invalid$",
            ):
                api.validate_provider_diagnostic_presentation(
                    value
                )

    def test_config_invalid_requires_empty_metadata(self):
        variants = (
            dataclasses.replace(
                config_invalid_presentation(),
                provider=VisionProviderKind.OPENAI,
                credential_environment_variable=(
                    "OPENAI_API_KEY"
                ),
            ),
            dataclasses.replace(
                config_invalid_presentation(),
                provider=VisionProviderKind.KIE_AI,
                credential_environment_variable=(
                    "KIE_API_KEY"
                ),
            ),
        )

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostic_presentation_invalid$",
            ):
                api.validate_provider_diagnostic_presentation(
                    value
                )

    def test_non_config_status_requires_metadata(self):
        value = dataclasses.replace(
            presentation(),
            provider=None,
            credential_environment_variable=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
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
                presentation(),
                credential_environment_variable=name,
            )

            with self.subTest(
                name=name
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_environment_variable_length_contract(self):
        value = dataclasses.replace(
            presentation(),
            credential_environment_variable=(
                "A"
                * 129
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_remote_dependency_requires_kie(self):
        value = presentation(
            status=(
                ProviderRuntimeDiagnosticStatus
                .REMOTE_DEPENDENCY_MISSING
            ),
            provider=VisionProviderKind.OPENAI,
            environment_variable="OPENAI_API_KEY",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                value
            )

    def test_offline_rejects_connectivity_statuses(self):
        statuses = (
            ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
            ProviderRuntimeDiagnosticStatus
            .PERMISSION_DENIED,
            ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED,
            ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE,
            ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
            ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
            ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID,
        )

        for status in statuses:
            value = presentation(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_title_requires_exact_string(self):
        for title in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                presentation(),
                title=title,
            )

            with self.subTest(
                title=title
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_title_must_be_nonempty_and_trimmed(self):
        for title in (
            "",
            " ",
            " Ready",
            "Ready ",
        ):
            value = dataclasses.replace(
                presentation(),
                title=title,
            )

            with self.subTest(
                title=title
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_title_length_contract(self):
        valid = dataclasses.replace(
            presentation(),
            title=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostic_presentation(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            presentation(),
            title=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                invalid
            )

    def test_title_must_be_printable(self):
        for title in (
            "Ready\nNow",
            "Ready\rNow",
            "Ready\tNow",
            "Ready\x00Now",
        ):
            value = dataclasses.replace(
                presentation(),
                title=title,
            )

            with self.subTest(
                title=repr(
                    title
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_detail_requires_exact_string(self):
        for detail in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                presentation(),
                detail=detail,
            )

            with self.subTest(
                detail=detail
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_detail_must_be_nonempty_and_trimmed(self):
        for detail in (
            "",
            " ",
            " Detail",
            "Detail ",
        ):
            value = dataclasses.replace(
                presentation(),
                detail=detail,
            )

            with self.subTest(
                detail=detail
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_detail_length_contract(self):
        valid = dataclasses.replace(
            presentation(),
            detail=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostic_presentation(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            presentation(),
            detail=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostic_presentation_invalid$",
        ):
            api.validate_provider_diagnostic_presentation(
                invalid
            )

    def test_detail_must_be_printable(self):
        for detail in (
            "Detail\nMore",
            "Detail\rMore",
            "Detail\tMore",
            "Detail\x00More",
        ):
            value = dataclasses.replace(
                presentation(),
                detail=detail,
            )

            with self.subTest(
                detail=repr(
                    detail
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostic_presentation_invalid$",
                ):
                    api.validate_provider_diagnostic_presentation(
                        value
                    )

    def test_detached_roundtrips(self):
        values = (
            presentation(),
            config_invalid_presentation(),
            presentation(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .AUTHENTICATION_FAILED
                ),
                severity=(
                    api.ProviderDiagnosticPresentationSeverity
                    .ERROR
                ),
                action=(
                    api.ProviderDiagnosticPresentationAction
                    .CHECK_CREDENTIAL
                ),
                title="Authentication failed",
                detail="Check the configured API credential.",
            ),
            presentation(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                status=(
                    ProviderRuntimeDiagnosticStatus
                    .REMOTE_DEPENDENCY_MISSING
                ),
                severity=(
                    api.ProviderDiagnosticPresentationSeverity
                    .WARNING
                ),
                action=(
                    api.ProviderDiagnosticPresentationAction
                    .ADD_REMOTE_SOURCE
                ),
                provider=VisionProviderKind.KIE_AI,
                environment_variable="KIE_API_KEY",
                title="Remote image source required",
                detail="Configure a remote image source.",
            ),
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
                    api.validate_provider_diagnostic_presentation(
                        variant
                    ),
                    value,
                )

    def test_presentation_contains_no_secret_fields(self):
        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                api.ProviderDiagnosticPresentation
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
                "diagnostic_status",
                "severity",
                "action",
                "provider",
                "credential_environment_variable",
                "title",
                "detail",
            },
        )

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_DETAIL_LENGTH",
                "MAX_PROVIDER_DIAGNOSTIC_PRESENTATION_TITLE_LENGTH",
                "PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION",
                "ProviderDiagnosticPresentation",
                "ProviderDiagnosticPresentationAction",
                "ProviderDiagnosticPresentationSeverity",
                "validate_provider_diagnostic_presentation",
            ),
        )


if __name__ == "__main__":
    unittest.main()