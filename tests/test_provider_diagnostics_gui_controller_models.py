"""M97 provider diagnostics GUI controller state contract."""

import copy
import dataclasses
import pickle
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_gui_controller as api
import creator_studio.provider_diagnostics_gui_controller.models as models_module

from creator_studio.provider_diagnostics_view_model import (
    PROVIDER_DIAGNOSTICS_VIEW_MODEL_SCHEMA_VERSION,
    ProviderDiagnosticsViewAction,
    ProviderDiagnosticsViewModel,
    ProviderDiagnosticsViewSeverity,
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


def state(
    phase,
    *,
    view_model=None,
    failure=None,
):
    return api.ProviderDiagnosticsGuiControllerState(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION
        ),
        phase=phase,
        view_model=view_model,
        failure=failure,
    )


def idle_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .IDLE
    )


def running_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .RUNNING
    )


def completed_ready_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .COMPLETED,
        view_model=ready_view_model(),
    )


def completed_not_ready_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .COMPLETED,
        view_model=not_ready_view_model(),
    )


def cancelled_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .CANCELLED
    )


def failed_invalid_request_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .FAILED,
        failure=(
            api.ProviderDiagnosticsGuiControllerFailure
            .INVALID_REQUEST
        ),
    )


def failed_internal_state():
    return state(
        api.ProviderDiagnosticsGuiControllerPhase
        .FAILED,
        failure=(
            api.ProviderDiagnosticsGuiControllerFailure
            .INTERNAL_FAILURE
        ),
    )


class ProviderDiagnosticsGuiControllerStateTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION,
            1,
        )

    def test_phase_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderDiagnosticsGuiControllerPhase
            },
            {
                "IDLE",
                "RUNNING",
                "COMPLETED",
                "CANCELLED",
                "FAILED",
            },
        )

    def test_failure_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderDiagnosticsGuiControllerFailure
            },
            {
                "INVALID_REQUEST",
                "INTERNAL_FAILURE",
            },
        )

    def test_idle_state_valid(self):
        value = idle_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

    def test_running_state_valid(self):
        value = running_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

    def test_completed_ready_state_valid(self):
        value = completed_ready_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

        self.assertIs(
            value.view_model.is_ready,
            True,
        )

    def test_completed_not_ready_state_valid(self):
        value = completed_not_ready_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

        self.assertIs(
            value.view_model.is_ready,
            False,
        )

    def test_cancelled_state_valid(self):
        value = cancelled_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

    def test_failed_invalid_request_state_valid(self):
        value = failed_invalid_request_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

    def test_failed_internal_failure_state_valid(self):
        value = failed_internal_state()

        self.assertIs(
            api.validate_provider_diagnostics_gui_controller_state(
                value
            ),
            value,
        )

    def test_state_is_frozen(self):
        value = idle_state()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.phase = (
                api.ProviderDiagnosticsGuiControllerPhase
                .RUNNING
            )

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                idle_state(),
                schema_version=version,
            )

            with self.subTest(
                version=version
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_gui_controller_state_invalid$",
                ):
                    api.validate_provider_diagnostics_gui_controller_state(
                        value
                    )

    def test_exact_type_contract(self):
        class Subclass(
            api.ProviderDiagnosticsGuiControllerState
        ):
            pass

        base = idle_state()

        value = Subclass(
            **base.__dict__
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_exact_shape_contract(self):
        value = copy.copy(
            idle_state()
        )

        object.__setattr__(
            value,
            "extra",
            "unexpected",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_phase_requires_exact_enum(self):
        value = dataclasses.replace(
            idle_state(),
            phase="IDLE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_completed_requires_exact_view_model(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=object(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_completed_rejects_view_model_subclass(self):
        base = ready_view_model()

        class Subclass(
            ProviderDiagnosticsViewModel
        ):
            pass

        view = Subclass(
            **base.__dict__
        )

        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=view,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_completed_rejects_invalid_nested_view_model(self):
        view = copy.copy(
            ready_view_model()
        )

        object.__setattr__(
            view,
            "extra",
            "unexpected",
        )

        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=view,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_idle_rejects_view_model(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .IDLE,
            view_model=ready_view_model(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_running_rejects_view_model(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
            view_model=ready_view_model(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_cancelled_rejects_view_model(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
            view_model=ready_view_model(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_failed_rejects_view_model(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            view_model=ready_view_model(),
            failure=(
                api.ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_completed_rejects_failure(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .COMPLETED,
            view_model=ready_view_model(),
            failure=(
                api.ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_idle_rejects_failure(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .IDLE,
            failure=(
                api.ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_running_rejects_failure(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .RUNNING,
            failure=(
                api.ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_cancelled_rejects_failure(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .CANCELLED,
            failure=(
                api.ProviderDiagnosticsGuiControllerFailure
                .INTERNAL_FAILURE
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_failed_requires_failure(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .FAILED
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_failed_failure_requires_exact_enum(self):
        value = state(
            api.ProviderDiagnosticsGuiControllerPhase
            .FAILED,
            failure="INTERNAL_FAILURE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_gui_controller_state_invalid$",
        ):
            api.validate_provider_diagnostics_gui_controller_state(
                value
            )

    def test_roundtrips(self):
        values = (
            idle_state(),
            running_state(),
            completed_ready_state(),
            completed_not_ready_state(),
            cancelled_state(),
            failed_invalid_request_state(),
            failed_internal_state(),
        )

        for value in values:
            variants = (
                copy.copy(
                    value
                ),
                copy.deepcopy(
                    value
                ),
                pickle.loads(
                    pickle.dumps(
                        value
                    )
                ),
            )

            for variant in variants:
                self.assertEqual(
                    api.validate_provider_diagnostics_gui_controller_state(
                        variant
                    ),
                    value,
                )

    def test_state_contains_only_gui_safe_fields(self):
        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                api.ProviderDiagnosticsGuiControllerState
            )
        }

        self.assertEqual(
            names,
            {
                "schema_version",
                "phase",
                "view_model",
                "failure",
            },
        )

        forbidden = {
            "config",
            "request",
            "credential",
            "credential_value",
            "credential_environment_variable",
            "secret",
            "password",
            "token",
            "api_key",
            "authorization",
            "http_status",
            "provider_code",
            "diagnostic_report",
            "presentation",
            "application_result",
            "check",
            "remote_image_source",
            "exception",
            "error_message",
            "traceback",
            "worker",
            "thread",
            "qthread",
        }

        self.assertTrue(
            names.isdisjoint(
                forbidden
            )
        )

    def test_nested_view_model_contains_no_upstream_fields(self):
        value = completed_ready_state()

        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                type(
                    value.view_model
                )
            )
        }

        forbidden = {
            "config",
            "credential",
            "credential_environment_variable",
            "http_status",
            "provider_code",
            "diagnostic_report",
            "presentation",
            "application_result",
            "check",
            "remote_image_source",
        }

        self.assertTrue(
            names.isdisjoint(
                forbidden
            )
        )

    def test_validator_memory_error_not_swallowed(self):
        value = completed_ready_state()

        with patch.object(
            models_module,
            "validate_provider_diagnostics_view_model",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                api.validate_provider_diagnostics_gui_controller_state(
                    value
                )

    def test_validator_sanitizes_nested_exception(self):
        value = completed_ready_state()

        with patch.object(
            models_module,
            "validate_provider_diagnostics_view_model",
            side_effect=RuntimeError(
                "private-nested-error"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_gui_controller_state_invalid$",
            ):
                api.validate_provider_diagnostics_gui_controller_state(
                    value
                )

    def test_validation_has_no_environment_or_network_side_effect(self):
        value = completed_ready_state()

        with patch(
            "os.getenv",
            side_effect=AssertionError(
                "environment must not be read"
            ),
        ) as getenv_mock:
            with patch.object(
                probe_module,
                "_open_https",
                side_effect=AssertionError(
                    "network must not open"
                ),
            ) as opened:
                result = (
                    api.validate_provider_diagnostics_gui_controller_state(
                        value
                    )
                )

        self.assertIs(
            result,
            value,
        )

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_public_api_contract(self):
        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_GUI_CONTROLLER_STATE_SCHEMA_VERSION",
                "ProviderDiagnosticsGuiControllerFailure",
                "ProviderDiagnosticsGuiControllerPhase",
                "ProviderDiagnosticsGuiControllerState",
                "validate_provider_diagnostics_gui_controller_state",
            ),
        )


if __name__ == "__main__":
    unittest.main()