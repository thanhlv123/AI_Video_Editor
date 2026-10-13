"""M92 provider connectivity probe execution.

This module performs a deliberately small authenticated provider connectivity
probe.

The probe:
- validates one M90 ProviderRuntimeConfig;
- resolves its runtime credential;
- performs one authenticated HTTPS GET against a provider diagnostic endpoint;
- sends no image;
- sends no semantic prompt;
- performs no model inference;
- bounds Kie.ai response reading;
- returns only a detached, secret-free diagnostic report.

The original ``probe`` path uses the M90 environment-backed credential source.
M100 host integration may explicitly supply a runtime credential-source factory
through ``probe_with_credential_source_factory``. The factory is not retained.

Probe endpoints:

OpenAI:
    GET https://api.openai.com/v1/models

Gemini:
    GET https://generativelanguage.googleapis.com/v1beta/models

Kie.ai:
    GET https://api.kie.ai/api/v1/chat/credit

Kie.ai common APIs may report application errors inside an HTTP 200 response,
so both HTTP status and provider application code are preserved separately.
"""

import json
import socket
import urllib.error
import urllib.request

from ..external_vision_http_transport import (
    ExternalVisionHTTPCredentialFailure,
    ExternalVisionHTTPCredentialFailureCode,
    ExternalVisionHTTPCredentialHeader,
)
from ..provider_runtime_assembly import (
    EnvironmentCredentialSource,
    ProviderRuntimeConfig,
    validate_provider_runtime_config,
)
from ..provider_specific_vision_adapter import (
    VisionProviderKind,
)
from .models import (
    PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION,
    ProviderConnectivityProbeReport,
    ProviderConnectivityProbeStatus,
    validate_provider_connectivity_probe_report,
)


OPENAI_CONNECTIVITY_PROBE_ENDPOINT = (
    "https://api.openai.com/v1/models"
)

GEMINI_CONNECTIVITY_PROBE_ENDPOINT = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models"
)

KIE_CONNECTIVITY_PROBE_ENDPOINT = (
    "https://api.kie.ai/api/v1/chat/credit"
)

MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS = (
    5000
)

MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES = (
    8192
)


class _NoRedirectHandler(
    urllib.request.HTTPRedirectHandler
):
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


def _open_https(
    request,
    timeout_seconds,
):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(
            {}
        ),
        _NoRedirectHandler(),
    )

    return opener.open(
        request,
        timeout=timeout_seconds,
    )


def _build_report(
    config,
    status,
    *,
    http_status=None,
    provider_code=None,
):
    try:
        if (
            status
            is ProviderConnectivityProbeStatus
            .CONFIG_INVALID
        ):
            provider = None
            environment_variable = None

        else:
            provider = config.profile.provider
            environment_variable = (
                config.credential_environment_variable
            )

        report = ProviderConnectivityProbeReport(
            schema_version=(
                PROVIDER_CONNECTIVITY_PROBE_SCHEMA_VERSION
            ),
            status=status,
            provider=provider,
            credential_environment_variable=(
                environment_variable
            ),
            http_status=http_status,
            provider_code=provider_code,
        )

        validate_provider_connectivity_probe_report(
            report
        )

    except MemoryError:
        raise

    except Exception:
        raise RuntimeError(
            "provider_connectivity_probe_internal"
        ) from None

    return report


def _config_invalid_report():
    return _build_report(
        None,
        (
            ProviderConnectivityProbeStatus
            .CONFIG_INVALID
        ),
    )


def _credential_failure_status(
    code,
):
    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .UNAVAILABLE
    ):
        return (
            ProviderConnectivityProbeStatus
            .CREDENTIAL_MISSING
        )

    if (
        code
        is ExternalVisionHTTPCredentialFailureCode
        .INVALID
    ):
        return (
            ProviderConnectivityProbeStatus
            .CREDENTIAL_INVALID
        )

    return (
        ProviderConnectivityProbeStatus
        .INTERNAL_FAILURE
    )


def _credential_header_name(
    header,
):
    if (
        header
        is ExternalVisionHTTPCredentialHeader
        .AUTHORIZATION
    ):
        return "Authorization"

    if (
        header
        is ExternalVisionHTTPCredentialHeader
        .X_GOOG_API_KEY
    ):
        return "X-Goog-Api-Key"

    raise ValueError()


def _probe_endpoint(
    provider,
):
    if (
        provider
        is VisionProviderKind.OPENAI
    ):
        return (
            OPENAI_CONNECTIVITY_PROBE_ENDPOINT
        )

    if (
        provider
        is VisionProviderKind.GEMINI
    ):
        return (
            GEMINI_CONNECTIVITY_PROBE_ENDPOINT
        )

    if (
        provider
        is VisionProviderKind.KIE_AI
    ):
        return (
            KIE_CONNECTIVITY_PROBE_ENDPOINT
        )

    raise ValueError()


def _timeout_seconds(
    config,
):
    timeout_millis = min(
        config.http_config.timeout_millis,
        MAX_PROVIDER_CONNECTIVITY_PROBE_TIMEOUT_MILLIS,
    )

    return (
        timeout_millis
        / 1000.0
    )


def _build_request(
    config,
    credential,
):
    endpoint = _probe_endpoint(
        config.profile.provider
    )

    header_name = (
        _credential_header_name(
            credential.header
        )
    )

    return urllib.request.Request(
        url=endpoint,
        data=None,
        headers={
            "Accept": "application/json",
            header_name: credential.value,
        },
        method="GET",
    )


def _close_response(
    response,
):
    if response is None:
        return

    try:
        response.close()

    except Exception:
        pass


def _response_status(
    response,
):
    status = getattr(
        response,
        "status",
        None,
    )

    if type(status) is int:
        if (
            100
            <= status
            <= 599
        ):
            return status

        raise ValueError()

    getcode = getattr(
        response,
        "getcode",
        None,
    )

    if not callable(
        getcode
    ):
        raise ValueError()

    status = getcode()

    if (
        type(status) is not int
        or status < 100
        or status > 599
    ):
        raise ValueError()

    return status


def _status_from_http(
    status,
):
    if status == 401:
        return (
            ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED
        )

    if status == 403:
        return (
            ProviderConnectivityProbeStatus
            .PERMISSION_DENIED
        )

    if status == 429:
        return (
            ProviderConnectivityProbeStatus
            .RATE_LIMITED
        )

    if (
        500
        <= status
        <= 599
    ):
        return (
            ProviderConnectivityProbeStatus
            .PROVIDER_UNAVAILABLE
        )

    if (
        200
        <= status
        <= 299
    ):
        return (
            ProviderConnectivityProbeStatus
            .READY
        )

    return (
        ProviderConnectivityProbeStatus
        .RESPONSE_INVALID
    )


def _reject_duplicate_pairs(
    pairs,
):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError()

        result[
            key
        ] = value

    return result


def _reject_nonfinite(
    value,
):
    raise ValueError()


def _read_kie_document(
    response,
    check,
):
    check()

    body = response.read(
        MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES
        + 1
    )

    check()

    if type(body) is not bytes:
        raise ValueError()

    if (
        not body
        or len(body)
        > MAX_PROVIDER_CONNECTIVITY_PROBE_RESPONSE_BYTES
    ):
        raise ValueError()

    text = body.decode(
        "utf-8"
    )

    document = json.loads(
        text,
        object_pairs_hook=(
            _reject_duplicate_pairs
        ),
        parse_constant=(
            _reject_nonfinite
        ),
    )

    if type(document) is not dict:
        raise ValueError()

    code = document.get(
        "code"
    )

    if (
        type(code) is not int
        or code < 100
        or code > 599
    ):
        raise ValueError()

    return code


def _status_from_provider_code(
    code,
):
    if code == 200:
        return (
            ProviderConnectivityProbeStatus
            .READY
        )

    if code == 401:
        return (
            ProviderConnectivityProbeStatus
            .AUTHENTICATION_FAILED
        )

    if code == 403:
        return (
            ProviderConnectivityProbeStatus
            .PERMISSION_DENIED
        )

    if code == 429:
        return (
            ProviderConnectivityProbeStatus
            .RATE_LIMITED
        )

    if (
        500
        <= code
        <= 599
    ):
        return (
            ProviderConnectivityProbeStatus
            .PROVIDER_UNAVAILABLE
        )

    return (
        ProviderConnectivityProbeStatus
        .RESPONSE_INVALID
    )


def _network_failure_report(
    config,
    status,
):
    return _build_report(
        config,
        status,
    )


class ProviderConnectivityProbe:
    """Stateless authenticated provider connectivity probe."""

    __slots__ = ()

    def probe(
        self,
        config,
        check,
    ):
        """
        Execute the original M92 connectivity probe.

        This preserves the existing M92 execution signature and uses the
        environment-backed M90 credential source.
        """
        return self._probe(
            config,
            check,
            EnvironmentCredentialSource,
        )

    def probe_with_credential_source_factory(
        self,
        config,
        check,
        credential_source_factory,
    ):
        """
        Execute connectivity using a caller-supplied runtime credential-source
        factory.

        The factory is runtime-only authority. It is never retained by this
        stateless probe and never enters the detached connectivity report.
        """
        return self._probe(
            config,
            check,
            credential_source_factory,
        )

    def _probe(
        self,
        config,
        check,
        credential_source_factory,
    ):
        check()

        try:
            validate_provider_runtime_config(
                config
            )

        except MemoryError:
            return _config_invalid_report()

        except Exception:
            return _config_invalid_report()

        if type(config) is not ProviderRuntimeConfig:
            return _config_invalid_report()

        check()

        try:
            credential_source = (
                credential_source_factory(
                    config.credential_environment_variable,
                    config.profile.credential_header,
                    config.credential_mode,
                )
            )

        except MemoryError:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        except Exception:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        check()

        try:
            credential = credential_source.resolve(
                check
            )

        except ExternalVisionHTTPCredentialFailure as exc:
            return _network_failure_report(
                config,
                _credential_failure_status(
                    exc.code
                ),
            )

        except MemoryError:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        except Exception:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        check()

        try:
            request = _build_request(
                config,
                credential,
            )

        except MemoryError:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        except Exception:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        check()

        response = None

        try:
            response = _open_https(
                request,
                _timeout_seconds(
                    config
                ),
            )

            check()

            http_status = _response_status(
                response
            )

            if (
                config.profile.provider
                is VisionProviderKind.KIE_AI
                and (
                    200
                    <= http_status
                    <= 299
                )
            ):
                try:
                    provider_code = (
                        _read_kie_document(
                            response,
                            check,
                        )
                    )

                except MemoryError:
                    return _network_failure_report(
                        config,
                        (
                            ProviderConnectivityProbeStatus
                            .INTERNAL_FAILURE
                        ),
                    )

                except Exception:
                    return _build_report(
                        config,
                        (
                            ProviderConnectivityProbeStatus
                            .RESPONSE_INVALID
                        ),
                        http_status=http_status,
                        provider_code=None,
                    )

                status = (
                    _status_from_provider_code(
                        provider_code
                    )
                )

                return _build_report(
                    config,
                    status,
                    http_status=http_status,
                    provider_code=provider_code,
                )

            status = _status_from_http(
                http_status
            )

            return _build_report(
                config,
                status,
                http_status=http_status,
                provider_code=None,
            )

        except urllib.error.HTTPError as exc:
            http_status = exc.code

            if (
                type(http_status) is not int
                or http_status < 100
                or http_status > 599
            ):
                return _network_failure_report(
                    config,
                    (
                        ProviderConnectivityProbeStatus
                        .INTERNAL_FAILURE
                    ),
                )

            return _build_report(
                config,
                _status_from_http(
                    http_status
                ),
                http_status=http_status,
                provider_code=None,
            )

        except urllib.error.URLError as exc:
            reason = exc.reason

            if isinstance(
                reason,
                (
                    socket.timeout,
                    TimeoutError,
                ),
            ):
                return _network_failure_report(
                    config,
                    (
                        ProviderConnectivityProbeStatus
                        .DEADLINE_EXCEEDED
                    ),
                )

            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .NETWORK_UNAVAILABLE
                ),
            )

        except (
            socket.timeout,
            TimeoutError,
        ):
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .DEADLINE_EXCEEDED
                ),
            )

        except MemoryError:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        except OSError:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .NETWORK_UNAVAILABLE
                ),
            )

        except Exception:
            return _network_failure_report(
                config,
                (
                    ProviderConnectivityProbeStatus
                    .INTERNAL_FAILURE
                ),
            )

        finally:
            _close_response(
                response
            )