"""M88 external vision HTTP transport configuration contract."""

import copy
import dataclasses
import pickle
import unittest

import creator_studio.external_vision_http_transport as api

from creator_studio.external_vision_provider_transport import (
    MAX_EXTERNAL_VISION_RESPONSE_BYTES,
)


def config():
    return api.ExternalVisionHTTPConfig(
        schema_version=(
            api.EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION
        ),
        endpoint=(
            "https://vision.example.test/v1/analyze"
        ),
        timeout_millis=10_000,
        max_request_bytes=(
            api.MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
        ),
        max_response_bytes=(
            api.MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
        ),
        header_policy=(
            api.ExternalVisionHTTPHeaderPolicy
            .STRICT_JSON_V1
        ),
    )


class Hostile:
    def __getattribute__(
        self,
        name,
    ):
        raise AssertionError(
            "hostile access"
        )

    def __repr__(self):
        raise AssertionError(
            "hostile repr"
        )

    def __eq__(
        self,
        other,
    ):
        raise AssertionError(
            "hostile equality"
        )


class ExternalVisionHTTPTransportConfigTests(
    unittest.TestCase
):

    def test_valid_config(self):
        value = config()

        self.assertIs(
            api.validate_external_vision_http_config(
                value
            ),
            value,
        )

    def test_config_is_frozen(self):
        value = config()

        with self.assertRaises(
            dataclasses.FrozenInstanceError
        ):
            value.timeout_millis = 1

    def test_schema_version_contract(self):
        variants = [
            dataclasses.replace(
                config(),
                schema_version=0,
            ),
            dataclasses.replace(
                config(),
                schema_version=2,
            ),
            dataclasses.replace(
                config(),
                schema_version=True,
            ),
        ]

        for value in variants:
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_requires_exact_string(self):
        variants = [
            b"https://vision.example.test/v1/analyze",
            123,
            None,
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_rejects_surrounding_whitespace(self):
        variants = [
            " https://vision.example.test/v1/analyze",
            "https://vision.example.test/v1/analyze ",
            "\thttps://vision.example.test/v1/analyze",
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_requires_https(self):
        variants = [
            "http://vision.example.test/v1/analyze",
            "ftp://vision.example.test/v1/analyze",
            "file:///tmp/vision",
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_requires_hostname(self):
        variants = [
            "https:///v1/analyze",
            "https://",
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_rejects_userinfo(self):
        variants = [
            (
                "https://user@vision.example.test/"
                "v1/analyze"
            ),
            (
                "https://user:secret@vision.example.test/"
                "v1/analyze"
            ),
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_rejects_query(self):
        value = dataclasses.replace(
            config(),
            endpoint=(
                "https://vision.example.test/v1/analyze"
                "?key=secret"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                value
            )

    def test_endpoint_rejects_fragment(self):
        value = dataclasses.replace(
            config(),
            endpoint=(
                "https://vision.example.test/v1/analyze"
                "#fragment"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                value
            )

    def test_endpoint_rejects_invalid_port(self):
        variants = [
            (
                "https://vision.example.test:"
                "notaport/v1/analyze"
            ),
            (
                "https://vision.example.test:"
                "99999/v1/analyze"
            ),
        ]

        for endpoint in variants:
            value = dataclasses.replace(
                config(),
                endpoint=endpoint,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_endpoint_length_limit(self):
        endpoint = (
            "https://vision.example.test/"
            + (
                "a"
                * api.MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH
            )
        )

        value = dataclasses.replace(
            config(),
            endpoint=endpoint,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                value
            )

    def test_timeout_lower_bound(self):
        valid = dataclasses.replace(
            config(),
            timeout_millis=(
                api.MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
            ),
        )

        self.assertIs(
            api.validate_external_vision_http_config(
                valid
            ),
            valid,
        )

        variants = [
            0,
            (
                api.MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
                - 1
            ),
            True,
        ]

        for timeout in variants:
            value = dataclasses.replace(
                config(),
                timeout_millis=timeout,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_timeout_upper_bound(self):
        valid = dataclasses.replace(
            config(),
            timeout_millis=(
                api.MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
            ),
        )

        self.assertIs(
            api.validate_external_vision_http_config(
                valid
            ),
            valid,
        )

        value = dataclasses.replace(
            config(),
            timeout_millis=(
                api.MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS
                + 1
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                value
            )

    def test_request_limit_contract(self):
        valid = dataclasses.replace(
            config(),
            max_request_bytes=1,
        )

        self.assertIs(
            api.validate_external_vision_http_config(
                valid
            ),
            valid,
        )

        variants = [
            0,
            -1,
            True,
            (
                api.MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES
                + 1
            ),
        ]

        for limit in variants:
            value = dataclasses.replace(
                config(),
                max_request_bytes=limit,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_response_limit_contract(self):
        valid = dataclasses.replace(
            config(),
            max_response_bytes=1,
        )

        self.assertIs(
            api.validate_external_vision_http_config(
                valid
            ),
            valid,
        )

        variants = [
            0,
            -1,
            True,
            (
                api.MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES
                + 1
            ),
        ]

        for limit in variants:
            value = dataclasses.replace(
                config(),
                max_response_bytes=limit,
            )

            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_header_policy_requires_exact_enum(self):
        value = dataclasses.replace(
            config(),
            header_policy="STRICT_JSON_V1",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                value
            )

    def test_exact_shape(self):
        base = config()

        class Subclass(
            api.ExternalVisionHTTPConfig
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
            with self.assertRaisesRegex(
                ValueError,
                "^external_vision_http_config_invalid$",
            ):
                api.validate_external_vision_http_config(
                    value
                )

    def test_detached_roundtrips(self):
        value = config()

        variants = [
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
        ]

        for variant in variants:
            self.assertEqual(
                api.validate_external_vision_http_config(
                    variant
                ),
                value,
            )

    def test_error_is_sanitized(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_config_invalid$",
        ):
            api.validate_external_vision_http_config(
                object()
            )

    def test_constants_are_stable(self):
        self.assertEqual(
            api.EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION,
            1,
        )

        self.assertEqual(
            api.MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH,
            2048,
        )

        self.assertEqual(
            api.MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS,
            100,
        )

        self.assertEqual(
            api.MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS,
            30_000,
        )

        self.assertEqual(
            api.MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES,
            10 * 1024 * 1024,
        )

        self.assertEqual(
            api.MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES,
            MAX_EXTERNAL_VISION_RESPONSE_BYTES,
        )

    def test_public_api(self):
        self.assertEqual(
            api.__all__,
            (
                "EXTERNAL_VISION_HTTP_CONFIG_SCHEMA_VERSION",
                "MAX_EXTERNAL_VISION_HTTP_ENDPOINT_LENGTH",
                "MAX_EXTERNAL_VISION_HTTP_REQUEST_BYTES",
                "MAX_EXTERNAL_VISION_HTTP_RESPONSE_BYTES",
                "MAX_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS",
                "MIN_EXTERNAL_VISION_HTTP_TIMEOUT_MILLIS",
                "ExternalVisionHTTPConfig",
                "ExternalVisionHTTPHeaderPolicy",
                "validate_external_vision_http_config",
            ),
        )

        self.assertEqual(
            {
                value.value
                for value
                in api.ExternalVisionHTTPHeaderPolicy
            },
            {
                "STRICT_JSON_V1",
            },
        )


if __name__ == "__main__":
    unittest.main()