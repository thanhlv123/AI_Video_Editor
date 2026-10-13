"""M95 provider diagnostics application model contract."""

import copy
import dataclasses
import pickle
import unittest
from unittest.mock import patch

import creator_studio.provider_connectivity_probe.probe as probe_module
import creator_studio.provider_diagnostics_application as api
import creator_studio.provider_diagnostics_application.models as models_module

from creator_studio.provider_diagnostics_presentation import (
    PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION,
    ProviderDiagnosticPresentation,
    ProviderDiagnosticPresentationAction,
    ProviderDiagnosticPresentationSeverity,
)
from creator_studio.provider_runtime_diagnostics import (
    ProviderRuntimeDiagnosticMode,
    ProviderRuntimeDiagnosticStatus,
)
from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)
from tests.test_provider_runtime_assembly_runtime_config import (
    openai_runtime_config,
)


def valid_request(
    mode=ProviderRuntimeDiagnosticMode.OFFLINE,
):
    return api.ProviderDiagnosticsApplicationRequest(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        config=openai_runtime_config(),
        mode=mode,
    )


def valid_presentation():
    return ProviderDiagnosticPresentation(
        schema_version=(
            PROVIDER_DIAGNOSTIC_PRESENTATION_SCHEMA_VERSION
        ),
        mode=ProviderRuntimeDiagnosticMode.OFFLINE,
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
        detail="Provider configuration is ready.",
    )


def valid_result():
    return api.ProviderDiagnosticsApplicationResult(
        schema_version=(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION
        ),
        presentation=valid_presentation(),
    )


class Hostile:
    def __getattribute__(
        self,
        name,
    ):
        raise AssertionError(
            "hostile access"
        )

    def __repr__(
        self,
    ):
        raise AssertionError(
            "hostile repr"
        )


class ProviderDiagnosticsApplicationModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION,
            1,
        )

    def test_request_is_frozen(self):
        value = valid_request()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.mode = (
                ProviderRuntimeDiagnosticMode
                .ONLINE
            )

    def test_result_is_frozen(self):
        value = valid_result()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.presentation = None

    def test_offline_request_valid(self):
        value = valid_request(
            ProviderRuntimeDiagnosticMode.OFFLINE
        )

        self.assertIs(
            api.validate_provider_diagnostics_application_request(
                value
            ),
            value,
        )

    def test_online_request_valid(self):
        value = valid_request(
            ProviderRuntimeDiagnosticMode.ONLINE
        )

        self.assertIs(
            api.validate_provider_diagnostics_application_request(
                value
            ),
            value,
        )

    def test_result_valid(self):
        value = valid_result()

        self.assertIs(
            api.validate_provider_diagnostics_application_result(
                value
            ),
            value,
        )

    def test_request_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                valid_request(),
                schema_version=version,
            )

            with self.subTest(
                version=version
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_request_invalid$",
                ):
                    api.validate_provider_diagnostics_application_request(
                        value
                    )

    def test_result_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                valid_result(),
                schema_version=version,
            )

            with self.subTest(
                version=version
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_result_invalid$",
                ):
                    api.validate_provider_diagnostics_application_result(
                        value
                    )

    def test_request_exact_shape_contract(self):
        base = valid_request()

        class Subclass(
            api.ProviderDiagnosticsApplicationRequest
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        forged = copy.copy(
            base
        )

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        for value in (
            Hostile(),
            subclass,
            forged,
        ):
            with self.subTest(
                value_type=type(
                    value
                ).__name__
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_request_invalid$",
                ):
                    api.validate_provider_diagnostics_application_request(
                        value
                    )

    def test_result_exact_shape_contract(self):
        base = valid_result()

        class Subclass(
            api.ProviderDiagnosticsApplicationResult
        ):
            pass

        subclass = Subclass(
            **base.__dict__
        )

        forged = copy.copy(
            base
        )

        object.__setattr__(
            forged,
            "extra",
            Hostile(),
        )

        for value in (
            Hostile(),
            subclass,
            forged,
        ):
            with self.subTest(
                value_type=type(
                    value
                ).__name__
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_diagnostics_application_result_invalid$",
                ):
                    api.validate_provider_diagnostics_application_result(
                        value
                    )

    def test_request_config_requires_exact_type(self):
        base = valid_request()

        config_type = type(
            base.config
        )

        class ConfigSubclass(
            config_type
        ):
            pass

        subclass = ConfigSubclass(
            **base.config.__dict__
        )

        value = dataclasses.replace(
            base,
            config=subclass,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_application_request_invalid$",
        ):
            api.validate_provider_diagnostics_application_request(
                value
            )

    def test_request_invalid_config_rejected(self):
        config = copy.copy(
            openai_runtime_config()
        )

        object.__setattr__(
            config,
            "extra",
            "unexpected",
        )

        value = dataclasses.replace(
            valid_request(),
            config=config,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_application_request_invalid$",
        ):
            api.validate_provider_diagnostics_application_request(
                value
            )

    def test_request_mode_requires_exact_enum(self):
        value = dataclasses.replace(
            valid_request(),
            mode="OFFLINE",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_application_request_invalid$",
        ):
            api.validate_provider_diagnostics_application_request(
                value
            )

    def test_result_presentation_requires_exact_type(self):
        base = valid_result()

        class PresentationSubclass(
            ProviderDiagnosticPresentation
        ):
            pass

        subclass = PresentationSubclass(
            **base.presentation.__dict__
        )

        value = dataclasses.replace(
            base,
            presentation=subclass,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_application_result_invalid$",
        ):
            api.validate_provider_diagnostics_application_result(
                value
            )

    def test_result_invalid_presentation_rejected(self):
        presentation = copy.copy(
            valid_presentation()
        )

        object.__setattr__(
            presentation,
            "extra",
            "unexpected",
        )

        value = dataclasses.replace(
            valid_result(),
            presentation=presentation,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_diagnostics_application_result_invalid$",
        ):
            api.validate_provider_diagnostics_application_result(
                value
            )

    def test_request_fields_contract(self):
        self.assertEqual(
            tuple(
                field.name
                for field
                in dataclasses.fields(
                    api.ProviderDiagnosticsApplicationRequest
                )
            ),
            (
                "schema_version",
                "config",
                "mode",
            ),
        )

    def test_result_fields_contract(self):
        self.assertEqual(
            tuple(
                field.name
                for field
                in dataclasses.fields(
                    api.ProviderDiagnosticsApplicationResult
                )
            ),
            (
                "schema_version",
                "presentation",
            ),
        )

    def test_request_contains_no_runtime_remote_source(self):
        names = {
            field.name
            for field
            in dataclasses.fields(
                api.ProviderDiagnosticsApplicationRequest
            )
        }

        self.assertNotIn(
            "remote_image_source",
            names,
        )

        self.assertNotIn(
            "check",
            names,
        )

    def test_result_contains_only_presentation(self):
        names = {
            field.name
            for field
            in dataclasses.fields(
                api.ProviderDiagnosticsApplicationResult
            )
        }

        self.assertEqual(
            names,
            {
                "schema_version",
                "presentation",
            },
        )

        self.assertNotIn(
            "diagnostic_report",
            names,
        )

    def test_detached_request_roundtrips(self):
        value = valid_request(
            ProviderRuntimeDiagnosticMode.ONLINE
        )

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
                api.validate_provider_diagnostics_application_request(
                    variant
                ),
                value,
            )

    def test_detached_result_roundtrips(self):
        value = valid_result()

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
                api.validate_provider_diagnostics_application_result(
                    variant
                ),
                value,
            )

    def test_request_validation_memory_error_not_swallowed(self):
        with patch.object(
            models_module,
            "validate_provider_runtime_config",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                api.validate_provider_diagnostics_application_request(
                    valid_request()
                )

    def test_result_validation_memory_error_not_swallowed(self):
        with patch.object(
            models_module,
            "validate_provider_diagnostic_presentation",
            side_effect=MemoryError(),
        ):
            with self.assertRaises(
                MemoryError
            ):
                api.validate_provider_diagnostics_application_result(
                    valid_result()
                )

    def test_request_validation_error_is_sanitized(self):
        with patch.object(
            models_module,
            "validate_provider_runtime_config",
            side_effect=RuntimeError(
                "private-config-error"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_application_request_invalid$",
            ):
                api.validate_provider_diagnostics_application_request(
                    valid_request()
                )

    def test_result_validation_error_is_sanitized(self):
        with patch.object(
            models_module,
            "validate_provider_diagnostic_presentation",
            side_effect=RuntimeError(
                "private-presentation-error"
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "^provider_diagnostics_application_result_invalid$",
            ):
                api.validate_provider_diagnostics_application_result(
                    valid_result()
                )

    def test_contract_validation_has_no_environment_or_network_side_effect(self):
        request = valid_request()
        result = valid_result()

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
                self.assertIs(
                    api.validate_provider_diagnostics_application_request(
                        request
                    ),
                    request,
                )

                self.assertIs(
                    api.validate_provider_diagnostics_application_result(
                        result
                    ),
                    result,
                )

        getenv_mock.assert_not_called()
        opened.assert_not_called()

    def test_public_api_contract(self):
        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_DIAGNOSTICS_APPLICATION_SCHEMA_VERSION",
                "ProviderDiagnosticsApplicationRequest",
                "ProviderDiagnosticsApplicationResult",
                "validate_provider_diagnostics_application_request",
                "validate_provider_diagnostics_application_result",
            ),
        )


if __name__ == "__main__":
    unittest.main()