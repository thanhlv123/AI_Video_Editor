"""M100 provider diagnostics host runtime public API tests."""

import inspect
import unittest

import creator_studio.provider_diagnostics_host.public_api as credential_api
import creator_studio.provider_diagnostics_host.runtime_api as runtime_api

from creator_studio.provider_diagnostics_host.credential_source import (
    APIKeyManagerCredentialSourceFactory,
)
from creator_studio.provider_diagnostics_host.runtime import (
    ProviderDiagnosticsHost as RuntimeProviderDiagnosticsHost,
)
from creator_studio.provider_diagnostics_host.runtime_api import (
    PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION,
    ProviderDiagnosticsHost,
)


class ProviderDiagnosticsHostRuntimeApiTests(
    unittest.TestCase
):

    def test_runtime_api_version(
        self,
    ):
        self.assertEqual(
            PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION,
            1,
        )

    def test_runtime_api_all_is_exact(
        self,
    ):
        self.assertEqual(
            runtime_api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_RUNTIME_API_VERSION",
                "ProviderDiagnosticsHost",
            ),
        )

    def test_runtime_host_identity(
        self,
    ):
        self.assertIs(
            ProviderDiagnosticsHost,
            RuntimeProviderDiagnosticsHost,
        )

    def test_runtime_host_constructor_signature(
        self,
    ):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderDiagnosticsHost
                ).parameters
            ),
            (),
        )

    def test_runtime_host_start_signature(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsHost.start
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "api_key_manager",
                "binder",
                "request",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_checkpoint_2a_public_api_remains_unchanged(
        self,
    ):
        self.assertEqual(
            credential_api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_PUBLIC_API_VERSION",
                "APIKeyManagerCredentialSourceFactory",
            ),
        )

        self.assertIs(
            credential_api.APIKeyManagerCredentialSourceFactory,
            APIKeyManagerCredentialSourceFactory,
        )

    def test_runtime_api_does_not_export_credential_authority(
        self,
    ):
        forbidden = {
            "APIKeyManager",
            "APIKeyManagerCredentialSourceFactory",
            "EnvironmentCredentialSource",
            "ExternalVisionHTTPCredential",
            "bind_api_key_manager_credential_source_factory",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                runtime_api.__all__
            )
        )


if __name__ == "__main__":
    unittest.main()