"""Public ingest requests and structured results; no runtime/provider objects."""
from dataclasses import dataclass, field
from enum import Enum
from ..manifest.content import ContentRecord, ContentProvenance, SourceType, IngestDiagnostic


@dataclass(frozen=True)
class IngestLimits:
    max_bytes: int = 5 * 1024 * 1024
    max_characters: int = 2_000_000

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in (self.max_bytes, self.max_characters)):
            raise ValueError("Positive integer ingest limits required")


@dataclass(frozen=True)
class IngestRequest:
    content_id: str
    source_type: SourceType = SourceType.DIRECT_TEXT
    text: str | None = None
    source_locator: str | None = None
    provenance: ContentProvenance = ContentProvenance.CREATOR_AUTHORED
    language: str | None = None
    title: str | None = None


class IngestStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass(frozen=True)
class IngestResult:
    status: IngestStatus
    content: ContentRecord | None = None
    diagnostics: list[IngestDiagnostic] = field(default_factory=list)
    source_type: SourceType | None = None
    source_locator: str | None = None

    @property
    def signature(self) -> str | None:
        return self.content.revision_signature if self.content else None
