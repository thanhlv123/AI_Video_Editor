"""M91 provider runtime readiness model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_runtime_readiness as api

from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def ready_report():
    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .READY
        ),
        failure_code=None,
        provider=(
            VisionProviderKind.OPENAI
        ),
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
    )


def credential_missing_report():
    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING
        ),
        provider=(
            VisionProviderKind.OPENAI
        ),
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
    )


def credential_invalid_report():
    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID
        ),
        provider=(
            VisionProviderKind.GEMINI
        ),
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
    )


def remote_source_required_report():
    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            api.ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED
        ),
        provider=(
            VisionProviderKind.KIE_AI
        ),
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
    )


def config_invalid_report():
    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            api.ProviderRuntimeReadinessFailureCode
            .CONFIG_INVALID
        ),
        provider=None,
        credential_environment_variable=None,
    )


def internal_failure_report(
    with_metadata,
):
    if with_metadata:
        provider = (
            VisionProviderKind.OPENAI
        )

        environment_variable = (
            "OPENAI_API_KEY"
        )

    else:
        provider = None
        environment_variable = None

    return api.ProviderRuntimeReadinessReport(
        schema_version=(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=(
            api.ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE
        ),
        provider=provider,
        credential_environment_variable=(
            environment_variable
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


class ProviderRuntimeReadinessModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION,
            1,
        )

    def test_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderRuntimeReadinessOutcome
            },
            {
                "READY",
                "NOT_READY",
            },
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderRuntimeReadinessFailureCode
            },
            {
                "CREDENTIAL_MISSING",
                "CREDENTIAL_INVALID",
                "CONFIG_INVALID",
                "REMOTE_IMAGE_SOURCE_REQUIRED",
                "INTERNAL_FAILURE",
            },
        )

    def test_ready_report_valid(self):
        value = ready_report()

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_credential_missing_report_valid(self):
        value = credential_missing_report()

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_credential_invalid_report_valid(self):
        value = credential_invalid_report()

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_remote_source_required_report_valid(self):
        value = remote_source_required_report()

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_config_invalid_report_valid(self):
        value = config_invalid_report()

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_internal_failure_with_metadata_valid(self):
        value = internal_failure_report(
            True
        )

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_internal_failure_without_metadata_valid(self):
        value = internal_failure_report(
            False
        )

        self.assertIs(
            api.validate_provider_runtime_readiness_report(
                value
            ),
            value,
        )

    def test_report_is_frozen(self):
        value = ready_report()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.outcome = (
                api.ProviderRuntimeReadinessOutcome
                .NOT_READY
            )

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                ready_report(),
                schema_version=version,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_readiness_report_invalid$",
            ):
                api.validate_provider_runtime_readiness_report(
                    value
                )

    def test_exact_shape_contract(self):
        base = ready_report()

        class Subclass(
            api.ProviderRuntimeReadinessReport
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
                    "^provider_runtime_readiness_report_invalid$",
                ):
                    api.validate_provider_runtime_readiness_report(
                        value
                    )

    def test_outcome_requires_exact_enum(self):
        value = dataclasses.replace(
            ready_report(),
            outcome="READY",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
                value
            )

    def test_failure_code_requires_exact_enum(self):
        value = dataclasses.replace(
            credential_missing_report(),
            failure_code="CREDENTIAL_MISSING",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
                value
            )

    def test_ready_requires_no_failure_code(self):
        value = dataclasses.replace(
            ready_report(),
            failure_code=(
                api.ProviderRuntimeReadinessFailureCode
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
                value
            )

    def test_ready_requires_metadata(self):
        variants = (
            dataclasses.replace(
                ready_report(),
                provider=None,
                credential_environment_variable=None,
            ),
            dataclasses.replace(
                ready_report(),
                provider=None,
            ),
            dataclasses.replace(
                ready_report(),
                credential_environment_variable=None,
            ),
        )

        for value in variants:
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_readiness_report_invalid$",
                ):
                    api.validate_provider_runtime_readiness_report(
                        value
                    )

    def test_not_ready_requires_failure_code(self):
        value = dataclasses.replace(
            credential_missing_report(),
            failure_code=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
                value
            )

    def test_metadata_must_be_paired(self):
        variants = (
            dataclasses.replace(
                internal_failure_report(
                    True
                ),
                provider=None,
            ),
            dataclasses.replace(
                internal_failure_report(
                    True
                ),
                credential_environment_variable=None,
            ),
        )

        for value in variants:
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_readiness_report_invalid$",
                ):
                    api.validate_provider_runtime_readiness_report(
                        value
                    )

    def test_config_invalid_rejects_metadata(self):
        value = dataclasses.replace(
            config_invalid_report(),
            provider=(
                VisionProviderKind.OPENAI
            ),
            credential_environment_variable=(
                "OPENAI_API_KEY"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
                value
            )

    def test_credential_failures_require_metadata(self):
        codes = (
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID,
        )

        for code in codes:
            with self.subTest(
                code=code
            ):
                value = (
                    api.ProviderRuntimeReadinessReport(
                        schema_version=(
                            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
                        ),
                        outcome=(
                            api.ProviderRuntimeReadinessOutcome
                            .NOT_READY
                        ),
                        failure_code=code,
                        provider=None,
                        credential_environment_variable=None,
                    )
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_readiness_report_invalid$",
                ):
                    api.validate_provider_runtime_readiness_report(
                        value
                    )

    def test_remote_source_failure_requires_kie(self):
        value = dataclasses.replace(
            remote_source_required_report(),
            provider=(
                VisionProviderKind.OPENAI
            ),
            credential_environment_variable=(
                "OPENAI_API_KEY"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_readiness_report_invalid$",
        ):
            api.validate_provider_runtime_readiness_report(
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
            with self.subTest(
                name=name
            ):
                value = dataclasses.replace(
                    ready_report(),
                    credential_environment_variable=name,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_readiness_report_invalid$",
                ):
                    api.validate_provider_runtime_readiness_report(
                        value
                    )

    def test_detached_roundtrips(self):
        values = (
            ready_report(),
            credential_missing_report(),
            credential_invalid_report(),
            remote_source_required_report(),
            config_invalid_report(),
            internal_failure_report(
                True
            ),
            internal_failure_report(
                False
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
                    api.validate_provider_runtime_readiness_report(
                        variant
                    ),
                    value,
                )

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION",
                "ProviderRuntimeReadinessFailureCode",
                "ProviderRuntimeReadinessOutcome",
                "ProviderRuntimeReadinessReport",
                "validate_provider_runtime_readiness_report",
            ),
        )


if __name__ == "__main__":
    unittest.main()