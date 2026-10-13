"""M99 diagnostics Qt view binding public API contract tests."""

import inspect
import unittest

from PyQt6.QtCore import QObject

import creator_studio.provider_diagnostics_qt_view as package_api
import creator_studio.provider_diagnostics_qt_view.public_api as view_public_api
import creator_studio.provider_diagnostics_qt_view.binding_api as binding_api

from creator_studio.provider_diagnostics_qt_view.binder import (
    ProviderDiagnosticsQtViewBinder as DirectBinder,
)


EXPECTED_BINDING_API = (
    "PROVIDER_DIAGNOSTICS_QT_VIEW_BINDING_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtViewBinder",
)

EXPECTED_ORIGINAL_VIEW_API = (
    "PROVIDER_DIAGNOSTICS_QT_VIEW_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtView",
)


class ProviderDiagnosticsQtViewBindingApiTests(
    unittest.TestCase
):

    def test_binding_public_api_version(self):
        self.assertEqual(
            binding_api
            .PROVIDER_DIAGNOSTICS_QT_VIEW_BINDING_PUBLIC_API_VERSION,
            1,
        )

    def test_binding_public_api_all_is_exact(self):
        self.assertEqual(
            binding_api.__all__,
            EXPECTED_BINDING_API,
        )

    def test_public_binder_identity(self):
        self.assertIs(
            binding_api.ProviderDiagnosticsQtViewBinder,
            DirectBinder,
        )

    def test_public_binder_is_qobject_type(self):
        self.assertTrue(
            issubclass(
                binding_api.ProviderDiagnosticsQtViewBinder,
                QObject,
            )
        )

    def test_binder_constructor_signature(self):
        parameters = inspect.signature(
            binding_api.ProviderDiagnosticsQtViewBinder
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "view",
                "bridge",
                "parent",
            ),
        )

        self.assertIsNone(
            parameters[
                "parent"
            ].default
        )

    def test_binder_start_signature(self):
        parameters = inspect.signature(
            binding_api
            .ProviderDiagnosticsQtViewBinder
            .start
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "request",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_original_view_public_api_is_unchanged(self):
        self.assertEqual(
            view_public_api.__all__,
            EXPECTED_ORIGINAL_VIEW_API,
        )

        self.assertNotIn(
            "ProviderDiagnosticsQtViewBinder",
            view_public_api.__all__,
        )

    def test_package_api_is_unchanged(self):
        self.assertEqual(
            package_api.__all__,
            EXPECTED_ORIGINAL_VIEW_API,
        )

        self.assertNotIn(
            "ProviderDiagnosticsQtViewBinder",
            package_api.__all__,
        )

    def test_binding_api_does_not_export_upstream_authority_types(self):
        forbidden = (
            "ProviderDiagnosticsApplicationRequest",
            "ProviderDiagnosticsApplicationResult",
            "ProviderRuntimeConfig",
            "ProviderRuntimeAssembly",
            "EnvironmentCredentialSource",
            "ProviderConnectivityProbe",
            "ExternalVisionHTTPConfig",
            "ProviderRuntimeDiagnosticReport",
        )

        for name in forbidden:
            with self.subTest(
                name=name
            ):
                self.assertNotIn(
                    name,
                    binding_api.__all__,
                )

    def test_binding_api_does_not_export_secret_or_transport_names(self):
        normalized = tuple(
            name.lower()
            for name in binding_api.__all__
        )

        forbidden_fragments = (
            "secret",
            "api_key",
            "authorization",
            "credential_value",
            "http_response",
            "provider_response",
        )

        for fragment in forbidden_fragments:
            with self.subTest(
                fragment=fragment
            ):
                self.assertFalse(
                    any(
                        fragment in name
                        for name in normalized
                    )
                )


if __name__ == "__main__":
    unittest.main()