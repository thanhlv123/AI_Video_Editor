"""One configurable M62 stage; reuse proves exact persistent baseline output."""
from copy import deepcopy
from ..manifest.codec import check_typed
from ..manifest.semantic import AnalysisSpec
from ..manifest.semantic import exact_signature
from ..manifest.semantic_validation import eligible_active_document
from ..orchestrator.contracts import (Artifact, Diagnostic, ManifestUpdate, Readiness,
    ReadinessKind, StageOutcome, StageResult, StageStatus, Cancelled)
from .analyzer import OfflineStructuralAnalyzer
from .engine import canonical_source, effective_spec, build_semantic_story
from .spans import SemanticError


class SemanticStoryStage:
    stage_id = "semantic_story"
    stage_version = "1"

    def __init__(self, *, dependencies=(), analyzer=None, structural_options=None):
        self.dependencies = tuple(dependencies)
        self.analyzer = analyzer or OfflineStructuralAnalyzer()
        self.structural_options = deepcopy(structural_options)

    def signature_inputs(self, manifest):
        try:
            source = canonical_source(manifest)
        except SemanticError as exc:
            return {"unavailable": exc.code}
        spec = effective_spec(source, self.analyzer, self.structural_options)
        return {"content_id": source.content_id, "revision": source.revision_signature,
                "normalized_source": exact_signature(source.normalized_text),
                "normalization_version": source.normalization_version,
                "source_language": source.language or "und", "purpose": "CREATOR_STORY",
                "specification": spec}

    def _diagnostics(self, code):
        return [Diagnostic(code=code, stage_id=self.stage_id,
                           message="Semantic story requires attention.")]

    def readiness(self, manifest):
        try:
            source = canonical_source(manifest)
            spec = effective_spec(source, self.analyzer, self.structural_options)
            check_typed(AnalysisSpec, spec)
            if spec.structural_options.long_block_characters < 1:
                raise SemanticError()
            return Readiness()
        except SemanticError as exc:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics(exc.code)))
        except Exception:
            return Readiness(ReadinessKind.NOT_READY, tuple(self._diagnostics("semantic_output_invalid")))

    @staticmethod
    def artifact(document, source_revision_fingerprint):
        return Artifact("semantic/" + document.semantic_document_id,
                        exact_signature([document.semantic_document_id, document.output_signature,
                                         document.source_revision_id, document.analysis_signature,
                                         source_revision_fingerprint]))

    @classmethod
    def artifacts(cls, manifest, document):
        archived = next(s for s in manifest.semantic.source_revisions
                        if s.source_revision_id == document.source_revision_id)
        return [cls.artifact(document, archived.source_signature),
                Artifact("semantic_source/" + archived.source_revision_id, archived.source_signature)]

    def validate_reuse(self, manifest, previous):
        try:
            source = canonical_source(manifest)
            spec = effective_spec(source, self.analyzer, self.structural_options)
            d = eligible_active_document(manifest, spec)
            if d is None or previous.artifacts != self.artifacts(manifest, d):
                return False
            # Future analyzers have no offline recomputation guarantee; conservative no reuse.
            if type(self.analyzer) is not OfflineStructuralAnalyzer:
                return False
            fresh = deepcopy(manifest)
            fresh.semantic.documents = []
            fresh.semantic.active_creator_document_id = None
            expected = build_semantic_story(fresh, analyzer=self.analyzer, structural_options=self.structural_options)
            return expected.semantic.documents[0] == d
        except Exception:
            return False

    def execute(self, context):
        context.cancellation.check()
        try:
            proposed = build_semantic_story(context.manifest, analyzer=self.analyzer,
                structural_options=self.structural_options, control=context.cancellation)
            context.cancellation.check()
            d = eligible_active_document(proposed, effective_spec(canonical_source(proposed),
                                        self.analyzer, self.structural_options))
            if d is None:
                raise SemanticError()
        except Cancelled:
            raise
        except SemanticError as exc:
            return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.FAILED,
                                diagnostics=self._diagnostics(exc.code)))
        return StageOutcome(StageResult(self.stage_id, self.stage_version, StageStatus.SUCCEEDED,
                            artifacts=self.artifacts(proposed, d)), ManifestUpdate(proposed))
