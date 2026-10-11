"""Runtime candidates have no authoritative persisted IDs."""
from dataclasses import dataclass, field
from ..manifest.semantic import (SourceExcerpt, SemanticAnnotations, Derivation,
                                 ReviewMetadata)


@dataclass(frozen=True)
class StoryUnitCandidate:
    source_excerpts: list[SourceExcerpt]
    block_ids: list[str]
    derivation: Derivation = Derivation.ANALYZER
    annotations: SemanticAnnotations = field(default_factory=SemanticAnnotations)
    review: ReviewMetadata = field(default_factory=ReviewMetadata)


@dataclass(frozen=True)
class SemanticAnalysisResult:
    story_units: list[StoryUnitCandidate]
