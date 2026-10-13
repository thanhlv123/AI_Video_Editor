"""Transport-neutral M85 semantic vision provider bridge.

This bridge converts one already-authority-checked M85 adapter request into a
bounded M86 payload, invokes one M87 transport, strictly parses the response,
and returns one normalized M85 adapter response.

It performs no network access by itself and carries no provider credentials.
"""

from ..bounded_vision_provider_payload.builder import (
    _PayloadBuildFailure,
    _PayloadBuildFailureCode,
    _build_payload,
)
from ..semantic_vision_observer.adapter_contract import (
    SemanticVisionAdapterRequest,
    validate_semantic_vision_adapter_request,
)
from ..semantic_vision_observer.provider_contract import (
    SemanticVisionProvider,
    SemanticVisionProviderFailure,
    SemanticVisionProviderFailureCode,
)
from .request_builder import (
    _TransportRequestBuildFailure,
    _TransportRequestBuildFailureCode,
    _build_transport_request,
)
from .response_parser import (
    _TransportResponseParseFailure,
    _TransportResponseParseFailureCode,
    _parse_transport_response,
)
from .transport_contract import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
    _invoke_transport,
)


def _map_payload_failure(code):
    if (
        code
        is _PayloadBuildFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if code in (
        _PayloadBuildFailureCode.RASTER_INVALID,
        _PayloadBuildFailureCode.EVIDENCE_INVALID,
        _PayloadBuildFailureCode.COHERENCE_INVALID,
        _PayloadBuildFailureCode.PAYLOAD_INVALID,
    ):
        return (
            SemanticVisionProviderFailureCode
            .INTERNAL_FAILURE
        )

    return (
        SemanticVisionProviderFailureCode
        .INTERNAL_FAILURE
    )


def _map_request_failure(code):
    if (
        code
        is _TransportRequestBuildFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    return (
        SemanticVisionProviderFailureCode
        .INTERNAL_FAILURE
    )


def _map_transport_failure(code):
    if (
        code
        is ExternalVisionTransportFailureCode
        .UNAVAILABLE
    ):
        return (
            SemanticVisionProviderFailureCode
            .UNAVAILABLE
        )

    if (
        code
        is ExternalVisionTransportFailureCode
        .RESPONSE_INVALID
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESPONSE_INVALID
        )

    if (
        code
        is ExternalVisionTransportFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if (
        code
        is ExternalVisionTransportFailureCode
        .DEADLINE_EXCEEDED
    ):
        return (
            SemanticVisionProviderFailureCode
            .DEADLINE_EXCEEDED
        )

    return (
        SemanticVisionProviderFailureCode
        .INTERNAL_FAILURE
    )


def _map_parse_failure(code):
    if (
        code
        is _TransportResponseParseFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if code in (
        _TransportResponseParseFailureCode
        .TRANSPORT_RESPONSE_INVALID,
        _TransportResponseParseFailureCode
        .JSON_INVALID,
        _TransportResponseParseFailureCode
        .SEMANTIC_RESPONSE_INVALID,
    ):
        return (
            SemanticVisionProviderFailureCode
            .RESPONSE_INVALID
        )

    return (
        SemanticVisionProviderFailureCode
        .INTERNAL_FAILURE
    )


class ExternalVisionSemanticProvider(
    SemanticVisionProvider
):
    """
    M85 provider implementation backed by one M87 transport.

    The incoming SemanticVisionAdapterRequest is detached data that was
    constructed by the controlling M85 runtime after source authority checks.
    """

    def __init__(self, transport):
        self._transport = transport

    def observe(
        self,
        request,
        check,
    ):
        try:
            validate_semantic_vision_adapter_request(
                request
            )

        except MemoryError:
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except Exception:
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE
            ) from None

        if type(request) is not SemanticVisionAdapterRequest:
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE
            )

        if not isinstance(
            self._transport,
            ExternalVisionTransport,
        ):
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .UNAVAILABLE
            )

        try:
            check()

            payload = _build_payload(
                request.raster,
                request.evidence,
                check,
            )

            check()

            transport_request = (
                _build_transport_request(
                    payload,
                    check,
                )
            )

            check()

            transport_response = (
                _invoke_transport(
                    self._transport,
                    transport_request,
                    check,
                )
            )

            check()

            semantic_response = (
                _parse_transport_response(
                    transport_response,
                    check,
                )
            )

            check()

            return semantic_response

        except _PayloadBuildFailure as exc:
            raise SemanticVisionProviderFailure(
                _map_payload_failure(
                    exc.code
                )
            ) from None

        except _TransportRequestBuildFailure as exc:
            raise SemanticVisionProviderFailure(
                _map_request_failure(
                    exc.code
                )
            ) from None

        except ExternalVisionTransportFailure as exc:
            raise SemanticVisionProviderFailure(
                _map_transport_failure(
                    exc.code
                )
            ) from None

        except _TransportResponseParseFailure as exc:
            raise SemanticVisionProviderFailure(
                _map_parse_failure(
                    exc.code
                )
            ) from None

        except SemanticVisionProviderFailure:
            raise

        except MemoryError:
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except Exception:
            raise SemanticVisionProviderFailure(
                SemanticVisionProviderFailureCode
                .INTERNAL_FAILURE
            ) from None