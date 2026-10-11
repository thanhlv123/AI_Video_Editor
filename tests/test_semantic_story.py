"""M64 tests are offline, with real M61/M62/M63 boundaries and fake candidates."""
from copy import deepcopy
from dataclasses import replace
import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.manifest import (ProjectManifest, validate, save, load,
    eligible_active_document)
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.migrations import migrate_document
from creator_studio.manifest.content import SourceType
from creator_studio.manifest.semantic import *
from creator_studio.manifest.semantic_validation import semantic_errors, valid_span
from creator_studio.content.ingest import ingest, apply_ingest
from creator_studio.content.models import IngestRequest
from creator_studio.semantic.engine import build_semantic_story
from creator_studio.semantic.stage import SemanticStoryStage
from creator_studio.semantic.analyzer import OfflineStructuralAnalyzer
from creator_studio.semantic.models import StoryUnitCandidate, SemanticAnalysisResult
from creator_studio.semantic.segmentation import segment
from creator_studio.semantic.spans import SemanticError, require_slice
from creator_studio.orchestrator import ProjectOrchestrator, ManifestRepository, StageStatus
from creator_studio.orchestrator.contracts import StageContext, CancellationToken, Cancelled


def content(text="First paragraph.\n\nSecond paragraph.", *, content_id="creator", markdown=False, manifest=None):
    return apply_ingest(manifest or ProjectManifest("M64"), ingest(IngestRequest(
        content_id, source_type=SourceType.MARKDOWN if markdown else SourceType.DIRECT_TEXT,
        text=text, language="en")))


def resign(d):
    d = replace(d, semantic_document_id=document_id(d), output_signature="")
    return replace(d, output_signature=output_signature(d))


class SemanticStoryTests(unittest.TestCase):
    def setUp(self):
        self.manifest = content()
        self.built = build_semantic_story(self.manifest)
        self.doc = self.built.semantic.documents[0]

    def test_stale_selection_preserves_history_and_never_reactivates(self):
        changed = content("Changed canonical.", manifest=self.built)
        self.assertFalse(validate(changed))
        self.assertIsNone(eligible_active_document(changed))
        self.assertEqual(changed.semantic, self.built.semantic)
        newer = build_semantic_story(changed)
        self.assertEqual(len(newer.semantic.documents), 2)
        back = content(manifest=newer)
        self.assertIsNone(eligible_active_document(back))
        self.assertEqual(back.semantic.active_creator_document_id, newer.semantic.active_creator_document_id)
        self.assertEqual(len(back.semantic.source_revisions), 2)

    def test_deterministic_document_and_ids(self):
        self.assertEqual(build_semantic_story(self.manifest).semantic, self.built.semantic)
        self.assertEqual(build_semantic_story(self.built).semantic, self.built.semantic)
        self.assertFalse(validate(self.built))
        self.assertEqual(self.doc.output_signature, output_signature(self.doc))

    def test_archive_dedup_and_exact_origin(self):
        original = content("First paragraph.\r\n\r\nSecond paragraph.\r\n")
        built = build_semantic_story(original)
        changed_format = content(manifest=built)
        again = build_semantic_story(changed_format)
        self.assertEqual(len(again.semantic.source_revisions), 1)
        self.assertEqual(again.semantic.source_revisions[0].content.original_text,
                         original.content.records[0].original_text)
        self.assertNotEqual(again.content.records[0].original_text,
                            again.semantic.source_revisions[0].content.original_text)

    def test_archive_tamper_and_missing_rejected(self):
        for mode in ("text", "original", "signature", "missing"):
            with self.subTest(mode=mode):
                m = deepcopy(self.built)
                s = m.semantic.source_revisions[0]
                if mode == "missing":
                    m.semantic.source_revisions.clear()
                elif mode == "signature":
                    m.semantic.source_revisions[0] = replace(s, source_signature="bad")
                else:
                    r = replace(s.content, **({"normalized_text": "Tampered"} if mode == "text" else {"original_text": "Tampered"}))
                    m.semantic.source_revisions[0] = replace(s, content=r)
                self.assertTrue(validate(m))
                self.assertIsNone(eligible_active_document(m))

    def test_reference_cannot_be_selected(self):
        m = deepcopy(self.built)
        d = resign(replace(self.doc, purpose=Purpose.REFERENCE_ANALYSIS,
                    analysis_signature=analysis_signature(self.doc.structure_signature,
                    self.doc.analysis_spec, Purpose.REFERENCE_ANALYSIS)))
        # Reassign analysis-dependent unit IDs for a valid reference document.
        units = [replace(u, story_unit_id=story_unit_id(d.analysis_signature, u.source_excerpts, u.derivation)) for u in d.story_units]
        d = resign(replace(d, story_units=units))
        m.semantic.documents = [d]
        m.semantic.active_creator_document_id = None
        self.assertFalse(validate(m))
        m.semantic.active_creator_document_id = d.semantic_document_id
        self.assertTrue(validate(m))
        self.assertIsNone(eligible_active_document(m))

    def test_strict_spans(self):
        for start, end in [(True, 2), (0, False), (0.0, 2), (0, 2.0), (0, 0), (-1, 2), (1, 4), (2, 1)]:
            with self.subTest(start=start, end=end):
                self.assertFalse(valid_span(SourceSpan(start, end), "abc"))
                with self.assertRaises(SemanticError):
                    require_slice("abc", SourceSpan(start, end), "a")
        require_slice("abc", SourceSpan(0, 3), "abc")
        with self.assertRaises(SemanticError):
            require_slice("abc", SourceSpan(0, 2), "ab ")

    def test_unicode_code_points_and_roundtrip(self):
        for text in ["Tiếng Việt", "Srpski latinica Српски ћирилица", "A😀𐐀B", "x\u0301 q", "👩\u200d💻 family 👨\u200d👩\u200d👧", "a\u2028b\u2029c"]:
            with self.subTest(text=text):
                m = build_semantic_story(content(text))
                source = m.content.script
                d = m.semantic.documents[0]
                self.assertEqual(len(d.blocks), 1)
                self.assertEqual(d.blocks[0].source_span, SourceSpan(0, len(source)))
                self.assertEqual(d.story_units[0].source_excerpts[0].source_text, source)
                self.assertEqual(decode(ProjectManifest, to_data(m)), m)

    def test_exact_unicode_fingerprint(self):
        self.assertNotEqual(exact_signature("é"), exact_signature("e\u0301"))

    def test_segmentation_precedence_coverage_and_headings(self):
        text = '# Heading\nprose\ncontinued\n\n- item\n  continuation\n+ next\n\n> quote\n> again\n\n```py\n# opaque\n- opaque\n```\n\nA | B\n--- | :---:\n1 | 2\n\n— "Hello"\nName: ordinary'
        m = build_semantic_story(content(text, markdown=True))
        d = m.semantic.documents[0]
        self.assertEqual([b.block_type for b in d.blocks], [BlockType.HEADING, BlockType.PARAGRAPH,
            BlockType.LIST_ITEM, BlockType.LIST_ITEM, BlockType.BLOCKQUOTE, BlockType.FENCED_CODE,
            BlockType.TABLE, BlockType.DIALOGUE_LIKE, BlockType.PARAGRAPH])
        self.assertEqual(d.blocks[2].source_text, "- item\n  continuation")
        self.assertEqual(d.blocks[5].source_text, "```py\n# opaque\n- opaque\n```")
        self.assertTrue(all(b.section_heading_id == d.blocks[0].block_id for b in d.blocks[1:]))
        self.assertEqual(len(d.story_units), 6)
        self.assertFalse(validate(m))

    def test_plain_text_no_markdown_overinterpretation(self):
        m = build_semantic_story(content("# heading\n- list\n> quote\n```\nopaque\n```"))
        self.assertEqual([b.block_type for b in m.semantic.documents[0].blocks], [BlockType.PARAGRAPH])

    def test_explicit_markdown_option(self):
        m = build_semantic_story(content("# Heading"), structural_options=StructuralOptions(True))
        self.assertEqual(m.semantic.documents[0].blocks[0].block_type, BlockType.HEADING)

    def test_conservative_constructs(self):
        cases = [("#No space", BlockType.PARAGRAPH), ("####### Nope", BlockType.PARAGRAPH),
                 ("Name: speech", BlockType.PARAGRAPH), ("A | B\n-- | ---", BlockType.PARAGRAPH),
                 ("1. item", BlockType.LIST_ITEM), ("* item", BlockType.LIST_ITEM)]
        for text, kind in cases:
            with self.subTest(text=text):
                d = build_semantic_story(content(text, markdown=True)).semantic.documents[0]
                self.assertEqual(d.blocks[0].block_type, kind)

    def test_unclosed_fence_consumes_remainder(self):
        m = build_semantic_story(content("~~~\n# opaque\n\nrest", markdown=True))
        d = m.semantic.documents[0]
        self.assertEqual(len(d.blocks), 1)
        self.assertEqual(d.blocks[0].source_text, m.content.script)
        self.assertEqual(d.diagnostics, [SemanticDiagnostic("semantic_unclosed_fence")])
        self.assertFalse(d.story_units)

    def test_long_scripts_never_truncated(self):
        for words in (500, 5000, 22000):
            with self.subTest(words=words):
                text = "word " * words
                m = build_semantic_story(content(text))
                d = m.semantic.documents[0]
                self.assertEqual(len(d.blocks), 1)
                self.assertEqual(d.blocks[0].source_text, text)
                self.assertEqual(d.story_units[0].source_excerpts[0].source_text, text)
                self.assertEqual(bool(d.diagnostics), len(text) > 20000)

    def test_many_blocks_linear_coverage(self):
        text = "\n\n".join("paragraph " + str(i) for i in range(3000))
        m = build_semantic_story(content(text))
        self.assertEqual(len(m.semantic.documents[0].blocks), 3000)
        self.assertFalse(validate(m))

    def test_baseline_no_inferred_facts_scenes_queries_or_timing(self):
        for u in self.doc.story_units:
            self.assertEqual(u.annotations, SemanticAnnotations())
            self.assertEqual(u.derivation, Derivation.STRUCTURAL_BASELINE)
            self.assertEqual(u.review, ReviewMetadata())
        self.assertEqual(self.built.scenes, self.manifest.scenes)
        payload = to_data(self.doc)
        self.assertFalse(set(payload) & {"duration", "start", "end", "search_query", "shots"})
        changed = deepcopy(self.manifest)
        changed.voice.speed = 1.5
        self.assertEqual(build_semantic_story(changed).semantic, self.built.semantic)

    def test_different_logical_ids_and_revisions_distinct(self):
        other = build_semantic_story(content(content_id="other"))
        self.assertNotEqual(other.semantic.documents[0].semantic_document_id, self.doc.semantic_document_id)
        revision = build_semantic_story(content("Other paragraph.\n\nSecond paragraph.", manifest=self.built))
        self.assertNotEqual(revision.semantic.documents[-1].story_units[0].story_unit_id, self.doc.story_units[0].story_unit_id)

    def invalid_document(self, d):
        m = deepcopy(self.built)
        m.semantic.documents = [d]
        m.semantic.active_creator_document_id = d.semantic_document_id
        self.assertTrue(validate(m))

    def test_block_corruption(self):
        b = self.doc.blocks[0]
        for mutation in [replace(b, ordinal=1), replace(b, source_text="Wrong"),
                         replace(b, block_id="untrusted"), replace(b, content_signature="bad"),
                         replace(b, section_heading_id=b.block_id), replace(b, heading_level=2)]:
            with self.subTest(mutation=mutation):
                self.invalid_document(resign(replace(self.doc, blocks=[mutation, self.doc.blocks[1]])))
        overlap = replace(self.doc.blocks[1], source_span=b.source_span, source_text=b.source_text)
        self.invalid_document(resign(replace(self.doc, blocks=[b, overlap])))
        self.invalid_document(replace(self.doc, blocks=[replace(b, source_span=SourceSpan(True, 5))]))

    def test_duplicate_ids_and_bad_output_signature(self):
        for field in ("documents", "source_revisions"):
            m = deepcopy(self.built)
            getattr(m.semantic, field).append(deepcopy(getattr(m.semantic, field)[0]))
            self.assertTrue(validate(m))
        self.invalid_document(replace(self.doc, output_signature="bad"))
        self.invalid_document(resign(replace(self.doc, story_units=[self.doc.story_units[0]] * 2)))

    def test_unit_ordinal_references_and_evidence_validation(self):
        u = self.doc.story_units[0]
        e = u.source_excerpts[0]
        for mutation in [replace(u, ordinal=1), replace(u, block_ids=["missing"]),
                         replace(u, source_excerpts=[e, e]), replace(u, block_ids=u.block_ids * 2),
                         replace(u, source_excerpts=[replace(e, source_text="bad")]),
                         replace(u, story_unit_id="untrusted")]:
            with self.subTest(mutation=mutation):
                self.invalid_document(resign(replace(self.doc, story_units=[mutation, self.doc.story_units[1]])))

    def custom_unit_document(self, spans, annotations=None):
        text = self.manifest.content.script
        excerpts = [SourceExcerpt(SourceSpan(a, b), text[a:b]) for a, b in spans]
        u = StoryUnit(story_unit_id(self.doc.analysis_signature, excerpts, Derivation.ANALYZER), 0,
                      excerpts, [b.block_id for b in self.doc.blocks], Derivation.ANALYZER,
                      annotations or SemanticAnnotations())
        return resign(replace(self.doc, story_units=[u]))

    def test_multiple_evidence_adjacent_and_whitespace_gaps(self):
        for spans in [[(0, 5), (5, 10)], [(0, 5), (6, 10)]]:
            d = self.custom_unit_document(spans)
            state = deepcopy(self.built.semantic)
            state.documents = [d]
            state.active_creator_document_id = d.semantic_document_id
            self.assertFalse(semantic_errors(state))

    def test_evidence_overlap_nested_duplicate_reversed(self):
        for spans in [[(0, 7), (5, 10)], [(0, 10), (2, 4)], [(0, 5), (0, 5)], [(6, 10), (0, 5)]]:
            self.invalid_document(self.custom_unit_document(spans))

    def test_cross_unit_overlap_allowed(self):
        d = self.custom_unit_document([(0, 5)])
        second = self.custom_unit_document([(0, 6)]).story_units[0]
        d = resign(replace(d, story_units=[d.story_units[0], replace(second, ordinal=1)]))
        state = SemanticState(deepcopy(self.built.semantic.source_revisions), [d], d.semantic_document_id)
        self.assertFalse(semantic_errors(state))

    def test_mention_containment_exact_text_and_confidence(self):
        for span, text, confidence, valid in [(SourceSpan(0, 5), "First", None, True),
                (SourceSpan(0, 5), "First", 0.0, True), (SourceSpan(0, 5), "First", 1.0, True),
                (SourceSpan(0, 5), "First", 0.5, True), (SourceSpan(0, 6), "First ", None, False),
                (SourceSpan(0, 5), "Wrong", None, False), (SourceSpan(0, 5), "First", True, False),
                (SourceSpan(0, 5), "First", float("nan"), False), (SourceSpan(0, 5), "First", float("inf"), False),
                (SourceSpan(0, 5), "First", -0.1, False), (SourceSpan(0, 5), "First", 1.1, False)]:
            with self.subTest(span=span, confidence=confidence):
                a = SemanticAnnotations(mentions=[Mention(span, text, AnnotationMetadata(confidence=confidence))])
                try:
                    d = self.custom_unit_document([(0, 5)], a)
                except ValueError:
                    self.assertFalse(valid)
                    continue
                state = SemanticState(deepcopy(self.built.semantic.source_revisions), [d], d.semantic_document_id)
                self.assertEqual(not semantic_errors(state), valid)

    def test_review_and_provenance_enum_strictness(self):
        m = deepcopy(self.built)
        d = replace(self.doc, review_status="APPROVED")
        m.semantic.documents = [d]
        self.assertTrue(validate(m))
        for confidence in (True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                decode(AnnotationMetadata, {"origin": "AI", "confidence": confidence})

    def test_save_load_and_older_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Dự án.json"
            save(self.built, path)
            self.assertEqual(load(path), self.built)
        for version in (61, 62, 63):
            data = to_data(self.manifest if version == 63 else ProjectManifest("Older"))
            data.pop("semantic")
            if version == 61:
                data["content"].pop("records")
                data["content"].pop("canonical_content_id")
            old = decode(ProjectManifest, migrate_document(data))
            self.assertEqual(old.semantic, SemanticState())
            self.assertFalse(validate(old))

    def test_malformed_present_semantic_not_defaulted(self):
        for payload in (None, [], {}, {"documents": []}):
            data = to_data(self.manifest)
            data["semantic"] = payload
            with self.assertRaises(ValueError):
                decode(ProjectManifest, migrate_document(data))

    def test_required_spec_eligibility(self):
        self.assertIsNotNone(eligible_active_document(self.built, self.doc.analysis_spec))
        self.assertIsNone(eligible_active_document(self.built, replace(self.doc.analysis_spec, analyzer_version="2")))

    def test_analyzer_invalid_source_and_failure_atomicity(self):
        before = to_data(self.built)
        class BadAnalyzer:
            analyzer_id = "fake"
            analyzer_version = "1"
            def analyze(self, source, blocks, options, control):
                return SemanticAnalysisResult([StoryUnitCandidate([SourceExcerpt(blocks[0].source_span, "bad")], [blocks[0].block_id])])
        with self.assertRaises(SemanticError) as caught:
            build_semantic_story(self.built, analyzer=BadAnalyzer())
        self.assertEqual(caught.exception.code, "semantic_source_text_mismatch")
        self.assertEqual(before, to_data(self.built))
        class Exploding(BadAnalyzer):
            def analyze(self, *args):
                raise RuntimeError("PRIVATE SCRIPT credential-value C:\\private")
        with self.assertRaises(SemanticError) as caught:
            build_semantic_story(self.built, analyzer=Exploding())
        self.assertEqual(str(caught.exception), "semantic_analysis_failed")
        self.assertEqual(before, to_data(self.built))

    def test_candidate_ids_not_accepted(self):
        class Forged(OfflineStructuralAnalyzer):
            def analyze(self, *args):
                result = super().analyze(*args)
                object.__setattr__(result.story_units[0], "story_unit_id", "FORGED")
                return result
        d = build_semantic_story(self.manifest, analyzer=Forged()).semantic.documents[0]
        self.assertTrue(d.story_units[0].story_unit_id.startswith("story_unit:"))
        self.assertNotEqual(d.story_units[0].story_unit_id, "FORGED")

    def test_analyzer_mutations_isolated(self):
        class Mutating(OfflineStructuralAnalyzer):
            def analyze(self, source, blocks, options, control):
                result = super().analyze(source, blocks, options, control)
                blocks.clear()
                source.diagnostics.clear()
                return result
        self.assertEqual(build_semantic_story(self.manifest, analyzer=Mutating()).semantic, self.built.semantic)

    def test_cancellation_discards_candidate(self):
        token = CancellationToken()
        class Cancelling(OfflineStructuralAnalyzer):
            def analyze(self, *args):
                result = super().analyze(*args)
                token.cancel()
                return result
        before = to_data(self.manifest)
        with self.assertRaises(Cancelled):
            build_semantic_story(self.manifest, analyzer=Cancelling(), control=token)
        self.assertEqual(to_data(self.manifest), before)

    def test_stage_readiness_success_and_safe_artifact(self):
        stage = SemanticStoryStage(dependencies=("content_ingest",))
        self.assertEqual(stage.dependencies, ("content_ingest",))
        self.assertEqual(stage.readiness(self.manifest).kind.value, "ready")
        self.assertEqual(stage.readiness(ProjectManifest("Empty")).kind.value, "not_ready")
        context = StageContext(self.manifest, CancellationToken(), 1, lambda *args: None)
        outcome = stage.execute(context)
        self.assertEqual(outcome.result.status, StageStatus.SUCCEEDED)
        self.assertEqual(outcome.update.manifest.semantic, self.built.semantic)
        self.assertNotIn("First paragraph", json.dumps(to_data(outcome.result)))
        self.assertTrue(stage.validate_reuse(outcome.update.manifest, outcome.result))

    def test_stage_failure_no_update(self):
        stage = SemanticStoryStage()
        outcome = stage.execute(StageContext(ProjectManifest("Empty"), CancellationToken(), 1, lambda *args: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertIsNone(outcome.update)

    def test_reuse_rejects_changed_outputs_and_sources(self):
        stage = SemanticStoryStage()
        outcome = stage.execute(StageContext(self.manifest, CancellationToken(), 1, lambda *args: None))
        for mode in ("missing_document", "missing_source", "selection", "revision", "valid_review", "valid_annotation"):
            with self.subTest(mode=mode):
                m = deepcopy(outcome.update.manifest)
                if mode == "missing_document": m.semantic.documents.clear()
                elif mode == "missing_source": m.semantic.source_revisions.clear()
                elif mode == "selection": m.semantic.active_creator_document_id = None
                elif mode == "revision": m = content("Changed revision", manifest=m)
                elif mode == "valid_review":
                    d = replace(self.doc, review_status=ReviewStatus.APPROVED)
                    m.semantic.documents[0] = replace(d, output_signature=output_signature(d))
                    self.assertFalse(validate(m))
                else:
                    d = self.custom_unit_document([(0, 5)], SemanticAnnotations(narrative_role=NarrativeRole.HOOK))
                    m.semantic.documents = [d]
                    m.semantic.active_creator_document_id = d.semantic_document_id
                    self.assertFalse(validate(m))
                self.assertFalse(stage.validate_reuse(m, outcome.result))

    def test_reuse_baseline_recomputation_rejects_self_consistent_edit(self):
        d = resign(replace(self.doc, story_units=[]))
        m = deepcopy(self.built)
        m.semantic.documents = [d]
        m.semantic.active_creator_document_id = d.semantic_document_id
        self.assertFalse(validate(m))
        previous = SemanticStoryStage().execute(StageContext(self.manifest, CancellationToken(), 1, lambda *args: None)).result
        previous.artifacts = SemanticStoryStage.artifacts(m, d)
        self.assertFalse(SemanticStoryStage().validate_reuse(m, previous))

    def test_version_and_options_invalidate_reuse(self):
        stage = SemanticStoryStage()
        result = stage.execute(StageContext(self.manifest, CancellationToken(), 1, lambda *args: None)).result
        original_inputs = stage.signature_inputs(self.manifest)
        for target in ("ENGINE_VERSION", "SEGMENTER_VERSION"):
            with patch("creator_studio.semantic.engine." + target, "2"):
                self.assertNotEqual(stage.signature_inputs(self.manifest), original_inputs)
                self.assertFalse(stage.validate_reuse(self.built, result))
        analyzer = OfflineStructuralAnalyzer()
        analyzer.analyzer_version = "2"
        self.assertFalse(SemanticStoryStage(analyzer=analyzer).validate_reuse(self.built, result))
        self.assertFalse(SemanticStoryStage(structural_options=StructuralOptions(True)).validate_reuse(self.built, result))
        self.assertFalse(SemanticStoryStage(structural_options=StructuralOptions(False, 10)).validate_reuse(self.built, result))

    def test_repeated_orchestrator_save_load_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project.json"
            save(self.manifest, path)
            for expected in (StageStatus.SUCCEEDED, StageStatus.SKIPPED, StageStatus.SKIPPED):
                runner = ProjectOrchestrator(ManifestRepository(path))
                runner.register(SemanticStoryStage())
                result = runner.run()
                self.assertEqual(result.results[0].status, expected)
                self.assertFalse(validate(load(path)))

    def test_review_preserved_on_rebuild(self):
        d = replace(self.doc, review_status=ReviewStatus.APPROVED)
        d = replace(d, output_signature=output_signature(d))
        m = deepcopy(self.built)
        m.semantic.documents[0] = d
        self.assertEqual(build_semantic_story(m).semantic.documents[0], d)

    def run_stage(self, path, options=None):
        runner = ProjectOrchestrator(ManifestRepository(path))
        runner.register(SemanticStoryStage(structural_options=options))
        return runner.run().results[0]

    def test_archive_exact_binding_orchestrator(self):
        for mode in ("unchanged", "format", "locator", "both", "missing_binding", "legacy"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "project.json"
                save(self.manifest, path)
                first = self.run_stage(path)
                self.assertEqual(first.status, StageStatus.SUCCEEDED)
                m = load(path)
                archived = m.semantic.source_revisions[0]
                self.assertEqual(first.artifacts[1].signature, archived.source_signature)
                self.assertNotIn(archived.content.original_text, json.dumps(to_data(first)))
                self.assertEqual(self.run_stage(path).status, StageStatus.SKIPPED)
                m = load(path)
                if mode in ("missing_binding", "legacy"):
                    previous = m.processing[0].execution
                    previous.artifacts = previous.artifacts[:1]
                    if mode == "legacy":
                        d = m.semantic.documents[0]
                        previous.artifacts[0].signature = exact_signature([
                            d.semantic_document_id, d.output_signature,
                            d.source_revision_id, d.analysis_signature])
                elif mode != "unchanged":
                    record = archived.content
                    if mode in ("format", "both"):
                        record = replace(record, original_text=record.original_text.replace("\n", "\r\n"))
                    if mode in ("locator", "both"):
                        record = replace(record, source_locator="retained-evidence.txt")
                    self.assertEqual(record.content_id, archived.content.content_id)
                    self.assertEqual(record.normalized_text, archived.content.normalized_text)
                    self.assertEqual(record.revision_signature, archived.content.revision_signature)
                    m.semantic.source_revisions[0] = replace(archived, content=record,
                        source_signature=exact_signature(record))
                    self.assertNotEqual(exact_signature(record), archived.source_signature)
                self.assertFalse(validate(m))
                save(m, path)
                result = self.run_stage(path)
                self.assertEqual(result.status, StageStatus.SKIPPED if mode == "unchanged" else StageStatus.SUCCEEDED)
                self.assertEqual(load(path).semantic, m.semantic)
                self.assertEqual(self.run_stage(path).status, StageStatus.SKIPPED)

    def reviewed(self, mode):
        m = deepcopy(self.built)
        d = m.semantic.documents[0]
        if mode == "document":
            d = replace(d, review_status=ReviewStatus.APPROVED)
        elif mode in ("unit", "locked", "rejected_locked"):
            review = ReviewMetadata(ReviewStatus.APPROVED if mode == "unit" else
                ReviewStatus.REJECTED if mode == "rejected_locked" else ReviewStatus.PENDING,
                mode != "unit")
            d = replace(d, story_units=[replace(d.story_units[0], review=review), *d.story_units[1:]])
        elif mode == "rejected":
            d = replace(d, review_status=ReviewStatus.REJECTED)
        m.semantic.documents[0] = replace(d, output_signature=output_signature(d))
        self.assertFalse(validate(m))
        return m

    def test_review_guard_orchestrator_atomicity(self):
        for mode in ("pending", "document", "unit", "locked", "rejected", "rejected_locked"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "project.json"
                save(self.manifest, path)
                self.assertEqual(self.run_stage(path).status, StageStatus.SUCCEEDED)
                m = load(path)
                m.semantic = self.reviewed(mode).semantic
                save(m, path)
                options = StructuralOptions(False, 5)
                protected = mode in ("document", "unit", "locked", "rejected_locked")
                if protected:
                    before = deepcopy(m)
                    with self.assertRaises(SemanticError) as error:
                        build_semantic_story(m, structural_options=options)
                    self.assertEqual(error.exception.code, "semantic_review_required")
                    self.assertEqual(m, before)
                    outcome = SemanticStoryStage(structural_options=options).execute(
                        StageContext(m, CancellationToken(), 1, lambda *args: None))
                    self.assertIsNone(outcome.update)
                result = self.run_stage(path, options)
                after = load(path)
                if protected:
                    self.assertEqual(result.status, StageStatus.FAILED)
                    self.assertEqual(result.diagnostics[0].code, "semantic_review_required")
                    self.assertFalse(result.retryable)
                    self.assertEqual(result.artifacts, [])
                    self.assertEqual(after.semantic, m.semantic)
                    self.assertEqual(after.content, m.content)
                    diagnostic = json.dumps(to_data(result.diagnostics))
                    self.assertNotIn(m.content.script, diagnostic)
                    self.assertNotIn("retained-evidence", diagnostic)
                    again = self.run_stage(path, options)
                    self.assertEqual(again.diagnostics, result.diagnostics)
                    self.assertEqual(again.status, StageStatus.FAILED)
                    # Explicit test setup removes creator protection, without an application override.
                    d = after.semantic.documents[0]
                    d = replace(d, review_status=ReviewStatus.PENDING,
                        story_units=[replace(u, review=ReviewMetadata()) for u in d.story_units])
                    after.semantic.documents[0] = replace(d, output_signature=output_signature(d))
                    save(after, path)
                    self.assertEqual(self.run_stage(path, options).status, StageStatus.SUCCEEDED)
                else:
                    self.assertEqual(result.status, StageStatus.SUCCEEDED)
                    self.assertNotEqual(after.semantic.active_creator_document_id, m.semantic.active_creator_document_id)
                    self.assertEqual(len(after.semantic.documents), 2)

    def test_same_id_approved_locked_orchestrator_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project.json"
            save(self.manifest, path)
            self.run_stage(path)
            m = load(path)
            m.semantic = self.reviewed("locked").semantic
            d = replace(m.semantic.documents[0], review_status=ReviewStatus.APPROVED)
            m.semantic.documents[0] = replace(d, output_signature=output_signature(d))
            save(m, path)
            self.assertEqual(self.run_stage(path).status, StageStatus.SUCCEEDED)
            self.assertEqual(load(path).semantic, m.semantic)

    def test_missing_current_canonical_is_stale_not_corrupt_history(self):
        m = deepcopy(self.built)
        m.content.records.clear()
        m.content.canonical_content_id = None
        self.assertFalse(validate(m))
        self.assertIsNone(eligible_active_document(m))
        self.assertEqual(m.semantic, self.built.semantic)

    def test_heading_forward_nonheading_and_cycle_references_rejected(self):
        m = build_semantic_story(content("# One\n\nprose\n\n## Two\n\nmore", markdown=True))
        d = m.semantic.documents[0]
        for index, target in [(0, d.blocks[2].block_id), (2, d.blocks[1].block_id), (2, d.blocks[2].block_id)]:
            blocks = list(d.blocks)
            blocks[index] = replace(blocks[index], section_heading_id=target)
            bad = resign(replace(d, blocks=blocks))
            state = SemanticState(m.semantic.source_revisions, [bad], bad.semantic_document_id)
            self.assertIn("semantic_reference_invalid", semantic_errors(state))

    def test_source_linkage_and_signature_corruption(self):
        for key, value in [("source_revision_id", "missing"), ("content_id", "other"),
                ("content_revision_signature", "bad"), ("source_language", "vi"),
                ("structure_signature", "bad"), ("analysis_signature", "bad")]:
            with self.subTest(field=key):
                self.invalid_document(resign(replace(self.doc, **{key: value})))

    def test_coverage_gap_rejected(self):
        self.invalid_document(resign(replace(self.doc, blocks=[self.doc.blocks[0]], story_units=[])))

    def test_unknown_diagnostic_and_malformed_semantic_review_rejected(self):
        self.invalid_document(resign(replace(self.doc, diagnostics=[SemanticDiagnostic("PRIVATE SCRIPT")])))
        self.invalid_document(replace(self.doc, story_units=[replace(self.doc.story_units[0],
            review=ReviewMetadata(locked="yes"))]))

    def test_structural_option_threshold_signed_and_used(self):
        stage = SemanticStoryStage(structural_options=StructuralOptions(False, 5))
        self.assertNotEqual(stage.signature_inputs(self.manifest), SemanticStoryStage().signature_inputs(self.manifest))
        m = build_semantic_story(self.manifest, structural_options=StructuralOptions(False, 5))
        self.assertEqual(m.semantic.documents[0].diagnostics, [SemanticDiagnostic("semantic_long_block")] * 2)
        self.assertIsNone(eligible_active_document(m))
        self.assertIsNotNone(eligible_active_document(m, m.semantic.documents[0].analysis_spec))

    def test_identity_excludes_locator_and_original_formatting(self):
        with tempfile.TemporaryDirectory() as temp:
            one, two = Path(temp) / "first.md", Path(temp) / "second.md"
            one.write_bytes(b"one\r\ntwo\r\n")
            two.write_bytes(b"one\ntwo")
            a = ingest(IngestRequest("same", source_type=SourceType.MARKDOWN, source_locator=str(one)))
            b = ingest(IngestRequest("same", source_type=SourceType.MARKDOWN, source_locator=str(two)))
        first = build_semantic_story(apply_ingest(ProjectManifest("A"), a))
        second = build_semantic_story(apply_ingest(ProjectManifest("B"), b))
        self.assertEqual(first.semantic.documents, second.semantic.documents)
        self.assertNotEqual(first.semantic.source_revisions[0].source_signature, second.semantic.source_revisions[0].source_signature)

    def test_invalid_analyzer_result_redacted_and_atomic(self):
        class Invalid(OfflineStructuralAnalyzer):
            def analyze(self, *args):
                return {"private": "PRIVATE SCRIPT"}
        before = to_data(self.manifest)
        outcome = SemanticStoryStage(analyzer=Invalid()).execute(StageContext(self.manifest,
            CancellationToken(), 1, lambda *args: None))
        self.assertIsNone(outcome.update)
        self.assertEqual(outcome.result.diagnostics[0].code, "semantic_output_invalid")
        self.assertNotIn("PRIVATE", json.dumps(to_data(outcome.result)))
        self.assertEqual(to_data(self.manifest), before)

    def test_stage_cancelled_after_analysis_has_no_update(self):
        token = CancellationToken()
        class CancelAfter(OfflineStructuralAnalyzer):
            def analyze(self, *args):
                result = super().analyze(*args)
                token.cancel()
                return result
        before = deepcopy(self.manifest)
        with self.assertRaises(Cancelled):
            SemanticStoryStage(analyzer=CancelAfter()).execute(StageContext(self.manifest, token, 1, lambda *args: None))
        self.assertEqual(before, self.manifest)

    def test_stage_ineligible_content(self):
        m = deepcopy(self.manifest)
        from creator_studio.manifest.content import ContentProvenance
        m.content.records[0] = replace(m.content.records[0], provenance=ContentProvenance.REFERENCE_ONLY)
        self.assertEqual(SemanticStoryStage().readiness(m).diagnostics[0].code, "semantic_content_ineligible")

    def test_strict_span_corruption_saved_payload(self):
        for start, end in [(True, 2), (0.0, 2), (0, 0), (0, 99999)]:
            data = to_data(self.built)
            data["semantic"]["documents"][0]["blocks"][0]["source_span"] = {"start": start, "end": end}
            try:
                m = decode(ProjectManifest, data)
            except ValueError:
                continue
            self.assertTrue(validate(m))

    def test_multi_paragraph_baseline_order(self):
        m = build_semantic_story(content("a\n\nb\n\nc"))
        d = m.semantic.documents[0]
        self.assertEqual([b.ordinal for b in d.blocks], [0, 1, 2])
        self.assertEqual([u.ordinal for u in d.story_units], [0, 1, 2])
        self.assertEqual([u.source_excerpts[0].source_text for u in d.story_units], ["a", "b", "c"])

    def test_runtime_dependency_boundary(self):
        files = list(Path("creator_studio/semantic").glob("*.py"))
        files += [Path("creator_studio/manifest/semantic.py"), Path("creator_studio/manifest/semantic_validation.py")]
        forbidden = {"PyQt6", "requests", "httpx", "openai", "anthropic", "subprocess", "pipeline", "stock", "engine", "socket", "urllib"}
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({a.name.split(".")[0] for a in node.names} & forbidden)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertNotIn((node.module or "").split(".")[0], forbidden)
        text = Path("creator_studio/manifest/semantic_validation.py").read_text(encoding="utf-8")
        self.assertNotIn("from ..semantic", text)


class OfflineLegacyRegressionTests(unittest.TestCase):
    """Exercise production pure logic with in-memory fixtures, no saved projects."""

    def test_semantic_window_production_expression(self):
        # Execute only the actual production expression, avoiding pipeline imports,
        # providers and media setup. No imitation of the production window string.
        tree = ast.parse(Path("pipeline/full_video_pipeline.py").read_text(encoding="utf-8"))
        assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == "semantic_scene" and t.attr == "text" for t in n.targets)]
        self.assertEqual(len(assignments), 1)
        expression = compile(ast.Expression(assignments[0].value), "production-semantic-window", "eval")
        for previous, current, following in [("wine industry", "continues here", "Casablanca"),
                ("Arab armies entered North", "Africa", "next thought"), ("", "Current", "")]:
            result = eval(expression, {"__builtins__": {}},
                          {"previous_text": previous, "current_text": current, "next_text": following})
            self.assertIn("PREVIOUS CONTEXT:\n" + (previous or "[NONE]"), result)
            self.assertIn("CURRENT NARRATION:\n" + current, result)
            self.assertIn("NEXT CONTEXT:\n" + (following or "[NONE]"), result)
            self.assertIn("Do NOT blend", result)

    def test_context_geography_production_offline(self):
        from pipeline.context_geo import enrich_manifest_with_project_context, filter_geography_candidates
        fixture = {"scenes": [{"scene_id": "one", "dialogue": "Morocco has historic cities.",
            "analysis": {"location": "Morocco"}, "search": {"primary_keyword": "city"}},
            {"scene_id": "two", "dialogue": "Moroccan markets are busy.",
            "analysis": {}, "search": {"primary_keyword": "market"}}]}
        enriched = enrich_manifest_with_project_context(deepcopy(fixture))
        self.assertEqual(enriched["project_context"]["required_country_key"], "morocco")
        scene = enriched["scenes"][1]
        candidates = [{"title": "Morocco market"}, {"title": "Japan street"}, {"title": "market"}]
        kept, rejected, bypassed = filter_geography_candidates(scene, candidates)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(rejected), 1)
        self.assertFalse(bypassed)
        kept, rejected, bypassed = filter_geography_candidates(scene, [candidates[1]])
        self.assertEqual(kept, [candidates[1]])
        self.assertTrue(bypassed)

    def test_visual_strategy_production_offline(self):
        from pipeline.visual_strategy import enrich_manifest_with_visual_strategy
        scene = {"scene_id": "one", "dialogue": "This is Morocco.",
                 "analysis": {"subject": "Morocco landscape", "location": "Morocco"},
                 "search": {"primary_keyword": "Morocco landscape"},
                 "project_context": {"required_country": "Morocco", "required_country_key": "morocco"}}
        original_search = deepcopy(scene["search"])
        m = enrich_manifest_with_visual_strategy({"scenes": [deepcopy(scene)]}, activate_search=False)
        result = m["scenes"][0]
        self.assertEqual(result["visual_strategy"]["geo_policy"], "STRICT")
        self.assertEqual(result["search"], original_search)
        self.assertTrue(result["visual_strategy"]["search_queries"])


if __name__ == "__main__":
    unittest.main()
