"""M100 M93 credential-source propagation seam tests.

These tests establish one runtime-only credential-source factory path through
M93 without changing the original ``ProviderRuntimeDiagnosticsCoordinator``
``diagnose`` contract.

The seam must:

- preserve the original diagnose signature and environment-backed path;
- accept one explicitly supplied runtime credential-source factory;
- use that authority for M91 readiness;
- reuse the same authority for M92 connectivity when ONLINE readiness succeeds;
- preserve OFFLINE no-network behavior;
- keep the factory and resolved secret out of detached diagnostic reports;
- keep the coordinator stateless.
"""

import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_runtime_diagnostics.public_api import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
    ProviderRuntimeDiagnosticsCoordinator,
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


class FailingCredentialSourceFactory:
    def __init__(
        self,
        message,
    ):
        self.message = message
        self.calls = 0

    def __call__(
        self,
        environment_variable,
        header,
        mode,
    ):
        self.calls += 1

        raise RuntimeError(
            self.message
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


class ProviderRuntimeDiagnosticsCredentialSourceInjectionTests(
    unittest.TestCase
):

    def test_original_diagnose_signature_is_unchanged(
        self,
    ):
        parameters = inspect.signature(
            ProviderRuntimeDiagnosticsCoordinator
            .diagnose
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "mode",
                "check",
                "remote_image_source",
            ),
        )

        self.assertIsNone(
            parameters[
                "remote_image_source"
            ].default
        )

    def test_injected_diagnose_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderRuntimeDiagnosticsCoordinator
            .diagnose_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "mode",
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

    def test_offline_uses_factory_once_and_never_opens_https(
        self,
    ):
        config = openai_runtime_config()

        factory = RecordingCredentialSourceFactory(
            "m100-m93-offline-secret"
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "OFFLINE diagnostics must not open HTTPS"
            ),
        ) as opened:
            report = (
                ProviderRuntimeDiagnosticsCoordinator()
                .diagnose_with_credential_source_factory(
                    config,
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE,
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

        self.assertIs(
            report.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            report.mode,
            ProviderRuntimeDiagnosticMode
            .OFFLINE,
        )

    def test_online_reuses_same_factory_for_readiness_and_connectivity(
        self,
    ):
        config = openai_runtime_config()

        secret = (
            "unique-m100-m93-online-secret-314159"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        response = FakeResponse(
            200
        )

        with patch.object(
            probe_module,
            "_open_https",
            return_value=response,
        ) as opened:
            report = (
                ProviderRuntimeDiagnosticsCoordinator()
                .diagnose_with_credential_source_factory(
                    config,
                    ProviderRuntimeDiagnosticMode
                    .ONLINE,
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

        self.assertIs(
            report.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIs(
            report.mode,
            ProviderRuntimeDiagnosticMode
            .ONLINE,
        )

        self.assertNotIn(
            secret,
            repr(
                report
            ),
        )

    def test_factory_failure_stops_before_connectivity_network(
        self,
    ):
        config = openai_runtime_config()

        private_message = (
            "private-m100-m93-factory-failure"
        )

        factory = FailingCredentialSourceFactory(
            private_message
        )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "failed readiness must stop before HTTPS"
            ),
        ) as opened:
            report = (
                ProviderRuntimeDiagnosticsCoordinator()
                .diagnose_with_credential_source_factory(
                    config,
                    ProviderRuntimeDiagnosticMode
                    .ONLINE,
                    lambda: None,
                    factory,
                )
            )

        opened.assert_not_called()

        self.assertEqual(
            factory.calls,
            1,
        )

        self.assertIs(
            report.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            private_message,
            repr(
                report
            ),
        )

    def test_factory_and_secret_are_not_retained(
        self,
    ):
        config = openai_runtime_config()

        secret = (
            "unique-m100-m93-retention-secret-271828"
        )

        factory = RecordingCredentialSourceFactory(
            secret
        )

        coordinator = (
            ProviderRuntimeDiagnosticsCoordinator()
        )

        report = (
            coordinator
            .diagnose_with_credential_source_factory(
                config,
                ProviderRuntimeDiagnosticMode
                .OFFLINE,
                lambda: None,
                factory,
            )
        )

        self.assertIs(
            report.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertNotIn(
            secret,
            repr(
                report
            ),
        )

        self.assertFalse(
            hasattr(
                coordinator,
                "__dict__",
            )
        )


if __name__ == "__main__":
    unittest.main()