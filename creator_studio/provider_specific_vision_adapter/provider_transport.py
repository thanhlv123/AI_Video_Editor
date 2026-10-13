"""M89 provider-specific vision transport orchestration.

This module adapts the generic M87 transport contract to one validated
provider-specific profile.

It intentionally performs no direct network access.

Pipeline:

    M87 request
        -> provider-specific serializer
        -> injected ProviderVisionHTTPExchange
        -> provider-specific response extractor
        -> normalized M87 response

For providers that require a remotely reachable image URL, the URL is resolved
at runtime through ProviderVisionRemoteImageSource. It is never persisted in
the provider profile.

The injected exchange is responsible for actual HTTP execution in a later
boundary.
"""

from abc import ABC, abstractmethod

from ..external_vision_provider_transport import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    ExternalVisionTransportRequest,
    ExternalVisionTransportResponse,
    validate_external_vision_transport_request,
    validate_external_vision_transport_response,
)
from .models import (
    ProviderVisionProfile,
    VisionProviderKind,
    validate_provider_vision_profile,
)
from .request_serializer import (
    _ProviderRequestSerializeFailure,
    _ProviderRequestSerializeFailureCode,
    _serialize_provider_request,
)
from .response_extractor import (
    _ProviderResponseExtractFailure,
    _ProviderResponseExtractFailureCode,
    _extract_provider_response,
)


class ProviderVisionHTTPExchange(ABC):
    """
    Execution contract for one already-serialized provider JSON request.

    Implementations may perform HTTPS execution, but this abstract contract
    itself grants no source authority and stores no credential.
    """

    @abstractmethod
    def send(
        self,
        profile,
        body,
        check,
    ):
        raise NotImplementedError


class ProviderVisionRemoteImageSource(ABC):
    """
    Runtime source of one HTTPS image URL.

    This is used only by provider profiles that require externally reachable
    media rather than inline image bytes.

    An implementation may upload or publish media, but that behavior belongs
    outside this orchestration module.
    """

    @abstractmethod
    def resolve(
        self,
        request,
        check,
    ):
        raise NotImplementedError


def _map_request_serialize_failure(
    code,
):
    if (
        code
        is _ProviderRequestSerializeFailureCode
        .REQUEST_INVALID
    ):
        return (
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        )

    if (
        code
        is _ProviderRequestSerializeFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if code in (
        _ProviderRequestSerializeFailureCode
        .PROFILE_INVALID,
        _ProviderRequestSerializeFailureCode
        .PROFILE_COHERENCE_INVALID,
        _ProviderRequestSerializeFailureCode
        .REMOTE_IMAGE_REQUIRED,
        _ProviderRequestSerializeFailureCode
        .REMOTE_IMAGE_INVALID,
        _ProviderRequestSerializeFailureCode
        .SERIALIZATION_INVALID,
    ):
        return (
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    return (
        ExternalVisionTransportFailureCode
        .INTERNAL_FAILURE
    )


def _map_response_extract_failure(
    code,
):
    if (
        code
        is _ProviderResponseExtractFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if code in (
        _ProviderResponseExtractFailureCode
        .TRANSPORT_RESPONSE_INVALID,
        _ProviderResponseExtractFailureCode
        .JSON_INVALID,
        _ProviderResponseExtractFailureCode
        .PROVIDER_RESPONSE_INVALID,
        _ProviderResponseExtractFailureCode
        .OUTPUT_INVALID,
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        )

    if (
        code
        is _ProviderResponseExtractFailureCode
        .PROFILE_INVALID
    ):
        return (
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    return (
        ExternalVisionTransportFailureCode
        .INTERNAL_FAILURE
    )


def _validate_request_for_execution(
    request,
):
    try:
        validate_external_vision_transport_request(
            request
        )

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        ) from None

    if type(request) is not ExternalVisionTransportRequest:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        )


def _resolve_remote_image(
    source,
    request,
    check,
):
    if not isinstance(
        source,
        ProviderVisionRemoteImageSource,
    ):
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    check()

    try:
        value = source.resolve(
            request,
            check,
        )

    except ExternalVisionTransportFailure:
        raise

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        ) from None

    check()

    return value


def _invoke_exchange(
    exchange,
    profile,
    body,
    check,
):
    if not isinstance(
        exchange,
        ProviderVisionHTTPExchange,
    ):
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    if type(body) is not bytes:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    if not body:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        )

    check()

    try:
        response = exchange.send(
            profile,
            body,
            check,
        )

    except ExternalVisionTransportFailure:
        raise

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .INTERNAL_FAILURE
        ) from None

    check()

    try:
        validate_external_vision_transport_response(
            response
        )

    except MemoryError:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        ) from None

    if type(response) is not ExternalVisionTransportResponse:
        raise ExternalVisionTransportFailure(
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        )

    check()

    return response


class ProviderSpecificVisionTransport(
    ExternalVisionTransport
):
    """
    M87-compatible provider-specific vision transport adapter.

    This class performs orchestration only. It does not open sockets, resolve
    credentials, or perform HTTP itself.
    """

    def __init__(
        self,
        profile,
        exchange,
        remote_image_source=None,
    ):
        try:
            validate_provider_vision_profile(
                profile
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "provider_specific_vision_transport_invalid"
            ) from None

        if type(profile) is not ProviderVisionProfile:
            raise ValueError(
                "provider_specific_vision_transport_invalid"
            )

        if not isinstance(
            exchange,
            ProviderVisionHTTPExchange,
        ):
            raise ValueError(
                "provider_specific_vision_transport_invalid"
            )

        if (
            profile.provider
            is VisionProviderKind.KIE_AI
        ):
            if not isinstance(
                remote_image_source,
                ProviderVisionRemoteImageSource,
            ):
                raise ValueError(
                    "provider_specific_vision_transport_invalid"
                )

        elif remote_image_source is not None:
            raise ValueError(
                "provider_specific_vision_transport_invalid"
            )

        self._profile = profile
        self._exchange = exchange
        self._remote_image_source = (
            remote_image_source
        )

    def send(
        self,
        request,
        check,
    ):
        _validate_request_for_execution(
            request
        )

        check()

        remote_image_url = None

        if self._remote_image_source is not None:
            remote_image_url = (
                _resolve_remote_image(
                    self._remote_image_source,
                    request,
                    check,
                )
            )

        check()

        try:
            body = _serialize_provider_request(
                request,
                self._profile,
                check,
                remote_image_url=(
                    remote_image_url
                ),
            )

        except _ProviderRequestSerializeFailure as exc:
            raise ExternalVisionTransportFailure(
                _map_request_serialize_failure(
                    exc.code
                )
            ) from None

        check()

        raw_response = _invoke_exchange(
            self._exchange,
            self._profile,
            body,
            check,
        )

        check()

        try:
            result = _extract_provider_response(
                raw_response,
                self._profile,
                check,
            )

        except _ProviderResponseExtractFailure as exc:
            raise ExternalVisionTransportFailure(
                _map_response_extract_failure(
                    exc.code
                )
            ) from None

        check()

        return result