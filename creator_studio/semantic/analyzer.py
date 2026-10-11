"""Provider-neutral candidate protocol and the only M64 analyzer."""
from typing import Protocol
from ..manifest.content import ContentRecord
from ..manifest.semantic import (SemanticBlock, AnalysisOptions, SourceExcerpt,
                                 BlockType, Derivation)
from .models import SemanticAnalysisResult, StoryUnitCandidate


class AnalysisControl(Protocol):
    def check(self) -> None: ...


class SemanticAnalyzer(Protocol):
    analyzer_id: str
    analyzer_version: str

    def analyze(self, source: ContentRecord, blocks: list[SemanticBlock],
                options: AnalysisOptions, control: AnalysisControl) -> SemanticAnalysisResult: ...


class OfflineStructuralAnalyzer:
    analyzer_id = "offline_structural"
    analyzer_version = "1"

    def analyze(self, source, blocks, options, control):
        units = []
        for block in blocks:
            control.check()
            if block.block_type not in {BlockType.HEADING, BlockType.FENCED_CODE, BlockType.TABLE}:
                units.append(StoryUnitCandidate([SourceExcerpt(block.source_span, block.source_text)],
                             [block.block_id], Derivation.STRUCTURAL_BASELINE))
        return SemanticAnalysisResult(units)
