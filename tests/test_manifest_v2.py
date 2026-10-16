"""Offline foundation tests; run with unittest discovery restricted to this file."""
import ast
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from creator_studio.manifest import (
    ProjectManifest, save, load, validate, signature, dependency_signature,
    snapshot_metadata, recover_previous, ManifestValidationError,
    PersistenceError, UnsupportedSchemaError,
)
from creator_studio.manifest.codec import to_data, decode
from creator_studio.manifest.models import (
    Scene, MediaReference, MediaKind, Provenance, Rights, SubtitleSegment,
    SubtitleTrack, TrackKind, TimelineReference, AudioReference, InputSource,
    InputKind, ProcessingState, Diagnostic,
)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "Dự án thử nghiệm.json"
        self.manifest = ProjectManifest("Việt Nam")

    def rich_manifest(self):
        m = self.manifest
        m.content.script = "Xin chào Việt Nam!"
        scene = Scene(narration=m.content.script, script_start=0,
                      script_end=len(m.content.script), start=0, end=2)
        media = MediaReference(reference="C:/Hình ảnh/phim.mp4",
                               provenance=Provenance(rights=Rights.OWNED), final_eligible=True)
        m.media.append(media)
        scene.media_ids.append(media.id)
        m.scenes.append(scene)
        original = SubtitleSegment(scene_id=scene.id, end=2, original_text=m.content.script)
        review = SubtitleSegment(scene_id=scene.id, end=2, original_text=m.content.script,
                                 translated_text="Hello Vietnam!", source_segment_id=original.id,
                                 original_locked=True, translation_locked=True)
        m.subtitle_tracks = [SubtitleTrack(segments=[original]),
                             SubtitleTrack(kind=TrackKind.REVIEW, language="vi", segments=[review])]
        m.timeline.append(TimelineReference(scene_id=scene.id, media_id=media.id, end=2))
        m.audio.append(AudioReference(media_id=media.id, scene_id=scene.id))
        m.voice.audio_media_id = media.id
        m.inputs = [InputSource(kind=k, reference="future reference") for k in InputKind]
        m.processing.append(ProcessingState(stage="analysis", diagnostics=[Diagnostic()]))
        return m

    def test_creation(self):
        self.assertEqual(validate(self.manifest), [])
        self.assertNotEqual(ProjectManifest("Other").project_id, self.manifest.project_id)
        self.assertEqual(self.manifest.schema_version, 2)

    def test_roundtrip_unicode_and_stable_ids(self):
        m = self.rich_manifest()
        save(m, self.path)
        self.assertEqual(to_data(load(self.path)), to_data(m))
        self.assertIn("Việt Nam", self.path.read_text(encoding="utf-8"))

    def test_signatures(self):
        self.assertEqual(signature({"a": 1, "b": "é"}), signature({"b": "e\u0301", "a": 1}))
        self.assertNotEqual(signature([1, 2]), signature([2, 1]))
        self.assertNotEqual(dependency_signature("a", "1", {}), dependency_signature("a", "2", {}))
        code = "from creator_studio.manifest import signature; print(signature({'x': 'Việt Nam'}))"
        result = subprocess.check_output([sys.executable, "-c", code], text=True, encoding="utf-8")
        self.assertEqual(result.strip(), signature({"x": "Việt Nam"}))
        for value in (float("nan"), float("inf"), {"é": 1, "e\u0301": 2}):
            with self.assertRaises(ValueError):
                signature(value)

    def test_duplicate_and_missing_ids(self):
        self.manifest.scenes = [Scene(id="same"), Scene(id="same", order=1)]
        self.assertIn("duplicate_id", {e.code for e in validate(self.manifest)})
        self.manifest.scenes = [Scene(id="")]
        self.assertIn("id", {e.code for e in validate(self.manifest)})

    def test_broken_cross_references(self):
        m = self.rich_manifest()
        m.scenes[0].media_ids = ["missing"]
        m.inputs[0].media_id = "missing"
        m.voice.audio_media_id = "missing"
        m.timeline[0].scene_id = "missing"
        m.audio[0].media_id = "missing"
        self.assertGreaterEqual(sum(e.code == "reference" for e in validate(m)), 5)

    def test_virtual_shots(self):
        m = self.rich_manifest()
        source = m.media[0]
        shot = MediaReference(kind=MediaKind.VIRTUAL_SHOT, reference=source.reference,
                              source_media_id=source.id, start=1, end=2,
                              provenance=Provenance(rights=Rights.OWNED), final_eligible=True)
        m.media.append(shot)
        self.assertEqual(validate(m), [])
        for start, end in [(2, 2), (3, 2), (-1, 2), (None, 2)]:
            shot.start, shot.end = start, end
            self.assertIn("interval", {e.code for e in validate(m)})
        shot.start, shot.end = 1, 2
        source.final_eligible = False
        self.assertIn("rights", {e.code for e in validate(m)})
        shot.source_media_id = shot.id
        self.assertIn("cycle", {e.code for e in validate(m)})

    def test_rights_defaults_and_eligibility(self):
        media = MediaReference()
        self.assertEqual(media.provenance.rights, Rights.REFERENCE_ONLY)
        self.assertFalse(media.final_eligible)
        self.manifest.media.append(media)
        for rights in Rights:
            media.provenance.rights = rights
            media.final_eligible = True
            has_error = any(e.code == "rights" for e in validate(self.manifest))
            self.assertEqual(has_error, rights in (Rights.REFERENCE_ONLY, Rights.UNKNOWN))

    def test_subtitle_relationships(self):
        m = self.rich_manifest()
        segment = m.subtitle_tracks[1].segments[0]
        segment.start = 0.5
        self.assertIn("alignment", {e.code for e in validate(m)})
        segment.scene_id = "missing"
        self.assertIn("reference", {e.code for e in validate(m)})
        segment.confidence = 2
        self.assertIn("confidence", {e.code for e in validate(m)})

    def test_invalid_save_preserves_destination(self):
        save(self.manifest, self.path)
        before = self.path.read_bytes()
        self.manifest.project_id = ""
        with self.assertRaises(ManifestValidationError):
            save(self.manifest, self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_atomic_replace_failure_preserves_valid_revision(self):
        save(self.manifest, self.path)
        before = self.path.read_bytes()
        self.manifest.project_name = "Changed"
        from creator_studio.manifest import persistence
        replace = persistence.os.replace

        def fail_target(source, destination):
            if Path(destination) == self.path:
                raise OSError("simulated failure")
            return replace(source, destination)

        with patch.object(persistence.os, "replace", side_effect=fail_target):
            with self.assertRaises(PersistenceError):
                save(self.manifest, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(recover_previous(self.path).project_name, "Việt Nam")
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_flush_failure_cleans_temporary(self):
        with patch("creator_studio.manifest.persistence.os.fsync", side_effect=OSError("failure")):
            with self.assertRaises(PersistenceError):
                save(self.manifest, self.path)
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_backup_and_explicit_recovery(self):
        save(self.manifest, self.path)
        self.manifest.project_name = "Revision 2"
        save(self.manifest, self.path)
        self.path.write_text("{incomplete", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            load(self.path)
        with self.assertRaises(PersistenceError):
            save(self.manifest, self.path)
        self.assertEqual(recover_previous(self.path).project_name, "Việt Nam")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{incomplete")

    def test_unsupported_schema(self):
        data = to_data(self.manifest)
        for version in (1, 3, True, "2"):
            data["schema_version"] = version
            self.path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(UnsupportedSchemaError):
                load(self.path)

    def test_strict_document_contract(self):
        data = to_data(self.manifest)
        for key, value in [("project_id", None), ("extra", 1), ("status", "bogus")]:
            bad = dict(data)
            bad[key] = value
            self.path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(PersistenceError):
                load(self.path)
        del data["project_id"]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PersistenceError):
            load(self.path)
        self.path.write_text('{"schema_version":2,"schema_version":2}', encoding="utf-8")
        with self.assertRaises(PersistenceError):
            load(self.path)

    def test_snapshot_metadata(self):
        snapshot = snapshot_metadata(self.manifest, "V1", "versions/v1.json")
        self.assertEqual(snapshot.content_signature, signature(self.manifest))
        with self.assertRaises(FrozenInstanceError):
            snapshot.label = "Changed"
        self.manifest.snapshots.append(snapshot)
        self.assertEqual(validate(self.manifest), [])
        save(self.manifest, self.path)
        self.assertEqual(load(self.path).snapshots[0], snapshot)

    def test_contract_ranges_and_diagnostics(self):
        m = self.rich_manifest()
        m.scenes[0].start = 2
        m.scenes[0].end = 1
        m.scenes[0].script_end = len(m.content.script) + 1
        m.content.revision = -1
        m.processing[0].diagnostics[0].code = "raw exception payload"
        self.assertTrue({"interval", "script_span", "revision", "diagnostic"}.issubset(
            {e.code for e in validate(m)}))

    def test_signature_encode_decode_stability(self):
        m = self.rich_manifest()
        self.assertEqual(signature(m), signature(decode(ProjectManifest, to_data(m))))

    def test_signature_save_load_stability(self):
        m = self.rich_manifest()
        save(m, self.path)
        self.assertEqual(signature(m), signature(load(self.path)))

    def test_snapshot_digest_roundtrip_stability(self):
        m = self.rich_manifest()
        captured = snapshot_metadata(m, "V1", "v1.json")
        save(m, self.path)
        self.assertEqual(captured.content_signature, signature(load(self.path)))
        m.snapshots.append(captured)
        save(m, self.path)
        loaded = load(self.path)
        self.assertEqual(signature(m), signature(loaded))
        self.assertEqual(loaded.snapshots[0].content_signature, captured.content_signature)

    def test_float_schema_normalization(self):
        m = self.rich_manifest()
        self.assertIs(type(m.scenes[0].start), float)
        m.voice.speed = 1
        m.subtitle_tracks[0].segments[0].confidence = 1
        data = to_data(m)
        self.assertIs(type(data["voice"]["speed"]), float)
        self.assertIs(type(data["content"]["revision"]), int)
        self.assertEqual(signature(m), signature(decode(ProjectManifest, data)))
        m.voice.speed = 1.0
        self.assertEqual(signature(m), signature(data))
        self.assertNotEqual(signature(1), signature(1.0))

    def test_nonfinite_schema_values(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            for cls, field in ((Scene, "start"), (SubtitleSegment, "confidence"),
                               (TimelineReference, "end"), (MediaReference, "start")):
                with self.subTest(value=value, cls=cls):
                    with self.assertRaises(ValueError):
                        cls(**{field: value})
            m = self.rich_manifest()
            m.voice.speed = value
            self.assertEqual(validate(m)[0].code, "contract")
            with self.assertRaises(ValueError):
                signature(m)
            data = to_data(ProjectManifest("finite"))
            data["voice"]["speed"] = value
            with self.assertRaises(ValueError):
                decode(ProjectManifest, data)

    def test_malformed_original_graph(self):
        mutations = (
            lambda m: setattr(m, "content", to_data(m.content)),
            lambda m: setattr(m.media[0], "provenance", to_data(m.media[0].provenance)),
            lambda m: setattr(m, "scenes", [to_data(m.scenes[0])]),
            lambda m: setattr(m.subtitle_tracks[0], "segments", [object()]),
            lambda m: setattr(m.processing[0], "diagnostics", [{}]),
            lambda m: setattr(m, "status", "pending"),
            lambda m: setattr(m.scenes[0], "order", 1.0),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                m = self.rich_manifest()
                mutate(m)
                self.assertEqual(validate(m)[0].code, "contract")
                with self.assertRaises(ManifestValidationError):
                    save(m, self.path)
                with self.assertRaises(ManifestValidationError):
                    snapshot_metadata(m, "bad", "bad.json")
                self.manifest = ProjectManifest("fresh")

    def nested_shots(self):
        m = self.rich_manifest()
        source = m.media[0]
        for start, end in ((2, 10), (3, 9), (4, 8)):
            shot = MediaReference(kind=MediaKind.VIRTUAL_SHOT, reference=source.reference,
                                  source_media_id=source.id, start=start, end=end,
                                  provenance=Provenance(rights=Rights.OWNED), final_eligible=True)
            m.media.append(shot)
            source = shot
        return m

    def test_multilevel_valid_containment(self):
        self.assertEqual(validate(self.nested_shots()), [])

    def test_nested_invalid_containment(self):
        for index, field, value in ((2, "start", 1), (2, "end", 11),
                                    (3, "start", 2), (3, "end", 10)):
            with self.subTest(index=index, field=field):
                self.manifest = ProjectManifest("nested")
                m = self.nested_shots()
                setattr(m.media[index], field, value)
                errors = validate(m)
                self.assertTrue(any(e.code == "shot_containment" and m.media[index].id in e.path
                                    for e in errors))

    def test_nested_cycle_and_physical_rights(self):
        m = self.nested_shots()
        m.media[0].provenance.rights = Rights.REFERENCE_ONLY
        self.assertIn("rights", {e.code for e in validate(m)})
        m.media[1].source_media_id = m.media[-1].id
        self.assertIn("cycle", {e.code for e in validate(m)})

    def test_scene_record_containment(self):
        for kind in ("subtitle", "timeline"):
            for start, end, valid in ((1, 2, True), (0, 2, False), (1, 4, False)):
                with self.subTest(kind=kind, start=start, end=end):
                    self.manifest = ProjectManifest("timing")
                    m = self.rich_manifest()
                    scene = m.scenes[0]
                    scene.start, scene.end = 1, 3
                    m.subtitle_tracks = m.subtitle_tracks[:1]
                    segment = m.subtitle_tracks[0].segments[0]
                    segment.start, segment.end = 1, 2
                    m.timeline[0].start, m.timeline[0].end = 1, 2
                    item = segment if kind == "subtitle" else m.timeline[0]
                    item.start, item.end = start, end
                    errors = [e for e in validate(m) if e.code == "scene_containment"]
                    self.assertEqual(not errors, valid)
                    if errors:
                        self.assertIn(item.id, errors[0].path)
                        self.assertIn(scene.id, errors[0].message)

    def test_untimed_scene_records(self):
        m = self.rich_manifest()
        m.scenes[0].start = m.scenes[0].end = None
        m.timeline[0].start, m.timeline[0].end = 20, 30
        self.assertEqual(validate(m), [])

    def test_primary_failure_survives_cleanup_failure(self):
        save(self.manifest, self.path)
        before = self.path.read_bytes()
        with patch("creator_studio.manifest.persistence.os.fsync", side_effect=OSError("primary fsync")), \
             patch("creator_studio.manifest.persistence.Path.unlink", side_effect=PermissionError("locked")):
            with self.assertRaises(PersistenceError) as caught:
                save(self.manifest, self.path)
        self.assertIn("primary fsync", str(caught.exception.__cause__))
        self.assertTrue(any("cleanup failed" in note for note in caught.exception.__cause__.__notes__))
        self.assertEqual(self.path.read_bytes(), before)

    def test_input_rights_cannot_upgrade_media(self):
        for rights in (Rights.REFERENCE_ONLY, Rights.UNKNOWN):
            for declared in (Rights.OWNED, Rights.LICENSED, Rights.PUBLIC_DOMAIN):
                with self.subTest(rights=rights, declared=declared):
                    media = MediaReference(provenance=Provenance(rights=rights))
                    m = ProjectManifest("rights", media=[media],
                                        inputs=[InputSource(media_id=media.id, rights=declared)])
                    self.assertIn("rights_authority", {e.code for e in validate(m)})
                    self.assertEqual(media.provenance.rights, rights)
                    self.assertFalse(media.final_eligible)
                    media.final_eligible = True
                    self.assertIn("rights", {e.code for e in validate(m)})
                    with self.assertRaises(ManifestValidationError):
                        save(m, self.path)

    def test_matching_ingest_rights(self):
        media = MediaReference(provenance=Provenance(rights=Rights.OWNED), final_eligible=True)
        m = ProjectManifest("rights", media=[media],
                            inputs=[InputSource(media_id=media.id, rights=Rights.OWNED)])
        self.assertEqual(validate(m), [])
        m.inputs[0].rights = Rights.REFERENCE_ONLY
        self.assertEqual(validate(m), [])

    def test_production_dependency_isolation(self):
        # M61 Manifest V2 owns the creator_studio/manifest dependency
        # boundary. Later Creator Studio milestones legitimately added
        # runtime, GUI, provider, rendering, and orchestration dependencies
        # elsewhere under creator_studio, so this isolation contract must
        # remain scoped to the manifest subsystem.
        root = (
            Path(__file__).resolve().parents[1]
            / "creator_studio"
            / "manifest"
        )
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    self.assertIn(module.split(".")[0], sys.stdlib_module_names)


if __name__ == "__main__":
    unittest.main()
