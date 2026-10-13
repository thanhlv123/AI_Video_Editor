"""M89 provider-specific vision profile model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_specific_vision_adapter as api

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialHeader,
)


def openai_profile():
    return api.ProviderVisionProfile(
        schema_version=(
            api.PROVIDER_VISION_PROFILE_SCHEMA_VERSION
        ),
        provider=(
            api.VisionProviderKind.OPENAI
        ),
        endpoint=(
            "https://api.openai.com/v1/responses"
        ),
        model="vision-model",
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        request_dialect=(
            api.VisionProviderRequestDialect
            .OPENAI_RESPONSES_V1
        ),
        response_dialect=(
            api.VisionProviderResponseDialect
            .OPENAI_RESPONSES_OUTPUT_TEXT_V1
        ),
        image_input_mode=(
            api.VisionProviderImageInputMode
            .BASE64_DATA_URL
        ),
    )


def gemini_profile():
    return api.ProviderVisionProfile(
        schema_version=(
            api.PROVIDER_VISION_PROFILE_SCHEMA_VERSION
        ),
        provider=(
            api.VisionProviderKind.GEMINI
        ),
        endpoint=(
            "https://generativelanguage.googleapis.com"
            "/v1beta/interactions"
        ),
        model="gemini-model",
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY
        ),
        request_dialect=(
            api.VisionProviderRequestDialect
            .GEMINI_INTERACTIONS_V1
        ),
        response_dialect=(
            api.VisionProviderResponseDialect
            .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1
        ),
        image_input_mode=(
            api.VisionProviderImageInputMode
            .INLINE_BASE64
        ),
    )


def kie_profile():
    return api.ProviderVisionProfile(
        schema_version=(
            api.PROVIDER_VISION_PROFILE_SCHEMA_VERSION
        ),
        provider=(
            api.VisionProviderKind.KIE_AI
        ),
        endpoint=(
            "https://api.kie.ai"
            "/gemini-3-flash/v1/chat/completions"
        ),
        model="gemini-model",
        credential_header=(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION
        ),
        request_dialect=(
            api.VisionProviderRequestDialect
            .KIE_OPENAI_CHAT_COMPLETIONS_V1
        ),
        response_dialect=(
            api.VisionProviderResponseDialect
            .KIE_CHAT_CHOICES_MESSAGE_CONTENT_V1
        ),
        image_input_mode=(
            api.VisionProviderImageInputMode
            .REMOTE_URL
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

    def __repr__(self):
        raise AssertionError(
            "hostile repr"
        )


class ProviderSpecificVisionAdapterModelTests(
    unittest.TestCase
):

    def test_openai_profile_valid(self):
        value = openai_profile()

        self.assertIs(
            api.validate_provider_vision_profile(
                value
            ),
            value,
        )

    def test_gemini_profile_valid(self):
        value = gemini_profile()

        self.assertIs(
            api.validate_provider_vision_profile(
                value
            ),
            value,
        )

    def test_kie_profile_valid(self):
        value = kie_profile()

        self.assertIs(
            api.validate_provider_vision_profile(
                value
            ),
            value,
        )

    def test_profile_is_frozen(self):
        value = openai_profile()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.model = "other"

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                openai_profile(),
                schema_version=version,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_provider_requires_exact_enum(self):
        value = dataclasses.replace(
            openai_profile(),
            provider="OPENAI",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_endpoint_requires_https(self):
        value = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "http://api.openai.com/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_endpoint_rejects_credentials_query_fragment(self):
        variants = [
            (
                "https://user:secret@api.openai.com"
                "/v1/responses"
            ),
            (
                "https://api.openai.com"
                "/v1/responses?key=secret"
            ),
            (
                "https://api.openai.com"
                "/v1/responses#fragment"
            ),
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                openai_profile(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_model_contract(self):
        variants = [
            "",
            " model",
            "model ",
            "model name",
            "\tmodel",
            "mödél",
            (
                "a"
                * (
                    api.MAX_PROVIDER_VISION_MODEL_LENGTH
                    + 1
                )
            ),
        ]

        for model in variants:
            value = dataclasses.replace(
                openai_profile(),
                model=model,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_openai_requires_openai_host(self):
        value = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://example.test/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_openai_requires_responses_path(self):
        value = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://api.openai.com/v1/chat/completions"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_openai_coherence(self):
        variants = [
            dataclasses.replace(
                openai_profile(),
                credential_header=(
                    ExternalVisionHTTPCredentialHeader
                    .X_API_KEY
                ),
            ),
            dataclasses.replace(
                openai_profile(),
                request_dialect=(
                    api.VisionProviderRequestDialect
                    .GEMINI_INTERACTIONS_V1
                ),
            ),
            dataclasses.replace(
                openai_profile(),
                response_dialect=(
                    api.VisionProviderResponseDialect
                    .GEMINI_INTERACTIONS_OUTPUT_TEXT_V1
                ),
            ),
            dataclasses.replace(
                openai_profile(),
                image_input_mode=(
                    api.VisionProviderImageInputMode
                    .INLINE_BASE64
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_gemini_requires_google_host(self):
        value = dataclasses.replace(
            gemini_profile(),
            endpoint=(
                "https://example.test/v1beta/interactions"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_gemini_coherence(self):
        variants = [
            dataclasses.replace(
                gemini_profile(),
                credential_header=(
                    ExternalVisionHTTPCredentialHeader
                    .AUTHORIZATION
                ),
            ),
            dataclasses.replace(
                gemini_profile(),
                image_input_mode=(
                    api.VisionProviderImageInputMode
                    .BASE64_DATA_URL
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_kie_requires_kie_host(self):
        value = dataclasses.replace(
            kie_profile(),
            endpoint=(
                "https://example.test"
                "/gemini-3-flash/v1/chat/completions"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_kie_requires_chat_completions_path(self):
        value = dataclasses.replace(
            kie_profile(),
            endpoint=(
                "https://api.kie.ai/gemini-3-flash/v1/responses"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_vision_profile_invalid$",
        ):
            api.validate_provider_vision_profile(
                value
            )

    def test_kie_coherence(self):
        variants = [
            dataclasses.replace(
                kie_profile(),
                credential_header=(
                    ExternalVisionHTTPCredentialHeader
                    .X_GOOG_API_KEY
                ),
            ),
            dataclasses.replace(
                kie_profile(),
                image_input_mode=(
                    api.VisionProviderImageInputMode
                    .INLINE_BASE64
                ),
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_exact_shape(self):
        base = openai_profile()

        class Subclass(
            api.ProviderVisionProfile
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
            with self.assertRaisesRegex(
                ValueError,
                "^provider_vision_profile_invalid$",
            ):
                api.validate_provider_vision_profile(
                    value
                )

    def test_detached_roundtrips(self):
        for value in (
            openai_profile(),
            gemini_profile(),
            kie_profile(),
        ):
            variants = [
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
            ]

            for variant in variants:
                self.assertEqual(
                    api.validate_provider_vision_profile(
                        variant
                    ),
                    value,
                )

    def test_public_api(self):
        self.assertEqual(
            api.PROVIDER_VISION_PROFILE_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_PROVIDER_VISION_MODEL_LENGTH,
            256,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_VISION_MODEL_LENGTH",
                "PROVIDER_VISION_PROFILE_SCHEMA_VERSION",
                "M88ProviderVisionHTTPExchange",
                "ProviderSpecificVisionTransport",
                "ProviderVisionHTTPExchange",
                "ProviderVisionProfile",
                "ProviderVisionRemoteImageSource",
                "VisionProviderImageInputMode",
                "VisionProviderKind",
                "VisionProviderRequestDialect",
                "VisionProviderResponseDialect",
                "validate_provider_vision_profile",
            ),
        )

        self.assertTrue(
            issubclass(
                api.M88ProviderVisionHTTPExchange,
                api.ProviderVisionHTTPExchange,
            )
        )


if __name__ == "__main__":
    unittest.main()