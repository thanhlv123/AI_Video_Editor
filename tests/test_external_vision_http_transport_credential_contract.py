"""M88 runtime-only external vision HTTP credential contract."""

import copy
import inspect
import pickle
import unittest

from creator_studio.external_vision_http_transport.credential_contract import (
    MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH,
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
    ExternalVisionHTTPCredentialSource,
    _resolve_http_credential,
)


class ValidSource(
    ExternalVisionHTTPCredentialSource
):
    def __init__(
        self,
        credential=None,
    ):
        if credential is None:
            credential = ExternalVisionHTTPCredential(
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                "Bearer test-token-123",
            )

        self.credential = credential
        self.checks = []

    def resolve(
        self,
        check,
    ):
        self.checks.append(
            check
        )

        check()

        return self.credential


class FailureSource(
    ExternalVisionHTTPCredentialSource
):
    def __init__(
        self,
        code,
    ):
        self.code = code

    def resolve(
        self,
        check,
    ):
        raise ExternalVisionHTTPCredentialFailure(
            self.code
        )


class MemorySource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        raise MemoryError()


class ErrorSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        raise RuntimeError(
            "private"
        )


class InterruptSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        raise KeyboardInterrupt()


class InvalidSource(
    ExternalVisionHTTPCredentialSource
):
    def resolve(
        self,
        check,
    ):
        return object()


class ExternalVisionHTTPCredentialContractTests(
    unittest.TestCase
):

    def credential(
        self,
    ):
        return ExternalVisionHTTPCredential(
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
            "Bearer test-token-123",
        )

    def test_valid_credential(self):
        value = self.credential()

        self.assertIs(
            value.header,
            ExternalVisionHTTPCredentialHeader
            .AUTHORIZATION,
        )

        self.assertEqual(
            value.value,
            "Bearer test-token-123",
        )

    def test_header_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_credential_invalid$",
        ):
            ExternalVisionHTTPCredential(
                "Authorization",
                "Bearer test-token",
            )

    def test_secret_requires_exact_string(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_credential_invalid$",
        ):
            ExternalVisionHTTPCredential(
                ExternalVisionHTTPCredentialHeader
                .AUTHORIZATION,
                b"secret",
            )

    def test_secret_rejects_empty_or_whitespace(self):
        for value in (
            "",
            " secret",
            "secret ",
            "\tsecret",
            "secret\n",
        ):
            with self.subTest(
                value=repr(
                    value
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^external_vision_http_credential_invalid$",
                ):
                    ExternalVisionHTTPCredential(
                        ExternalVisionHTTPCredentialHeader
                        .X_API_KEY,
                        value,
                    )

    def test_secret_rejects_control_and_non_ascii(self):
        for value in (
            "abc\rdef",
            "abc\ndef",
            "abc\x00def",
            "tökén",
        ):
            with self.subTest(
                value=repr(
                    value
                )
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "^external_vision_http_credential_invalid$",
                ):
                    ExternalVisionHTTPCredential(
                        ExternalVisionHTTPCredentialHeader
                        .X_API_KEY,
                        value,
                    )

    def test_secret_length_bound(self):
        valid = ExternalVisionHTTPCredential(
            ExternalVisionHTTPCredentialHeader
            .X_API_KEY,
            "a"
            * MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH,
        )

        self.assertEqual(
            len(
                valid.value
            ),
            MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH,
        )

        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_credential_invalid$",
        ):
            ExternalVisionHTTPCredential(
                ExternalVisionHTTPCredentialHeader
                .X_API_KEY,
                "a"
                * (
                    MAX_EXTERNAL_VISION_HTTP_CREDENTIAL_LENGTH
                    + 1
                ),
            )

    def test_repr_is_redacted(self):
        value = self.credential()

        self.assertEqual(
            repr(
                value
            ),
            "ExternalVisionHTTPCredential(<redacted>)",
        )

        self.assertNotIn(
            "test-token-123",
            repr(
                value
            ),
        )

    def test_str_is_redacted(self):
        value = self.credential()

        self.assertEqual(
            str(
                value
            ),
            "<redacted>",
        )

        self.assertNotIn(
            "test-token-123",
            str(
                value
            ),
        )

    def test_copy_is_rejected(self):
        value = self.credential()

        with self.assertRaisesRegex(
            TypeError,
            "^external_vision_http_credential_noncopyable$",
        ):
            copy.copy(
                value
            )

        with self.assertRaisesRegex(
            TypeError,
            "^external_vision_http_credential_noncopyable$",
        ):
            copy.deepcopy(
                value
            )

    def test_pickle_is_rejected(self):
        value = self.credential()

        with self.assertRaisesRegex(
            TypeError,
            "^external_vision_http_credential_nonserializable$",
        ):
            pickle.dumps(
                value
            )

    def test_source_is_abstract(self):
        with self.assertRaises(
            TypeError
        ):
            ExternalVisionHTTPCredentialSource()

    def test_source_signature(self):
        self.assertEqual(
            tuple(
                inspect.signature(
                    ExternalVisionHTTPCredentialSource
                    .resolve
                ).parameters
            ),
            (
                "self",
                "check",
            ),
        )

    def test_resolve_success(self):
        source = ValidSource()

        result = _resolve_http_credential(
            source,
            lambda: None,
        )

        self.assertIs(
            result,
            source.credential,
        )

    def test_check_identity_reaches_source(self):
        source = ValidSource()

        def check():
            pass

        _resolve_http_credential(
            source,
            check,
        )

        self.assertEqual(
            len(
                source.checks
            ),
            1,
        )

        self.assertIs(
            source.checks[
                0
            ],
            check,
        )

    def test_check_is_used_repeatedly(self):
        source = ValidSource()
        calls = [0]

        def check():
            calls[
                0
            ] += 1

        _resolve_http_credential(
            source,
            check,
        )

        self.assertGreaterEqual(
            calls[
                0
            ],
            3,
        )

    def test_invalid_source_maps_unavailable(self):
        with self.assertRaises(
            ExternalVisionHTTPCredentialFailure
        ) as caught:
            _resolve_http_credential(
                object(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .UNAVAILABLE,
        )

    def test_invalid_resolved_value_mapping(self):
        with self.assertRaises(
            ExternalVisionHTTPCredentialFailure
        ) as caught:
            _resolve_http_credential(
                InvalidSource(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .INVALID,
        )

    def test_declared_failure_is_preserved(self):
        for code in ExternalVisionHTTPCredentialFailureCode:
            with self.subTest(
                code=code
            ):
                with self.assertRaises(
                    ExternalVisionHTTPCredentialFailure
                ) as caught:
                    _resolve_http_credential(
                        FailureSource(
                            code
                        ),
                        lambda: None,
                    )

                self.assertIs(
                    caught.exception.code,
                    code,
                )

    def test_memory_error_mapping(self):
        with self.assertRaises(
            ExternalVisionHTTPCredentialFailure
        ) as caught:
            _resolve_http_credential(
                MemorySource(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .RESOURCE_LIMIT_EXCEEDED,
        )

    def test_unexpected_exception_mapping(self):
        with self.assertRaises(
            ExternalVisionHTTPCredentialFailure
        ) as caught:
            _resolve_http_credential(
                ErrorSource(),
                lambda: None,
            )

        self.assertIs(
            caught.exception.code,
            ExternalVisionHTTPCredentialFailureCode
            .INTERNAL_FAILURE,
        )

    def test_baseexception_not_swallowed(self):
        with self.assertRaises(
            KeyboardInterrupt
        ):
            _resolve_http_credential(
                InterruptSource(),
                lambda: None,
            )

    def test_failure_requires_exact_enum(self):
        with self.assertRaisesRegex(
            ValueError,
            "^external_vision_http_credential_failure_invalid$",
        ):
            ExternalVisionHTTPCredentialFailure(
                "UNAVAILABLE"
            )

    def test_header_enum_is_stable(self):
        self.assertEqual(
            {
                value.value
                for value
                in ExternalVisionHTTPCredentialHeader
            },
            {
                "Authorization",
                "X-API-Key",
                "api-key",
                "X-Goog-Api-Key",
            },
        )

    def test_failure_enum_is_stable(self):
        self.assertEqual(
            {
                value.value
                for value
                in ExternalVisionHTTPCredentialFailureCode
            },
            {
                "UNAVAILABLE",
                "INVALID",
                "RESOURCE_LIMIT_EXCEEDED",
                "DEADLINE_EXCEEDED",
                "INTERNAL_FAILURE",
            },
        )


if __name__ == "__main__":
    unittest.main()