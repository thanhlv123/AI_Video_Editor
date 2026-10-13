"""M97 framework-neutral provider diagnostics GUI controller."""

import copy
import pickle
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_gui_controller.controller as controller_module

from creator_studio.provider_diagnostics_application import (
    PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
    ProviderDiagnosticsApplicationResult,
)
from creator_studio.provider_diagnostics_gui_controller import (
    ProviderDiagnosticsGuiControllerFailure,
    ProviderDiagnosticsGuiControllerPhase,
    validate_provider_diagnostics_gui_controller_state,
)
from creator_studio.provider_diagnostics_gui_controller.controller import (
    ProviderDiagnosticsGuiController,
    ProviderDiagnosticsGuiControllerCancelled,
)
from creator_studio.provider_diagnostics_presentation import (
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
)
from creator_studio.provider_diagnostics_view_model import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
)
from creator_studio.provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def application_result():
    presentation = ProviderDiagnosticPresentation(
        schema_version=(
            PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
        ),
        mode=(
            ProviderRuntimeDiagnosticMode
            .OFFLINE
        ),
        diagnostic_status=(
            ProviderRuntimeDiagnosticStatus
            .READY
        ),
        severity=(
            ProviderDiagnosticPresentationSeverity
            .SUCCESS
        ),
        action=(
            ProviderDiagnosticPresentationAction
            .NONE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        title="Ready",
        detail=(
            "Provider configuration is ready."
        ),
    )

    return ProviderDiagnosticsApplicationResult(
        schema_version=(
            PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        presentation=presentation,
    )


def ready_view_model():
    return ProviderDiagnosticsViewModel(
        schema_version=(
            PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Ready",
        detail_text=(
            "Provider configuration is ready."
        ),
        severity=(
            ProviderDiagnosticsViewSeverity
            .SUCCESS
        ),
        action=(
            ProviderDiagnosticsViewAction
            .NONE
        ),
        action_text="No action required",
        is_ready=True,
    )


def not_ready_view_model():
    return ProviderDiagnosticsViewModel(
        schema_version=(
            PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION
        ),
        provider_label="OpenAI",
        status_text="Network unavailable",
        detail_text=(
            "Check the network connection and retry."
        ),
        severity=(
            ProviderDiagnosticsViewSeverity
            .WARNING
        ),
        action=(
            ProviderDiagnosticsViewAction
            .CHECK_NETWORK
        ),
        action_text="Check network",
        is_ready=False,
    )


class ProviderDiagnosticsGuiControllerTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.controller = (
            ProviderDiagnosticsGuiController()
        )

    def test_initial_state_is_idle(self):
        state = self.controller.state

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertIsNone(
            state.view_model
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIs(
            validate_provider_diagnostics_gui_controller_state(
                state
            ),
            state,
        )

    def test_controller_slots(self):
        self.assertEqual(
            ProviderDiagnosticsGuiController
            .__slots__,
            (
                "_gate",
                "_state",
            ),
        )

        self.assertFalse(
            hasattr(
                self.controller,
                "__dict__",
            )
        )

    def test_repr_contains_only_phase_metadata(self):
        self.assertEqual(
            repr(
                self.controller
            ),
            (
                "ProviderDiagnosticsGuiController("
                "phase='IDLE'"
                ")"
            ),
        )

    def test_successful_run_publishes_completed_ready(self):
        source = application_result()
        view = ready_view_model()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                source
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    view
                )

                state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model,
            view,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIs(
            self.controller.state,
            state,
        )

    def test_not_ready_provider_is_still_completed(self):
        source = application_result()
        view = not_ready_view_model()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                source
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    view
                )

                state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            state.view_model.is_ready,
            False,
        )

        self.assertIsNone(
            state.failure
        )

    def test_running_state_is_published_before_service_execution(self):
        observed = []

        def service_run(
            request,
            check,
            remote_image_source=None,
        ):
            observed.append(
                self.controller.state
            )

            return application_result()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                final_state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertEqual(
            len(
                observed
            ),
            1,
        )

        self.assertIs(
            observed[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

        self.assertIs(
            final_state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            observed[
                0
            ].phase,
            ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
        )

    def test_application_service_receives_runtime_arguments(self):
        request = object()
        remote_source = object()
        source = application_result()

        def check():
            return None

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                source
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    request,
                    check,
                    remote_source,
                )

        call = (
            service_type
            .return_value
            .run
            .call_args
        )

        self.assertIs(
            call.args[
                0
            ],
            request,
        )

        self.assertIsNot(
            call.args[
                1
            ],
            check,
        )

        self.assertIs(
            call.args[
                2
            ],
            remote_source,
        )

    def test_controller_does_not_call_check_itself(self):
        calls = [
            0
        ]

        def check():
            calls[
                0
            ] += 1

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    object(),
                    check,
                )

        self.assertEqual(
            calls[
                0
            ],
            0,
        )

    def test_adapter_receives_exact_application_result(self):
        source = application_result()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                source
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    object(),
                    lambda: None,
                )

        adapter_type.return_value.adapt.assert_called_once_with(
            source
        )

    def test_invalid_request_becomes_failed_invalid_request(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                ValueError(
                    "provider_diagnostics_application_request_invalid"
                )
            )

            state = self.controller.run(
                object(),
                lambda: None,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INVALID_REQUEST,
        )

        self.assertIsNone(
            state.view_model
        )

    def test_other_service_value_error_is_internal_failure(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                ValueError(
                    "different-error"
                )
            )

            state = self.controller.run(
                object(),
                lambda: None,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

    def test_service_runtime_error_is_internal_failure(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                RuntimeError(
                    "private-service-error"
                )
            )

            state = self.controller.run(
                object(),
                lambda: None,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            "private-service-error",
            repr(
                state
            ),
        )

    def test_adapter_error_is_internal_failure(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.side_effect = (
                    RuntimeError(
                        "private-adapter-error"
                    )
                )

                state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            "private-adapter-error",
            repr(
                state
            ),
        )

    def test_cancellation_from_caller_check_becomes_cancelled(self):
        def check():
            raise ProviderDiagnosticsGuiControllerCancelled()

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

            raise AssertionError(
                "unreachable"
            )

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            state = self.controller.run(
                object(),
                check,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
        )

        self.assertIsNone(
            state.failure
        )

        self.assertIsNone(
            state.view_model
        )

    def test_check_cannot_spoof_invalid_request_failure(self):
        def check():
            raise ValueError(
                "provider_diagnostics_application_request_invalid"
            )

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

            raise AssertionError(
                "unreachable"
            )

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            state = self.controller.run(
                object(),
                check,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

    def test_runtime_error_from_caller_check_becomes_internal_failure(self):
        def check():
            raise RuntimeError(
                "caller-private-error"
            )

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

            raise AssertionError(
                "unreachable"
            )

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            state = self.controller.run(
                object(),
                check,
            )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

        self.assertNotIn(
            "caller-private-error",
            repr(
                state
            ),
        )

    def test_memory_error_from_caller_check_is_not_swallowed(self):
        def check():
            raise MemoryError()

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

            raise AssertionError(
                "unreachable"
            )

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            with self.assertRaises(
                MemoryError
            ):
                self.controller.run(
                    object(),
                    check,
                )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

        self.assertIs(
            self.controller.state.failure,
            ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE,
        )

    def test_baseexception_from_caller_check_is_not_swallowed(self):
        def check():
            raise KeyboardInterrupt()

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

            raise AssertionError(
                "unreachable"
            )

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.controller.run(
                    object(),
                    check,
                )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_service_memory_error_is_not_swallowed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                MemoryError()
            )

            with self.assertRaises(
                MemoryError
            ):
                self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_service_baseexception_is_not_swallowed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                KeyboardInterrupt()
            )

            with self.assertRaises(
                KeyboardInterrupt
            ):
                self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_adapter_memory_error_is_not_swallowed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.side_effect = (
                    MemoryError()
                )

                with self.assertRaises(
                    MemoryError
                ):
                    self.controller.run(
                        object(),
                        lambda: None,
                    )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_adapter_baseexception_is_not_swallowed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.side_effect = (
                    KeyboardInterrupt()
                )

                with self.assertRaises(
                    KeyboardInterrupt
                ):
                    self.controller.run(
                        object(),
                        lambda: None,
                    )

        self.assertIs(
            self.controller.state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .FAILED,
        )

    def test_reset_returns_idle_after_completed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    object(),
                    lambda: None,
                )

        state = self.controller.reset()

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

        self.assertIs(
            self.controller.state,
            state,
        )

    def test_reset_returns_idle_after_failed(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                RuntimeError(
                    "private"
                )
            )

            self.controller.run(
                object(),
                lambda: None,
            )

        state = self.controller.reset()

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

    def test_reset_returns_idle_after_cancelled(self):
        def check():
            raise ProviderDiagnosticsGuiControllerCancelled()

        def service_run(
            request,
            supplied_check,
            remote_image_source=None,
        ):
            supplied_check()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            self.controller.run(
                object(),
                check,
            )

        state = self.controller.reset()

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .IDLE,
        )

    def test_reset_while_running_is_rejected(self):
        observed = []

        def service_run(
            request,
            check,
            remote_image_source=None,
        ):
            try:
                self.controller.reset()

            except RuntimeError as exc:
                observed.append(
                    str(
                        exc
                    )
                )

            return application_result()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertEqual(
            observed,
            [
                "provider_diagnostics_gui_controller_busy",
            ],
        )

    def test_reentrant_run_while_running_is_rejected(self):
        observed = []

        def service_run(
            request,
            check,
            remote_image_source=None,
        ):
            try:
                self.controller.run(
                    object(),
                    lambda: None,
                )

            except RuntimeError as exc:
                observed.append(
                    str(
                        exc
                    )
                )

            return application_result()

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.side_effect = (
                service_run
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertEqual(
            observed,
            [
                "provider_diagnostics_gui_controller_busy",
            ],
        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

    def test_second_run_after_completion_is_allowed(self):
        views = [
            ready_view_model(),
            not_ready_view_model(),
        ]

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.side_effect = (
                    views
                )

                first = self.controller.run(
                    object(),
                    lambda: None,
                )

                second = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            first.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            first.view_model.is_ready,
            True,
        )

        self.assertIs(
            second.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        self.assertIs(
            second.view_model.is_ready,
            False,
        )

        self.assertIs(
            self.controller.state,
            second,
        )

    def test_controller_does_not_store_runtime_arguments(self):
        request = object()
        remote_source = object()

        def check():
            return None

        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                self.controller.run(
                    request,
                    check,
                    remote_source,
                )

        for name in (
            "request",
            "check",
            "remote_image_source",
            "application_result",
            "service",
            "adapter",
            "credential",
            "secret",
            "api_key",
        ):
            self.assertFalse(
                hasattr(
                    self.controller,
                    name,
                )
            )

    def test_final_state_validates(self):
        with patch.object(
            controller_module,
            "ProviderDiagnosticsApplicationService",
        ) as service_type:
            service_type.return_value.run.return_value = (
                application_result()
            )

            with patch.object(
                controller_module,
                "ProviderDiagnosticsViewModelAdapter",
            ) as adapter_type:
                adapter_type.return_value.adapt.return_value = (
                    ready_view_model()
                )

                state = self.controller.run(
                    object(),
                    lambda: None,
                )

        self.assertIs(
            validate_provider_diagnostics_gui_controller_state(
                state
            ),
            state,
        )

    def test_controller_is_not_copyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_gui_controller_runtime_only$",
        ):
            copy.copy(
                self.controller
            )

    def test_controller_is_not_deepcopyable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_gui_controller_runtime_only$",
        ):
            copy.deepcopy(
                self.controller
            )

    def test_controller_is_not_pickleable(self):
        with self.assertRaisesRegex(
            TypeError,
            "^provider_diagnostics_gui_controller_runtime_only$",
        ):
            pickle.dumps(
                self.controller
            )

    def test_controller_layer_has_no_environment_or_network_access(self):
        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "controller must not read environment"
            ),
        ) as getenv_mock:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "controller must not open network directly"
                ),
            ) as opened:
                with patch.object(
                    controller_module,
                    "ProviderDiagnosticsApplicationService",
                ) as service_type:
                    service_type.return_value.run.return_value = (
                        application_result()
                    )

                    with patch.object(
                        controller_module,
                        "ProviderDiagnosticsViewModelAdapter",
                    ) as adapter_type:
                        adapter_type.return_value.adapt.return_value = (
                            ready_view_model()
                        )

                        state = self.controller.run(
                            object(),
                            lambda: None,
                        )

        self.assertIs(
            state.phase,
            ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()