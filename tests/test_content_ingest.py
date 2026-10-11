"""M63 offline contracts. All source/output files live in temporary directories."""
import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.content import (ContentProvenance as Provenance, SourceType,
    IngestRequest, IngestLimits, IngestStatus, IngestError, ingest, apply_ingest)
from creator_studio.content.stage import ContentIngestStage
from creator_studio.manifest import save, load, validate, signature
from creator_studio.manifest.codec import to_data
from creator_studio.manifest.models import ProjectManifest, ProcessingState, Status
from creator_studio.manifest.execution import ExecutionRecord, ExecutionStatus
from creator_studio.orchestrator import ManifestRepository, ProjectOrchestrator, ReadinessKind, StageStatus
from creator_studio.orchestrator.contracts import StageContext, CancellationToken


class ContentIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = ProjectManifest("Content ingest")

    def request(self, text="Hello world", **kwargs):
        return IngestRequest("script-main", text=text, **kwargs)

    def file_request(self, payload=b"Hello\r\nworld\n", name="source.txt", source_type=SourceType.TEXT_FILE):
        path = self.root / name
        path.write_bytes(payload)
        return IngestRequest("script-main", source_type=source_type, source_locator=str(path),
                             provenance=Provenance.IMPORTED_OWNED)

    def failure(self, request, code, limits=IngestLimits()):
        result = ingest(request, limits)
        self.assertEqual(result.status, IngestStatus.FAILURE)
        self.assertIsNone(result.content)
        self.assertIsNone(result.signature)
        self.assertEqual([d.code for d in result.diagnostics], [code])
        return result

    def runner(self, request, **kwargs):
        path = self.root / "project.json"
        if not path.exists():
            save(self.manifest, path)
        runner = ProjectOrchestrator(ManifestRepository(path))
        runner.register(ContentIngestStage(request, **kwargs))
        return runner

    def test_direct_text(self):
        result = ingest(self.request())
        self.assertEqual(result.status, IngestStatus.SUCCESS)
        self.assertEqual(result.content.normalized_text, "Hello world")

    def test_utf8_file(self):
        result = ingest(self.file_request())
        self.assertEqual(result.content.original_text, "Hello\r\nworld\n")
        self.assertEqual(result.content.normalized_text, "Hello\nworld")

    def test_bom_file(self):
        self.assertEqual(ingest(self.file_request(b"\xef\xbb\xbfHello")).content.original_text, "Hello")

    def test_direct_bom_preservation(self):
        record = ingest(self.request("\ufeffHello")).content
        self.assertEqual(record.original_text, "\ufeffHello")
        self.assertEqual(record.normalized_text, "Hello")

    def test_markdown_direct(self):
        text = "# Title\n\n**Bold** [link](example)\n\n- item"
        self.assertEqual(ingest(self.request(text, source_type=SourceType.MARKDOWN)).content.normalized_text, text)

    def test_markdown_file(self):
        record = ingest(self.file_request(b"# Title\n", "notes.markdown", SourceType.MARKDOWN)).content
        self.assertEqual(record.normalized_text, "# Title")

    def test_vietnamese_unicode_path(self):
        text = "Việt Nam tươi đẹp.\n\nTôi yêu tiếng Việt."
        record = ingest(self.file_request(text.encode("utf-8"), "Nội dung có dấu.txt")).content
        self.assertEqual(record.original_text, text)
        self.assertEqual(record.normalized_text, text)

    def test_english_serbian(self):
        text = "Hello Србија! Čačak, Đorđe."
        self.assertEqual(ingest(self.request(text)).content.normalized_text, text)

    def test_nfc(self):
        record = ingest(self.request("Cafe\u0301")).content
        self.assertEqual(record.original_text, "Cafe\u0301")
        self.assertEqual(record.normalized_text, "Café")

    def test_crlf_cr_normalization(self):
        record = ingest(self.request("A\r\n\r\nB\rC\n\n")).content
        self.assertEqual(record.normalized_text, "A\n\nB\nC")

    def test_whitespace_policy(self):
        text = "  A\t \n\n B  "
        self.assertEqual(ingest(self.request(text)).content.normalized_text, text)

    def test_original_unchanged(self):
        text = "  Café!\r\n\r\nNext.  \n"
        self.assertEqual(ingest(self.request(text)).content.original_text, text)

    def test_normalization_deterministic(self):
        a, b = ingest(self.request("Cafe\u0301\r\n")), ingest(self.request("Café\n\n"))
        self.assertEqual(a.content.normalized_text, b.content.normalized_text)
        self.assertEqual(a.signature, b.signature)

    def test_signature_repeat(self):
        self.assertEqual(ingest(self.request()), ingest(self.request()))

    def test_signature_save_load(self):
        result = ingest(self.request("Việt Nam", language="VI"))
        manifest = apply_ingest(self.manifest, result)
        path = self.root / "project.json"
        save(manifest, path)
        restored = load(path)
        self.assertEqual(restored.content.records[0], result.content)
        self.assertEqual(restored.content.records[0].revision_signature, result.signature)
        self.assertEqual(validate(restored), [])

    def test_changed_text_revision(self):
        a, b = ingest(self.request("A")), ingest(self.request("B"))
        self.assertNotEqual(a.signature, b.signature)
        self.assertEqual(a.content.content_id, b.content.content_id)
        first = apply_ingest(self.manifest, a)
        second = apply_ingest(first, b)
        self.assertEqual(second.content.revision, first.content.revision + 1)
        self.assertEqual(len(second.content.records), 1)
        self.assertEqual(first.content.script, "A")

    def test_unchanged_revision(self):
        result = ingest(self.request())
        first = apply_ingest(self.manifest, result)
        self.assertEqual(apply_ingest(first, result).content.revision, first.content.revision)

    def test_entity_id_excluded_from_signature(self):
        a, b = ingest(self.request()), ingest(replace(self.request(), content_id="other"))
        self.assertEqual(a.signature, b.signature)
        self.assertNotEqual(a.content.content_id, b.content.content_id)

    def test_source_path_excluded_from_revision(self):
        a = ingest(self.file_request(name="a.txt"))
        b = ingest(self.file_request(name="b.txt"))
        self.assertEqual(a.signature, b.signature)

    def test_metadata_changes_signature(self):
        base = ingest(self.request())
        for kwargs in ({"language": "vi"}, {"title": "Title"}, {"provenance": Provenance.LICENSED},
                       {"source_type": SourceType.MARKDOWN}):
            self.assertNotEqual(base.signature, ingest(self.request(**kwargs)).signature)

    def test_empty(self):
        self.failure(self.request(""), "content_empty")

    def test_whitespace_only(self):
        self.failure(self.request(" \t\r\n"), "content_empty")

    def test_missing_file(self):
        self.failure(IngestRequest("script", SourceType.TEXT_FILE, source_locator=str(self.root / "absent.txt")), "source_not_found")

    def test_directory(self):
        self.failure(IngestRequest("script", SourceType.TEXT_FILE, source_locator=str(self.root)), "source_is_directory")

    def test_invalid_utf8(self):
        self.failure(self.file_request(b"\xff\xfe"), "invalid_utf8")

    def test_unsupported_source(self):
        self.failure(self.request(source_type=SourceType.IMPORTED_TRANSCRIPT), "unsupported_source_type")
        self.failure(self.request(source_type="PDF"), "unsupported_source_type")

    def test_unsupported_extension(self):
        self.failure(self.file_request(name="source.py"), "unsupported_file_type")

    def test_byte_limit_direct(self):
        self.failure(self.request("éé"), "content_too_large", IngestLimits(max_bytes=3))

    def test_byte_limit_file_no_truncation(self):
        request = self.file_request(b"abcdefgh")
        self.failure(request, "content_too_large", IngestLimits(max_bytes=7))
        self.assertEqual(Path(request.source_locator).read_bytes(), b"abcdefgh")

    def test_character_limit(self):
        self.failure(self.request("abc"), "content_too_large", IngestLimits(max_characters=2))

    def test_exact_limits(self):
        self.assertEqual(ingest(self.request("abc"), IngestLimits(3, 3)).status, IngestStatus.SUCCESS)

    def test_invalid_limits(self):
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                IngestLimits(max_bytes=value)

    def test_invalid_controls(self):
        for char in ("\x00", "\x01", "\x7f", "\x85", "\ud800"):
            self.failure(self.request("A" + char), "invalid_control_character")

    def test_language_normalization(self):
        self.assertEqual(ingest(self.request(language=" EN_us ")).content.language, "en-us")

    def test_language_unknown(self):
        result = ingest(self.request())
        self.assertIsNone(result.content.language)
        self.assertEqual(apply_ingest(self.manifest, result).content.source_language, "und")

    def test_invalid_language(self):
        self.failure(self.request(language="not a language"), "invalid_language")

    def test_creator_provenance(self):
        self.assertEqual(ingest(self.request()).content.provenance, Provenance.CREATOR_AUTHORED)

    def test_reference_provenance(self):
        result = ingest(self.request(source_type=SourceType.REFERENCE_TEXT))
        self.assertEqual(result.content.provenance, Provenance.REFERENCE_ONLY)

    def test_reference_no_promotion(self):
        for kwargs in ({"source_type": SourceType.REFERENCE_TEXT}, {"provenance": Provenance.REFERENCE_ONLY},
                       {"provenance": Provenance.UNKNOWN}):
            result = ingest(self.request(**kwargs))
            with self.assertRaisesRegex(IngestError, "reference_content_not_canonical"):
                apply_ingest(self.manifest, result)
            proposal = apply_ingest(self.manifest, result, canonical=False)
            self.assertEqual(proposal.content.script, "")
            self.assertIsNone(proposal.content.canonical_content_id)
            self.assertEqual(len(proposal.content.records), 1)
            self.assertEqual(validate(proposal), [])

    def test_noncanonical_cannot_replace_active_entity(self):
        manifest = apply_ingest(self.manifest, ingest(self.request()))
        with self.assertRaisesRegex(IngestError, "canonical_content_conflict"):
            apply_ingest(manifest, ingest(self.request(provenance=Provenance.REFERENCE_ONLY)), canonical=False)

    def test_licensed_and_imported_owned(self):
        for provenance in (Provenance.LICENSED, Provenance.IMPORTED_OWNED):
            self.assertEqual(validate(apply_ingest(self.manifest, ingest(self.request(provenance=provenance)))), [])

    def test_safe_diagnostics_exception_secrets(self):
        request = self.file_request()
        marker = "PRIVATE_TEST_MARKER"
        with patch.object(Path, "open", side_effect=PermissionError(marker)):
            result = self.failure(request, "source_read_failed")
        payload = json.dumps(to_data(result))
        self.assertNotIn(marker, payload)
        self.assertNotIn(request.source_locator, payload)
        self.assertNotIn("PermissionError", payload)

    def test_environment_not_read(self):
        with patch.dict("os.environ", {"INGEST_TEST_VALUE": "PRIVATE_TEST_MARKER"}):
            result = ingest(self.request())
        self.assertNotIn("PRIVATE_TEST_MARKER", json.dumps(to_data(result)))

    def test_manifest_update_copy_valid(self):
        before = deepcopy(self.manifest)
        proposal = apply_ingest(self.manifest, ingest(self.request()))
        self.assertEqual(self.manifest, before)
        self.assertEqual(validate(proposal), [])

    def test_m61_old_document_load(self):
        document = to_data(self.manifest)
        del document["content"]["records"]
        del document["content"]["canonical_content_id"]
        document["content"]["script"] = "Old script"
        path = self.root / "old.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        restored = load(path)
        self.assertEqual(restored.content.script, "Old script")
        self.assertEqual(restored.content.records, [])
        self.assertEqual(restored.schema_version, 2)

    def test_m62_execution_preserved(self):
        self.manifest.processing.append(ProcessingState(stage="earlier", status=Status.SUCCEEDED,
            execution=ExecutionRecord("earlier", "1", ExecutionStatus.SUCCEEDED)))
        proposal = apply_ingest(self.manifest, ingest(self.request()))
        self.assertEqual(proposal.processing, self.manifest.processing)
        path = self.root / "execution.json"
        save(proposal, path)
        self.assertEqual(load(path).processing, self.manifest.processing)

    def test_manifest_rejects_tampered_record(self):
        manifest = apply_ingest(self.manifest, ingest(self.request()))
        manifest.content.records[0] = replace(manifest.content.records[0], revision_signature="bad")
        self.assertTrue(validate(manifest))

    def test_manifest_rejects_reference_promotion(self):
        result = ingest(self.request(source_type=SourceType.REFERENCE_TEXT))
        manifest = apply_ingest(self.manifest, result, canonical=False)
        manifest.content.canonical_content_id = result.content.content_id
        manifest.content.script = result.content.normalized_text
        self.assertTrue(validate(manifest))

    def test_stage_success(self):
        summary = self.runner(self.request()).run()
        self.assertEqual(summary.status, StageStatus.SUCCEEDED)
        self.assertEqual(load(self.root / "project.json").content.script, "Hello world")

    def test_stage_readiness(self):
        self.assertEqual(ContentIngestStage(self.request()).readiness(self.manifest).kind, ReadinessKind.READY)
        self.assertEqual(ContentIngestStage(self.request("")).readiness(self.manifest).kind, ReadinessKind.NOT_READY)
        stage = ContentIngestStage(self.request(source_type=SourceType.REFERENCE_TEXT))
        self.assertEqual(stage.readiness(self.manifest).kind, ReadinessKind.BLOCKED)

    def test_stage_signature_changes(self):
        a, b = ContentIngestStage(self.request("A")), ContentIngestStage(self.request("B"))
        self.assertNotEqual(signature(a.signature_inputs(self.manifest)), signature(b.signature_inputs(self.manifest)))

    def test_stage_reuse(self):
        self.runner(self.request()).run()
        runner = self.runner(self.request())
        with patch.object(ContentIngestStage, "execute", side_effect=AssertionError("Must reuse")):
            self.assertEqual(runner.run().results[0].status, StageStatus.SKIPPED)

    def test_stage_changed_text_runs(self):
        self.runner(self.request("A")).run()
        self.assertEqual(self.runner(self.request("B")).run().results[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(load(self.root / "project.json").content.script, "B")

    def test_stage_file_change_invalidates(self):
        request = self.file_request(b"A")
        self.runner(request).run()
        Path(request.source_locator).write_bytes(b"B")
        self.assertEqual(self.runner(request).run().results[0].status, StageStatus.SUCCEEDED)

    def test_stage_original_format_change_invalidates(self):
        self.runner(self.request("A\r\n")).run()
        self.assertEqual(self.runner(self.request("A\n")).run().results[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(load(self.root / "project.json").content.records[0].original_text, "A\n")

    def test_stage_original_unicode_change_invalidates(self):
        self.runner(self.request("Cafe\u0301")).run()
        self.assertEqual(self.runner(self.request("Café")).run().results[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(load(self.root / "project.json").content.records[0].original_text, "Café")

    def test_stage_source_changed_during_execution(self):
        request = self.file_request(b"A")
        stage = ContentIngestStage(request)
        stage.signature_inputs(self.manifest)
        Path(request.source_locator).write_bytes(b"B")
        outcome = stage.execute(StageContext(self.manifest, CancellationToken(), 1, lambda *_: None))
        self.assertEqual(outcome.result.status, StageStatus.FAILED)
        self.assertIsNone(outcome.update)
        self.assertEqual(outcome.result.diagnostics[0].code, "source_changed")

    def test_failure_preserves_canonical(self):
        self.runner(self.request("Good script")).run()
        self.runner(self.request("\x00")).run()
        self.assertEqual(load(self.root / "project.json").content.script, "Good script")
        with self.assertRaises(IngestError):
            apply_ingest(self.manifest, ingest(self.request("")))

    def test_reference_stage_storage(self):
        self.assertEqual(self.runner(self.request(source_type=SourceType.REFERENCE_TEXT), canonical=False).run().status,
                         StageStatus.SUCCEEDED)
        manifest = load(self.root / "project.json")
        self.assertEqual(manifest.content.script, "")
        self.assertEqual(manifest.content.records[0].provenance, Provenance.REFERENCE_ONLY)

    def test_source_unchanged(self):
        request = self.file_request(b"\xef\xbb\xbfA\r\n")
        before = Path(request.source_locator).read_bytes()
        self.runner(request).run()
        self.assertEqual(Path(request.source_locator).read_bytes(), before)

    def test_invalid_request_types(self):
        self.failure(replace(self.request(), language=42), "invalid_request")
        self.failure(replace(self.request(), content_id="bad id"), "invalid_content_id")
        self.failure(replace(self.request(), source_locator="also.txt"), "ambiguous_source")
        self.failure(self.request(title="bad\ud800"), "invalid_metadata")
        self.assertEqual(ingest(None).diagnostics[0].code, "invalid_request")

    def test_existing_scene_spans_preserved_on_invalid_edit(self):
        from creator_studio.manifest.models import Scene
        manifest = apply_ingest(self.manifest, ingest(self.request("Long script")))
        manifest.scenes.append(Scene(script_start=0, script_end=11))
        before = deepcopy(manifest)
        with self.assertRaisesRegex(IngestError, "manifest_update_invalid"):
            apply_ingest(manifest, ingest(self.request("Short")))
        self.assertEqual(manifest, before)

    def test_span_integrity_matrix(self):
        from creator_studio.manifest.models import Scene
        for text, allowed in [("XXAlpha beta tail", False), ("pha beta tail extra", False),
                              ("Alpha BETA tail", False), ("Alpha beta tail extra", True),
                              ("Omega beta tail", True), ("Short", False)]:
            with self.subTest(text=text):
                manifest = apply_ingest(self.manifest, ingest(self.request("Alpha beta tail")))
                manifest.scenes = [Scene(id="one", order=0, script_start=6, script_end=10),
                                   Scene(id="two", order=1, script_start=11, script_end=15)]
                before = deepcopy(manifest)
                if allowed:
                    proposed = apply_ingest(manifest, ingest(self.request(text)))
                    self.assertEqual(validate(proposed), [])
                else:
                    with self.assertRaises(IngestError) as caught:
                        apply_ingest(manifest, ingest(self.request(text)))
                    if text != "Short":
                        self.assertEqual(caught.exception.code, "scene_script_span_changed")
                        self.assertEqual(caught.exception.scene_id, "one")
                        self.assertEqual((caught.exception.span_start, caught.exception.span_end), (6, 10))
                    self.assertNotIn("beta", str(caught.exception))
                    self.assertNotIn(text, str(caught.exception))
                self.assertEqual(manifest, before)

    def test_reuse_persisted_output_matrix(self):
        from creator_studio.manifest.models import Scene
        changes = ["unchanged", "replace", "remove", "canonical", "projection", "format",
                   "unicode", "newline", "language", "title", "provenance",
                   "reference_replace", "reference_remove", "conflict"]
        for change in changes:
            with self.subTest(change=change):
                path = self.root / "project.json"
                save(self.manifest, path)
                reference = change.startswith("reference")
                request = self.request("Caf\u00e9\nLine", source_type=(SourceType.REFERENCE_TEXT
                                       if reference else SourceType.DIRECT_TEXT))
                self.runner(request, canonical=not reference).run()
                manifest = load(path)
                if change in {"replace", "reference_replace", "conflict"}:
                    manifest = apply_ingest(manifest, ingest(replace(request, text="Other text")),
                                            canonical=not reference)
                elif change in {"remove", "reference_remove"}:
                    manifest.content.records = []
                    manifest.content.canonical_content_id = None
                elif change == "canonical":
                    manifest = apply_ingest(manifest, ingest(replace(request, content_id="other")))
                elif change == "projection":
                    manifest.content.canonical_content_id = None
                    manifest.content.script = "Different projection"
                elif change != "unchanged":
                    updates = {"format": {"text": "Caf\u00e9\r\nLine"},
                               "unicode": {"text": "Cafe\u0301\nLine"},
                               "newline": {"text": "Caf\u00e9\nLine\n"},
                               "language": {"language": "VI_vn"}, "title": {"title": "New title"},
                               "provenance": {"provenance": Provenance.LICENSED}}
                    manifest = apply_ingest(manifest, ingest(replace(request, **updates[change])))
                if change == "conflict":
                    manifest.scenes = [Scene(id="protected", script_start=0, script_end=5)]
                before = deepcopy(manifest.content)
                save(manifest, path)
                result = self.runner(request, canonical=not reference).run().results[0]
                if change == "unchanged":
                    self.assertEqual(result.status, StageStatus.SKIPPED)
                elif change == "conflict":
                    self.assertEqual(result.status, StageStatus.BLOCKED)
                    self.assertEqual(result.diagnostics[0].code, "scene_script_span_changed")
                    self.assertEqual(load(path).content, before)
                else:
                    self.assertEqual(result.status, StageStatus.SUCCEEDED)
                    stored = load(path)
                    self.assertEqual(stored.content.records[0], ingest(request).content)
                    self.assertEqual(validate(stored), [])

    def test_normalization_parity(self):
        from creator_studio.manifest.content import revision_signature
        for text in ["A\r\n\r\nB\n\n", "\ufeffCafe\u0301\rC", " A\t \n B ",
                     "\ufeff\ufeffA", "# Header\n\n- item", "\u0344"]:
            with self.subTest(text=repr(text)):
                result = ingest(self.request(text))
                manifest = apply_ingest(self.manifest, result)
                self.assertEqual(validate(manifest), [])
                bad = replace(result.content, normalized_text=result.content.normalized_text + "x")
                bad = replace(bad, revision_signature=revision_signature(bad))
                manifest.content.records = [bad]
                self.assertIn("content_normalization", [e.code for e in validate(manifest)])

    def test_size_order_and_post_nfc(self):
        self.failure(self.request("xx\ud800"), "content_too_large", IngestLimits(max_characters=1))
        self.failure(self.request("\u00e9\u00e9"), "content_too_large", IngestLimits(max_bytes=3))
        self.failure(self.request("\u0344"), "content_too_large", IngestLimits(max_characters=1))

    def test_format_change_between_signature_and_execute(self):
        request = self.file_request(b"A\r\n")
        stage = ContentIngestStage(request)
        stage.signature_inputs(self.manifest)
        Path(request.source_locator).write_bytes(b"A\n")
        outcome = stage.execute(StageContext(self.manifest, CancellationToken(), 1, lambda *_: None))
        self.assertEqual(outcome.result.diagnostics[0].code, "source_changed")
        self.assertIsNone(outcome.update)

    def test_identical_content_relocated(self):
        first = self.file_request(b"Same", "first.txt")
        second = self.file_request(b"Same", "second.txt")
        self.runner(first).run()
        self.assertEqual(self.runner(second).run().results[0].status, StageStatus.SUCCEEDED)
        self.assertEqual(load(self.root / "project.json").content.records[0].source_locator,
                         second.source_locator)

    def test_no_external_dependencies(self):
        allowed = {"ast", "copy", "dataclasses", "enum", "json", "pathlib", "re", "unicodedata"}
        root = Path(__file__).resolve().parents[1] / "creator_studio" / "content"
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name.split(".")[0] in allowed for alias in node.names))
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split(".")[0], allowed)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], {"pipeline", "stock", "engine", "PyQt6"})


if __name__ == "__main__":
    unittest.main()
