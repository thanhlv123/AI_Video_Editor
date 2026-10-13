"""M96 provider diagnostics view-model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_diagnostics_view_model as api


def ready_view_model():
    return api.ProviderDiagnosticsViewModel(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Ready",
        detail_text=(
            "Provider configuration is ready."
        ),
        severity=(
            api.ProviderDiagnosticsViewSeverity
            .SUCCESS
        ),
        action=(
            api.ProviderDiagnosticsViewAction
            .NONE
        ),
        action_text="No action required",
        is_ready=True,
    )


def warning_view_model():
    return api.ProviderDiagnosticsViewModel(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Network unavailable",
        detail_text=(
            "Check the network connection and retry."
        ),
        severity=(
            api.ProviderDiagnosticsViewSeverity
            .WARNING
        ),
        action=(
            api.ProviderDiagnosticsViewAction
            .CHECK_NETWORK
        ),
        action_text="Check network",
        is_ready=False,
    )


def error_view_model():
    return api.ProviderDiagnosticsViewModel(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Authentication failed",
        detail_text=(
            "Check the configured API credential."
        ),
        severity=(
            api.ProviderDiagnosticsViewSeverity
            .ERROR
        ),
        action=(
            api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL
        ),
        action_text="Check credential",
        is_ready=False,
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


class ProviderDiagnosticsViewModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
            1,
        )

    def test_text_limit_constants(self):
        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH,
            40,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH,
            80,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH,
            320,
        )

        self.assertEqual(
            api.MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH,
            120,
        )

    def test_severity_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderDiagnosticsViewSeverity
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
                in api.ProviderDiagnosticsViewAction
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

    def test_ready_view_model_valid(self):
        value = ready_view_model()

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                value
            ),
            value,
        )

    def test_warning_view_model_valid(self):
        value = warning_view_model()

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                value
            ),
            value,
        )

    def test_error_view_model_valid(self):
        value = error_view_model()

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                value
            ),
            value,
        )

    def test_view_model_is_frozen(self):
        value = ready_view_model()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.status_text = "Changed"

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                schema_version=version,
            )

            with self.subTest(
                version=version
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_exact_shape_contract(self):
        base = ready_view_model()

        class Subclass(
            api.ProviderDiagnosticsViewModel
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
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_severity_requires_exact_enum(self):
        value = dataclasses.replace(
            ready_view_model(),
            severity="SUCCESS",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                value
            )

    def test_action_requires_exact_enum(self):
        value = dataclasses.replace(
            ready_view_model(),
            action="NONE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                value
            )

    def test_is_ready_requires_exact_bool(self):
        for value_in in (
            1,
            0,
            "true",
            None,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                is_ready=value_in,
            )

            with self.subTest(
                value=value_in
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_ready_requires_success_severity(self):
        for severity in (
            api.ProviderDiagnosticsViewSeverity
            .WARNING,
            api.ProviderDiagnosticsViewSeverity
            .ERROR,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                severity=severity,
            )

            with self.subTest(
                severity=severity
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_ready_requires_none_action(self):
        actions = (
            api.ProviderDiagnosticsViewAction
            .REVIEW_CONFIGURATION,
            api.ProviderDiagnosticsViewAction
            .CONFIGURE_CREDENTIAL,
            api.ProviderDiagnosticsViewAction
            .CHECK_CREDENTIAL,
            api.ProviderDiagnosticsViewAction
            .ADD_REMOTE_SOURCE,
            api.ProviderDiagnosticsViewAction
            .RETRY,
            api.ProviderDiagnosticsViewAction
            .CHECK_NETWORK,
        )

        for action in actions:
            value = dataclasses.replace(
                ready_view_model(),
                action=action,
            )

            with self.subTest(
                action=action
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_nonready_rejects_success_severity(self):
        value = dataclasses.replace(
            warning_view_model(),
            severity=(
                api.ProviderDiagnosticsViewSeverity
                .SUCCESS
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                value
            )

    def test_nonready_rejects_none_action(self):
        value = dataclasses.replace(
            warning_view_model(),
            action=(
                api.ProviderDiagnosticsViewAction
                .NONE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                value
            )

    def test_provider_label_requires_exact_string(self):
        for label in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                provider_label=label,
            )

            with self.subTest(
                label=label
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_provider_label_must_be_nonempty_and_trimmed(self):
        for label in (
            "",
            " ",
            " OpenAI",
            "OpenAI ",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                provider_label=label,
            )

            with self.subTest(
                label=label
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_provider_label_length_contract(self):
        valid = dataclasses.replace(
            ready_view_model(),
            provider_label=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            ready_view_model(),
            provider_label=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                invalid
            )

    def test_provider_label_must_be_printable(self):
        for label in (
            "Open\nAI",
            "Open\rAI",
            "Open\tAI",
            "Open\x00AI",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                provider_label=label,
            )

            with self.subTest(
                label=repr(
                    label
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_status_text_requires_exact_string(self):
        for status in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                status_text=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_status_text_must_be_nonempty_and_trimmed(self):
        for status in (
            "",
            " ",
            " Ready",
            "Ready ",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                status_text=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_status_text_length_contract(self):
        valid = dataclasses.replace(
            ready_view_model(),
            status_text=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            ready_view_model(),
            status_text=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                invalid
            )

    def test_status_text_must_be_printable(self):
        for status in (
            "Ready\nNow",
            "Ready\rNow",
            "Ready\tNow",
            "Ready\x00Now",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                status_text=status,
            )

            with self.subTest(
                status=repr(
                    status
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_detail_text_requires_exact_string(self):
        for detail in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                detail_text=detail,
            )

            with self.subTest(
                detail=detail
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_detail_text_must_be_nonempty_and_trimmed(self):
        for detail in (
            "",
            " ",
            " Detail",
            "Detail ",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                detail_text=detail,
            )

            with self.subTest(
                detail=detail
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_detail_text_length_contract(self):
        valid = dataclasses.replace(
            ready_view_model(),
            detail_text=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            ready_view_model(),
            detail_text=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                invalid
            )

    def test_detail_text_must_be_printable(self):
        for detail in (
            "Detail\nMore",
            "Detail\rMore",
            "Detail\tMore",
            "Detail\x00More",
        ):
            value = dataclasses.replace(
                ready_view_model(),
                detail_text=detail,
            )

            with self.subTest(
                detail=repr(
                    detail
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_action_text_requires_exact_string(self):
        for action_text in (
            None,
            123,
            True,
        ):
            value = dataclasses.replace(
                ready_view_model(),
                action_text=action_text,
            )

            with self.subTest(
                action_text=action_text
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_action_text_must_be_nonempty_and_trimmed(self):
        for action_text in (
            "",
            " ",
            " Retry",
            "Retry ",
        ):
            value = dataclasses.replace(
                warning_view_model(),
                action_text=action_text,
            )

            with self.subTest(
                action_text=action_text
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_action_text_length_contract(self):
        valid = dataclasses.replace(
            ready_view_model(),
            action_text=(
                "A"
                * api.MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH
            ),
        )

        self.assertIs(
            api.validate_provider_diagnostics_view_model(
                valid
            ),
            valid,
        )

        invalid = dataclasses.replace(
            ready_view_model(),
            action_text=(
                "A"
                * (
                    api.MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH
                    + 1
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_view_model_invalid$",
        ):
            api.validate_provider_diagnostics_view_model(
                invalid
            )

    def test_action_text_must_be_printable(self):
        for action_text in (
            "Check\nnetwork",
            "Check\rnetwork",
            "Check\tnetwork",
            "Check\x00network",
        ):
            value = dataclasses.replace(
                warning_view_model(),
                action_text=action_text,
            )

            with self.subTest(
                action_text=repr(
                    action_text
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_view_model_invalid$",
                ):
                    api.validate_provider_diagnostics_view_model(
                        value
                    )

    def test_detached_roundtrips(self):
        values = (
            ready_view_model(),
            warning_view_model(),
            error_view_model(),
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
                    api.validate_provider_diagnostics_view_model(
                        variant
                    ),
                    value,
                )

    def test_view_model_contains_no_runtime_or_secret_fields(self):
        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                api.ProviderDiagnosticsViewModel
            )
        }

        forbidden = {
            "config",
            "credential",
            "credential_value",
            "credential_environment_variable",
            "secret",
            "password",
            "token",
            "api_key",
            "authorization",
            "http_status",
            "provider_code",
            "diagnostic_report",
            "presentation",
            "check",
            "remote_image_source",
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
                "provider_label",
                "status_text",
                "detail_text",
                "severity",
                "action",
                "action_text",
                "is_ready",
            },
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_ACTION_TEXT_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_DETAIL_TEXT_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_PROVIDER_LABEL_LENGTH",
                "MAX_PROVIDER_DIAGNOSTICS_VIEW_STATUS_TEXT_LENGTH",
                "PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION",
                "ProviderDiagnosticsViewAction",
                "ProviderDiagnosticsViewModel",
                "ProviderDiagnosticsViewSeverity",
                "validate_provider_diagnostics_view_model",
            ),
        )


if __name__ == "__main__":
    unittest.main()