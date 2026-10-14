"""M100 provider diagnostics host detached request builder tests."""

import copy
import inspect
import pickle
import unittest
from unittest.mock import patch

from config.api_key_manager import (
    APIKeyManager,
)

import creator_studio.provider_diagnostics_host.public_api as host_public_api
import creator_studio.provider_diagnostics_host.runtime_api as host_runtime_api
from creator_studio.external_vision_http_transport import (
    MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES,
    MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES,
    ExternalVisionHTTPHeaderPolicy,
)
from creator_studio.provider_diagnostics_application.public_api import (
    ProviderDiagnosticsApplicationRequest,
    validate_provider_diagnostics_application_request,
)
from creator_studio.provider_diagnostics_host.request_api import (
    PROVIDER_DIAGNOSTICS_HOST_REQUEST_API_VERSION,
    ProviderDiagnosticsRequestBuilder,
)
from creator_studio.provider_diagnostics_host.request_builder import (
    KIE_AI_DIAGNOSTICS_ENDPOINT,
    KIE_AI_DIAGNOSTICS_PROFILE_ID,
    PROVIDER_DIAGNOSTICS_REQUEST_TIMEOUT_MILLIS,
)
from creator_studio.provider_runtime_assembly.public_api import (
    ProviderEnvironmentCredentialMode,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderImageInputMode,
    VisionProviderKind,
    VisionProviderRequestDialect,
    VisionProviderResponseDialect,
)


def new_manager():
    return object.__new__(
        APIKeyManager
    )


def kie_profile(
    *,
    model="gpt-6-luna",
    environment_variable="KIE_API_KEY",
    base_url="",
    fields=None,
):
    profile = {
        "id": "kie_ai",
        "name": "KIE AI",
        "env_var": environment_variable,
        "base_url": base_url,
        "model": model,
        "enabled": True,
    }

    if fields is not None:
        profile[
            "fields"
        ] = fields

    return profile


class ProviderDiagnosticsHostRequestBuilderTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.builder = (
            ProviderDiagnosticsRequestBuilder()
        )

        self.manager = new_manager()

    def build(
        self,
        mode=(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        ),
        profile=None,
    ):
        if profile is None:
            profile = kie_profile()

        with patch.object(
            APIKeyManager,
            "get_profile",
            return_value=profile,
        ) as get_profile:
            request = (
                self.builder.build_kie(
                    self.manager,
                    mode,
                )
            )

        return (
            request,
            get_profile,
        )

    def test_public_request_api_is_narrow_and_versioned(
        self,
    ):
        self.assertEqual(
            PROVIDER_DIAGNOSTICS_HOST_REQUEST_API_VERSION,
            1,
        )

        import creator_studio.provider_diagnostics_host.request_api as api

        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_REQUEST_API_VERSION",
                "ProviderDiagnosticsRequestBuilder",
            ),
        )

    def test_existing_host_public_apis_remain_unchanged(
        self,
    ):
        self.assertEqual(
            host_public_api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION",
                "APIKeyManagerCredentialSourceFactory",
            ),
        )

        self.assertEqual(
            host_runtime_api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION",
                "ProviderDiagnosticsHost",
            ),
        )

    def test_builder_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsRequestBuilder.build_kie
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "api_key_manager",
                "mode",
            ),
        )

    def test_offline_builds_valid_kie_responses_request(
        self,
    ):
        request, get_profile = self.build()

        self.assertIs(
            type(request),
            ProviderDiagnosticsApplicationRequest,
        )

        self.assertIs(
            validate_provider_diagnostics_application_request(
                request
            ),
            request,
        )

        self.assertIs(
            request.mode,
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

        config = request.config

        self.assertIs(
            config.profile.provider,
            VisionProviderKind.KIE_AI,
        )

        self.assertEqual(
            config.profile.endpoint,
            KIE_AI_DIAGNOSTICS_ENDPOINT,
        )

        self.assertEqual(
            config.http_config.endpoint,
            KIE_AI_DIAGNOSTICS_ENDPOINT,
        )

        self.assertEqual(
            config.profile.model,
            "gpt-6-luna",
        )

        self.assertEqual(
            config.credential_environment_variable,
            "KIE_API_KEY",
        )

        self.assertIs(
            config.credential_mode,
            ProviderEnvironmentCredentialMode
            .BEARER,
        )

        self.assertIs(
            config.profile.request_dialect,
            VisionProviderRequestDialect
            .KIE_OPENAI_RESPONSES_V1,
        )

        self.assertIs(
            config.profile.response_dialect,
            VisionProviderResponseDialect
            .KIE_RESPONSES_OUTPUT_TEXT_V1,
        )

        self.assertIs(
            config.profile.image_input_mode,
            VisionProviderImageInputMode
            .REMOTE_URL,
        )

        get_profile.assert_called_once_with(
            KIE_AI_DIAGNOSTICS_PROFILE_ID
        )

    def test_online_mode_is_preserved_without_execution(
        self,
    ):
        request, _ = self.build(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        self.assertIs(
            request.mode,
            ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

    def test_http_bounds_match_m90_runtime_policy(
        self,
    ):
        request, _ = self.build()
        http_config = request.config.http_config

        self.assertEqual(
            http_config.timeout_millis,
            PROVIDER_DIAGNOSTICS_REQUEST_TIMEOUT_MILLIS,
        )

        self.assertEqual(
            http_config.max_request_bytes,
            MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES,
        )

        self.assertEqual(
            http_config.max_response_bytes,
            MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES,
        )

        self.assertIs(
            http_config.header_policy,
            ExternalVisionHTTPHeaderPolicy
            .STRICT_JSON_V1,
        )

    def test_profile_model_and_environment_metadata_are_used(
        self,
    ):
        request, _ = self.build(
            profile=(
                kie_profile(
                    model="gpt-6-sol",
                    environment_variable=(
                        "CUSTOM_KIE_API_KEY"
                    ),
                )
            )
        )

        self.assertEqual(
            request.config.profile.model,
            "gpt-6-sol",
        )

        self.assertEqual(
            request.config.credential_environment_variable,
            "CUSTOM_KIE_API_KEY",
        )

    def test_profile_base_url_cannot_redirect_production_diagnostics(
        self,
    ):
        request, _ = self.build(
            profile=(
                kie_profile(
                    base_url=(
                        "https://redirect.invalid/private"
                    )
                )
            )
        )

        self.assertEqual(
            request.config.profile.endpoint,
            KIE_AI_DIAGNOSTICS_ENDPOINT,
        )

        self.assertEqual(
            request.config.http_config.endpoint,
            KIE_AI_DIAGNOSTICS_ENDPOINT,
        )

    def test_build_performs_no_secret_or_bulk_runtime_lookup(
        self,
    ):
        profile = kie_profile()
        sentinel_secret = (
            "unique-m100-request-builder-secret-86420"
        )

        with (
            patch.object(
                APIKeyManager,
                "get_profile",
                return_value=profile,
            ) as get_profile,
            patch.object(
                APIKeyManager,
                "get_secret",
                side_effect=AssertionError(
                    "request builder must not read secret"
                ),
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "request builder must not load secrets"
                ),
            ) as runtime_environment,
            patch.object(
                APIKeyManager,
                "runtime_provider_settings",
                side_effect=AssertionError(
                    "request builder must use only one profile"
                ),
            ) as runtime_provider_settings,
        ):
            request = (
                self.builder.build_kie(
                    self.manager,
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )
            )

        get_profile.assert_called_once_with(
            "kie_ai"
        )
        get_secret.assert_not_called()
        runtime_environment.assert_not_called()
        runtime_provider_settings.assert_not_called()

        self.assertNotIn(
            sentinel_secret,
            repr(
                request
            ),
        )

        self.assertNotIn(
            sentinel_secret,
            repr(
                self.builder
            ),
        )

    def test_invalid_authority_or_mode_is_rejected_before_profile_lookup(
        self,
    ):
        with patch.object(
            APIKeyManager,
            "get_profile",
        ) as get_profile:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_request_builder_invalid$",
            ):
                self.builder.build_kie(
                    object(),
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_request_builder_invalid$",
            ):
                self.builder.build_kie(
                    self.manager,
                    "OFFLINE",
                )

        get_profile.assert_not_called()

    def test_invalid_kie_profile_metadata_is_rejected(
        self,
    ):
        cases = (
            None,
            {},
            {
                "id": "openai",
                "model": "gpt-6-luna",
                "env_var": "KIE_API_KEY",
            },
            kie_profile(
                model=""
            ),
            kie_profile(
                model=" gpt-6-luna "
            ),
            kie_profile(
                environment_variable=""
            ),
            kie_profile(
                fields=[
                    {
                        "key": "secret"
                    }
                ]
            ),
        )

        for profile in cases:
            with self.subTest(
                profile=profile
            ):
                with patch.object(
                    APIKeyManager,
                    "get_profile",
                    return_value=profile,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "^provider_diagnostics_request_builder_invalid$",
                    ):
                        self.builder.build_kie(
                            self.manager,
                            ProviderRuntimeDiagnosticMode
                            .OFFLINE,
                        )

    def test_profile_lookup_failure_is_internal_and_memory_error_propagates(
        self,
    ):
        with patch.object(
            APIKeyManager,
            "get_profile",
            side_effect=RuntimeError(
                "private storage failure"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^provider_diagnostics_request_builder_internal$",
            ):
                self.builder.build_kie(
                    self.manager,
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

        with patch.object(
            APIKeyManager,
            "get_profile",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                self.builder.build_kie(
                    self.manager,
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE,
                )

    def test_builder_is_stateless_and_not_copyable_or_picklable(
        self,
    ):
        self.assertEqual(
            ProviderDiagnosticsRequestBuilder.__slots__,
            (),
        )

        self.assertEqual(
            repr(
                self.builder
            ),
            "ProviderDiagnosticsRequestBuilder()",
        )

        with self.assertRaises(
            TypeError
        ):
            copy.copy(
                self.builder
            )

        with self.assertRaises(
            TypeError
        ):
            copy.deepcopy(
                self.builder
            )

        with self.assertRaises(
            TypeError
        ):
            pickle.dumps(
                self.builder
            )


if __name__ == "__main__":
    unittest.main()
