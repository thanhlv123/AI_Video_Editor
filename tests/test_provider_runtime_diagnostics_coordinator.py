"""M93 provider runtime diagnostics coordinator."""

import inspect
import unittest
from unittest.mock import patch

import creator_studio.provider_runtime_diagnostics.coordinator as coordinator_module

from creator_studio.provider_connectivity_probe.public_api import (
    PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION,
    ProviderConnectivityProbeReport,
    ProviderConnectivityProbeStatus,
)
from creator_studio.provider_runtime_diagnostics.coordinator import (
    ProviderRuntimeDiagnosticsCoordinator,
)
from creator_studio.provider_runtime_diagnostics.models import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
    validate_provider_runtime_diagnostic_report,
)
from creator_studio.provider_runtime_readiness.public_api import (
    PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION,
    ProviderRuntimeReadinessFailureCode,
    ProviderRuntimeReadinessOutcome,
    ProviderRuntimeReadinessReport,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    kie_runtime_config,
    openai_runtime_config,
)


def environment_name(
    provider,
):
    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        return "OPENAI_API_KEY"

    if (
        provider
        is VisionProviderKind.GEMINI
    ):
        return "GEMINI_API_KEY"

    if (
        provider
        is VisionProviderKind.KIE_AI
    ):
        return "KIE_API_KEY"

    raise ValueError()


def readiness_ready(
    provider=VisionProviderKind.OPENAI,
):
    return ProviderRuntimeReadinessReport(
        schema_version=(
            PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            ProviderRuntimeReadinessOutcome
            .READY
        ),
        failure_code=None,
        provider=provider,
        credential_environment_variable=(
            environment_name(
                provider
            )
        ),
    )


def readiness_failure(
    failure_code,
    provider=VisionProviderKind.OPENAI,
):
    if (
        failure_code
        is ProviderRuntimeReadinessFailureCode
        .CONFIG_INVALID
    ):
        provider_value = None
        environment_variable = None

    else:
        if (
            failure_code
            is ProviderRuntimeReadinessFailureCode
            .REMOTE_IMAGE_SOURCE_REQUIRED
        ):
            provider = VisionProviderKind.KIE_AI

        provider_value = provider

        environment_variable = (
            environment_name(
                provider
            )
        )

    return ProviderRuntimeReadinessReport(
        schema_version=(
            PROVIDER_RUNTIME_READINESS_SCHEMA_VERSION
        ),
        outcome=(
            ProviderRuntimeReadinessOutcome
            .NOT_READY
        ),
        failure_code=failure_code,
        provider=provider_value,
        credential_environment_variable=(
            environment_variable
        ),
    )


def connectivity_report(
    status,
    provider=VisionProviderKind.OPENAI,
):
    if (
        status
        is ProviderConnectivityProbeStatus
        .CONFIG_INVALID
    ):
        return ProviderConnectivityProbeReport(
            schema_version=(
                PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
            ),
            status=status,
            provider=None,
            credential_environment_variable=None,
            http_status=None,
            provider_code=None,
        )

    http_status = None
    provider_code = None

    if (
        status
        is ProviderConnectivityProbeStatus
        .READY
    ):
        http_status = 200

        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            provider_code = 200

    elif (
        status
        is ProviderConnectivityProbeStatus
        .AUTHENTICATION_FAILED
    ):
        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            http_status = 200
            provider_code = 401

        else:
            http_status = 401

    elif (
        status
        is ProviderConnectivityProbeStatus
        .PERMISSION_DENIED
    ):
        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            http_status = 200
            provider_code = 403

        else:
            http_status = 403

    elif (
        status
        is ProviderConnectivityProbeStatus
        .RATE_LIMITED
    ):
        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            http_status = 200
            provider_code = 429

        else:
            http_status = 429

    elif (
        status
        is ProviderConnectivityProbeStatus
        .PROVIDER_UNAVAILABLE
    ):
        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            http_status = 200
            provider_code = 503

        else:
            http_status = 503

    elif (
        status
        is ProviderConnectivityProbeStatus
        .RESPONSE_INVALID
    ):
        if (
            provider
            is VisionProviderKind.KIE_AI
        ):
            http_status = 200
            provider_code = 422

        else:
            http_status = 422

    return ProviderConnectivityProbeReport(
        schema_version=(
            PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=status,
        provider=provider,
        credential_environment_variable=(
            environment_name(
                provider
            )
        ),
        http_status=http_status,
        provider_code=provider_code,
    )


class ProviderRuntimeDiagnosticsCoordinatorTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.coordinator = (
            ProviderRuntimeDiagnosticsCoordinator()
        )

    def run_diagnostic(
        self,
        *,
        mode,
        readiness,
        connectivity=None,
        config=None,
        remote_image_source=None,
    ):
        if config is None:
            config = openai_runtime_config()

        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                connectivity_type.return_value.probe.return_value = (
                    connectivity
                )

                result = self.coordinator.diagnose(
                    config,
                    mode,
                    lambda: None,
                    remote_image_source,
                )

        return (
            result,
            readiness_type,
            connectivity_type,
        )

    def test_coordinator_is_stateless(self):
        self.assertEqual(
            ProviderRuntimeDiagnosticsCoordinator
            .__slots__,
            (),
        )

        self.assertFalse(
            hasattr(
                self.coordinator,
                "__dict__",
            )
        )

    def test_diagnose_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ProviderRuntimeDiagnosticsCoordinator
                    .diagnose
                ).parameters
            ),
            (
                "self",
                "config",
                "mode",
                "check",
                "remote_image_source",
            ),
        )

    def test_invalid_mode_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "^provider_runtime_diagnostic_mode_invalid$",
        ):
            self.coordinator.diagnose(
                openai_runtime_config(),
                "OFFLINE",
                lambda: None,
            )

    def test_offline_ready_mapping(self):
        result, _, connectivity_type = (
            self.run_diagnostic(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                readiness=readiness_ready(),
            )
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertIsNone(
            result.http_status
        )

        connectivity_type.assert_not_called()

    def test_offline_config_invalid_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .OFFLINE
            ),
            readiness=readiness_failure(
                ProviderRuntimeReadinessFailureCode
                .CONFIG_INVALID
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID,
        )

        self.assertIsNone(
            result.provider
        )

    def test_offline_credential_missing_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .OFFLINE
            ),
            readiness=readiness_failure(
                ProviderRuntimeReadinessFailureCode
                .CREDENTIAL_MISSING
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

    def test_offline_credential_invalid_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .OFFLINE
            ),
            readiness=readiness_failure(
                ProviderRuntimeReadinessFailureCode
                .CREDENTIAL_INVALID
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

    def test_offline_remote_dependency_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .OFFLINE
            ),
            readiness=readiness_failure(
                ProviderRuntimeReadinessFailureCode
                .REMOTE_IMAGE_SOURCE_REQUIRED
            ),
            config=kie_runtime_config(),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .REMOTE_DEPENDENCY_MISSING,
        )

        self.assertIs(
            result.provider,
            VisionProviderKind.KIE_AI,
        )

    def test_offline_internal_failure_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .OFFLINE
            ),
            readiness=readiness_failure(
                ProviderRuntimeReadinessFailureCode
                .INTERNAL_FAILURE
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

    def test_offline_never_constructs_connectivity_probe(self):
        _, _, connectivity_type = (
            self.run_diagnostic(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                readiness=readiness_ready(),
            )
        )

        connectivity_type.assert_not_called()

    def test_online_ready_runs_connectivity(self):
        result, _, connectivity_type = (
            self.run_diagnostic(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                readiness=readiness_ready(),
                connectivity=connectivity_report(
                    ProviderConnectivityProbeStatus
                    .READY
                ),
            )
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        connectivity_type.assert_called_once_with()

        connectivity_type.return_value.probe.assert_called_once()

    def test_online_readiness_failure_prevents_connectivity(self):
        failures = (
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_MISSING,
            ProviderRuntimeReadinessFailureCode
            .CREDENTIAL_INVALID,
            ProviderRuntimeReadinessFailureCode
            .INTERNAL_FAILURE,
        )

        for failure in failures:
            with self.subTest(
                failure=failure
            ):
                _, _, connectivity_type = (
                    self.run_diagnostic(
                        mode=(
                            ProviderRuntimeDiagnosticMode
                            .ONLINE
                        ),
                        readiness=readiness_failure(
                            failure
                        ),
                    )
                )

                connectivity_type.assert_not_called()

    def test_online_config_invalid_prevents_connectivity(self):
        result, _, connectivity_type = (
            self.run_diagnostic(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .ONLINE
                ),
                readiness=readiness_failure(
                    ProviderRuntimeReadinessFailureCode
                    .CONFIG_INVALID
                ),
            )
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID,
        )

        connectivity_type.assert_not_called()

    def test_online_connectivity_credential_missing_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .CREDENTIAL_MISSING
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_MISSING,
        )

    def test_online_connectivity_credential_invalid_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .CREDENTIAL_INVALID
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CREDENTIAL_INVALID,
        )

    def test_online_authentication_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .AUTHENTICATION_FAILED
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            401,
        )

    def test_online_permission_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .PERMISSION_DENIED
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .PERMISSION_DENIED,
        )

    def test_online_rate_limit_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .RATE_LIMITED
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .RATE_LIMITED,
        )

    def test_online_provider_unavailable_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .PROVIDER_UNAVAILABLE
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .PROVIDER_UNAVAILABLE,
        )

        self.assertEqual(
            result.http_status,
            503,
        )

    def test_online_network_unavailable_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .NETWORK_UNAVAILABLE
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .NETWORK_UNAVAILABLE,
        )

        self.assertIsNone(
            result.http_status
        )

    def test_online_deadline_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .DEADLINE_EXCEEDED
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .DEADLINE_EXCEEDED,
        )

    def test_online_response_invalid_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .RESPONSE_INVALID
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .RESPONSE_INVALID,
        )

        self.assertEqual(
            result.http_status,
            422,
        )

    def test_online_internal_failure_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .INTERNAL_FAILURE
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

    def test_kie_wrapped_authentication_preserved(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(
                VisionProviderKind.KIE_AI
            ),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .AUTHENTICATION_FAILED,
                VisionProviderKind.KIE_AI,
            ),
            config=kie_runtime_config(),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .AUTHENTICATION_FAILED,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertEqual(
            result.provider_code,
            401,
        )

    def test_kie_ready_provider_code_preserved(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(
                VisionProviderKind.KIE_AI
            ),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .READY,
                VisionProviderKind.KIE_AI,
            ),
            config=kie_runtime_config(),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            result.http_status,
            200,
        )

        self.assertEqual(
            result.provider_code,
            200,
        )

    def test_connectivity_config_invalid_mapping(self):
        result, _, _ = self.run_diagnostic(
            mode=(
                ProviderRuntimeDiagnosticMode
                .ONLINE
            ),
            readiness=readiness_ready(),
            connectivity=connectivity_report(
                ProviderConnectivityProbeStatus
                .CONFIG_INVALID
            ),
        )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .CONFIG_INVALID,
        )

        self.assertIsNone(
            result.provider
        )

    def test_invalid_readiness_report_maps_internal(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                object()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                result = self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

        connectivity_type.assert_not_called()

    def test_invalid_connectivity_report_maps_internal(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness_ready()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                connectivity_type.return_value.probe.return_value = (
                    object()
                )

                result = self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

    def test_readiness_unexpected_exception_maps_internal(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.side_effect = (
                RuntimeError(
                    "private-readiness"
                )
            )

            result = self.coordinator.diagnose(
                openai_runtime_config(),
                (
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                lambda: None,
            )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

    def test_connectivity_unexpected_exception_maps_internal(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness_ready()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                connectivity_type.return_value.probe.side_effect = (
                    RuntimeError(
                        "private-connectivity"
                    )
                )

                result = self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    lambda: None,
                )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .INTERNAL_FAILURE,
        )

    def test_initial_check_exception_not_swallowed(self):
        def check():
            raise RuntimeError(
                "caller-check"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "^caller-check$",
        ):
            self.coordinator.diagnose(
                openai_runtime_config(),
                (
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                check,
            )

    def test_check_exception_inside_readiness_not_swallowed(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            if (
                calls[
                    0
                ]
                == 2
            ):
                raise RuntimeError(
                    "nested-readiness-check"
                )

        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            def run_readiness(
                config,
                supplied_check,
                remote_image_source=None,
            ):
                supplied_check()

                return readiness_ready()

            readiness_type.return_value.check.side_effect = (
                run_readiness
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "^nested-readiness-check$",
            ):
                self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    check,
                )

    def test_check_exception_inside_connectivity_not_swallowed(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

            if (
                calls[
                    0
                ]
                == 3
            ):
                raise RuntimeError(
                    "nested-connectivity-check"
                )

        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness_ready()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                def run_connectivity(
                    config,
                    supplied_check,
                ):
                    supplied_check()

                    return connectivity_report(
                        ProviderConnectivityProbeStatus
                        .READY
                    )

                connectivity_type.return_value.probe.side_effect = (
                    run_connectivity
                )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "^nested-connectivity-check$",
                ):
                    self.coordinator.diagnose(
                        openai_runtime_config(),
                        (
                            ProviderRuntimeDiagnosticMode
                            .ONLINE
                        ),
                        check,
                    )

    def test_readiness_baseexception_not_swallowed(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.side_effect = (
                KeyboardInterrupt()
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .OFFLINE
                    ),
                    lambda: None,
                )

    def test_connectivity_baseexception_not_swallowed(self):
        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness_ready()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                connectivity_type.return_value.probe.side_effect = (
                    KeyboardInterrupt()
                )

                with self.assertRaises(
                    KeyboardInterrupt
                ):
                    self.coordinator.diagnose(
                        openai_runtime_config(),
                        (
                            ProviderRuntimeDiagnosticMode
                            .ONLINE
                        ),
                        lambda: None,
                    )

    def test_remote_source_forwarded_to_readiness(self):
        remote_source = object()

        _, readiness_type, _ = (
            self.run_diagnostic(
                mode=(
                    ProviderRuntimeDiagnosticMode
                    .OFFLINE
                ),
                readiness=readiness_ready(
                    VisionProviderKind.KIE_AI
                ),
                config=kie_runtime_config(),
                remote_image_source=remote_source,
            )
        )

        call = (
            readiness_type
            .return_value
            .check
            .call_args
        )

        self.assertIs(
            call.args[
                2
            ],
            remote_source,
        )

    def test_check_occurs_between_readiness_and_connectivity(self):
        events = []

        def check():
            events.append(
                "check"
            )

        with patch.object(
            coordinator_module,
            "ProviderRuntimeReadinessChecker",
        ) as readiness_type:
            readiness_type.return_value.check.return_value = (
                readiness_ready()
            )

            with patch.object(
                coordinator_module,
                "ProviderConnectivityProbe",
            ) as connectivity_type:
                def run_probe(
                    config,
                    supplied_check,
                ):
                    events.append(
                        "probe"
                    )

                    return connectivity_report(
                        ProviderConnectivityProbeStatus
                        .READY
                    )

                connectivity_type.return_value.probe.side_effect = (
                    run_probe
                )

                result = self.coordinator.diagnose(
                    openai_runtime_config(),
                    (
                        ProviderRuntimeDiagnosticMode
                        .ONLINE
                    ),
                    check,
                )

        self.assertIs(
            result.status,
            ProviderRuntimeDiagnosticStatus
            .READY,
        )

        self.assertEqual(
            events,
            [
                "check",
                "check",
                "probe",
            ],
        )

    def test_all_returned_reports_validate(self):
        cases = (
            (
                ProviderRuntimeDiagnosticMode
                .OFFLINE,
                readiness_ready(),
                None,
            ),
            (
                ProviderRuntimeDiagnosticMode
                .OFFLINE,
                readiness_failure(
                    ProviderRuntimeReadinessFailureCode
                    .CREDENTIAL_MISSING
                ),
                None,
            ),
            (
                ProviderRuntimeDiagnosticMode
                .ONLINE,
                readiness_ready(),
                connectivity_report(
                    ProviderConnectivityProbeStatus
                    .READY
                ),
            ),
            (
                ProviderRuntimeDiagnosticMode
                .ONLINE,
                readiness_ready(),
                connectivity_report(
                    ProviderConnectivityProbeStatus
                    .AUTHENTICATION_FAILED
                ),
            ),
        )

        for (
            mode,
            readiness,
            connectivity,
        ) in cases:
            with self.subTest(
                mode=mode,
                readiness=readiness,
                connectivity=connectivity,
            ):
                result, _, _ = (
                    self.run_diagnostic(
                        mode=mode,
                        readiness=readiness,
                        connectivity=connectivity,
                    )
                )

                self.assertIs(
                    validate_provider_runtime_diagnostic_report(
                        result
                    ),
                    result,
                )


if __name__ == "__main__":
    unittest.main()