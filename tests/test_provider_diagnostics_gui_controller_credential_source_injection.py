"""M100 M97 credential-source propagation seam tests.

These tests establish one runtime-only credential-source factory path through
M97 without changing the original ``ProviderDiagnosticsGuiController.run``
contract.

The seam must:

- preserve the original run signature and environment-backed path;
- accept one explicitly supplied runtime credential-source factory;
- forward that authority through M95/M93 to M91/M92;
- preserve OFFLINE no-network behavior;
- allow ONLINE connectivity through the same runtime authority;
- keep the factory and secret out of immutable M97 state;
- keep provider diagnostic failures as COMPLETED GUI outcomes;
- keep the controller itself free of retained credential authority.
"""

import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_diagnostics_application.public_api import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationRequest,
)
from creator_studio.provider_diagnostics_gui_controller.public_api import (
    ProviderDiagnosticsGuiController,
    ProviderDiagnosticsGuiControllerPhase,
    validate_provider_diagnostics_gui_controller_state,
)
from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


class FakeCredential:
    def __init__(
        self,
        header,
        value,
    ):
        self.header = header
        self.value = value


class FakeCredentialSource:
    def __init__(
        self,
        credential,
    ):
        self.credential = credential

    def resolve(
        self,
        check,
    ):
        check()

        return self.credential


class RecordingCredentialSourceFactory:
    def __init__(
        self,
        secret,
    ):
        self.secret = secret
        self.calls = []

    def __call__(
        self,
        environment_variable,
        header,
        mode,
    ):
        self.calls.append(
            (
                environment_variable,
                header,
                mode,
            )
        )

        return FakeCredentialSource(
            FakeCredential(
                header,
                self.secret,
            )
        )


class FakeResponse:
    def __init__(
        self,
        status=200,
    ):
        self.status = status
        self.closed = False

    def close(
        self,
    ):
        self.closed = True


def build_request(
    mode,
):
    return ProviderDiagnosticsApplicationRequest(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=openai_runtime_config(),
        mode=mode,
    )


class ProviderDiagnosticsGuiControllerCredentialSourceInjectionTests(
    unittest.TestCase
):

    def test_original_run_signature_is_unchanged(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsGuiController.run
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "request",
                "check",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_run_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderDiagnosticsGuiController
            .run_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "request",
                "check",
                "credential_source_factory",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_offline_factory_reaches_real_stack_without_network(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        config = request.config

        secret = (
            "unique-m100-m97-offline-secret-141421"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        controller = (
            ProviderDiagnosticsGuiController()
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "OFFLINE GUI diagnostics must not open HTTPS"
            ),
        ) as opened:
            state = (
                controller
                .run_with_credential_source_factory(
                    request,
                    lambda: None,
                    factory,
                )
            )

        opened.assert_not_called()

        self.assertEqual(
            factory.calls,
            [
                (
                    config.credential_environment_variable,
                    config.profile.credential_header,
                    config.credential_mode,
                )
            ],
        )

        validate_provider_diagnostics_gui_controller_state(
            state
        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertTrue(
            state.view_model.is_ready
        )

        self.assertNotIn(
            secret,
            repr(
                state
            ),
        )

    def test_online_same_factory_reaches_readiness_and_connectivity(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        config = request.config

        secret = (
            "unique-m100-m97-online-secret-173205"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        response = FakeResponse(
            200
        )

        controller = (
            ProviderDiagnosticsGuiController()
        )

        with patch.object(
            probe_module,
            "_open_https",
            return_value=response,
        ) as opened:
            state = (
                controller
                .run_with_credential_source_factory(
                    request,
                    lambda: None,
                    factory,
                )
            )

        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

        expected_metadata = (
            config.credential_environment_variable,
            config.profile.credential_header,
            config.credential_mode,
        )

        self.assertEqual(
            factory.calls,
            [
                expected_metadata,
                expected_metadata,
            ],
        )

        validate_provider_diagnostics_gui_controller_state(
            state
        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertTrue(
            state.view_model.is_ready
        )

        self.assertNotIn(
            secret,
            repr(
                state
            ),
        )

    def test_factory_failure_is_completed_not_ready_and_stops_network(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .ONLINE
        )

        private_message = (
            "private-m100-m97-factory-failure"
        )

        calls = []

        def factory(
            environment_variable,
            header,
            mode,
        ):
            calls.append(
                (
                    environment_variable,
                    header,
                    mode,
                )
            )

            raise RuntimeError(
                private_message
            )

        controller = (
            ProviderDiagnosticsGuiController()
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "failed readiness must stop before HTTPS"
            ),
        ) as opened:
            state = (
                controller
                .run_with_credential_source_factory(
                    request,
                    lambda: None,
                    factory,
                )
            )

        opened.assert_not_called()

        self.assertEqual(
            len(
                calls
            ),
            1,
        )

        validate_provider_diagnostics_gui_controller_state(
            state
        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIsNotNone(
            state.view_model
        )

        self.assertFalse(
            state.view_model.is_ready
        )

        self.assertNotIn(
            private_message,
            repr(
                state
            ),
        )

    def test_factory_and_secret_are_not_retained(
        self,
    ):
        request = build_request(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        )

        secret = (
            "unique-m100-m97-retention-secret-223606"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        controller = (
            ProviderDiagnosticsGuiController()
        )

        state = (
            controller
            .run_with_credential_source_factory(
                request,
                lambda: None,
                factory,
            )
        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertTrue(
            state.view_model.is_ready
        )

        self.assertNotIn(
            secret,
            repr(
                controller
            ),
        )

        self.assertNotIn(
            secret,
            repr(
                controller.state
            ),
        )

        self.assertFalse(
            hasattr(
                controller,
                "__dict__",
            )
        )


if __name__ == "__main__":
    unittest.main()