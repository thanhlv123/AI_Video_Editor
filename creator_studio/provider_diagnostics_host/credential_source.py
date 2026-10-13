"""M100 provider diagnostics host credential integration.

This module adapts the application's existing APIKeyManager credential store
to the runtime-only credential-source contract used by provider diagnostics.

Security properties:

- no secret is accepted by a factory or source constructor;
- no secret is stored in the factory or source object;
- only one APIKeyManager profile is bound to one factory;
- provider metadata must match the bound APIKeyManager profile;
- the secret is read only when resolve() executes;
- every resolve() performs a fresh get_secret(profile_id) lookup;
- runtime_environment() is never used;
- process environment variables are never modified;
- no network operation is performed here;
- returned credentials use the existing M88 credential contract.

The factory itself is runtime authority and must never be inserted into
detached configuration, diagnostic reports, GUI state or presentation models.
"""

from config.api_key_manager import (
    APIKeyManager,
)

from ..external_vision_http_transport import (
    ExternalVisionHTTPCredential,
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialSource,
)
from ..provider_runtime_assembly import (
    EnvironmentCredentialSource,
    ProviderEnvironmentCredentialMode,
)


MAX_PROVIDER_DIAGNOSTICS_HOST_PROFILE_ID_LENGTH = 128


def _invalid_factory():
    raise ValueError(
        "api_key_manager_credential_source_factory_invalid"
    )


def _validate_profile_id(
    value,
):
    if type(value) is not str:
        _invalid_factory()

    if (
        not value
        or value != value.strip()
        or len(value)
        > MAX_PROVIDER_DIAGNOSTICS_HOST_PROFILE_ID_LENGTH
    ):
        _invalid_factory()

    for character in value:
        if (
            (
                "a"
                <= character
                <= "z"
            )
            or (
                "A"
                <= character
                <= "Z"
            )
            or (
                "0"
                <= character
                <= "9"
            )
            or character == "_"
            or character == "-"
        ):
            continue

        _invalid_factory()


def _validate_raw_secret(
    value,
):
    if type(value) is not str:
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    if (
        not value
        or value != value.strip()
    ):
        raise ExternalVisionHTTPCredentialFailure(
            ExternalVisionHTTPCredentialFailureCode
            .INVALID
        )

    for character in value:
        code = ord(
            character
        )

        if (
            code <= 32
            or code > 126
        ):
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            )


def _validated_runtime_metadata(
    environment_variable,
    header,
    mode,
):
    """
    Reuse the M90 constructor contract to validate runtime metadata.

    EnvironmentCredentialSource construction performs metadata validation only.
    Its resolve() method is never invoked here.
    """
    try:
        validator = EnvironmentCredentialSource(
            environment_variable,
            header,
            mode,
        )

    except MemoryError:
        raise

    except Exception:
        _invalid_factory()

    metadata = (
        validator.environment_variable,
        validator.header,
        validator.mode,
    )

    del validator

    return metadata


def _validated_manager_profile(
    api_key_manager,
    profile_id,
    environment_variable,
):
    try:
        profile = api_key_manager.get_profile(
            profile_id
        )

    except MemoryError:
        raise

    except Exception:
        _invalid_factory()

    if type(profile) is not dict:
        _invalid_factory()

    if (
        profile.get(
            "id"
        )
        != profile_id
    ):
        _invalid_factory()

    profile_environment_variable = (
        profile.get(
            "env_var"
        )
    )

    if (
        type(
            profile_environment_variable
        )
        is not str
        or profile_environment_variable
        != environment_variable
    ):
        _invalid_factory()

    fields = profile.get(
        "fields",
        [],
    )

    if fields is None:
        fields = []

    if (
        type(fields) is not list
        or fields
    ):
        _invalid_factory()

    return profile


class _APIKeyManagerCredentialSource(
    ExternalVisionHTTPCredentialSource
):
    """Resolve one APIKeyManager secret without retaining the secret."""

    __slots__ = (
        "_api_key_manager",
        "_profile_id",
        "_environment_variable",
        "_header",
        "_mode",
    )

    def __init__(
        self,
        api_key_manager,
        profile_id,
        environment_variable,
        header,
        mode,
    ):
        if (
            type(api_key_manager)
            is not APIKeyManager
        ):
            _invalid_factory()

        _validate_profile_id(
            profile_id
        )

        (
            environment_variable,
            header,
            mode,
        ) = _validated_runtime_metadata(
            environment_variable,
            header,
            mode,
        )

        self._api_key_manager = (
            api_key_manager
        )

        self._profile_id = (
            profile_id
        )

        self._environment_variable = (
            environment_variable
        )

        self._header = header
        self._mode = mode

    @property
    def profile_id(
        self,
    ):
        return self._profile_id

    @property
    def environment_variable(
        self,
    ):
        return self._environment_variable

    @property
    def header(
        self,
    ):
        return self._header

    @property
    def mode(
        self,
    ):
        return self._mode

    def resolve(
        self,
        check,
    ):
        check()

        try:
            raw_secret = (
                self._api_key_manager
                .get_secret(
                    self._profile_id
                )
            )

        except MemoryError:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except Exception:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE
            ) from None

        check()

        if (
            raw_secret is None
            or raw_secret == ""
        ):
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .UNAVAILABLE
            )

        _validate_raw_secret(
            raw_secret
        )

        check()

        try:
            if (
                self._mode
                is ProviderEnvironmentCredentialMode
                .BEARER
            ):
                credential_value = (
                    "Bearer "
                    + raw_secret
                )

            elif (
                self._mode
                is ProviderEnvironmentCredentialMode
                .RAW
            ):
                credential_value = (
                    raw_secret
                )

            else:
                raise ExternalVisionHTTPCredentialFailure(
                    ExternalVisionHTTPCredentialFailureCode
                    .INTERNAL_FAILURE
                )

            credential = (
                ExternalVisionHTTPCredential(
                    self._header,
                    credential_value,
                )
            )

        except ExternalVisionHTTPCredentialFailure:
            raise

        except MemoryError:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except ValueError:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INVALID
            ) from None

        except Exception:
            raise ExternalVisionHTTPCredentialFailure(
                ExternalVisionHTTPCredentialFailureCode
                .INTERNAL_FAILURE
            ) from None

        del raw_secret
        del credential_value

        check()

        return credential

    def __copy__(
        self,
    ):
        raise TypeError(
            "api_key_manager_credential_source_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "api_key_manager_credential_source_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "api_key_manager_credential_source_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "_APIKeyManagerCredentialSource("
            f"profile_id={self._profile_id!r}, "
            f"environment_variable="
            f"{self._environment_variable!r}, "
            f"header={self._header.value!r}, "
            f"mode={self._mode.value!r})"
        )


class APIKeyManagerCredentialSourceFactory:
    """
    Bind exactly one APIKeyManager profile to provider diagnostics.

    The factory stores APIKeyManager authority and non-secret profile metadata
    only. The credential itself is looked up later by the returned source.
    """

    __slots__ = (
        "_api_key_manager",
        "_profile_id",
    )

    def __init__(
        self,
        api_key_manager,
        profile_id,
    ):
        if (
            type(api_key_manager)
            is not APIKeyManager
        ):
            _invalid_factory()

        _validate_profile_id(
            profile_id
        )

        self._api_key_manager = (
            api_key_manager
        )

        self._profile_id = (
            profile_id
        )

    @property
    def profile_id(
        self,
    ):
        return self._profile_id

    def __call__(
        self,
        environment_variable,
        header,
        mode,
    ):
        (
            environment_variable,
            header,
            mode,
        ) = _validated_runtime_metadata(
            environment_variable,
            header,
            mode,
        )

        _validated_manager_profile(
            self._api_key_manager,
            self._profile_id,
            environment_variable,
        )

        return _APIKeyManagerCredentialSource(
            self._api_key_manager,
            self._profile_id,
            environment_variable,
            header,
            mode,
        )

    def __copy__(
        self,
    ):
        raise TypeError(
            "api_key_manager_credential_source_factory_runtime_only"
        )

    def __deepcopy__(
        self,
        memo,
    ):
        raise TypeError(
            "api_key_manager_credential_source_factory_runtime_only"
        )

    def __reduce__(
        self,
    ):
        raise TypeError(
            "api_key_manager_credential_source_factory_runtime_only"
        )

    def __repr__(
        self,
    ):
        return (
            "APIKeyManagerCredentialSourceFactory("
            f"profile_id={self._profile_id!r})"
        )