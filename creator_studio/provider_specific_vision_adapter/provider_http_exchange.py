"""M89 concrete provider HTTP exchange backed by M88 HTTPS primitives.

This module is the concrete execution bridge between the provider-specific M89
transport orchestration and the bounded HTTPS machinery introduced in M88.

It intentionally:
- accepts already-serialized provider JSON bytes;
- validates one provider profile before execution;
- requires profile endpoint and M88 config endpoint coherence;
- resolves credentials only at runtime;
- requires the resolved credential header to match the provider profile;
- performs POST requests only;
- sends JSON only;
- follows no redirects through the M88 HTTPS opener;
- inherits no ambient proxy configuration through the M88 HTTPS opener;
- bounds both request and response sizes;
- returns the raw provider JSON as a normalized M87 transport response.

No source authority is accepted or created by this module.
"""

import socket
import urllib.error
import urllib.request

from ..external_vision_http_transport import (
    ExternalVisionHTTPConfig,
    ExternalVisionHTTPCredentialSource,
    validate_external_vision_http_config,
)
from ..external_vision_http_transport.credential_contract import (
    ExternalVisionHTTPCredentialFailure,
    _resolve_http_credential,
)
from ..external_vision_http_transport.http_transport import (
    _map_credential_failure,
    _map_http_status,
    _map_reader_failure,
    _open_https,
)
from ..external_vision_http_transport.response_reader import (
    ExternalVisionHTTPResponseEnvelope,
    _HTTPResponseReadFailure,
    _read_http_response,
)
from ..external_vision_provider_transport import (
    ExternalVisionTransportFailure,
    ExternalVisionTransportFailureCode,
)
from .models import (
    ProviderVisionProfile,
    validate_provider_vision_profile,
)
from .provider_transport import (
    ProviderVisionHTTPExchange,
)


class M88ProviderVisionHTTPExchange(
    ProviderVisionHTTPExchange
):
    """
    Concrete M89 provider exchange using the M88 bounded HTTPS boundary.

    Credentials are resolved for each send() call and are never persisted in
    the provider profile or serialized provider request body.
    """

    def __init__(
        self,
        config,
        credential_source,
    ):
        try:
            validate_external_vision_http_config(
                config
            )

        except MemoryError:
            raise

        except Exception:
            raise ValueError(
                "m88_provider_vision_http_exchange_invalid"
            ) from None

        if type(config) is not ExternalVisionHTTPConfig:
            raise ValueError(
                "m88_provider_vision_http_exchange_invalid"
            )

        if not isinstance(
            credential_source,
            ExternalVisionHTTPCredentialSource,
        ):
            raise ValueError(
                "m88_provider_vision_http_exchange_invalid"
            )

        self._config = config
        self._credential_source = (
            credential_source
        )

    def send(
        self,
        profile,
        body,
        check,
    ):
        try:
            validate_provider_vision_profile(
                profile
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

        if type(profile) is not ProviderVisionProfile:
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE
            )

        if (
            profile.endpoint
            != self._config.endpoint
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

        if (
            len(body)
            > self._config.max_request_bytes
        ):
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )

        check()

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

        if (
            credential.header
            is not profile.credential_header
        ):
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .INTERNAL_FAILURE
            )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            credential.header.value: (
                credential.value
            ),
        }

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

            response_headers = getattr(
                response,
                "headers",
                None,
            )

            if (
                response_headers is None
                or not hasattr(
                    response_headers,
                    "get",
                )
            ):
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .RESPONSE_INVALID
                )

            content_type = (
                response_headers.get(
                    "Content-Type",
                    "",
                )
            )

            if type(content_type) is not str:
                raise ExternalVisionTransportFailure(
                    ExternalVisionTransportFailureCode
                    .RESPONSE_INVALID
                )

            read_limit = (
                self._config.max_response_bytes
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
            > self._config.max_response_bytes
        ):
            raise ExternalVisionTransportFailure(
                ExternalVisionTransportFailureCode
                .RESOURCE_LIMIT_EXCEEDED
            )

        check()

        envelope = (
            ExternalVisionHTTPResponseEnvelope(
                status_code=status_code,
                content_type=content_type,
                body_length=len(
                    raw_body
                ),
                body=raw_body,
            )
        )

        try:
            result = _read_http_response(
                envelope,
                self._config,
                self._config.max_response_bytes,
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