"""M100 M91 credential-source injection seam tests.

These tests establish a runtime-only credential-source factory seam in M91
without changing the original ``ProviderRuntimeReadinessChecker.check``
contract.

The seam must:

- preserve the original environment-backed execution path;
- allow an explicitly supplied runtime source factory;
- pass provider credential metadata to that factory;
- preserve caller-owned check/cancellation authority;
- keep the factory and resolved secret out of detached readiness reports;
- keep the checker stateless.
"""

import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_readiness.checker as readiness_module

from creator_studio.provider_runtime_readiness.public_api import (
    ProviderRuntimeReadinessChecker,
    ProviderRuntimeReadinessFailureCode,
    ProviderRuntimeReadinessOutcome,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


class FakeCredential:
    def __init__(
        self,
        header,
        value,
    ):
        self.header = header
        self.value = value


class FakeCredentialSource:
    def __init__(
        self,
        credential,
        *,
        resolve_calls=None,
    ):
        self.credential = credential
        self.resolve_calls = resolve_calls

    def resolve(
        self,
        check,
    ):
        if self.resolve_calls is not None:
            self.resolve_calls.append(
                check
            )

        check()

        return self.credential


class ProviderRuntimeReadinessCredentialSourceInjectionTests(
    unittest.TestCase
):

    def test_original_check_signature_is_unchanged(
        self,
    ):
        parameters = inspect.signature(
            ProviderRuntimeReadinessChecker.check
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "check",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_check_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderRuntimeReadinessChecker
            .check_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "check",
                "credential_source_factory",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_factory_receives_exact_runtime_metadata(
        self,
    ):
        config = openai_runtime_config()

        calls = []

        source = FakeCredentialSource(
            FakeCredential(
                config.profile.credential_header,
                "m100-readiness-secret",
            )
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            calls.append(
                (
                    environment_variable,
                    header,
                    mode,
                )
            )

            return source

        with patch.object(
            readiness_module,
            "EnvironmentCredentialSource",
            side_effect=AssertionError(
                "default environment source must not be used"
            ),
        ) as default_source:
            report = (
                ProviderRuntimeReadinessChecker()
                .check_with_credential_source_factory(
                    config,
                    lambda: None,
                    factory,
                )
            )

        default_source.assert_not_called()

        self.assertEqual(
            calls,
            [
                (
                    config.credential_environment_variable,
                    config.profile.credential_header,
                    config.credential_mode,
                )
            ],
        )

        self.assertIs(
            report.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertIsNone(
            report.failure_code
        )

    def test_injected_source_receives_exact_check_callable(
        self,
    ):
        config = openai_runtime_config()

        resolve_calls = []

        source = FakeCredentialSource(
            FakeCredential(
                config.profile.credential_header,
                "m100-check-identity-secret",
            ),
            resolve_calls=resolve_calls,
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            return source

        def check():
            return None

        report = (
            ProviderRuntimeReadinessChecker()
            .check_with_credential_source_factory(
                config,
                check,
                factory,
            )
        )

        self.assertIs(
            report.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            resolve_calls,
            [
                check
            ],
        )

    def test_factory_failure_maps_to_internal_failure(
        self,
    ):
        config = openai_runtime_config()

        private_message = (
            "private-m100-readiness-factory-failure"
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            raise RuntimeError(
                private_message
            )

        report = (
            ProviderRuntimeReadinessChecker()
            .check_with_credential_source_factory(
                config,
                lambda: None,
                factory,
            )
        )

        self.assertIs(
            report.outcome,
            ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            report.failure_code,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            private_message,
            repr(
                report
            ),
        )

    def test_secret_and_factory_are_not_retained(
        self,
    ):
        config = openai_runtime_config()

        secret = (
            "unique-m100-readiness-secret-741852"
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            return FakeCredentialSource(
                FakeCredential(
                    header,
                    secret,
                )
            )

        checker = (
            ProviderRuntimeReadinessChecker()
        )

        report = (
            checker
            .check_with_credential_source_factory(
                config,
                lambda: None,
                factory,
            )
        )

        self.assertIs(
            report.outcome,
            ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertNotIn(
            secret,
            repr(
                report
            ),
        )

        self.assertFalse(
            hasattr(
                checker,
                "__dict__",
            )
        )


if __name__ == "__main__":
    unittest.main()