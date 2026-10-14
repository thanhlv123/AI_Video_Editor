"""M100 provider diagnostics host runtime assembly tests."""

import copy
import inspect
import pickle
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
)

from config.api_key_manager import (
    APIKeyManager,
)

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
)
from creator_studio.provider_diagnostics_host.credential_source import (
    APIKeyManagerCredentialSourceFactory,
)
from creator_studio.provider_diagnostics_host.runtime import (
    ProviderDiagnosticsHost,
)
from creator_studio.provider_diagnostics_qt_view.binding_api import (
    ProviderDiagnosticsQtViewBinder,
)
from creator_studio.provider_diagnostics_qt_view.public_api import (
    ProviderDiagnosticsQtView,
)
from creator_studio.provider_diagnostics_qt_worker.public_api import (
    ProviderDiagnosticsQtThreadBridge,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    gemini_runtime_config,
    kie_runtime_config,
    openai_runtime_config,
)


APP = (
    QApplication.instance()
    or QApplication([])
)


def new_manager():
    return object.__new__(
        APIKeyManager
    )


def build_request(
    config,
):
    return ProviderDiagnosticsApplicationRequest(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=config,
        mode=(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        ),
    )


def running_state():
    return ProviderDiagnosticsGuiControllerState(
        schema_version=(
            PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=(
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING
        ),
        view_model=None,
        failure=None,
    )


class ProviderDiagnosticsHostRuntimeTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.host = (
            ProviderDiagnosticsHost()
        )

        self.manager = (
            new_manager()
        )

        self.view = (
            ProviderDiagnosticsQtView()
        )

        self.bridge = (
            ProviderDiagnosticsQtThreadBridge()
        )

        self.binder = (
            ProviderDiagnosticsQtViewBinder(
                self.view,
                self.bridge,
            )
        )

    def tearDown(
        self,
    ):
        self.binder.deleteLater()
        self.bridge.deleteLater()
        self.view.deleteLater()

        APP.processEvents()

    def test_host_is_stateless_and_signature_is_explicit(
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

        self.assertFalse(
            hasattr(
                self.host,
                "__dict__",
            )
        )

        self.assertEqual(
            repr(
                self.host
            ),
            "ProviderDiagnosticsHost()",
        )

    def test_host_requires_exact_runtime_authority_types(
        self,
    ):
        request = build_request(
            openai_runtime_config()
        )

        cases = (
            (
                object(),
                self.binder,
                request,
            ),
            (
                self.manager,
                object(),
                request,
            ),
            (
                self.manager,
                self.binder,
                object(),
            ),
        )

        for (
            manager,
            binder,
            candidate_request,
        ) in cases:
            with self.subTest(
                manager=type(
                    manager
                ).__name__,
                binder=type(
                    binder
                ).__name__,
                request=type(
                    candidate_request
                ).__name__,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_host_invalid$",
                ):
                    self.host.start(
                        manager,
                        binder,
                        candidate_request,
                    )

    def test_openai_request_binds_openai_factory_and_preserves_request_identity(
        self,
    ):
        request = build_request(
            openai_runtime_config()
        )

        state = running_state()

        captured = {}

        def start(
            binder,
            supplied_request,
            factory,
            remote_image_source=None,
        ):
            captured[
                "request"
            ] = supplied_request

            captured[
                "factory"
            ] = factory

            captured[
                "remote_image_source"
            ] = remote_image_source

            return state

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "start_with_credential_source_factory",
            new=start,
        ):
            returned = self.host.start(
                self.manager,
                self.binder,
                request,
            )

        self.assertIs(
            returned,
            state,
        )

        self.assertIs(
            captured[
                "request"
            ],
            request,
        )

        self.assertIs(
            type(
                captured[
                    "factory"
                ]
            ),
            APIKeyManagerCredentialSourceFactory,
        )

        self.assertEqual(
            captured[
                "factory"
            ].profile_id,
            "openai",
        )

        self.assertIsNone(
            captured[
                "remote_image_source"
            ]
        )

    def test_all_supported_providers_bind_to_expected_factory_profile(
        self,
    ):
        cases = (
            (
                openai_runtime_config(),
                "openai",
            ),
            (
                gemini_runtime_config(),
                "gemini",
            ),
            (
                kie_runtime_config(),
                "kie_ai",
            ),
        )

        for config, expected_profile_id in cases:
            with self.subTest(
                provider=(
                    config.profile.provider
                )
            ):
                request = build_request(
                    config
                )

                captured = {}

                def start(
                    binder,
                    supplied_request,
                    factory,
                    remote_image_source=None,
                ):
                    captured[
                        "factory"
                    ] = factory

                    return running_state()

                with patch.object(
                    ProviderDiagnosticsQtViewBinder,
                    "start_with_credential_source_factory",
                    new=start,
                ):
                    self.host.start(
                        self.manager,
                        self.binder,
                        request,
                    )

                self.assertEqual(
                    captured[
                        "factory"
                    ].profile_id,
                    expected_profile_id,
                )

    def test_remote_image_source_is_transited_exactly(
        self,
    ):
        request = build_request(
            kie_runtime_config()
        )

        remote_image_source = object()

        state = running_state()

        captured = {}

        def start(
            binder,
            supplied_request,
            factory,
            supplied_remote_image_source=None,
        ):
            captured[
                "remote_image_source"
            ] = supplied_remote_image_source

            return state

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "start_with_credential_source_factory",
            new=start,
        ):
            returned = self.host.start(
                self.manager,
                self.binder,
                request,
                remote_image_source,
            )

        self.assertIs(
            returned,
            state,
        )

        self.assertIs(
            captured[
                "remote_image_source"
            ],
            remote_image_source,
        )

    def test_host_itself_never_reads_secret_or_bulk_environment(
        self,
    ):
        request = build_request(
            openai_runtime_config()
        )

        with (
            patch.object(
                APIKeyManager,
                "get_secret",
                side_effect=AssertionError(
                    "host must not read a secret"
                ),
            ) as get_secret,
            patch.object(
                APIKeyManager,
                "runtime_environment",
                side_effect=AssertionError(
                    "host must not load all secrets"
                ),
            ) as runtime_environment,
            patch.object(
                APIKeyManager,
                "get_profile",
                side_effect=AssertionError(
                    "host assembly must remain lazy"
                ),
            ) as get_profile,
            patch.object(
                ProviderDiagnosticsQtViewBinder,
                "start_with_credential_source_factory",
                return_value=running_state(),
            ),
        ):
            self.host.start(
                self.manager,
                self.binder,
                request,
            )

        get_secret.assert_not_called()
        runtime_environment.assert_not_called()
        get_profile.assert_not_called()

    def test_binder_failure_propagates_without_host_retention(
        self,
    ):
        request = build_request(
            openai_runtime_config()
        )

        private_message = (
            "private-m100-host-binder-failure"
        )

        with patch.object(
            ProviderDiagnosticsQtViewBinder,
            "start_with_credential_source_factory",
            side_effect=RuntimeError(
                private_message
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^private-m100-host-binder-failure$",
            ):
                self.host.start(
                    self.manager,
                    self.binder,
                    request,
                )

        self.assertFalse(
            hasattr(
                self.host,
                "__dict__",
            )
        )

        self.assertEqual(
            repr(
                self.host
            ),
            "ProviderDiagnosticsHost()",
        )

    def test_host_is_not_copyable_or_pickleable(
        self,
    ):
        with self.assertRaises(
            TypeError
        ):
            copy.copy(
                self.host
            )

        with self.assertRaises(
            TypeError
        ):
            copy.deepcopy(
                self.host
            )

        with self.assertRaises(
            TypeError
        ):
            pickle.dumps(
                self.host
            )


if __name__ == "__main__":
    unittest.main()