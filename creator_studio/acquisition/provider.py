"""Separate acquisition protocol; resolution handles remain runtime-only."""
from dataclasses import dataclass, field
from typing import Protocol
from ..manifest.acquisition import AcquisitionProviderSpec, RenditionObservation


@dataclass(frozen=True)
class AcquisitionRequest:
    retrieval_id: str
    candidate_id: str
    metadata_fingerprint: str
    provider_id: str
    catalog_namespace: str
    provider_candidate_ref: str


@dataclass(frozen=True, repr=False)
class ResolvedRendition:
    observation: RenditionObservation
    handle: object = field(repr=False)

    def __repr__(self):
        return "<ResolvedRendition>"


class AcquisitionProvider(Protocol):
    spec: AcquisitionProviderSpec

    def resolve(self, request: AcquisitionRequest, control) -> list[ResolvedRendition]: ...
    def acquire(self, handle: object, sink, control) -> None: ...


def choose_rendition(resolved, kind):
    from ..manifest.acquisition_validation import rendition_valid
    from .models import AcquisitionError
    if (type(resolved) is not list or not 0 < len(resolved) <= 32
            or any(type(r) is not ResolvedRendition or not rendition_valid(r.observation)
                   or r.observation.media_kind != kind for r in resolved)
            or len({r.observation.rendition_id for r in resolved}) != len(resolved)):
        raise AcquisitionError("acquisition_validation_failed")
    return sorted(resolved, key=lambda r: (-r.observation.width * r.observation.height,
        -r.observation.width, -r.observation.height, r.observation.rendition_id))[0]
