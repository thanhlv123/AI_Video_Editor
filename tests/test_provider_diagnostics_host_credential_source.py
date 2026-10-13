"""M100 APIKeyManager credential-source adapter tests."""

import copy
import inspect
import pickle
import unittest
from unittest.mock import patch

import creator_studio.provider_diagnostics_host as host_package
import creator_studio.provider_diagnostics_host.public_api as host_api

from config.api_key_manager import (
    APIKeyManager,
)

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)
from creator_studio.provider_diagnostics_host.public_api import (
    APIKeyManagerCredentialSourceFactory,
    PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION,
)
from creator_studio.provider_runtime_assembly import (
    ProviderEnvironmentCredentialMode,
)
from creator_studio.provider_runtime_readiness.public_api import (
    ProviderRuntimeReadinessChecker,
    ProviderRuntimeReadinessOutcome,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


def new_manager():
    """
    Create an exact APIKeyManager instance without running its filesystem
    initialization. Individual methods are patched explicitly by each test.
    """
    return object.__new__(
        APIKeyManager
    )


def single_key_profile(
    profile_id,
    environment_variable,
):
    return {
        "id": profile_id,
        "name": profile_id,
        "env_var": environment_variable,
        "base_url": "",
        "model": "",
        "enabled": True,
    }


def build_openai_source(
    manager,
):
    factory = (
        APIKeyManagerCredentialSourceFactory(
            manager,
            "openai",
        )
    )

    with patch.object(
        APIKeyManager,
        "get_profile",
        return_value=single_key_profile(
            "openai",
            "OPENAI_API_KEY",
        ),
    ):
        source = factory(
            "OPENAI_API_KEY",
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            ProviderEnvironmentCredentialMode
            .BEARER,
        )

    return (
        factory,
        source,
    )


class ProviderDiagnosticsHostCredentialSourceTests(
    unittest.TestCase
):

    def test_public_api_is_exact(
        self,
    ):
        self.assertEqual(
            PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION,
            1,
        )

        expected = (
            "PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION",
            "APIKeyManagerCredentialSourceFactory",
        )

        self.assertEqual(
            host_api.__all__,
            expected,
        )

        self.assertEqual(
            host_package.__all__,
            expected,
        )

        self.assertIs(
            host_package.APIKeyManagerCredentialSourceFactory,
            APIKeyManagerCredentialSourceFactory,
        )

    def test_factory_signatures_are_explicit(
        self,
    ):
        constructor_parameters = (
            inspect.signature(
                APIKeyManagerCredentialSourceFactory
            ).parameters
        )

        self.assertEqual(
            tuple(
                constructor_parameters
            ),
            (
                "api_key_manager",
                "profile_id",
            ),
        )

        call_parameters = (
            inspect.signature(
                APIKeyManagerCredentialSourceFactory
                .__call__
            ).parameters
        )

        self.assertEqual(
            tuple(
                call_parameters
            ),
            (
                "self",
                "environment_variable",
                "header",
                "mode",
            ),
        )

    def test_factory_requires_exact_api_key_manager(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "^api_key_manager_credential_source_factory_invalid$",
        ):
            APIKeyManagerCredentialSourceFactory(
                object(),
                "openai",
            )

    def test_factory_validates_bound_profile_metadata_without_reading_secret(
        self,
    ):
        manager = new_manager()

        factory = (
            APIKeyManagerCredentialSourceFactory(
                manager,
                "openai",
            )
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=single_key_profile(
                    "openai",
                    "OPENAI_API_KEY",
                ),
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                side_effect=AssertionError(
                    "factory construction must not read a secret"
                ),
            ) as get_secret,
        ):
            source = factory(
                "OPENAI_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                ProviderEnvironmentCredentialMode
                .BEARER,
            )

        get_profile.assert_called_once_with(
            "openai"
        )

        get_secret.assert_not_called()

        self.assertIsInstance(
            source,
            ExternalVisionHTTPCredentialSource,
        )

    def test_profile_environment_mismatch_is_rejected(
        self,
    ):
        manager = new_manager()

        factory = (
            APIKeyManagerCredentialSourceFactory(
                manager,
                "openai",
            )
        )

        with patch.object(
            APIKeyManager,
            "get_profile",
            return_value=single_key_profile(
                "openai",
                "KIE_API_KEY",
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^api_key_manager_credential_source_factory_invalid$",
            ):
                factory(
                    "OPENAI_API_KEY",
                    ExternalVisionHTTPCredentialHeader
                    .AUTHORIZATION,
                    ProviderEnvironmentCredentialMode
                    .BEARER,
                )

    def test_multi_field_profile_is_rejected(
        self,
    ):
        manager = new_manager()

        factory = (
            APIKeyManagerCredentialSourceFactory(
                manager,
                "openai",
            )
        )

        profile = single_key_profile(
            "openai",
            "OPENAI_API_KEY",
        )

        profile[
            "fields"
        ] = [
            {
                "key": "secret",
                "env_var": "OPENAI_API_KEY",
                "required": True,
            }
        ]

        with patch.object(
            APIKeyManager,
            "get_profile",
            return_value=profile,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^api_key_manager_credential_source_factory_invalid$",
            ):
                factory(
                    "OPENAI_API_KEY",
                    ExternalVisionHTTPCredentialHeader
                    .AUTHORIZATION,
                    ProviderEnvironmentCredentialMode
                    .BEARER,
                )

    def test_resolve_reads_only_bound_secret_and_formats_bearer(
        self,
    ):
        manager = new_manager()

        factory, source = (
            build_openai_source(
                manager
            )
        )

        secret = (
            "unique-m100-host-openai-secret-314159"
        )

        with (
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value=secret,
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "runtime_environment must not be used"
                ),
            ) as runtime_environment,
        ):
            credential = source.resolve(
                lambda: None
            )

        get_secret.assert_called_once_with(
            "openai"
        )

        runtime_environment.assert_not_called()

        self.assertIs(
            credential.header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertEqual(
            credential.value,
            (
                "Bearer "
                + secret
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                factory
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                source
            ),
        )

    def test_raw_mode_preserves_secret_without_bearer_prefix(
        self,
    ):
        manager = new_manager()

        factory = (
            APIKeyManagerCredentialSourceFactory(
                manager,
                "gemini",
            )
        )

        with patch.object(
            APIKeyManager,
            "get_profile",
            return_value=single_key_profile(
                "gemini",
                "GEMINI_API_KEY",
            ),
        ):
            source = factory(
                "GEMINI_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .X_GOOG_API_KEY,
                ProviderEnvironmentCredentialMode
                .RAW,
            )

        secret = (
            "unique-m100-host-gemini-secret-271828"
        )

        with patch.object(
            APIKeyManager,
            "get_secret",
            return_value=secret,
        ):
            credential = source.resolve(
                lambda: None
            )

        self.assertIs(
            credential.header,
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
        )

        self.assertEqual(
            credential.value,
            secret,
        )

        self.assertNotEqual(
            credential.value,
            (
                "Bearer "
                + secret
            ),
        )

    def test_missing_secret_maps_to_unavailable(
        self,
    ):
        manager = new_manager()

        _, source = (
            build_openai_source(
                manager
            )
        )

        with patch.object(
            APIKeyManager,
            "get_secret",
            return_value="",
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as context:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            context.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .UNAVAILABLE,
        )

    def test_invalid_secret_maps_to_invalid(
        self,
    ):
        manager = new_manager()

        _, source = (
            build_openai_source(
                manager
            )
        )

        with patch.object(
            APIKeyManager,
            "get_secret",
            return_value=" bad-secret ",
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as context:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            context.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .INVALID,
        )

    def test_manager_failure_maps_to_internal_failure(
        self,
    ):
        manager = new_manager()

        _, source = (
            build_openai_source(
                manager
            )
        )

        with patch.object(
            APIKeyManager,
            "get_secret",
            side_effect=RuntimeError(
                "private-keyring-failure"
            ),
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as context:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            context.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            "private-keyring-failure",
            repr(
                context.exception
            ),
        )

    def test_caller_check_failure_propagates_before_secret_lookup(
        self,
    ):
        manager = new_manager()

        _, source = (
            build_openai_source(
                manager
            )
        )

        class Stop(
            BaseException
        ):
            pass

        def check():
            raise Stop()

        with patch.object(
            APIKeyManager,
            "get_secret",
        ) as get_secret:
            with self.assertRaises(
                Stop
            ):
                source.resolve(
                    check
                )

        get_secret.assert_not_called()

    def test_factory_and_source_are_not_copyable_or_pickleable(
        self,
    ):
        manager = new_manager()

        factory, source = (
            build_openai_source(
                manager
            )
        )

        for value in (
            factory,
            source,
        ):
            with self.assertRaises(
                TypeError
            ):
                copy.copy(
                    value
                )

            with self.assertRaises(
                TypeError
            ):
                copy.deepcopy(
                    value
                )

            with self.assertRaises(
                TypeError
            ):
                pickle.dumps(
                    value
                )

    def test_real_m91_injected_path_uses_api_key_manager_adapter(
        self,
    ):
        manager = new_manager()

        factory = (
            APIKeyManagerCredentialSourceFactory(
                manager,
                "openai",
            )
        )

        secret = (
            "unique-m100-host-m91-secret-161803"
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=single_key_profile(
                    "openai",
                    "OPENAI_API_KEY",
                ),
            ),
            patch.object(
                APIKeyManager,
                "get_secret",
                return_value=secret,
            ),
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "M100 diagnostics must not load all secrets"
                ),
            ),
        ):
            report = (
                ProviderRuntimeReadinessChecker()
                .check_with_credential_source_factory(
                    openai_runtime_config(),
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


if __name__ == "__main__":
    unittest.main()