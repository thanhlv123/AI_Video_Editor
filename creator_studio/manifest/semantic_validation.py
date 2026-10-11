"""Pure persistent validation and derived selection eligibility."""
import math
import re
import unicodedata
from .codec import check_typed
from .content import canonical_eligible, revision_signature, SourceType, ContentProvenance
from .semantic import (SemanticState, SourceSpan, Purpose, BlockType, Derivation,
                       SemanticAnnotations, AnalysisSpec, StructuralOptions, exact_signature, source_revision_id,
                       structure_signature, analysis_signature, block_id,
                       story_unit_id, document_id, output_signature)

DIAGNOSTIC_CODES = frozenset("""semantic_content_missing semantic_content_ineligible
semantic_revision_mismatch semantic_span_invalid semantic_source_text_mismatch
semantic_empty_block semantic_duplicate_id semantic_reference_invalid
semantic_signature_mismatch semantic_analysis_failed semantic_output_invalid
semantic_stale semantic_limit_exceeded semantic_long_block semantic_unclosed_fence
semantic_review_required""".split())


def valid_span(span, text):
    return (type(span) is SourceSpan and type(span.start) is int and type(span.end) is int
            and 0 <= span.start < span.end <= len(text))


def semantic_errors(state):
    errors = []
    def fail(code):
        errors.append(code)
    try:
        check_typed(SemanticState, state)
    except (ValueError, TypeError, AttributeError):
        return ["semantic_output_invalid"]
    sources, documents = {}, {}
    def unique(key, collection):
        if key in collection:
            fail("semantic_duplicate_id")
        collection[key] = True
    for source in state.source_revisions:
        unique(source.source_revision_id, sources)
        sources[source.source_revision_id] = source
        r = source.content
        original = r.original_text.removeprefix("\ufeff")
        normalized = unicodedata.normalize("NFC", original.replace("\r\n", "\n").replace("\r", "\n")).rstrip("\n")
        if (r.normalization_version != "1" or not r.normalized_text.strip()
                or not re.fullmatch(r"[A-Za-z0-9_.:-]+", r.content_id)
                or (r.language is not None and not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", r.language))
                or any(x.code != "reference_content_not_canonical" for x in r.diagnostics)
                or normalized != r.normalized_text
                or any((unicodedata.category(c) == "Cc" and c not in "\t\r\n")
                       or unicodedata.category(c) == "Cs" for c in original)
                or (r.source_type == SourceType.REFERENCE_TEXT and r.provenance != ContentProvenance.REFERENCE_ONLY)
                or r.revision_signature != revision_signature(r)
                or source.source_revision_id != source_revision_id(r)
                or source.source_signature != exact_signature(r)):
            fail("semantic_signature_mismatch")
    for d in state.documents:
        unique(d.semantic_document_id, documents)
        documents[d.semantic_document_id] = d
        source = sources.get(d.source_revision_id)
        if source is None:
            fail("semantic_reference_invalid")
            continue
        r = source.content
        text = r.normalized_text
        if ((d.content_id, d.content_revision_signature, d.source_language) !=
                (r.content_id, r.revision_signature, r.language or "und")):
            fail("semantic_revision_mismatch")
        if d.purpose == Purpose.CREATOR_STORY and not canonical_eligible(r):
            fail("semantic_content_ineligible")
        spec = d.analysis_spec
        if (not all((spec.analyzer_id, spec.analyzer_version, spec.engine_version,
                     spec.annotation_contract_version, spec.segmenter_version))
                or spec.structural_options.long_block_characters < 1):
            fail("semantic_output_invalid")
        if (d.structure_signature != structure_signature(source, spec)
                or d.analysis_signature != analysis_signature(d.structure_signature, spec, d.purpose)):
            fail("semantic_signature_mismatch")
        blocks = {}
        previous_end = 0
        def slice_valid(span, value):
            if not valid_span(span, text):
                fail("semantic_span_invalid")
                return False
            if text[span.start:span.end] != value:
                fail("semantic_source_text_mismatch")
            return True
        for i, b in enumerate(d.blocks):
            unique(b.block_id, blocks)
            # Resolve headings only against earlier entries.
            heading = blocks.get(b.section_heading_id)
            if b.section_heading_id is not None and (not hasattr(heading, "block_type") or heading.block_type != BlockType.HEADING):
                fail("semantic_reference_invalid")
            blocks[b.block_id] = b
            if b.ordinal != i:
                fail("semantic_output_invalid")
            if slice_valid(b.source_span, b.source_text):
                if b.source_span.start < previous_end or text[previous_end:b.source_span.start].strip():
                    fail("semantic_span_invalid")
                previous_end = b.source_span.end
            if not b.source_text.strip():
                fail("semantic_empty_block")
            if (b.block_type == BlockType.HEADING and (b.heading_level is None or not 1 <= b.heading_level <= 6)) or (b.block_type != BlockType.HEADING and b.heading_level is not None):
                fail("semantic_output_invalid")
            if (b.block_id != block_id(d.structure_signature, b.source_span, b.block_type)
                    or b.content_signature != exact_signature(b.source_text)):
                fail("semantic_signature_mismatch")
        if text[previous_end:].strip():
            fail("semantic_span_invalid")
        units = {}
        for i, u in enumerate(d.story_units):
            unique(u.story_unit_id, units)
            if u.ordinal != i or not u.source_excerpts or not u.block_ids or len(set(u.block_ids)) != len(u.block_ids):
                fail("semantic_output_invalid")
            referenced = [blocks.get(key) for key in u.block_ids]
            if any(b is None for b in referenced):
                fail("semantic_reference_invalid")
            elif [b.ordinal for b in referenced] != sorted(b.ordinal for b in referenced):
                fail("semantic_reference_invalid")
            end = -1
            for e in u.source_excerpts:
                if slice_valid(e.source_span, e.source_text):
                    if e.source_span.start < end:
                        fail("semantic_span_invalid")
                    end = e.source_span.end
                    # Evidence must be represented by the referenced blocks; separators may be whitespace.
                    cursor = e.source_span.start
                    for b in referenced:
                        if b is None or b.source_span.end <= cursor or b.source_span.start >= end:
                            continue
                        if text[cursor:min(b.source_span.start, end)].strip():
                            fail("semantic_reference_invalid")
                        cursor = min(end, b.source_span.end)
                    if text[cursor:end].strip():
                        fail("semantic_reference_invalid")
            a = u.annotations
            for metadata in [a.metadata, *(m.metadata for m in a.mentions)]:
                c = metadata.confidence
                if c is not None and (type(c) is not float or not math.isfinite(c) or not 0 <= c <= 1):
                    fail("semantic_output_invalid")
            for m in a.mentions:
                if slice_valid(m.source_span, m.text) and not any(e.source_span.start <= m.source_span.start < m.source_span.end <= e.source_span.end for e in u.source_excerpts):
                    fail("semantic_reference_invalid")
            if u.derivation == Derivation.STRUCTURAL_BASELINE:
                if (a != SemanticAnnotations() or len(u.source_excerpts) != 1 or len(referenced) != 1
                        or referenced[0] is None
                        or referenced[0].block_type in {BlockType.HEADING, BlockType.TABLE, BlockType.FENCED_CODE}
                        or u.source_excerpts[0].source_span != referenced[0].source_span):
                    fail("semantic_output_invalid")
            if u.story_unit_id != story_unit_id(d.analysis_signature, u.source_excerpts, u.derivation):
                fail("semantic_signature_mismatch")
        if any(x.code not in DIAGNOSTIC_CODES for x in d.diagnostics):
            fail("semantic_output_invalid")
        if d.semantic_document_id != document_id(d) or d.output_signature != output_signature(d):
            fail("semantic_signature_mismatch")
    selected = state.active_creator_document_id
    if selected is not None and (selected not in documents or documents[selected].purpose != Purpose.CREATOR_STORY):
        fail("semantic_reference_invalid")
    return errors


def eligible_active_document(manifest, required_spec=None):
    """Never changes selection or revives historical output."""
    if semantic_errors(manifest.semantic):
        return None
    d = next((d for d in manifest.semantic.documents if d.semantic_document_id == manifest.semantic.active_creator_document_id), None)
    r = next((r for r in manifest.content.records if r.content_id == manifest.content.canonical_content_id), None)
    if required_spec is None and r is not None:
        required_spec = AnalysisSpec(structural_options=StructuralOptions(markdown=r.source_type == SourceType.MARKDOWN))
    if (d is None or r is None or not canonical_eligible(r) or d.purpose != Purpose.CREATOR_STORY
            or (d.content_id, d.content_revision_signature) != (r.content_id, r.revision_signature)
            or r.revision_signature != revision_signature(r)
            or manifest.content.script != r.normalized_text
            or manifest.content.source_language != (r.language or "und")
            or (required_spec is not None and d.analysis_spec != required_spec)):
        return None
    source = next(s for s in manifest.semantic.source_revisions if s.source_revision_id == d.source_revision_id)
    if source.content.normalized_text != r.normalized_text:
        return None
    return d
