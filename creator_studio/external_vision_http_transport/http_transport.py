"""M88 concrete bounded HTTPS JSON transport.

This module is the first M88 layer capable of outbound HTTPS execution.

It intentionally:
- accepts only previously validated HTTPS configuration;
- sends POST requests only;
- sends JSON only;
- keeps provider credentials outside configuration and payload models;
- supports only the explicit credential header contract;
- disables HTTP redirect following;
- disables inherited environment proxy configuration;
- reads at most one byte beyond the permitted response size;
- normalizes expected execution failures into the M87 transport contract.

Credentials are resolved only at runtime through the M88 credential boundary.
"""

import socket
import urllib.error
import urllib.request

from ..external_vision_provider_transport import (
    ExternalVisionTransport,
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
)
from .config import (
    ExternalVisionHTTPConfig,
    validate_external_vision_http_config,
)
from .credential_contract import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialSource,
    _resolve_http_credential,
)
from .response_reader import (
    ExternalVisionHTTPResponseEnvelope,
    _HTTPResponseReadFailure,
    _HTTPResponseReadFailureCode,
    _read_http_response,
)
from .serializer import (
    _HTTPRequestSerializeFailure,
    _HTTPRequestSerializeFailureCode,
    _serialize_http_request,
)


class _NoRedirectHandler(
    urllib.request.HTTPRedirectHandler
):
    """Reject every HTTP redirect."""

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        return None


def _build_https_opener():
    """
    Build one direct HTTP(S) opener.

    ProxyHandler({}) intentionally prevents ambient environment proxy
    configuration from silently changing the transport path.

    Redirect handling is explicitly disabled.
    """
    return urllib.request.build_opener(
        urllib.request.ProxyHandler(
            {}
        ),
        _NoRedirectHandler(),
    )


def _open_https(
    request,
    timeout_seconds,
):
    """
    Execute one request through the bounded opener.

    Kept as a separate function so execution can be replaced by deterministic
    fakes in tests without performing real network access.
    """
    opener = _build_https_opener()

    return opener.open(
        request,
        timeout=timeout_seconds,
    )


def _map_http_status(
    status_code,
):
    """Map one HTTP status to the normalized M87 transport failure contract."""
    if type(status_code) is not int:
        return (
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        )

    if status_code in (
        408,
        504,
    ):
        return (
            ExternalVisionTransportFailureCode
            .DEADLINE_EXCEEDED
        )

    if status_code == 413:
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if status_code in (
        400,
        404,
        405,
        415,
        422,
    ):
        return (
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        )

    if status_code in (
        401,
        403,
        407,
        429,
        500,
        502,
        503,
    ):
        return (
            ExternalVisionTransportFailureCode
            .UNAVAILABLE
        )

    return (
        ExternalVisionTransportFailureCode
        .RESPONSE_INVALID
    )


def _map_serializer_failure(
    code,
):
    """Map the M88 serializer failure contract into the M87 contract."""
    if (
        code
        is _HTTPRequestSerializeFailureCode
        .REQUEST_INVALID
    ):
        return (
            ExternalVisionTransportFailureCode
            .REQUEST_INVALID
        )

    if (
        code
        is _HTTPRequestSerializeFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    return (
        ExternalVisionTransportFailureCode
        .INTERNAL_FAILURE
    )


def _map_reader_failure(
    code,
):
    """Map the M88 bounded response reader failure into the M87 contract."""
    if (
        code
        is _HTTPResponseReadFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if code in (
        _HTTPResponseReadFailureCode
        .ENVELOPE_INVALID,
        _HTTPResponseReadFailureCode
        .HTTP_STATUS_INVALID,
        _HTTPResponseReadFailureCode
        .CONTENT_TYPE_INVALID,
        _HTTPResponseReadFailureCode
        .RESPONSE_INVALID,
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESPONSE_INVALID
        )

    return (
        ExternalVisionTransportFailureCode
        .INTERNAL_FAILURE
    )


def _map_credential_failure(
    code,
):
    """Map runtime credential failures into the M87 transport contract."""
    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .UNAVAILABLE
    ):
        return (
            ExternalVisionTransportFailureCode
            .UNAVAILABLE
        )

    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .RESOURCE_LIMIT_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        )

    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .DEADLINE_EXCEEDED
    ):
        return (
            ExternalVisionTransportFailureCode
            .DEADLINE_EXCEEDED
        )

    return (
        ExternalVisionTransportFailureCode
        .INTERNAL_FAILURE
    )


class ExternalVisionHTTPSJSONTransport(
    ExternalVisionTransport
):
    """
    Concrete HTTPS implementation of the M87 transport.

    Provider credentials remain outside configuration and payload models.

    An optional runtime credential source is resolved only during send().
    The resolved credential is used solely to construct the HTTP request
    header and is never added to the serialized JSON payload.
    """

    def __init__(
        self,
        config,
        credential_source=None,
    ):
        try:
            validate_external_vision_http_config(
                config
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "external_vision_https_json_transport_invalid"
            ) from None

        if type(config) is not ExternalVisionHTTPConfig:
            raise ValueError(
                "external_vision_https_json_transport_invalid"
            )

        if (
            credential_source is not None
            and not isinstance(
                credential_source,
                ExternalVisionHTTPCredentialSource,
            )
        ):
            raise ValueError(
                "external_vision_https_json_transport_invalid"
            )

        self._config = config
        self._credential_source = (
            credential_source
        )

    def send(
        self,
        request,
        check,
    ):
        """
        Serialize and execute one bounded HTTPS JSON request.

        Source authority is not accepted by this layer. The request is already
        detached M87 transport data.

        Credentials, when configured, are resolved only for this execution.
        """
        try:
            body = _serialize_http_request(
                request,
                self._config,
                check,
            )

        except _HTTPRequestSerializeFailure as exc:
            raise ExternalVisionTransportFailure(
                _map_serializer_failure(
                    exc.code
                )
            ) from None

        check()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self._credential_source is not None:
            try:
                credential = (
                    _resolve_http_credential(
                        self._credential_source,
                        check,
                    )
                )

            except ExternalVisionHTTPCredentialFailure as exc:
                raise ExternalVisionTransportFailure(
                    _map_credential_failure(
                        exc.code
                    )
                ) from None

            check()

            headers[
                credential.header.value
            ] = credential.value

        check()

        try:
            http_request = urllib.request.Request(
                url=self._config.endpoint,
                data=body,
                headers=headers,
                method="POST",
            )

            timeout_seconds = (
                self._config.timeout_millis
                / 1000.0
            )

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

        response = None

        try:
            response = _open_https(
                http_request,
                timeout_seconds,
            )

            check()

            status_code = response.getcode()

            if type(status_code) is not int:
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .RESPONSE_INVALID
                )

            if status_code != 200:
                raise ExternalVisionTransportFailure(
                    _map_http_status(
                        status_code
                    )
                )

            headers_object = getattr(
                response,
                "headers",
                None,
            )

            if (
                headers_object is None
                or not hasattr(
                    headers_object,
                    "get",
                )
            ):
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .RESPONSE_INVALID
                )

            content_type = headers_object.get(
                "Content-Type",
                "",
            )

            if type(content_type) is not str:
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .RESPONSE_INVALID
                )

            read_limit = (
                request.max_response_bytes
                + 1
            )

            raw_body = response.read(
                read_limit
            )

            check()

        except ExternalVisionTransportFailure:
            raise

        except urllib.error.HTTPError as exc:
            raise ExternalVisionTransportFailure(
                _map_http_status(
                    exc.code
                )
            ) from None

        except urllib.error.URLError as exc:
            if isinstance(
                exc.reason,
                (
                    socket.timeout,
                    TimeoutError,
                ),
            ):
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .DEADLINE_EXCEEDED
                ) from None

            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .UNAVAILABLE
            ) from None

        except (
            socket.timeout,
            TimeoutError,
        ):
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .DEADLINE_EXCEEDED
            ) from None

        except MemoryError:
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            ) from None

        except OSError:
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .UNAVAILABLE
            ) from None

        except Exception:
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE
            ) from None

        finally:
            if response is not None:
                try:
                    response.close()

                except Exception:
                    pass

        if type(raw_body) is not bytes:
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .RESPONSE_INVALID
            )

        if (
            len(raw_body)
            > request.max_response_bytes
            or len(raw_body)
            > self._config.max_response_bytes
        ):
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )

        check()

        envelope = ExternalVisionHTTPResponseEnvelope(
            status_code=status_code,
            content_type=content_type,
            body_length=len(
                raw_body
            ),
            body=raw_body,
        )

        try:
            result = _read_http_response(
                envelope,
                self._config,
                request.max_response_bytes,
                check,
            )

        except _HTTPResponseReadFailure as exc:
            raise ExternalVisionTransportFailure(
                _map_reader_failure(
                    exc.code
                )
            ) from None

        check()

        return result