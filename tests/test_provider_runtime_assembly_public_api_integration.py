"""M90 final public API and preset-to-runtime integration.

No real provider network access is performed.

The tests exercise:

    public facade
        -> provider preset
        -> ProviderRuntimeConfig
        -> runtime factory
        -> environment credential source
        -> M89 provider transport
        -> M88 HTTPS boundary
        -> provider response
        -> semantic observation

Credentials used here are test-only values.
"""

import json
import os
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_assembly.credential_source as credential_module
import creator_studio.provider_runtime_assembly.public_api as api
import creator_studio.provider_specific_vision_adapter.provider_http_exchange as exchange_module

from creator_studio.provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)
from creator_studio.semantic_vision_observer import (
    SemanticVisionFailureCode,
    SemanticVisionOutcome,
)
from tests.test_external_vision_http_transport_config import (
    config,
)
from tests.test_external_vision_http_transport_execution import (
    FakeResponse,
)
from tests.test_png8_structural_preflight import (
    capture,
)
from tests.test_provider_specific_vision_adapter_response_extractor import (
    gemini_document,
    kie_document,
    openai_document,
)
from tests.test_raster_feature_runtime import (
    rgba_png,
)


KIE_ENDPOINT = (
    "https://api.kie.ai/"
    "gemini-3-flash/v1/chat/completions"
)

REMOTE_IMAGE_URL = (
    "https://media.example.test/"
    "m90-runtime-image.png?signature=test-only"
)


def provider_body(
    document,
):
    return json.dumps(
        document,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )


class RemoteImageSource(
    ProviderVisionRemoteImageSource
):
    def __init__(
        self,
        value=REMOTE_IMAGE_URL,
    ):
        self.value = value
        self.calls = 0

    def resolve(
        self,
        request,
        check,
    ):
        self.calls += 1

        check()

        return self.value


class ProviderRuntimeAssemblyPublicAPIIntegrationTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.data = rgba_png(
            2,
            2,
            bytes([
                10, 20, 30, 0,
                40, 50, 60, 128,
                70, 80, 90, 255,
                100, 110, 120, 255,
            ]),
        )

        self.source, self.snapshot = capture(
            self.data
        )

    def tearDown(
        self,
    ):
        try:
            self.source.release(
                self.snapshot
            )

        except Exception:
            pass

    def test_public_api(self):
        self.assertEqual(
            api.PROVIDER_RUNTIME_PUBLIC_API_VERSION,
            1,
        )

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
                "DEFAULT_GEMINI_CREDENTIAL_ENVIRONMENT_VARIABLE",
                "DEFAULT_KIE_CREDENTIAL_ENVIRONMENT_VARIABLE",
                "DEFAULT_OPENAI_CREDENTIAL_ENVIRONMENT_VARIABLE",
                "GEMINI_VISION_ENDPOINT",
                "MAX_PROVIDER_ENVIRONMENT_VARIABLE_NAME_LENGTH",
                "OPENAI_VISION_ENDPOINT",
                "PROVIDER_RUNTIME_CONFIG_SCHEMA_VERSION",
                "PROVIDER_RUNTIME_PUBLIC_API_VERSION",
                "EnvironmentCredentialSource",
                "ProviderEnvironmentCredentialMode",
                "ProviderRuntimeAssembly",
                "ProviderRuntimeConfig",
                "assemble_provider_runtime",
                "build_gemini_runtime_config",
                "build_kie_runtime_config",
                "build_openai_runtime_config",
                "validate_provider_runtime_config",
            ),
        )

    def test_build_and_assembly_are_lazy(self):
        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=AssertionError(
                "credential must not be resolved"
            ),
        ) as getenv_mock:
            with patch.object(
                exchange_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not be opened"
                ),
            ) as opened:
                runtime_config = (
                    api.build_openai_runtime_config(
                        "vision-model",
                        config(),
                    )
                )

                assembly = (
                    api.assemble_provider_runtime(
                        runtime_config
                    )
                )

        self.assertIs(
            type(assembly),
            api.ProviderRuntimeAssembly,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_openai_end_to_end(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        secret = "openai-final-test-secret"

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=False,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        openai_document()
                    )
                ),
            ) as opened:
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = (
            opened.call_args.args[
                0
            ]
        )

        headers = {
            name.lower(): value
            for name, value
            in request_value.header_items()
        }

        self.assertEqual(
            request_value.full_url,
            api.OPENAI_VISION_ENDPOINT,
        )

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer "
            + secret,
        )

        self.assertNotIn(
            secret.encode(
                "ascii"
            ),
            request_value.data,
        )

    def test_gemini_end_to_end(self):
        runtime_config = (
            api.build_gemini_runtime_config(
                "gemini-model",
                config(),
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        secret = "gemini-final-test-secret"

        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": secret,
            },
            clear=False,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        gemini_document()
                    )
                ),
            ) as opened:
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = (
            opened.call_args.args[
                0
            ]
        )

        headers = {
            name.lower(): value
            for name, value
            in request_value.header_items()
        }

        self.assertEqual(
            request_value.full_url,
            api.GEMINI_VISION_ENDPOINT,
        )

        self.assertEqual(
            headers[
                "x-goog-api-key"
            ],
            secret,
        )

        self.assertNotIn(
            secret.encode(
                "ascii"
            ),
            request_value.data,
        )

    def test_kie_end_to_end(self):
        runtime_config = (
            api.build_kie_runtime_config(
                "gemini-model",
                KIE_ENDPOINT,
                config(),
            )
        )

        remote_source = (
            RemoteImageSource()
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config,
                remote_source,
            )
        )

        secret = "kie-final-test-secret"

        with patch.dict(
            os.environ,
            {
                "KIE_API_KEY": secret,
            },
            clear=False,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        kie_document()
                    )
                ),
            ) as opened:
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            remote_source.calls,
            1,
        )

        request_value = (
            opened.call_args.args[
                0
            ]
        )

        headers = {
            name.lower(): value
            for name, value
            in request_value.header_items()
        }

        self.assertEqual(
            headers[
                "authorization"
            ],
            "Bearer "
            + secret,
        )

        document = json.loads(
            request_value.data.decode(
                "utf-8"
            )
        )

        remote_url = (
            document[
                "messages"
            ][
                0
            ][
                "content"
            ][
                1
            ][
                "image_url"
            ][
                "url"
            ]
        )

        self.assertEqual(
            remote_url,
            REMOTE_IMAGE_URL,
        )

        self.assertNotIn(
            secret.encode(
                "ascii"
            ),
            request_value.data,
        )

    def test_environment_is_resolved_once_at_send_time(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        calls = []

        def getenv(
            name,
        ):
            calls.append(
                name
            )

            return (
                "lazy-runtime-secret"
            )

        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=getenv,
        ):
            assembly = (
                api.assemble_provider_runtime(
                    runtime_config
                )
            )

            self.assertEqual(
                calls,
                [],
            )

            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        openai_document()
                    )
                ),
            ):
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            calls,
            [
                "OPENAI_API_KEY",
            ],
        )

    def test_custom_environment_variable_is_used(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
                "CUSTOM_OPENAI_KEY",
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        calls = []

        def getenv(
            name,
        ):
            calls.append(
                name
            )

            if name == "CUSTOM_OPENAI_KEY":
                return (
                    "custom-runtime-secret"
                )

            return None

        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=getenv,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        openai_document()
                    )
                ),
            ):
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        self.assertEqual(
            calls,
            [
                "CUSTOM_OPENAI_KEY",
            ],
        )

    def test_missing_environment_maps_adapter_unavailable(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        with patch.object(
            credential_module.os,
            "getenv",
            return_value=None,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
            ) as opened:
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.FAILURE,
        )

        self.assertIs(
            result.failure_code,
            SemanticVisionFailureCode
            .ADAPTER_UNAVAILABLE,
        )

        opened.assert_not_called()

    def test_secret_never_enters_config_repr_or_request_body(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        secret = (
            "unique-m90-final-secret-"
            "5544332211"
        )

        self.assertNotIn(
            secret,
            repr(
                runtime_config
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                assembly
            ),
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": secret,
            },
            clear=False,
        ):
            with patch.object(
                exchange_module,
                "_open_https",
                return_value=FakeResponse(
                    body=provider_body(
                        openai_document()
                    )
                ),
            ) as opened:
                result = (
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )
                )

        self.assertIs(
            result.outcome,
            SemanticVisionOutcome.SUCCESS,
        )

        request_value = (
            opened.call_args.args[
                0
            ]
        )

        self.assertNotIn(
            secret.encode(
                "ascii"
            ),
            request_value.data,
        )

        self.assertNotIn(
            secret,
            repr(
                runtime_config
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                assembly
            ),
        )

    def test_environment_baseexception_not_swallowed(self):
        runtime_config = (
            api.build_openai_runtime_config(
                "vision-model",
                config(),
            )
        )

        assembly = (
            api.assemble_provider_runtime(
                runtime_config
            )
        )

        with patch.object(
            credential_module.os,
            "getenv",
            side_effect=KeyboardInterrupt(),
        ):
            with patch.object(
                exchange_module,
                "_open_https",
            ) as opened:
                with self.assertRaises(
                    KeyboardInterrupt
                ):
                    assembly.runtime.observe(
                        self.source,
                        self.snapshot,
                    )

        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()