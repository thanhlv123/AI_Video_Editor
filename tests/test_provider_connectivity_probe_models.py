"""M92 provider connectivity probe model contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.provider_connectivity_probe as api

from creator_studio.provider_specific_vision_adapter import (
    VisionProviderKind,
)


def ready_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .READY
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=200,
        provider_code=None,
    )


def kie_ready_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .READY
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=200,
    )


def config_invalid_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .CONFIG_INVALID
        ),
        provider=None,
        credential_environment_variable=None,
        http_status=None,
        provider_code=None,
    )


def credential_missing_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .CREDENTIAL_MISSING
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def credential_invalid_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .CREDENTIAL_INVALID
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def authentication_failed_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=401,
        provider_code=None,
    )


def kie_authentication_failed_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=401,
    )


def permission_denied_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .PERMISSION_DENIED
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=403,
        provider_code=None,
    )


def rate_limited_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .RATE_LIMITED
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=429,
        provider_code=None,
    )


def provider_unavailable_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .PROVIDER_UNAVAILABLE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=503,
        provider_code=None,
    )


def kie_provider_unavailable_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .PROVIDER_UNAVAILABLE
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=500,
    )


def network_unavailable_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .NETWORK_UNAVAILABLE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def deadline_exceeded_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .DEADLINE_EXCEEDED
        ),
        provider=VisionProviderKind.GEMINI,
        credential_environment_variable=(
            "GEMINI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
    )


def response_invalid_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .RESPONSE_INVALID
        ),
        provider=VisionProviderKind.KIE_AI,
        credential_environment_variable=(
            "KIE_API_KEY"
        ),
        http_status=200,
        provider_code=422,
    )


def internal_failure_report():
    return api.ProviderConnectivityProbeReport(
        schema_version=(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
        ),
        status=(
            api.ProviderConnectivityProbeStatus
            .INTERNAL_FAILURE
        ),
        provider=VisionProviderKind.OPENAI,
        credential_environment_variable=(
            "OPENAI_API_KEY"
        ),
        http_status=None,
        provider_code=None,
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


class ProviderConnectivityProbeModelTests(
    unittest.TestCase
):

    def test_schema_version_constant(self):
        self.assertEqual(
            api.PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION,
            1,
        )

    def test_status_enum_contract(self):
        self.assertEqual(
            {
                value.value
                for value
                in api.ProviderConnectivityProbeStatus
            },
            {
                "READY",
                "CONFIG_INVALID",
                "CREDENTIAL_MISSING",
                "CREDENTIAL_INVALID",
                "AUTHENTICATION_FAILED",
                "PERMISSION_DENIED",
                "RATE_LIMITED",
                "PROVIDER_UNAVAILABLE",
                "NETWORK_UNAVAILABLE",
                "DEADLINE_EXCEEDED",
                "RESPONSE_INVALID",
                "INTERNAL_FAILURE",
            },
        )

    def test_ready_report_valid(self):
        for value in (
            ready_report(),
            kie_ready_report(),
        ):
            with self.subTest(
                provider=value.provider
            ):
                self.assertIs(
                    api.validate_provider_connectivity_probe_report(
                        value
                    ),
                    value,
                )

    def test_config_invalid_report_valid(self):
        value = config_invalid_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_authentication_failed_report_valid(self):
        for value in (
            authentication_failed_report(),
            kie_authentication_failed_report(),
        ):
            with self.subTest(
                provider=value.provider
            ):
                self.assertIs(
                    api.validate_provider_connectivity_probe_report(
                        value
                    ),
                    value,
                )

    def test_permission_denied_report_valid(self):
        value = permission_denied_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_rate_limited_report_valid(self):
        value = rate_limited_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_provider_unavailable_report_valid(self):
        for value in (
            provider_unavailable_report(),
            kie_provider_unavailable_report(),
        ):
            with self.subTest(
                provider=value.provider
            ):
                self.assertIs(
                    api.validate_provider_connectivity_probe_report(
                        value
                    ),
                    value,
                )

    def test_network_unavailable_report_valid(self):
        value = network_unavailable_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_deadline_exceeded_report_valid(self):
        value = deadline_exceeded_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_response_invalid_report_valid(self):
        value = response_invalid_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_internal_failure_report_valid(self):
        value = internal_failure_report()

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                value
            ),
            value,
        )

    def test_report_is_frozen(self):
        value = ready_report()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.status = (
                api.ProviderConnectivityProbeStatus
                .INTERNAL_FAILURE
            )

    def test_schema_version_contract(self):
        for version in (
            0,
            2,
            True,
        ):
            value = dataclasses.replace(
                ready_report(),
                schema_version=version,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^provider_connectivity_probe_report_invalid$",
            ):
                api.validate_provider_connectivity_probe_report(
                    value
                )

    def test_exact_shape_contract(self):
        base = ready_report()

        class Subclass(
            api.ProviderConnectivityProbeReport
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
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_status_requires_exact_enum(self):
        value = dataclasses.replace(
            ready_report(),
            status="READY",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_connectivity_probe_report_invalid$",
        ):
            api.validate_provider_connectivity_probe_report(
                value
            )

    def test_provider_requires_exact_enum(self):
        value = dataclasses.replace(
            ready_report(),
            provider="OPENAI",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_connectivity_probe_report_invalid$",
        ):
            api.validate_provider_connectivity_probe_report(
                value
            )

    def test_metadata_must_be_paired(self):
        variants = (
            dataclasses.replace(
                ready_report(),
                provider=None,
            ),
            dataclasses.replace(
                ready_report(),
                credential_environment_variable=None,
            ),
        )

        for value in variants:
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_config_invalid_requires_empty_metadata(self):
        variants = (
            dataclasses.replace(
                config_invalid_report(),
                provider=VisionProviderKind.OPENAI,
                credential_environment_variable=(
                    "OPENAI_API_KEY"
                ),
            ),
            dataclasses.replace(
                config_invalid_report(),
                http_status=400,
            ),
            dataclasses.replace(
                config_invalid_report(),
                provider_code=400,
            ),
        )

        for value in variants:
            with self.subTest(
                value=value
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_non_config_status_requires_metadata(self):
        value = dataclasses.replace(
            network_unavailable_report(),
            provider=None,
            credential_environment_variable=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_connectivity_probe_report_invalid$",
        ):
            api.validate_provider_connectivity_probe_report(
                value
            )

    def test_environment_variable_contract(self):
        invalid = (
            "",
            " OPENAI_API_KEY",
            "OPENAI_API_KEY ",
            "openai_api_key",
            "9OPENAI_API_KEY",
            "OPENAI-API-KEY",
            "OPENAI API KEY",
        )

        for name in invalid:
            with self.subTest(
                name=name
            ):
                value = dataclasses.replace(
                    ready_report(),
                    credential_environment_variable=name,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_http_status_requires_exact_integer(self):
        for status in (
            True,
            200.0,
            "200",
        ):
            value = dataclasses.replace(
                ready_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_http_status_range(self):
        for status in (
            99,
            600,
        ):
            value = dataclasses.replace(
                response_invalid_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_ready_requires_success_http_status(self):
        for status in (
            None,
            199,
            300,
            401,
            500,
        ):
            value = dataclasses.replace(
                ready_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

        for provider_code in (
            199,
            300,
            401,
            500,
        ):
            value = dataclasses.replace(
                kie_ready_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                provider_code=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_authentication_requires_401(self):
        direct_invalid = (
            None,
            400,
            403,
            429,
            500,
        )

        for status in direct_invalid:
            value = dataclasses.replace(
                authentication_failed_report(),
                http_status=status,
            )

            with self.subTest(
                direct_http=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

        wrapped_invalid = (
            400,
            403,
            429,
            500,
        )

        for provider_code in wrapped_invalid:
            value = dataclasses.replace(
                kie_authentication_failed_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                provider_code=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_permission_requires_403(self):
        for status in (
            None,
            400,
            401,
            429,
            500,
        ):
            value = dataclasses.replace(
                permission_denied_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

        wrapped = dataclasses.replace(
            permission_denied_report(),
            http_status=200,
            provider_code=403,
        )

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                wrapped
            ),
            wrapped,
        )

    def test_rate_limit_requires_429(self):
        for status in (
            None,
            400,
            401,
            403,
            500,
        ):
            value = dataclasses.replace(
                rate_limited_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

        wrapped = dataclasses.replace(
            rate_limited_report(),
            http_status=200,
            provider_code=429,
        )

        self.assertIs(
            api.validate_provider_connectivity_probe_report(
                wrapped
            ),
            wrapped,
        )

    def test_provider_unavailable_requires_5xx(self):
        for status in (
            None,
            200,
            400,
            499,
            600,
        ):
            value = dataclasses.replace(
                provider_unavailable_report(),
                http_status=status,
            )

            with self.subTest(
                status=status
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

        for provider_code in (
            200,
            400,
            499,
            600,
        ):
            value = dataclasses.replace(
                kie_provider_unavailable_report(),
                provider_code=provider_code,
            )

            with self.subTest(
                provider_code=provider_code
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^provider_connectivity_probe_report_invalid$",
                ):
                    api.validate_provider_connectivity_probe_report(
                        value
                    )

    def test_non_http_failures_reject_http_status(self):
        values = (
            credential_missing_report(),
            credential_invalid_report(),
            network_unavailable_report(),
            deadline_exceeded_report(),
            internal_failure_report(),
        )

        for base in values:
            variants = (
                dataclasses.replace(
                    base,
                    http_status=500,
                ),
                dataclasses.replace(
                    base,
                    provider_code=500,
                ),
            )

            for value in variants:
                with self.subTest(
                    probe_status=base.status,
                    value=value,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "^provider_connectivity_probe_report_invalid$",
                    ):
                        api.validate_provider_connectivity_probe_report(
                            value
                        )

    def test_response_invalid_requires_http_status(self):
        value = dataclasses.replace(
            response_invalid_report(),
            http_status=None,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^provider_connectivity_probe_report_invalid$",
        ):
            api.validate_provider_connectivity_probe_report(
                value
            )

    def test_detached_roundtrips(self):
        values = (
            ready_report(),
            kie_ready_report(),
            config_invalid_report(),
            credential_missing_report(),
            credential_invalid_report(),
            authentication_failed_report(),
            kie_authentication_failed_report(),
            permission_denied_report(),
            rate_limited_report(),
            provider_unavailable_report(),
            kie_provider_unavailable_report(),
            network_unavailable_report(),
            deadline_exceeded_report(),
            response_invalid_report(),
            internal_failure_report(),
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
                    api.validate_provider_connectivity_probe_report(
                        variant
                    ),
                    value,
                )

    def test_report_contains_no_secret_fields(self):
        names = {
            field.name.lower()
            for field
            in dataclasses.fields(
                api.ProviderConnectivityProbeReport
            )
        }

        forbidden = {
            "secret",
            "password",
            "token",
            "api_key",
            "credential",
            "credential_value",
            "authorization",
            "request_body",
            "response_body",
        }

        self.assertTrue(
            names.isdisjoint(
                forbidden
            )
        )

        self.assertEqual(
            names,
            {
                "schema_version",
                "status",
                "provider",
                "credential_environment_variable",
                "http_status",
                "provider_code",
            },
        )

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION",
                "ProviderConnectivityProbeReport",
                "ProviderConnectivityProbeStatus",
                "validate_provider_connectivity_probe_report",
            ),
        )


if __name__ == "__main__":
    unittest.main()