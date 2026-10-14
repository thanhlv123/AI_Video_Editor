"""M100 GUI-support API and diagnostics remote-image marker tests."""

import copy
import inspect
import pickle
import unittest

import creator_studio.provider_diagnostics_host.gui_api as gui_api

from creator_studio.provider_diagnostics_host.gui_api import (
    ProviderDiagnosticsRemoteImageSource,
    ProviderDiagnosticsRequestBuilder,
)
from creator_studio.provider_specific_vision_adapter import (
    ProviderVisionRemoteImageSource,
)


class ProviderDiagnosticsHostGuiApiTests(
    unittest.TestCase
):

    def test_public_api_exact_contract(
        self,
    ):
        self.assertEqual(
            gui_api
            .PROVIDER_DIAGNOSTICS_HOST_GUI_API_VERSION,
            1,
        )

        self.assertEqual(
            gui_api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_HOST_GUI_API_VERSION",
                "ProviderDiagnosticsRemoteImageSource",
                "ProviderDiagnosticsRequestBuilder",
            ),
        )

        self.assertIs(
            gui_api.ProviderDiagnosticsRequestBuilder,
            ProviderDiagnosticsRequestBuilder,
        )

        self.assertIs(
            gui_api.ProviderDiagnosticsRemoteImageSource,
            ProviderDiagnosticsRemoteImageSource,
        )

    def test_remote_image_marker_satisfies_m89_runtime_shape(
        self,
    ):
        source = (
            ProviderDiagnosticsRemoteImageSource()
        )

        self.assertIsInstance(
            source,
            ProviderVisionRemoteImageSource,
        )

    def test_remote_image_resolution_fails_closed(
        self,
    ):
        source = (
            ProviderDiagnosticsRemoteImageSource()
        )

        calls = []

        def check():
            calls.append(
                "check"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "provider_diagnostics_remote_image_resolution_forbidden",
        ):
            source.resolve(
                object(),
                check,
            )

        self.assertEqual(
            calls,
            [
                "check",
            ],
        )

    def test_remote_image_marker_rejects_invalid_check(
        self,
    ):
        source = (
            ProviderDiagnosticsRemoteImageSource()
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "provider_diagnostics_remote_image_source_invalid_check",
        ):
            source.resolve(
                object(),
                None,
            )

    def test_remote_image_marker_copy_pickle_blocked(
        self,
    ):
        source = (
            ProviderDiagnosticsRemoteImageSource()
        )

        for operation in (
            lambda: copy.copy(
                source
            ),
            lambda: copy.deepcopy(
                source
            ),
            lambda: pickle.dumps(
                source
            ),
        ):
            with self.assertRaises(
                TypeError
            ):
                operation()

    def test_remote_image_marker_repr_is_secret_free(
        self,
    ):
        source = (
            ProviderDiagnosticsRemoteImageSource()
        )

        self.assertEqual(
            repr(source),
            "ProviderDiagnosticsRemoteImageSource()",
        )

    def test_remote_image_marker_module_has_no_secret_or_network_authority(
        self,
    ):
        source = inspect.getsource(
            ProviderDiagnosticsRemoteImageSource
        )

        for forbidden in (
            "get_secret",
            "runtime_environment",
            "os.environ",
            "urllib",
            "requests.",
            "keyring",
        ):
            self.assertNotIn(
                forbidden,
                source,
            )


if __name__ == "__main__":
    unittest.main()
