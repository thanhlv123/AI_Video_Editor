"""Semantic vision provider interface contract.

This module defines an implementation-neutral boundary for future vision
providers. It performs no network access and grants no source authority.
"""

from abc import ABC, abstractmethod
from enum import Enum

from .adapter_contract import (
    SemanticVisionAdapterRequest,
    SemanticVisionAdapterResponse,
    validate_semantic_vision_adapter_request,
    validate_semantic_vision_adapter_response,
)


class SemanticVisionProviderFailureCode(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class SemanticVisionProviderFailure(Exception):
    """Normalized failure raised across the provider boundary."""

    def __init__(self, code):
        if type(code) is not SemanticVisionProviderFailureCode:
            raise ValueError(
                "semantic_vision_provider_failure_invalid"
            )

        self.code = code

        super().__init__(
            code.value
        )


class SemanticVisionProvider(ABC):
    """Implementation-neutral semantic vision provider boundary."""

    @abstractmethod
    def observe(self, request, check):
        """
        Produce one normalized SemanticVisionAdapterResponse.

        request is detached data only and grants no source authority.
        check is supplied by the controlling runtime for bounded execution.
        """
        raise NotImplementedError


def _invoke_provider(
    provider,
    request,
    check,
):
    """
    Invoke one provider through the normalized contract.

    This helper does not establish source authority. The controlling runtime
    must establish authority before constructing the adapter request.
    """
    if not isinstance(
        provider,
        SemanticVisionProvider,
    ):
        raise SemanticVisionProviderFailure(
            SemanticVisionProviderFailureCode.UNAVAILABLE
        )

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

    check()

    try:
        response = provider.observe(
            request,
            check,
        )

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

    check()

    try:
        validate_semantic_vision_adapter_response(
            response
        )

    except MemoryError:
        raise SemanticVisionProviderFailure(
            SemanticVisionProviderFailureCode
            .RESOURCE_LIMIT_EXCEEDED
        ) from None

    except Exception:
        raise SemanticVisionProviderFailure(
            SemanticVisionProviderFailureCode
            .RESPONSE_INVALID
        ) from None

    if type(response) is not SemanticVisionAdapterResponse:
        raise SemanticVisionProviderFailure(
            SemanticVisionProviderFailureCode
            .RESPONSE_INVALID
        )

    return response