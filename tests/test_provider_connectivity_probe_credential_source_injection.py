"""M100 M92 credential-source injection seam tests.

These tests establish a runtime-only credential-source factory seam in M92
without changing the original ``ProviderConnectivityProbe.probe`` contract.

The seam must:

- preserve the original environment-backed execution path;
- allow an explicitly supplied runtime source factory;
- pass provider credential metadata to that factory;
- preserve caller-owned check authority;
- keep the factory and resolved secret out of detached reports;
- keep the probe stateless.
"""

import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module

from creator_studio.provider_connectivity_probe.public_api import (
    ProviderConnectivityProbe,
    ProviderConnectivityProbeStatus,
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
        *,
        resolve_calls=None,
    ):
        self.credential = credential
        self.resolve_calls = resolve_calls

    def resolve(
        self,
        check,
    ):
        if self.resolve_calls is not None:
            self.resolve_calls.append(
                check
            )

        check()

        return self.credential


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


class ProviderConnectivityProbeCredentialSourceInjectionTests(
    unittest.TestCase
):

    def test_original_probe_signature_is_unchanged(
        self,
    ):
        parameters = inspect.signature(
            ProviderConnectivityProbe.probe
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "check",
            ),
        )

    def test_injected_probe_signature_is_explicit(
        self,
    ):
        parameters = inspect.signature(
            ProviderConnectivityProbe
            .probe_with_credential_source_factory
        ).parameters

        self.assertEqual(
            tuple(
                parameters
            ),
            (
                "self",
                "config",
                "check",
                "credential_source_factory",
            ),
        )

    def test_injected_factory_receives_exact_runtime_metadata(
        self,
    ):
        config = openai_runtime_config()

        calls = []

        source = FakeCredentialSource(
            FakeCredential(
                config.profile.credential_header,
                "m100-connectivity-secret",
            )
        )

        response = FakeResponse(
            200
        )

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

            return source

        with patch.object(
            probe_module,
            "EnvironmentCredentialSource",
            side_effect=AssertionError(
                "default environment source must not be used"
            ),
        ) as default_source:
            with patch.object(
                probe_module,
                "_open_https",
                return_value=response,
            ) as opened:
                report = (
                    ProviderConnectivityProbe()
                    .probe_with_credential_source_factory(
                        config,
                        lambda: None,
                        factory,
                    )
                )

        default_source.assert_not_called()
        opened.assert_called_once()

        self.assertTrue(
            response.closed
        )

        self.assertEqual(
            calls,
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
            ProviderConnectivityProbeStatus
            .READY,
        )

    def test_injected_source_receives_exact_check_callable(
        self,
    ):
        config = openai_runtime_config()

        resolve_calls = []

        source = FakeCredentialSource(
            FakeCredential(
                config.profile.credential_header,
                "m100-check-identity-secret",
            ),
            resolve_calls=resolve_calls,
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            return source

        def check():
            return None

        with patch.object(
            probe_module,
            "_open_https",
            return_value=FakeResponse(
                200
            ),
        ):
            report = (
                ProviderConnectivityProbe()
                .probe_with_credential_source_factory(
                    config,
                    check,
                    factory,
                )
            )

        self.assertIs(
            report.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertEqual(
            resolve_calls,
            [
                check
            ],
        )

    def test_factory_failure_maps_to_internal_failure_without_network(
        self,
    ):
        config = openai_runtime_config()

        private_message = (
            "private-m100-connectivity-factory-failure"
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            raise RuntimeError(
                private_message
            )

        with patch.object(
            probe_module,
            "_open_https",
            side_effect=AssertionError(
                "factory failure must stop before HTTPS"
            ),
        ) as opened:
            report = (
                ProviderConnectivityProbe()
                .probe_with_credential_source_factory(
                    config,
                    lambda: None,
                    factory,
                )
            )

        opened.assert_not_called()

        self.assertIs(
            report.status,
            ProviderConnectivityProbeStatus
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            private_message,
            repr(
                report
            ),
        )

    def test_secret_and_factory_are_not_retained(
        self,
    ):
        config = openai_runtime_config()

        secret = (
            "unique-m100-connectivity-secret-963258"
        )

        def factory(
            environment_variable,
            header,
            mode,
        ):
            return FakeCredentialSource(
                FakeCredential(
                    header,
                    secret,
                )
            )

        probe = ProviderConnectivityProbe()

        response = FakeResponse(
            200
        )

        with patch.object(
            probe_module,
            "_open_https",
            return_value=response,
        ):
            report = (
                probe
                .probe_with_credential_source_factory(
                    config,
                    lambda: None,
                    factory,
                )
            )

        self.assertIs(
            report.status,
            ProviderConnectivityProbeStatus
            .READY,
        )

        self.assertTrue(
            response.closed
        )

        self.assertNotIn(
            secret,
            repr(
                report
            ),
        )

        self.assertFalse(
            hasattr(
                probe,
                "__dict__",
            )
        )


if __name__ == "__main__":
    unittest.main()