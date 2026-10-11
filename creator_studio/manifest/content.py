"""Persisted, provider-neutral textual content contracts (additive V2 extension)."""
from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    DIRECT_TEXT = "DIRECT_TEXT"
    TEXT_FILE = "TEXT_FILE"
    MARKDOWN = "MARKDOWN"
    IMPORTED_TRANSCRIPT = "IMPORTED_TRANSCRIPT"
    REFERENCE_TEXT = "REFERENCE_TEXT"


class ContentProvenance(str, Enum):
    CREATOR_AUTHORED = "creator_authored"
    IMPORTED_OWNED = "imported_owned"
    LICENSED = "licensed"
    REFERENCE_ONLY = "reference_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IngestDiagnostic:
    code: str


@dataclass(frozen=True)
class ContentRecord:
    content_id: str
    source_type: SourceType
    original_text: str
    normalized_text: str
    revision_signature: str
    provenance: ContentProvenance
    language: str | None = None
    title: str | None = None
    source_locator: str | None = None
    normalization_version: str = "1"
    diagnostics: list[IngestDiagnostic] = field(default_factory=list)


def revision_signature(record: ContentRecord) -> str:
    """Entity ID, source path and original technical formatting do not define revision."""
    from .signatures import signature
    return signature({"text": record.normalized_text, "source_type": record.source_type,
                      "provenance": record.provenance, "language": record.language,
                      "title": record.title, "normalization": record.normalization_version})


def canonical_eligible(record: ContentRecord) -> bool:
    return (record.source_type != SourceType.REFERENCE_TEXT and record.provenance in {
        ContentProvenance.CREATOR_AUTHORED, ContentProvenance.IMPORTED_OWNED,
        ContentProvenance.LICENSED})
