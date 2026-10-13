"""M90 provider runtime configuration contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_runtime_assembly as api

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredentialHeader,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_provider_specific_vision_adapter_models import (
    gemini_profile,
    kie_profile,
    openai_profile,
)


def openai_runtime_config():
    profile = openai_profile()

    return api.ProviderRuntimeConfig(
        schema_version=(
            api.PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION
        ),
        profile=profile,
        http_config=dataclasses.replace(
            config(),
            endpoint=profile.endpoint,
        ),
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        credential_mode=(
            api.ProviderEnvironmentCredentialMode
            .BEARER
        ),
    )


def gemini_runtime_config():
    profile = gemini_profile()

    return api.ProviderRuntimeConfig(
        schema_version=(
            api.PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION
        ),
        profile=profile,
        http_config=dataclasses.replace(
            config(),
            endpoint=profile.endpoint,
        ),
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        credential_mode=(
            api.ProviderEnvironmentCredentialMode
            .RAW
        ),
    )


def kie_runtime_config():
    profile = kie_profile()

    return api.ProviderRuntimeConfig(
        schema_version=(
            api.PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION
        ),
        profile=profile,
        http_config=dataclasses.replace(
            config(),
            endpoint=profile.endpoint,
        ),
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        credential_mode=(
            api.ProviderEnvironmentCredentialMode
            .BEARER
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


class ProviderRuntimeAssemblyRuntimeConfigTests(
    unittest.TestCase
):

    def test_openai_runtime_config_valid(self):
        value = openai_runtime_config()

        self.assertIs(
            api.validate_provider_runtime_config(
                value
            ),
            value,
        )

    def test_gemini_runtime_config_valid(self):
        value = gemini_runtime_config()

        self.assertIs(
            api.validate_provider_runtime_config(
                value
            ),
            value,
        )

    def test_kie_runtime_config_valid(self):
        value = kie_runtime_config()

        self.assertIs(
            api.validate_provider_runtime_config(
                value
            ),
            value,
        )

    def test_config_is_frozen(self):
        value = openai_runtime_config()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.credential_environment_variable = (
                "OTHER_API_KEY"
            )

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                openai_runtime_config(),
                schema_version=version,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_config_invalid$",
            ):
                api.validate_provider_runtime_config(
                    value
                )

    def test_exact_shape_contract(self):
        base = openai_runtime_config()

        class Subclass(
            api.ProviderRuntimeConfig
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
                    "^provider_runtime_config_invalid$",
                ):
                    api.validate_provider_runtime_config(
                        value
                    )

    def test_invalid_provider_profile_rejected(self):
        invalid_profile = dataclasses.replace(
            openai_profile(),
            endpoint=(
                "https://example.test/v1/responses"
            ),
        )

        value = dataclasses.replace(
            openai_runtime_config(),
            profile=invalid_profile,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_profile_requires_exact_type(self):
        value = dataclasses.replace(
            openai_runtime_config(),
            profile=object(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_invalid_http_config_rejected(self):
        invalid_http_config = (
            dataclasses.replace(
                openai_runtime_config()
                .http_config,
                endpoint=(
                    "http://api.openai.com/v1/responses"
                ),
            )
        )

        value = dataclasses.replace(
            openai_runtime_config(),
            http_config=invalid_http_config,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_http_config_requires_exact_type(self):
        value = dataclasses.replace(
            openai_runtime_config(),
            http_config=object(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_profile_endpoint_must_match_http_config(self):
        value = openai_runtime_config()

        mismatched_http = dataclasses.replace(
            value.http_config,
            endpoint=(
                "https://generativelanguage.googleapis.com"
                "/v1beta/interactions"
            ),
        )

        value = dataclasses.replace(
            value,
            http_config=mismatched_http,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_environment_variable_name_contract(self):
        invalid_names = (
            "",
            " OPENAI_API_KEY",
            "OPENAI_API_KEY ",
            "openai_api_key",
            "9OPENAI_API_KEY",
            "OPENAI-API-KEY",
            "OPENAI API KEY",
        )

        for name in invalid_names:
            with self.subTest(
                name=name
            ):
                value = dataclasses.replace(
                    openai_runtime_config(),
                    credential_environment_variable=name,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_runtime_config_invalid$",
                ):
                    api.validate_provider_runtime_config(
                        value
                    )

    def test_credential_mode_requires_exact_enum(self):
        value = dataclasses.replace(
            openai_runtime_config(),
            credential_mode="BEARER",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_authorization_header_requires_bearer_mode(self):
        value = dataclasses.replace(
            openai_runtime_config(),
            credential_mode=(
                api.ProviderEnvironmentCredentialMode
                .RAW
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_non_authorization_header_requires_raw_mode(self):
        value = dataclasses.replace(
            gemini_runtime_config(),
            credential_mode=(
                api.ProviderEnvironmentCredentialMode
                .BEARER
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_config_invalid$",
        ):
            api.validate_provider_runtime_config(
                value
            )

    def test_openai_runtime_metadata(self):
        value = openai_runtime_config()

        self.assertEqual(
            value.credential_environment_variable,
            "OPENAI_API_KEY",
        )

        self.assertIs(
            value.credential_mode,
            api.ProviderEnvironmentCredentialMode
            .BEARER,
        )

        self.assertIs(
            value.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertEqual(
            value.profile.endpoint,
            value.http_config.endpoint,
        )

    def test_gemini_runtime_metadata(self):
        value = gemini_runtime_config()

        self.assertEqual(
            value.credential_environment_variable,
            "GEMINI_API_KEY",
        )

        self.assertIs(
            value.credential_mode,
            api.ProviderEnvironmentCredentialMode
            .RAW,
        )

        self.assertIs(
            value.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
        )

        self.assertEqual(
            value.profile.endpoint,
            value.http_config.endpoint,
        )

    def test_kie_runtime_metadata(self):
        value = kie_runtime_config()

        self.assertEqual(
            value.credential_environment_variable,
            "KIE_API_KEY",
        )

        self.assertIs(
            value.credential_mode,
            api.ProviderEnvironmentCredentialMode
            .BEARER,
        )

        self.assertIs(
            value.profile.credential_header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertEqual(
            value.profile.endpoint,
            value.http_config.endpoint,
        )

    def test_config_contains_no_secret_field(self):
        value = openai_runtime_config()

        names = {
            field.name
            for field
            in dataclasses.fields(
                api.ProviderRuntimeConfig
            )
        }

        self.assertEqual(
            names,
            {
                "schema_version",
                "profile",
                "http_config",
                "credential_environment_variable",
                "credential_mode",
            },
        )

        forbidden = (
            "secret",
            "password",
            "token",
            "api_key",
            "credential_value",
        )

        for name in names:
            lower_name = name.lower()

            for word in forbidden:
                self.assertNotEqual(
                    lower_name,
                    word,
                )

    def test_detached_roundtrips(self):
        for value in (
            openai_runtime_config(),
            gemini_runtime_config(),
            kie_runtime_config(),
        ):
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
                    api.validate_provider_runtime_config(
                        variant
                    ),
                    value,
                )

    def test_public_api(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
            128,
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH",
                "PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION",
                "EnvironmentCredentialSource",
                "ProviderEnvironmentCredentialMode",
                "ProviderRuntimeConfig",
                "validate_provider_runtime_config",
            ),
        )


if __name__ == "__main__":
    unittest.main()