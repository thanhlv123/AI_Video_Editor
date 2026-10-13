"""M91 provider runtime readiness checker."""

import dataclasses
import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_readiness.checker as checker_module

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
)
from creator_studio.provider_runtime_readiness.checker import (
    ProviderRuntimeReadinessChecker,
)
from creator_studio.provider_runtime_readiness.models import (
    ProviderRuntimeReadinessFailureCode,
    ProviderRuntimeReadinessOutcome,
    validate_provider_runtime_readiness_report,
)
from creator_studio.provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    gemini_runtime_config,
    kie_runtime_config,
    openai_runtime_config,
)


REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "readiness-runtime-image.png"
)


class FakeRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
    ):
        self.calls = 0

    def resolve(
        self,
        request,
        check,
    ):
        self.calls += 1

        check()

        return REMOTE_IMAGE_URL


class ProviderRuntimeReadinessCheckerTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.checker = (
            ProviderRuntimeReadinessChecker()
        )

    def test_checker_has_no_instance_state(self):
        self.assertEqual(
            ProviderRuntimeReadinessChecker
            .__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.checker,
                "__dict__",
            )
        )

    def test_check_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderRuntimeReadinessChecker
                    .check
                ).parameters
            ),
            (
                "self",
                "config",
                "check",
                "remote_image_source",
            ),
        )

    def test_openai_ready(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source = source_type.return_value

            source.resolve.return_value = (
                object()
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertIsNone(
            result.failure_code
        )

        self.assertEqual(
            result.credential_environment_variable,
            "OPENAI_API_KEY",
        )

    def test_gemini_ready(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            result = self.checker.check(
                gemini_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "GEMINI_API_KEY",
        )

    def test_kie_ready_with_remote_source(self):
        remote_source = (
            FakeRemoteImageSource()
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            result = self.checker.check(
                kie_runtime_config(),
                lambda: None,
                remote_source,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

    def test_invalid_config_returns_config_invalid(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            result = self.checker.check(
                object(),
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .CONFIG_INVALID,
        )

        self.assertIsNone(
            result.provider
        )

        self.assertIsNone(
            result.credential_environment_variable
        )

        source_type.assert_not_called()

    def test_invalid_config_does_not_touch_environment(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
            side_effect=AssertionError(
                "must not construct credential source"
            ),
        ):
            result = self.checker.check(
                object(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .CONFIG_INVALID,
        )

    def test_kie_missing_remote_source(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            result = self.checker.check(
                kie_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "KIE_API_KEY",
        )

        source_type.assert_not_called()

    def test_kie_invalid_remote_source(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            result = self.checker.check(
                kie_runtime_config(),
                lambda: None,
                object(),
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED,
        )

        source_type.assert_not_called()

    def test_remote_source_is_not_resolved(self):
        remote_source = (
            FakeRemoteImageSource()
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            result = self.checker.check(
                kie_runtime_config(),
                lambda: None,
                remote_source,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

    def test_missing_credential_mapping(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            )
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
        )

    def test_invalid_credential_mapping(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            )
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID,
        )

    def test_resource_credential_failure_maps_internal(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_deadline_credential_failure_maps_internal(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .DEADLINE_EXCEEDED
            )
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_internal_credential_failure_maps_internal(self):
        failure = (
            ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE
            )
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                failure
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_credential_source_constructor_failure_maps_internal(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_credential_source_memory_failure_maps_internal(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
            side_effect=MemoryError(),
        ):
            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_resolve_memory_failure_maps_internal(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                MemoryError()
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_resolve_unexpected_exception_maps_internal(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                RuntimeError(
                    "private"
                )
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertIs(
            result.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

    def test_secret_never_enters_report(self):
        secret = (
            "unique-readiness-secret-998877"
        )

        class Credential:
            value = secret

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                Credential()
            )

            result = self.checker.check(
                openai_runtime_config(),
                lambda: None,
            )

        self.assertNotIn(
            secret,
            repr(
                result
            ),
        )

        self.assertNotIn(
            secret,
            str(
                result
            ),
        )

    def test_credential_source_receives_exact_metadata(self):
        config = (
            gemini_runtime_config()
        )

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            self.checker.check(
                config,
                lambda: None,
            )

        source_type.assert_called_once_with(
            config.credential_environment_variable,
            config.profile.credential_header,
            config.credential_mode,
        )

    def test_check_is_used_repeatedly(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            result = self.checker.check(
                openai_runtime_config(),
                check,
            )

        self.assertIs(
            result.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            6,
        )

    def test_check_exception_not_swallowed(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            raise RuntimeError(
                "caller-check"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^caller-check$",
        ):
            self.checker.check(
                openai_runtime_config(),
                check,
            )

    def test_baseexception_not_swallowed(self):
        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.side_effect = (
                KeyboardInterrupt()
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.checker.check(
                    openai_runtime_config(),
                    lambda: None,
                )

    def test_all_returned_reports_validate(self):
        reports = []

        with patch.object(
            checker_module,
            "EnvironmentCredentialSource",
        ) as source_type:
            source_type.return_value.resolve.return_value = (
                object()
            )

            reports.append(
                self.checker.check(
                    openai_runtime_config(),
                    lambda: None,
                )
            )

        reports.append(
            self.checker.check(
                object(),
                lambda: None,
            )
        )

        reports.append(
            self.checker.check(
                kie_runtime_config(),
                lambda: None,
            )
        )

        for report in reports:
            self.assertIs(
                validate_provider_runtime_readiness_report(
                    report
                ),
                report,
            )


if __name__ == "__main__":
    unittest.main()