"""M91 provider runtime readiness integration.

These tests exercise the complete readiness path:

    M90 provider preset
        -> ProviderRuntimeConfig
        -> M91 ProviderRuntimeReadinessChecker
        -> environment credential validation
        -> secret-free readiness report

No real network access is performed.
No provider API request is performed.
No remote image URL is resolved.
"""

import os
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_assembly.credential_source as credential_module
import creator_studio.provider_runtime_assembly.public_api as runtime_api
import creator_studio.provider_runtime_readiness.public_api as api
import creator_studio.provider_specific_vision_adapter.provider_http_exchange as exchange_module

from creator_studio.provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)
from tests.test_external_vision_http_transport_config import (
    config,
)


KIE_ENDPOINT = (
    "https://api.kie.ai/"
    "gemini-3-flash/v1/chat/completions"
)

REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "m91-readiness-image.png"
)


class RemoteImageSource(
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


class ProviderRuntimeReadinessIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.checker = (
            api.ProviderRuntimeReadinessChecker()
        )

    def test_public_api_contract(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_READINESS_PUBLIC_API_VERSION,
            1,
        )

        self.assertEqual(
            api.PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_RUNTIME_READINESS_PUBLIC_API_VERSION",
                "PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION",
                "ProviderRuntimeReadinessChecker",
                "ProviderRuntimeReadinessFailureCode",
                "ProviderRuntimeReadinessOutcome",
                "ProviderRuntimeReadinessReport",
                "validate_provider_runtime_readiness_report",
            ),
        )

    def test_openai_ready_from_environment(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "openai-readiness-secret"
                ),
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertIsNone(
            result.failure_code
        )

        self.assertEqual(
            result.credential_environment_variable,
            "OPENAI_API_KEY",
        )

    def test_gemini_ready_from_environment(self):
        runtime_config = (
            runtime_api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": (
                    "gemini-readiness-secret"
                ),
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "GEMINI_API_KEY",
        )

    def test_kie_ready_with_remote_source(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                config(),
            )
        )

        remote_source = (
            RemoteImageSource()
        )

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": (
                    "kie-readiness-secret"
                ),
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
                remote_source,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            remote_source.calls,
            0,
        )

    def test_kie_missing_remote_source(self):
        runtime_config = (
            runtime_api.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                config(),
            )
        )

        with patch.object(
            credential_module.os,
            "getenv",
        ) as getenv_mock:
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            result.failure_code,
            api.ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED,
        )

        getenv_mock.assert_not_called()

    def test_missing_environment_credential(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            result.failure_code,
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
        )

    def test_invalid_environment_credential(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "invalid secret"
                ),
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            result.failure_code,
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID,
        )

    def test_custom_environment_variable(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
                "CUSTOM_OPENAI_KEY",
            )
        )

        with patch.dict(
            os.environ,
            {
                "CUSTOM_OPENAI_KEY": (
                    "custom-readiness-secret"
                ),
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "CUSTOM_OPENAI_KEY",
        )

    def test_readiness_never_opens_network(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "network-free-secret"
                ),
            },
            clear=True,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not open"
                ),
            ) as opened:
                result = self.checker.check(
                    runtime_config,
                    lambda: None,
                )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        opened.assert_not_called()

    def test_secret_never_enters_report(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        secret = (
            "unique-m91-readiness-secret-778899"
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=True,
        ):
            result = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
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

        self.assertEqual(
            set(
                result.__dict__
            ),
            {
                "schema_version",
                "outcome",
                "failure_code",
                "provider",
                "credential_environment_variable",
            },
        )

    def test_invalid_config_touches_no_environment_or_network(self):
        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ) as getenv_mock:
            with patch.object(
                exchange_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not open"
                ),
            ) as opened:
                result = self.checker.check(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            result.outcome,
            api.ProviderRuntimeReadinessOutcome
            .NOT_READY,
        )

        self.assertIs(
            result.failure_code,
            api.ProviderRuntimeReadinessFailureCode
            .CONFIG_INVALID,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_environment_is_rechecked_each_time(self):
        runtime_config = (
            runtime_api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        values = [
            None,
            "second-check-secret",
        ]

        calls = []

        def getenv(
            name,
        ):
            calls.append(
                name
            )

            return values.pop(
                0
            )

        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=getenv,
        ):
            first = self.checker.check(
                runtime_config,
                lambda: None,
            )

            second = self.checker.check(
                runtime_config,
                lambda: None,
            )

        self.assertIs(
            first.failure_code,
            api.ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
        )

        self.assertIs(
            second.outcome,
            api.ProviderRuntimeReadinessOutcome
            .READY,
        )

        self.assertEqual(
            calls,
            [
                "OPENAI_API_KEY",
                "OPENAI_API_KEY",
            ],
        )


if __name__ == "__main__":
    unittest.main()