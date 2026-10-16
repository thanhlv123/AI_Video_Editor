"""M120 read-only timeline preflight and failure diagnostics."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from creator_studio.timeline_preflight import inspect_timeline, main


class TimelinePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="m120_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "dự án"
        self.root.mkdir()
        self.image = self.root / "assets/images/làng quê.png"
        self.voice = self.root / "assets/voice/giọng đọc.wav"
        for path in (self.image, self.voice):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic-nonempty-media")
        self.manifest = {
            "format": "creator_studio_timeline_m113",
            "status": "ready",
            "duration_seconds": 3.0,
            "tracks": {
                "visuals": [{
                    "clip_id": "visual_0001",
                    "start_seconds": 0.0,
                    "duration_seconds": 3.0,
                    "asset": {
                        "asset_id": "image_1",
                        "media_type": "image",
                        "path": "assets/images/làng quê.png",
                        "duration_seconds": 0.0,
                        "width": 1280, "height": 720,
                    },
                    "operation": {"mode": "still"},
                }],
                "narration": {
                    "asset_id": "voice_1",
                    "path": "assets/voice/giọng đọc.wav",
                    "start_seconds": 0.0,
                    "end_seconds": 3.0,
                    "source_duration_seconds": 3.0,
                },
                "music": None,
            },
            "music_state": {"included": False},
        }
        self.timeline = self.root / "work/automation/run_test/timeline_manifest.json"
        self.timeline.parent.mkdir(parents=True)
        self.save()

    def save(self):
        self.timeline.write_text(json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8")

    def inspect(self):
        return inspect_timeline(self.timeline, self.root)

    def test_ready_with_unicode_paths_and_no_music(self):
        report = self.inspect()
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["summary"]["reference_count"], 2)
        self.assertEqual(report["summary"]["error_count"], 0)
        self.assertEqual(report["format"], "creator_studio.timeline_preflight.v1")

    def test_inspection_does_not_modify_project(self):
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        self.inspect()
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_media_is_actionable(self):
        self.manifest["tracks"]["visuals"][0]["asset"]["path"] = "assets/images/not_found.png"
        self.save()
        report = self.inspect()
        self.assertEqual(report["status"], "blocked")
        issue = next(x for x in report["issues"] if x["code"] == "missing_media")
        self.assertIn("reassign", issue["action"].lower())

    def test_empty_media_is_blocking(self):
        self.manifest["tracks"]["visuals"][0]["asset"]["path"] = "assets/images/empty.png"
        (self.root / "assets/images/empty.png").touch()
        self.save()
        self.assertIn("empty_media", {x["code"] for x in self.inspect()["issues"]})

    def test_null_source_duration_uses_timeline_fallback(self):
        self.manifest["tracks"]["narration"]["source_duration_seconds"] = None
        self.save()
        report = self.inspect()
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["summary"]["error_count"], 0)
        self.assertNotIn("render_contract", {x["code"] for x in report["issues"]})

    def test_invalid_nonnull_source_duration_is_still_blocked(self):
        for value in (0, -1, False, "", "nan", "inf"):
            with self.subTest(value=value):
                self.manifest["tracks"]["narration"]["source_duration_seconds"] = value
                self.save()
                report = self.inspect()
                self.assertEqual(report["status"], "blocked")
                self.assertIn("render_contract", {x["code"] for x in report["issues"]})

    def test_disabled_music_does_not_require_music_asset(self):
        self.manifest["tracks"]["music"] = {"path": "missing.mp3"}
        self.manifest["music_state"]["included"] = False
        self.save()
        self.assertEqual(self.inspect()["status"], "ready")

    def test_included_music_must_exist(self):
        self.manifest["tracks"]["music"] = {"path": "missing.mp3"}
        self.manifest["music_state"]["included"] = True
        self.save()
        self.assertEqual(self.inspect()["status"], "blocked")
        self.assertIn("missing_media", {x["code"] for x in self.inspect()["issues"]})

    def test_not_ready_and_invalid_duration(self):
        self.manifest["status"] = "failed"
        self.manifest["duration_seconds"] = 0
        self.save()
        report = self.inspect()
        self.assertEqual(report["status"], "blocked")
        self.assertIn("timeline_not_ready", {x["code"] for x in report["issues"]})
        self.assertIn("invalid_duration", {x["code"] for x in report["issues"]})

    def test_malformed_manifest_and_missing_manifest(self):
        self.timeline.write_text("{bad json", encoding="utf-8")
        self.assertIn("invalid_json", {x["code"] for x in self.inspect()["issues"]})
        other = self.timeline.with_name("missing.json")
        self.assertIn("timeline_missing", {
            x["code"] for x in inspect_timeline(other, self.root)["issues"]
        })

    def test_external_asset_is_a_portability_warning(self):
        external = Path(self.temp.name) / "outside.png"
        external.write_bytes(b"synthetic-nonempty-media")
        self.manifest["tracks"]["visuals"][0]["asset"]["path"] = str(external)
        self.save()
        report = self.inspect()
        self.assertEqual(report["status"], "ready")
        self.assertIn("external_media", {x["code"] for x in report["issues"]})

    def test_cli_returns_machine_readable_status(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = main([str(self.timeline), "--project-root", str(self.root)])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "ready")
        self.manifest["status"] = "failed"
        self.save()
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = main([str(self.timeline), "--project-root", str(self.root)])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
