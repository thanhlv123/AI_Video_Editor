"""M90 provider runtime configuration presets."""

import dataclasses
import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_assembly.provider_presets as presets

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialHeader,
)
from creator_studio.provider_runtime_assembly import (
    ProviderEnvironmentCredentialMode,
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderImageInputMode,
    VisionProviderKind,
    VisionProviderRequestDialect,
    VisionProviderResponseDialect,
)
from tests.test_external_vision_http_transport_config import (
    config,
)


KIE_ENDPOINT = (
    "https://api.kie.ai/"
    "gemini-3-flash/v1/chat/completions"
)


class ProviderRuntimeAssemblyProviderPresetTests(
    unittest.TestCase
):

    def template(
        self,
    ):
        return config()

    def test_openai_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    presets.build_openai_runtime_config
                ).parameters
            ),
            (
                "model",
                "http_config",
                "credential_environment_variable",
            ),
        )

    def test_gemini_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    presets.build_gemini_runtime_config
                ).parameters
            ),
            (
                "model",
                "http_config",
                "credential_environment_variable",
            ),
        )

    def test_kie_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    presets.build_kie_runtime_config
                ).parameters
            ),
            (
                "model",
                "endpoint",
                "http_config",
                "credential_environment_variable",
            ),
        )

    def test_openai_success(self):
        result = (
            presets.build_openai_runtime_config(
                "vision-model",
                self.template(),
            )
        )

        self.assertIs(
            type(result),
            ProviderRuntimeConfig,
        )

        self.assertIs(
            validate_provider_runtime_config(
                result
            ),
            result,
        )

        self.assertIs(
            result.profile.provider,
            VisionProviderKind.OPENAI,
        )

        self.assertEqual(
            result.profile.endpoint,
            presets.OPENAI_VISION_ENDPOINT,
        )

        self.assertEqual(
            result.profile.model,
            "vision-model",
        )

        self.assertIs(
            result.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertIs(
            result.profile.request_dialect,
            VisionProviderRequestDialect
            .OPENAI_RESPONSES_V1,
        )

        self.assertIs(
            result.profile.response_dialect,
            VisionProviderResponseDialect
            .OPENAI_RESPONSES_OUTPUT_TEXT_V1,
        )

        self.assertIs(
            result.profile.image_input_mode,
            VisionProviderImageInputMode
            .BASE64_DATA_URL,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "OPENAI_API_KEY",
        )

        self.assertIs(
            result.credential_mode,
            ProviderEnvironmentCredentialMode
            .BEARER,
        )

    def test_gemini_success(self):
        result = (
            presets.build_gemini_runtime_config(
                "gemini-model",
                self.template(),
            )
        )

        self.assertIs(
            type(result),
            ProviderRuntimeConfig,
        )

        self.assertIs(
            validate_provider_runtime_config(
                result
            ),
            result,
        )

        self.assertIs(
            result.profile.provider,
            VisionProviderKind.GEMINI,
        )

        self.assertEqual(
            result.profile.endpoint,
            presets.GEMINI_VISION_ENDPOINT,
        )

        self.assertEqual(
            result.profile.model,
            "gemini-model",
        )

        self.assertIs(
            result.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
        )

        self.assertIs(
            result.profile.request_dialect,
            VisionProviderRequestDialect
            .GEMINI_INTERACTIONS_V1,
        )

        self.assertIs(
            result.profile.response_dialect,
            VisionProviderResponseDialect
            .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1,
        )

        self.assertIs(
            result.profile.image_input_mode,
            VisionProviderImageInputMode
            .INLINE_BASE64,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "GEMINI_API_KEY",
        )

        self.assertIs(
            result.credential_mode,
            ProviderEnvironmentCredentialMode
            .RAW,
        )

    def test_kie_success(self):
        result = (
            presets.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                self.template(),
            )
        )

        self.assertIs(
            type(result),
            ProviderRuntimeConfig,
        )

        self.assertIs(
            validate_provider_runtime_config(
                result
            ),
            result,
        )

        self.assertIs(
            result.profile.provider,
            VisionProviderKind.KIE_AI,
        )

        self.assertEqual(
            result.profile.endpoint,
            KIE_ENDPOINT,
        )

        self.assertEqual(
            result.profile.model,
            "gemini-model",
        )

        self.assertIs(
            result.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertIs(
            result.profile.request_dialect,
            VisionProviderRequestDialect
            .KIE_OPENAI_CHAT_COMPLETIONS_V1,
        )

        self.assertIs(
            result.profile.response_dialect,
            VisionProviderResponseDialect
            .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1,
        )

        self.assertIs(
            result.profile.image_input_mode,
            VisionProviderImageInputMode
            .REMOTE_URL,
        )

        self.assertEqual(
            result.credential_environment_variable,
            "KIE_API_KEY",
        )

        self.assertIs(
            result.credential_mode,
            ProviderEnvironmentCredentialMode
            .BEARER,
        )

    def test_openai_endpoint_is_fixed(self):
        result = (
            presets.build_openai_runtime_config(
                "vision-model",
                self.template(),
            )
        )

        self.assertEqual(
            result.profile.endpoint,
            "https://api.openai.com/v1/responses",
        )

        self.assertEqual(
            result.http_config.endpoint,
            result.profile.endpoint,
        )

    def test_gemini_endpoint_is_fixed(self):
        result = (
            presets.build_gemini_runtime_config(
                "gemini-model",
                self.template(),
            )
        )

        self.assertEqual(
            result.profile.endpoint,
            (
                "https://generativelanguage.googleapis.com"
                "/v1beta/interactions"
            ),
        )

        self.assertEqual(
            result.http_config.endpoint,
            result.profile.endpoint,
        )

    def test_kie_endpoint_is_explicit(self):
        result = (
            presets.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                self.template(),
            )
        )

        self.assertEqual(
            result.profile.endpoint,
            KIE_ENDPOINT,
        )

        self.assertEqual(
            result.http_config.endpoint,
            KIE_ENDPOINT,
        )

    def test_http_policy_is_preserved_except_endpoint(self):
        template = self.template()

        builders = (
            presets.build_openai_runtime_config(
                "vision-model",
                template,
            ),
            presets.build_gemini_runtime_config(
                "gemini-model",
                template,
            ),
            presets.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                template,
            ),
        )

        for result in builders:
            with self.subTest(
                provider=(
                    result.profile.provider
                )
            ):
                self.assertEqual(
                    result.http_config.schema_version,
                    template.schema_version,
                )

                self.assertEqual(
                    result.http_config.timeout_millis,
                    template.timeout_millis,
                )

                self.assertEqual(
                    result.http_config.max_request_bytes,
                    template.max_request_bytes,
                )

                self.assertEqual(
                    result.http_config.max_response_bytes,
                    template.max_response_bytes,
                )

                self.assertIs(
                    result.http_config.header_policy,
                    template.header_policy,
                )

                self.assertEqual(
                    result.http_config.endpoint,
                    result.profile.endpoint,
                )

    def test_template_is_not_mutated(self):
        template = self.template()

        before = dataclasses.replace(
            template
        )

        presets.build_openai_runtime_config(
            "vision-model",
            template,
        )

        self.assertEqual(
            template,
            before,
        )

    def test_custom_environment_variable_openai(self):
        result = (
            presets.build_openai_runtime_config(
                "vision-model",
                self.template(),
                "MY_OPENAI_API_KEY",
            )
        )

        self.assertEqual(
            result.credential_environment_variable,
            "MY_OPENAI_API_KEY",
        )

    def test_custom_environment_variable_gemini(self):
        result = (
            presets.build_gemini_runtime_config(
                "gemini-model",
                self.template(),
                "MY_GEMINI_API_KEY",
            )
        )

        self.assertEqual(
            result.credential_environment_variable,
            "MY_GEMINI_API_KEY",
        )

    def test_custom_environment_variable_kie(self):
        result = (
            presets.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                self.template(),
                "MY_KIE_API_KEY",
            )
        )

        self.assertEqual(
            result.credential_environment_variable,
            "MY_KIE_API_KEY",
        )

    def test_invalid_environment_variable_is_sanitized(self):
        builders = (
            lambda: (
                presets.build_openai_runtime_config(
                    "vision-model",
                    self.template(),
                    "invalid-name",
                )
            ),
            lambda: (
                presets.build_gemini_runtime_config(
                    "gemini-model",
                    self.template(),
                    "invalid-name",
                )
            ),
            lambda: (
                presets.build_kie_runtime_config(
                    "gemini-model",
                    KIE_ENDPOINT,
                    self.template(),
                    "invalid-name",
                )
            ),
        )

        for builder in builders:
            with self.subTest():
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_preset_invalid$",
                ):
                    builder()

    def test_invalid_model_is_sanitized(self):
        builders = (
            lambda: (
                presets.build_openai_runtime_config(
                    "",
                    self.template(),
                )
            ),
            lambda: (
                presets.build_gemini_runtime_config(
                    "",
                    self.template(),
                )
            ),
            lambda: (
                presets.build_kie_runtime_config(
                    "",
                    KIE_ENDPOINT,
                    self.template(),
                )
            ),
        )

        for builder in builders:
            with self.subTest():
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_preset_invalid$",
                ):
                    builder()

    def test_invalid_http_config_type_is_sanitized(self):
        builders = (
            lambda: (
                presets.build_openai_runtime_config(
                    "vision-model",
                    object(),
                )
            ),
            lambda: (
                presets.build_gemini_runtime_config(
                    "gemini-model",
                    object(),
                )
            ),
            lambda: (
                presets.build_kie_runtime_config(
                    "gemini-model",
                    KIE_ENDPOINT,
                    object(),
                )
            ),
        )

        for builder in builders:
            with self.subTest():
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_preset_invalid$",
                ):
                    builder()

    def test_invalid_kie_endpoint_is_sanitized(self):
        invalid = (
            "http://api.kie.ai/"
            "gemini-3-flash/v1/chat/completions"
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_preset_invalid$",
        ):
            presets.build_kie_runtime_config(
                "gemini-model",
                invalid,
                self.template(),
            )

    def test_non_kie_provider_endpoint_cannot_be_injected(self):
        openai = (
            presets.build_openai_runtime_config(
                "vision-model",
                self.template(),
            )
        )

        gemini = (
            presets.build_gemini_runtime_config(
                "gemini-model",
                self.template(),
            )
        )

        self.assertEqual(
            openai.profile.endpoint,
            presets.OPENAI_VISION_ENDPOINT,
        )

        self.assertEqual(
            gemini.profile.endpoint,
            presets.GEMINI_VISION_ENDPOINT,
        )

    def test_builders_are_deterministic(self):
        template = self.template()

        first = (
            presets.build_openai_runtime_config(
                "vision-model",
                template,
            )
        )

        second = (
            presets.build_openai_runtime_config(
                "vision-model",
                template,
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_no_secret_argument_exists(self):
        for function in (
            presets.build_openai_runtime_config,
            presets.build_gemini_runtime_config,
            presets.build_kie_runtime_config,
        ):
            names = set(
                inspect.signature(
                    function
                ).parameters
            )

            self.assertNotIn(
                "secret",
                names,
            )

            self.assertNotIn(
                "api_key",
                names,
            )

            self.assertNotIn(
                "token",
                names,
            )

            self.assertNotIn(
                "credential_value",
                names,
            )

    def test_default_environment_constants(self):
        self.assertEqual(
            presets.DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE,
            "OPENAI_API_KEY",
        )

        self.assertEqual(
            presets.DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE,
            "GEMINI_API_KEY",
        )

        self.assertEqual(
            presets.DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE,
            "KIE_API_KEY",
        )

    def test_endpoint_constants(self):
        self.assertEqual(
            presets.OPENAI_VISION_ENDPOINT,
            "https://api.openai.com/v1/responses",
        )

        self.assertEqual(
            presets.GEMINI_VISION_ENDPOINT,
            (
                "https://generativelanguage.googleapis.com"
                "/v1beta/interactions"
            ),
        )

    def test_memory_error_is_not_reclassified(self):
        with patch.object(
            presets,
            "validate_external_vision_http_config",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                presets.build_openai_runtime_config(
                    "vision-model",
                    self.template(),
                )


if __name__ == "__main__":
    unittest.main()