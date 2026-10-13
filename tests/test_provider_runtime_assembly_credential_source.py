"""M90 runtime environment credential source contract."""

import inspect
import os
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_assembly as api
import creator_studio.provider_runtime_assembly.credential_source as source_module

from creator_studio.external_vision_http_transport import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
)


class EnvironmentCredentialSourceTests(
    unittest.TestCase
):

    def bearer_source(
        self,
    ):
        return api.EnvironmentCredentialSource(
            "OPENAI_API_KEY",
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            api.ProviderEnvironmentCredentialMode
            .BEARER,
        )

    def raw_source(
        self,
    ):
        return api.EnvironmentCredentialSource(
            "GEMINI_API_KEY",
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
            api.ProviderEnvironmentCredentialMode
            .RAW,
        )

    def test_bearer_source_contract(self):
        source = self.bearer_source()

        self.assertIsInstance(
            source,
            ExternalVisionHTTPCredentialSource,
        )

        self.assertEqual(
            source.environment_variable,
            "OPENAI_API_KEY",
        )

        self.assertIs(
            source.header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertIs(
            source.mode,
            api.ProviderEnvironmentCredentialMode
            .BEARER,
        )

    def test_raw_source_contract(self):
        source = self.raw_source()

        self.assertEqual(
            source.environment_variable,
            "GEMINI_API_KEY",
        )

        self.assertIs(
            source.header,
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
        )

        self.assertIs(
            source.mode,
            api.ProviderEnvironmentCredentialMode
            .RAW,
        )

    def test_bearer_resolve_success(self):
        source = self.bearer_source()

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": (
                    "test-openai-secret"
                ),
            },
            clear=False,
        ):
            result = source.resolve(
                lambda: None
            )

        self.assertIs(
            type(result),
            ExternalVisionHTTPCredential,
        )

        self.assertIs(
            result.header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertEqual(
            result.value,
            "Bearer test-openai-secret",
        )

    def test_raw_resolve_success(self):
        source = self.raw_source()

        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": (
                    "test-gemini-secret"
                ),
            },
            clear=False,
        ):
            result = source.resolve(
                lambda: None
            )

        self.assertIs(
            type(result),
            ExternalVisionHTTPCredential,
        )

        self.assertIs(
            result.header,
            ExternalVisionHTTPCredentialHeader
            .X_GOOG_API_KEY,
        )

        self.assertEqual(
            result.value,
            "test-gemini-secret",
        )

    def test_environment_is_read_at_resolve_time(self):
        source = self.bearer_source()

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "first-secret",
            },
            clear=False,
        ):
            first = source.resolve(
                lambda: None
            )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "second-secret",
            },
            clear=False,
        ):
            second = source.resolve(
                lambda: None
            )

        self.assertEqual(
            first.value,
            "Bearer first-secret",
        )

        self.assertEqual(
            second.value,
            "Bearer second-secret",
        )

    def test_secret_is_not_persisted_on_source(self):
        source = self.bearer_source()

        secret = (
            "unique-runtime-secret-998877"
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=False,
        ):
            credential = source.resolve(
                lambda: None
            )

        self.assertEqual(
            credential.value,
            "Bearer "
            + secret,
        )

        self.assertNotIn(
            secret,
            repr(
                source
            ),
        )

        self.assertFalse(
            hasattr(
                source,
                "_value",
            )
        )

        self.assertFalse(
            hasattr(
                source,
                "_secret",
            )
        )

        self.assertFalse(
            hasattr(
                source,
                "_credential",
            )
        )

    def test_repr_contains_metadata_only(self):
        source = self.bearer_source()

        rendered = repr(
            source
        )

        self.assertIn(
            "OPENAI_API_KEY",
            rendered,
        )

        self.assertIn(
            "Authorization",
            rendered,
        )

        self.assertIn(
            "BEARER",
            rendered,
        )

    def test_missing_environment_variable_maps_unavailable(self):
        source = self.bearer_source()

        with patch.object(
            source_module.os,
            "getenv",
            return_value=None,
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as caught:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .UNAVAILABLE,
        )

    def test_empty_environment_variable_maps_unavailable(self):
        source = self.bearer_source()

        with patch.object(
            source_module.os,
            "getenv",
            return_value="",
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as caught:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .UNAVAILABLE,
        )

    def test_invalid_secret_maps_invalid(self):
        source = self.bearer_source()

        variants = (
            " secret",
            "secret ",
            "secret value",
            "secret\nvalue",
            "secret\tvalue",
            "sëcret",
        )

        for value in variants:
            with self.subTest(
                value=repr(
                    value
                )
            ):
                with patch.object(
                    source_module.os,
                    "getenv",
                    return_value=value,
                ):
                    with self.assertRaises(
                        ExternalVisionHTTPCredentialFailure
                    ) as caught:
                        source.resolve(
                            lambda: None
                        )

                self.assertIs(
                    caught.exception.code,
                    ExternalVisionHTTPCredentialFailureCode
                    .INVALID,
                )

    def test_environment_name_contract(self):
        invalid = (
            "",
            " OPENAI_API_KEY",
            "OPENAI_API_KEY ",
            "openai_api_key",
            "9OPENAI_API_KEY",
            "OPENAI-API-KEY",
            "OPENAI API KEY",
            "OPENAI.API.KEY",
            (
                "A"
                * (
                    api.MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH
                    + 1
                )
            ),
        )

        for value in invalid:
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^environment_credential_source_invalid$",
                ):
                    api.EnvironmentCredentialSource(
                        value,
                        ExternalVisionHTTPCredentialHeader
                        .AUTHORIZATION,
                        api.ProviderEnvironmentCredentialMode
                        .BEARER,
                    )

    def test_environment_name_boundary(self):
        name = (
            "A"
            * api.MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH
        )

        source = (
            api.EnvironmentCredentialSource(
                name,
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                api.ProviderEnvironmentCredentialMode
                .BEARER,
            )
        )

        self.assertEqual(
            source.environment_variable,
            name,
        )

    def test_environment_name_may_begin_underscore(self):
        source = (
            api.EnvironmentCredentialSource(
                "_PROVIDER_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                api.ProviderEnvironmentCredentialMode
                .BEARER,
            )
        )

        self.assertEqual(
            source.environment_variable,
            "_PROVIDER_API_KEY",
        )

    def test_header_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^environment_credential_source_invalid$",
        ):
            api.EnvironmentCredentialSource(
                "OPENAI_API_KEY",
                "Authorization",
                api.ProviderEnvironmentCredentialMode
                .BEARER,
            )

    def test_mode_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^environment_credential_source_invalid$",
        ):
            api.EnvironmentCredentialSource(
                "OPENAI_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                "BEARER",
            )

    def test_bearer_requires_authorization_header(self):
        with self.assertRaisesRegex(
            ValueError,
            "^environment_credential_source_invalid$",
        ):
            api.EnvironmentCredentialSource(
                "GEMINI_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .X_GOOG_API_KEY,
                api.ProviderEnvironmentCredentialMode
                .BEARER,
            )

    def test_raw_rejects_authorization_header(self):
        with self.assertRaisesRegex(
            ValueError,
            "^environment_credential_source_invalid$",
        ):
            api.EnvironmentCredentialSource(
                "OPENAI_API_KEY",
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                api.ProviderEnvironmentCredentialMode
                .RAW,
            )

    def test_resolve_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    api.EnvironmentCredentialSource
                    .resolve
                ).parameters
            ),
            (
                "self",
                "check",
            ),
        )

    def test_check_is_used_repeatedly(self):
        source = self.bearer_source()

        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-secret",
            },
            clear=False,
        ):
            result = source.resolve(
                check
            )

        self.assertIs(
            type(result),
            ExternalVisionHTTPCredential,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            4,
        )

    def test_environment_memory_error_mapping(self):
        source = self.bearer_source()

        with patch.object(
            source_module.os,
            "getenv",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as caught:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_environment_unexpected_exception_mapping(self):
        source = self.bearer_source()

        with patch.object(
            source_module.os,
            "getenv",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            with self.assertRaises(
                ExternalVisionHTTPCredentialFailure
            ) as caught:
                source.resolve(
                    lambda: None
                )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .INTERNAL_FAILURE,
        )

    def test_check_exception_not_swallowed(self):
        source = self.bearer_source()

        def check():
            raise RuntimeError(
                "private"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^private$",
        ):
            source.resolve(
                check
            )

    def test_baseexception_not_swallowed(self):
        source = self.bearer_source()

        def check():
            raise KeyboardInterrupt()

        with self.assertRaises(
            KeyboardInterrupt
        ):
            source.resolve(
                check
            )

    def test_public_api(self):
        self.assertEqual(
            api.MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH,
            128,
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderEnvironmentCredentialMode
            },
            {
                "BEARER",
                "RAW",
            },
        )

        self.assertEqual(
            api.__all__,
            (
                "MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH",
                "EnvironmentCredentialSource",
                "ProviderEnvironmentCredentialMode",
            ),
        )


if __name__ == "__main__":
    unittest.main()