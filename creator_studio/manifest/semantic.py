"""Revision-bound persisted contracts; no semantic runtime dependencies."""
from dataclasses import dataclass, field
from enum import Enum
import json
from .content import ContentRecord
from .codec import to_data
from .signatures import signature

CONTRACT_VERSION = "1"


class Purpose(str, Enum):
    CREATOR_STORY = "CREATOR_STORY"
    REFERENCE_ANALYSIS = "REFERENCE_ANALYSIS"


class BlockType(str, Enum):
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    LIST_ITEM = "LIST_ITEM"
    BLOCKQUOTE = "BLOCKQUOTE"
    FENCED_CODE = "FENCED_CODE"
    TABLE = "TABLE"
    DIALOGUE_LIKE = "DIALOGUE_LIKE"
    OTHER = "OTHER"


class Derivation(str, Enum):
    STRUCTURAL_BASELINE = "STRUCTURAL_BASELINE"
    ANALYZER = "ANALYZER"


class AnnotationOrigin(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    AI = "AI"
    CREATOR = "CREATOR"
    IMPORTED = "IMPORTED"
    UNKNOWN = "UNKNOWN"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class NarrativeRole(str, Enum):
    UNKNOWN = "UNKNOWN"
    HOOK = "HOOK"
    SETUP = "SETUP"
    CONTEXT = "CONTEXT"
    EVENT = "EVENT"
    ACTION = "ACTION"
    EXPLANATION = "EXPLANATION"
    CONFLICT = "CONFLICT"
    TURNING_POINT = "TURNING_POINT"
    REFLECTION = "REFLECTION"
    RESOLUTION = "RESOLUTION"
    CTA = "CTA"
    TRANSITION = "TRANSITION"
    OTHER = "OTHER"


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    PLACE = "PLACE"
    OBJECT = "OBJECT"
    EVENT = "EVENT"
    CONCEPT = "CONCEPT"
    UNKNOWN = "UNKNOWN"


class LocationOrigin(str, Enum):
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    UNKNOWN = "UNKNOWN"


class TemporalKind(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"
    UNSPECIFIED = "UNSPECIFIED"


class Visualizability(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int


@dataclass(frozen=True)
class SourceExcerpt:
    source_span: SourceSpan
    source_text: str


@dataclass(frozen=True)
class SemanticSourceRevision:
    source_revision_id: str
    content: ContentRecord
    source_signature: str


@dataclass(frozen=True)
class StructuralOptions:
    markdown: bool = False
    long_block_characters: int = 20000


@dataclass(frozen=True)
class AnalysisOptions:
    # Empty by design: baseline has no unused configuration.
    pass


@dataclass(frozen=True)
class AnalysisSpec:
    analyzer_id: str = "offline_structural"
    analyzer_version: str = "1"
    engine_version: str = "1"
    annotation_contract_version: str = CONTRACT_VERSION
    segmenter_version: str = "1"
    structural_options: StructuralOptions = field(default_factory=StructuralOptions)
    analysis_options: AnalysisOptions = field(default_factory=AnalysisOptions)


@dataclass(frozen=True)
class ReviewMetadata:
    status: ReviewStatus = ReviewStatus.PENDING
    locked: bool = False


@dataclass(frozen=True)
class AnnotationMetadata:
    origin: AnnotationOrigin = AnnotationOrigin.UNKNOWN
    confidence: float | None = None


@dataclass(frozen=True)
class Mention:
    source_span: SourceSpan
    text: str
    metadata: AnnotationMetadata = field(default_factory=AnnotationMetadata)
    entity_type: EntityType | None = None
    location_origin: LocationOrigin | None = None
    temporal_kind: TemporalKind | None = None


@dataclass(frozen=True)
class SemanticAnnotations:
    narrative_role: NarrativeRole | None = None
    mentions: list[Mention] = field(default_factory=list)
    visualizability: Visualizability = Visualizability.UNKNOWN
    metadata: AnnotationMetadata = field(default_factory=AnnotationMetadata)


@dataclass(frozen=True)
class SemanticBlock:
    block_id: str
    ordinal: int
    source_span: SourceSpan
    source_text: str
    block_type: BlockType
    heading_level: int | None
    section_heading_id: str | None
    content_signature: str


@dataclass(frozen=True)
class StoryUnit:
    story_unit_id: str
    ordinal: int
    source_excerpts: list[SourceExcerpt]
    block_ids: list[str]
    derivation: Derivation
    annotations: SemanticAnnotations = field(default_factory=SemanticAnnotations)
    review: ReviewMetadata = field(default_factory=ReviewMetadata)


@dataclass(frozen=True)
class SemanticDiagnostic:
    code: str


@dataclass(frozen=True)
class SemanticDocument:
    semantic_document_id: str
    source_revision_id: str
    content_id: str
    content_revision_signature: str
    purpose: Purpose
    source_language: str
    analysis_spec: AnalysisSpec
    structure_signature: str
    analysis_signature: str
    blocks: list[SemanticBlock]
    story_units: list[StoryUnit]
    diagnostics: list[SemanticDiagnostic]
    review_status: ReviewStatus
    output_signature: str


@dataclass
class SemanticState:
    source_revisions: list[SemanticSourceRevision] = field(default_factory=list)
    documents: list[SemanticDocument] = field(default_factory=list)
    active_creator_document_id: str | None = None


def exact_signature(value):
    """M63-safe ASCII serialization before the existing M61 signature utility."""
    return signature(json.dumps(to_data(value), ensure_ascii=True, sort_keys=True,
                                separators=(",", ":"), allow_nan=False))


def source_revision_id(record):
    return "semantic_source:" + exact_signature([record.content_id, record.revision_signature, CONTRACT_VERSION])


def structure_signature(source, spec):
    return exact_signature([source.source_revision_id, exact_signature(source.content.normalized_text),
                            source.content.normalization_version, spec.segmenter_version,
                            spec.structural_options])


def analysis_signature(structure, spec, purpose):
    return exact_signature([structure, spec, purpose])


def block_id(structure, span, kind):
    return "semantic_block:" + exact_signature([structure, span, kind])


def story_unit_id(analysis, excerpts, derivation):
    return "story_unit:" + exact_signature([analysis, [e.source_span for e in excerpts], derivation])


def generated_payload(document):
    data = to_data(document)
    for key in ("semantic_document_id", "output_signature", "review_status"):
        data.pop(key)
    for unit in data["story_units"]:
        unit.pop("review")
    return data


def document_id(document):
    return "semantic_document:" + exact_signature([document.analysis_signature, generated_payload(document)])


def output_signature(document):
    data = to_data(document)
    data.pop("output_signature")
    # Reviews are preserved and included: a reviewed output invalidates stage reuse.
    return exact_signature(data)
