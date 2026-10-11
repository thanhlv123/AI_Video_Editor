"""Authoritative validation, deterministic identities, and atomic copied proposals."""
from copy import deepcopy
from dataclasses import replace
from ..manifest.codec import check_typed
from ..manifest.content import canonical_eligible, SourceType
from ..manifest.validation import require_valid, ManifestValidationError
from ..manifest.semantic import (AnalysisSpec, StructuralOptions, Purpose,
    SemanticSourceRevision, SemanticDocument, StoryUnit, ReviewStatus,
    source_revision_id, exact_signature, structure_signature, analysis_signature,
    story_unit_id, document_id, output_signature)
from ..orchestrator.contracts import CancellationToken, Cancelled
from .analyzer import OfflineStructuralAnalyzer
from .models import SemanticAnalysisResult
from .segmentation import segment, SEGMENTER_VERSION
from .spans import SemanticError, require_slice

ENGINE_VERSION = "1"


def canonical_source(manifest):
    r = next((r for r in manifest.content.records if r.content_id == manifest.content.canonical_content_id), None)
    if r is None:
        raise SemanticError("semantic_content_missing")
    if not canonical_eligible(r):
        raise SemanticError("semantic_content_ineligible")
    try:
        require_valid(manifest)
    except ManifestValidationError:
        raise SemanticError("semantic_output_invalid") from None
    return r


def effective_spec(source, analyzer=None, structural_options=None):
    analyzer = analyzer or OfflineStructuralAnalyzer()
    return AnalysisSpec(analyzer_id=analyzer.analyzer_id, analyzer_version=analyzer.analyzer_version,
                        engine_version=ENGINE_VERSION, segmenter_version=SEGMENTER_VERSION,
                        structural_options=deepcopy(structural_options) if structural_options is not None
                        else StructuralOptions(markdown=source.source_type == SourceType.MARKDOWN))


def has_protected_review(document):
    """Explicit document/unit acceptance or unit locking protects active output.

    Unit ReviewMetadata is the only lock in the current annotation/unit contract.
    Unlocked PENDING and REJECTED states do not express protected acceptance.
    """
    return (document.review_status == ReviewStatus.APPROVED
            or any(u.review.status == ReviewStatus.APPROVED or u.review.locked
                   for u in document.story_units))


def build_semantic_story(manifest, *, analyzer=None, structural_options=None, control=None):
    control = control or CancellationToken()
    analyzer = analyzer or OfflineStructuralAnalyzer()
    control.check()
    # Entire operation uses an isolated input, including analyzer arguments.
    candidate = deepcopy(manifest)
    source = canonical_source(candidate)
    spec = effective_spec(source, analyzer, structural_options)
    try:
        check_typed(AnalysisSpec, spec)
        key = source_revision_id(source)
        archived = next((s for s in candidate.semantic.source_revisions if s.source_revision_id == key), None)
        if archived is None:
            archived = SemanticSourceRevision(key, deepcopy(source), exact_signature(source))
            candidate.semantic.source_revisions.append(archived)
        # Same M63 revision may preserve different original technical formatting;
        # retained evidence remains the first exact originating record.
        structure = structure_signature(archived, spec)
        analysis = analysis_signature(structure, spec, Purpose.CREATOR_STORY)
        blocks, diagnostics = segment(archived.content.normalized_text, structure, spec.structural_options, control)
        try:
            result = analyzer.analyze(deepcopy(archived.content), deepcopy(blocks),
                                      deepcopy(spec.analysis_options), control)
        except Cancelled:
            raise
        except Exception:
            raise SemanticError("semantic_analysis_failed") from None
        control.check()
        check_typed(SemanticAnalysisResult, result)
        units = []
        for i, u in enumerate(result.story_units):
            control.check()
            for e in u.source_excerpts:
                require_slice(archived.content.normalized_text, e.source_span, e.source_text)
            units.append(StoryUnit(story_unit_id(analysis, u.source_excerpts, u.derivation), i,
                         deepcopy(u.source_excerpts), deepcopy(u.block_ids), u.derivation,
                         deepcopy(u.annotations), deepcopy(u.review)))
        d = SemanticDocument("", key, source.content_id, source.revision_signature,
            Purpose.CREATOR_STORY, source.language or "und", spec, structure, analysis,
            blocks, units, diagnostics, ReviewStatus.PENDING, "")
        d = replace(d, semantic_document_id=document_id(d))
        d = replace(d, output_signature=output_signature(d))
        active = next((old for old in candidate.semantic.documents
                       if old.semantic_document_id == candidate.semantic.active_creator_document_id), None)
        if (active is not None and active.semantic_document_id != d.semantic_document_id
                and has_protected_review(active)):
            raise SemanticError("semantic_review_required")
        existing = next((old for old in candidate.semantic.documents if old.semantic_document_id == d.semantic_document_id), None)
        if existing is None:
            candidate.semantic.documents.append(d)
        # Deterministic regeneration must preserve existing human review metadata.
        candidate.semantic.active_creator_document_id = d.semantic_document_id
        require_valid(candidate)
        control.check()
        return candidate
    except (Cancelled, SemanticError):
        raise
    except Exception:
        raise SemanticError("semantic_output_invalid") from None
