"""Discovery protocol; no resolution, acquisition, or provider query syntax."""
from typing import Protocol
from ..manifest.retrieval import SourceClass, VisualMediaKind
from .models import ProviderCapabilities, ProviderRetrievalResult, RetrievalRequest


class MediaProvider(Protocol):
    provider_id: str
    provider_version: str
    capabilities: ProviderCapabilities
    catalog_namespace: str
    source_class: SourceClass
    request_limit: int

    def retrieve(self, request: RetrievalRequest, control) -> ProviderRetrievalResult: ...


class OfflineEmptyProvider:
    provider_id = "offline_empty"
    provider_version = "1"
    catalog_namespace = "empty"
    source_class = SourceClass.UNKNOWN
    request_limit = 32

    @property
    def capabilities(self):
        return ProviderCapabilities([VisualMediaKind.VIDEO, VisualMediaKind.IMAGE,
                                     VisualMediaKind.GRAPHIC], True)

    def retrieve(self, request, control):
        control.check()
        return ProviderRetrievalResult()
