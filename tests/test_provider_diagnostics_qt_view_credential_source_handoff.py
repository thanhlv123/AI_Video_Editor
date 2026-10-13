"""M100 M99 credential-source transit tests.

The M99 binder remains a presentation/execution binding boundary.

It may transit caller-owned runtime arguments to M98, but it must not create,
resolve, inspect or retain credential authority itself.
"""

import inspect
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
)

from creator_studio.provider_diagnostics_gui_controller.public_api import (
    PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
    ProviderDiagnosticsGuiControllerPhase,
    ProviderDiagnosticsGuiControllerState,
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


APP = (
    QApplication.instance()
    or QApplication([])
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


class ProviderDiagnosticsQtViewCredentialSourceHandoffTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
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
        self.view.deleteLater()
        self.bridge.deleteLater()
        self.binder.deleteLater()

        APP.processEvents()

    def test_original_start_signature_is_unchanged(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsQtViewBinder.start
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

    def test_injected_start_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsQtViewBinder
            .start_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "request",
                "credential_source_factory",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_start_transits_exact_runtime_arguments(
        self,
    ):
        request = object()
        factory = object()
        remote_image_source = object()

        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start_with_credential_source_factory",
            return_value=state,
        ) as started:
            returned = (
                self.binder
                .start_with_credential_source_factory(
                    request,
                    factory,
                    remote_image_source,
                )
            )

        started.assert_called_once_with(
            request,
            factory,
            remote_image_source,
        )

        self.assertIs(
            returned,
            state,
        )

    def test_injected_start_renders_and_emits_running_state(
        self,
    ):
        state = running_state()

        emitted = []

        self.binder.state_changed.connect(
            emitted.append
        )

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start_with_credential_source_factory",
            return_value=state,
        ):
            returned = (
                self.binder
                .start_with_credential_source_factory(
                    object(),
                    object(),
                )
            )

        self.assertIs(
            returned,
            state,
        )

        self.assertIs(
            self.binder.phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertEqual(
            emitted,
            [
                state
            ],
        )

    def test_injected_start_failure_does_not_render_running(
        self,
    ):
        initial_phase = (
            self.binder.phase
        )

        emitted = []

        self.binder.state_changed.connect(
            emitted.append
        )

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start_with_credential_source_factory",
            side_effect=RuntimeError(
                "private-m100-binder-start-failure"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^private-m100-binder-start-failure$",
            ):
                (
                    self.binder
                    .start_with_credential_source_factory(
                        object(),
                        object(),
                    )
                )

        self.assertIs(
            self.binder.phase,
            initial_phase,
        )

        self.assertEqual(
            emitted,
            [],
        )

    def test_runtime_authority_is_not_retained_by_binder(
        self,
    ):
        request = object()
        factory = object()
        remote_image_source = object()

        state = running_state()

        with patch.object(
            ProviderDiagnosticsQtThreadBridge,
            "start_with_credential_source_factory",
            return_value=state,
        ):
            self.binder.start_with_credential_source_factory(
                request,
                factory,
                remote_image_source,
            )

        values = tuple(
            vars(
                self.binder
            ).values()
        )

        self.assertFalse(
            any(
                value is request
                for value in values
            )
        )

        self.assertFalse(
            any(
                value is factory
                for value in values
            )
        )

        self.assertFalse(
            any(
                value is remote_image_source
                for value in values
            )
        )

        self.assertNotIn(
            repr(
                factory
            ),
            repr(
                self.binder
            ),
        )


if __name__ == "__main__":
    unittest.main()