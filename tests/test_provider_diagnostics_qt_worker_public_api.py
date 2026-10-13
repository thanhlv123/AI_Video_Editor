"""M98 provider diagnostics Qt worker public API contract.

The package-level API remains backward-compatible with the original M98
worker checkpoint.

The expanded stable M98 interface lives in ``public_api``.
"""

import inspect
import unittest

from PyQt6.QtCore import QObject

import creator_studio.provider_diagnostics_qt_worker as package_api
import creator_studio.provider_diagnostics_qt_worker.public_api as public_api

from creator_studio.provider_diagnostics_qt_worker.bridge import (
    ProviderDiagnosticsQtThreadBridge as DirectThreadBridge,
)
from creator_studio.provider_diagnostics_qt_worker.cancellation import (
    ProviderDiagnosticsQtCancellationToken as DirectCancellationToken,
)
from creator_studio.provider_diagnostics_qt_worker.worker import (
    ProviderDiagnosticsQtWorker as DirectWorker,
)


EXPECTED_PUBLIC_API = (
    "PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION",
    "ProviderDiagnosticsQtCancellationToken",
    "ProviderDiagnosticsQtThreadBridge",
    "ProviderDiagnosticsQtWorker",
)

EXPECTED_PACKAGE_API = (
    "ProviderDiagnosticsQtCancellationToken",
    "ProviderDiagnosticsQtWorker",
)


class ProviderDiagnosticsQtWorkerPublicApiTests(
    unittest.TestCase
):

    def test_public_api_version(self):
        self.assertEqual(
            public_api
            .PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION,
            1,
        )

    def test_public_api_all_is_exact(self):
        self.assertEqual(
            public_api.__all__,
            EXPECTED_PUBLIC_API,
        )

    def test_package_all_preserves_checkpoint_one_contract(self):
        self.assertEqual(
            package_api.__all__,
            EXPECTED_PACKAGE_API,
        )

    def test_public_cancellation_token_identity(self):
        self.assertIs(
            public_api.ProviderDiagnosticsQtCancellationToken,
            DirectCancellationToken,
        )

    def test_package_cancellation_token_identity(self):
        self.assertIs(
            package_api.ProviderDiagnosticsQtCancellationToken,
            DirectCancellationToken,
        )

    def test_public_worker_identity(self):
        self.assertIs(
            public_api.ProviderDiagnosticsQtWorker,
            DirectWorker,
        )

    def test_package_worker_identity(self):
        self.assertIs(
            package_api.ProviderDiagnosticsQtWorker,
            DirectWorker,
        )

    def test_public_thread_bridge_identity(self):
        self.assertIs(
            public_api.ProviderDiagnosticsQtThreadBridge,
            DirectThreadBridge,
        )

    def test_worker_is_qobject_type(self):
        self.assertTrue(
            issubclass(
                public_api.ProviderDiagnosticsQtWorker,
                QObject,
            )
        )

    def test_thread_bridge_is_qobject_type(self):
        self.assertTrue(
            issubclass(
                public_api.ProviderDiagnosticsQtThreadBridge,
                QObject,
            )
        )

    def test_cancellation_token_constructor_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    public_api
                    .ProviderDiagnosticsQtCancellationToken
                ).parameters
            ),
            (),
        )

    def test_worker_constructor_signature(self):
        parameters = (
            inspect.signature(
                public_api.ProviderDiagnosticsQtWorker
            ).parameters
        )

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "request",
                "remote_image_source",
                "parent",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

        self.assertIsNone(
            parameters[
                "parent"
            ].default
        )

    def test_thread_bridge_constructor_signature(self):
        parameters = (
            inspect.signature(
                public_api
                .ProviderDiagnosticsQtThreadBridge
            ).parameters
        )

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "parent",
            ),
        )

        self.assertIsNone(
            parameters[
                "parent"
            ].default
        )

    def test_expanded_symbols_are_not_added_to_package_all(self):
        self.assertNotIn(
            "PROVIDER_DIAGNOSTICS_QT_WORKER_PUBLIC_API_VERSION",
            package_api.__all__,
        )

        self.assertNotIn(
            "ProviderDiagnosticsQtThreadBridge",
            package_api.__all__,
        )

    def test_public_surface_does_not_export_upstream_payload_types(self):
        forbidden = (
            "ProviderDiagnosticsApplicationRequest",
            "ProviderDiagnosticsApplicationResult",
            "ProviderRuntimeDiagnosticReport",
            "ProviderDiagnosticsViewModel",
            "ProviderRuntimeConfig",
            "EnvironmentCredentialSource",
            "ExternalVisionHTTPConfig",
        )

        for name in forbidden:
            with self.subTest(
                name=name
            ):
                self.assertNotIn(
                    name,
                    public_api.__all__,
                )

                self.assertNotIn(
                    name,
                    package_api.__all__,
                )

    def test_public_surface_does_not_export_secret_or_transport_names(self):
        normalized = tuple(
            name.lower()
            for name in public_api.__all__
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