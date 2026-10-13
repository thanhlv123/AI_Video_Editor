"""M90 provider runtime factory."""

import copy
import inspect
import os
import pickle
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_assembly.credential_source as credential_module
import creator_studio.provider_runtime_assembly.runtime_factory as factory_module

from creator_studio.external_vision_provider_transport import (
    ExternalVisionSemanticProvider,
)
from creator_studio.provider_runtime_assembly.credential_source import (
    EnvironmentCredentialSource,
)
from creator_studio.provider_runtime_assembly.runtime_factory import (
    ProviderRuntimeAssembly,
    assemble_provider_runtime,
)
from creator_studio.provider_specific_vision_adapter import (
    M88ProviderVisionHTTPExchange,
    ProviderSpecificVisionTransport,
    ProviderVisionRemoteImageSource,
)
from creator_studio.semantic_vision_observer import (
    SemanticVisionObservationRuntime,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    gemini_runtime_config,
    kie_runtime_config,
    openai_runtime_config,
)


REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "runtime-factory-image.png"
)


class FakeRemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
        value=REMOTE_IMAGE_URL,
    ):
        self.value = value

    def resolve(
        self,
        request,
        check,
    ):
        check()

        return self.value


class ProviderRuntimeAssemblyRuntimeFactoryTests(
    unittest.TestCase
):

    def test_factory_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    assemble_provider_runtime
                ).parameters
            ),
            (
                "config",
                "remote_image_source",
            ),
        )

    def test_openai_assembly_success(self):
        config = openai_runtime_config()

        assembly = assemble_provider_runtime(
            config
        )

        self.assertIs(
            type(assembly),
            ProviderRuntimeAssembly,
        )

        self.assertIs(
            assembly.config,
            config,
        )

        self.assertIs(
            type(
                assembly.credential_source
            ),
            EnvironmentCredentialSource,
        )

        self.assertIs(
            type(
                assembly.exchange
            ),
            M88ProviderVisionHTTPExchange,
        )

        self.assertIs(
            type(
                assembly.transport
            ),
            ProviderSpecificVisionTransport,
        )

        self.assertIs(
            type(
                assembly.provider
            ),
            ExternalVisionSemanticProvider,
        )

        self.assertIs(
            type(
                assembly.runtime
            ),
            SemanticVisionObservationRuntime,
        )

    def test_gemini_assembly_success(self):
        config = gemini_runtime_config()

        assembly = assemble_provider_runtime(
            config
        )

        self.assertIs(
            assembly.config,
            config,
        )

        self.assertEqual(
            assembly.credential_source.environment_variable,
            "GEMINI_API_KEY",
        )

        self.assertIs(
            assembly.credential_source.header,
            config.profile.credential_header,
        )

        self.assertIs(
            assembly.credential_source.mode,
            config.credential_mode,
        )

    def test_kie_assembly_success(self):
        config = kie_runtime_config()

        remote_source = (
            FakeRemoteImageSource()
        )

        assembly = assemble_provider_runtime(
            config,
            remote_source,
        )

        self.assertIs(
            assembly.config,
            config,
        )

        self.assertIs(
            type(
                assembly.runtime
            ),
            SemanticVisionObservationRuntime,
        )

    def test_kie_requires_remote_image_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_assembly_invalid$",
        ):
            assemble_provider_runtime(
                kie_runtime_config()
            )

    def test_kie_rejects_invalid_remote_image_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_assembly_invalid$",
        ):
            assemble_provider_runtime(
                kie_runtime_config(),
                object(),
            )

    def test_openai_rejects_remote_image_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_assembly_invalid$",
        ):
            assemble_provider_runtime(
                openai_runtime_config(),
                FakeRemoteImageSource(),
            )

    def test_gemini_rejects_remote_image_source(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_assembly_invalid$",
        ):
            assemble_provider_runtime(
                gemini_runtime_config(),
                FakeRemoteImageSource(),
            )

    def test_invalid_config_is_sanitized(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_assembly_invalid$",
        ):
            assemble_provider_runtime(
                object()
            )

    def test_factory_does_not_read_environment(self):
        config = openai_runtime_config()

        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ):
            assembly = assemble_provider_runtime(
                config
            )

        self.assertIs(
            type(assembly),
            ProviderRuntimeAssembly,
        )

    def test_factory_does_not_require_environment_variable_to_exist(self):
        config = openai_runtime_config()

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            assembly = assemble_provider_runtime(
                config
            )

        self.assertIs(
            type(assembly),
            ProviderRuntimeAssembly,
        )

    def test_credential_source_metadata_is_derived_from_config(self):
        for config in (
            openai_runtime_config(),
            gemini_runtime_config(),
            kie_runtime_config(),
        ):
            with self.subTest(
                provider=(
                    config.profile.provider
                )
            ):
                remote_source = None

                if (
                    config.profile.provider.value
                    == "KIE_AI"
                ):
                    remote_source = (
                        FakeRemoteImageSource()
                    )

                assembly = (
                    assemble_provider_runtime(
                        config,
                        remote_source,
                    )
                )

                source = (
                    assembly.credential_source
                )

                self.assertEqual(
                    source.environment_variable,
                    config.credential_environment_variable,
                )

                self.assertIs(
                    source.header,
                    config.profile.credential_header,
                )

                self.assertIs(
                    source.mode,
                    config.credential_mode,
                )

    def test_exchange_uses_exact_http_config(self):
        config = openai_runtime_config()

        assembly = assemble_provider_runtime(
            config
        )

        self.assertIs(
            assembly.exchange._config,
            config.http_config,
        )

    def test_exchange_uses_exact_credential_source(self):
        assembly = assemble_provider_runtime(
            openai_runtime_config()
        )

        self.assertIs(
            assembly.exchange._credential_source,
            assembly.credential_source,
        )

    def test_transport_uses_exact_profile(self):
        config = openai_runtime_config()

        assembly = assemble_provider_runtime(
            config
        )

        self.assertIs(
            assembly.transport._profile,
            config.profile,
        )

    def test_transport_uses_exact_exchange(self):
        assembly = assemble_provider_runtime(
            openai_runtime_config()
        )

        self.assertIs(
            assembly.transport._exchange,
            assembly.exchange,
        )

    def test_kie_transport_uses_exact_remote_source(self):
        remote_source = (
            FakeRemoteImageSource()
        )

        assembly = assemble_provider_runtime(
            kie_runtime_config(),
            remote_source,
        )

        self.assertIs(
            assembly.transport._remote_image_source,
            remote_source,
        )

    def test_non_kie_transport_has_no_remote_source(self):
        for config in (
            openai_runtime_config(),
            gemini_runtime_config(),
        ):
            with self.subTest(
                provider=(
                    config.profile.provider
                )
            ):
                assembly = (
                    assemble_provider_runtime(
                        config
                    )
                )

                self.assertIsNone(
                    assembly.transport
                    ._remote_image_source
                )

    def test_assembly_repr_contains_metadata_only(self):
        assembly = assemble_provider_runtime(
            openai_runtime_config()
        )

        rendered = repr(
            assembly
        )

        self.assertIn(
            "OPENAI",
            rendered,
        )

        self.assertIn(
            "vision-model",
            rendered,
        )

        self.assertIn(
            "OPENAI_API_KEY",
            rendered,
        )

        self.assertNotIn(
            "Bearer ",
            rendered,
        )

    def test_assembly_has_fixed_slots(self):
        self.assertEqual(
            set(
                ProviderRuntimeAssembly
                .__slots__
            ),
            {
                "_config",
                "_credential_source",
                "_exchange",
                "_transport",
                "_provider",
                "_runtime",
            },
        )

    def test_assembly_is_noncopyable(self):
        assembly = assemble_provider_runtime(
            openai_runtime_config()
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_runtime_assembly_noncopyable$",
        ):
            copy.copy(
                assembly
            )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_runtime_assembly_noncopyable$",
        ):
            copy.deepcopy(
                assembly
            )

    def test_assembly_is_nonserializable(self):
        assembly = assemble_provider_runtime(
            openai_runtime_config()
        )

        with self.assertRaisesRegex(
            TypeError,
            "^provider_runtime_assembly_nonserializable$",
        ):
            pickle.dumps(
                assembly
            )

    def test_validation_memory_error_is_not_reclassified(self):
        with patch.object(
            factory_module,
            "validate_provider_runtime_config",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                assemble_provider_runtime(
                    openai_runtime_config()
                )

    def test_validation_exception_is_sanitized(self):
        with patch.object(
            factory_module,
            "validate_provider_runtime_config",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_assembly_invalid$",
            ):
                assemble_provider_runtime(
                    openai_runtime_config()
                )

    def test_component_constructor_failure_is_sanitized(self):
        with patch.object(
            factory_module,
            "EnvironmentCredentialSource",
            side_effect=RuntimeError(
                "private"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_runtime_assembly_invalid$",
            ):
                assemble_provider_runtime(
                    openai_runtime_config()
                )

    def test_component_memory_error_is_not_reclassified(self):
        with patch.object(
            factory_module,
            "EnvironmentCredentialSource",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                assemble_provider_runtime(
                    openai_runtime_config()
                )

    def test_baseexception_not_swallowed(self):
        with patch.object(
            factory_module,
            "EnvironmentCredentialSource",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(
                KeyboardInterrupt
            ):
                assemble_provider_runtime(
                    openai_runtime_config()
                )


if __name__ == "__main__":
    unittest.main()