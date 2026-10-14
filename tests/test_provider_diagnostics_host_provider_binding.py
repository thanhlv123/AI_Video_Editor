"""M100 provider diagnostics host provider/profile binding tests."""

import inspect
import unittest
from unittest.mock import patch

from config.api_key_manager import (
    APIKeyManager,
)

from creator_studio.provider_diagnostics_host.credential_source import (
    APIKeyManagerCredentialSourceFactory,
)
from creator_studio.provider_diagnostics_host.provider_binding import (
    GEMINI_API_KEY_MANAGER_PROFILE_ID,
    KIE_AI_API_KEY_MANAGER_PROFILE_ID,
    OPENAI_API_KEY_MANAGER_PROFILE_ID,
    api_key_manager_profile_id_for_provider,
    bind_api_key_manager_credential_source_factory,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    gemini_runtime_config,
    kie_runtime_config,
    openai_runtime_config,
)


def new_manager():
    return object.__new__(
        APIKeyManager
    )


class ProviderDiagnosticsHostProviderBindingTests(
    unittest.TestCase
):

    def test_canonical_profile_ids_are_exact(
        self,
    ):
        self.assertEqual(
            OPENAI_API_KEY_MANAGER_PROFILE_ID,
            "openai",
        )

        self.assertEqual(
            GEMINI_API_KEY_MANAGER_PROFILE_ID,
            "gemini",
        )

        self.assertEqual(
            KIE_AI_API_KEY_MANAGER_PROFILE_ID,
            "kie_ai",
        )

    def test_provider_mapping_is_exact(
        self,
    ):
        self.assertEqual(
            api_key_manager_profile_id_for_provider(
                VisionProviderKind.OPENAI
            ),
            "openai",
        )

        self.assertEqual(
            api_key_manager_profile_id_for_provider(
                VisionProviderKind.GEMINI
            ),
            "gemini",
        )

        self.assertEqual(
            api_key_manager_profile_id_for_provider(
                VisionProviderKind.KIE_AI
            ),
            "kie_ai",
        )

    def test_non_provider_is_rejected(
        self,
    ):
        for value in (
            None,
            object(),
            "OPENAI",
            "openai",
            1,
            True,
        ):
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_host_provider_invalid$",
                ):
                    api_key_manager_profile_id_for_provider(
                        value
                    )

    def test_binding_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            bind_api_key_manager_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "api_key_manager",
                "config",
            ),
        )

    def test_runtime_configs_bind_to_canonical_profiles(
        self,
    ):
        manager = new_manager()

        cases = (
            (
                openai_runtime_config(),
                "openai",
            ),
            (
                gemini_runtime_config(),
                "gemini",
            ),
            (
                kie_runtime_config(),
                "kie_ai",
            ),
        )

        for config, expected_profile_id in cases:
            with self.subTest(
                provider=(
                    config.profile.provider
                )
            ):
                factory = (
                    bind_api_key_manager_credential_source_factory(
                        manager,
                        config,
                    )
                )

                self.assertIs(
                    type(factory),
                    APIKeyManagerCredentialSourceFactory,
                )

                self.assertEqual(
                    factory.profile_id,
                    expected_profile_id,
                )

    def test_binding_requires_exact_api_key_manager(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_host_binding_invalid$",
        ):
            bind_api_key_manager_credential_source_factory(
                object(),
                openai_runtime_config(),
            )

    def test_binding_rejects_non_runtime_config(
        self,
    ):
        manager = new_manager()

        for value in (
            None,
            object(),
            {},
            "config",
        ):
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_host_binding_invalid$",
                ):
                    bind_api_key_manager_credential_source_factory(
                        manager,
                        value,
                    )

    def test_binding_performs_no_secret_or_bulk_environment_lookup(
        self,
    ):
        manager = new_manager()

        with (
            patch.object(
                APIKeyManager,
                "get_secret",
                side_effect=AssertionError(
                    "binding must not read provider secret"
                ),
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "binding must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                APIKeyManager,
                "get_profile",
                side_effect=AssertionError(
                    "profile validation belongs to source creation"
                ),
            ) as get_profile,
        ):
            factory = (
                bind_api_key_manager_credential_source_factory(
                    manager,
                    openai_runtime_config(),
                )
            )

        get_secret.assert_not_called()
        runtime_environment.assert_not_called()
        get_profile.assert_not_called()

        self.assertEqual(
            factory.profile_id,
            "openai",
        )


if __name__ == "__main__":
    unittest.main()