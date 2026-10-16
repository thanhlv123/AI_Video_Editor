"""M127 interrupted export regression tests."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from creator_studio.export_recovery import recover_interrupted_exports


def report(root, status="rendering", **changes):
    data = {
        "format": "creator_studio.render_export.v1",
        "status": status,
        "project_root": str(root),
        "output_path": str(root / "exports/final_video_001.mp4"),
        "issues": [],
    }
    data.update(changes)
    return data


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class ExportRecoveryTests(unittest.TestCase):
    def test_interrupted_manifest_failed_and_mp4_preserved(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "render_export_manifest.json"
            output = root / "final_video_001.mp4"
            output.write_bytes(b"keep-my-video")
            save(path, report(root))
            self.assertEqual(recover_interrupted_exports(root, root), [path])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "failed")
            self.assertIn("render_interrupted", data["issues"])
            self.assertEqual(output.read_bytes(), b"keep-my-video")
            self.assertEqual(recover_interrupted_exports(root, root), [])

    def test_finalized_states_are_unchanged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for n, status in enumerate(("completed", "failed", "cancelled"), 2):
                save(root / f"render_export_manifest_{n:03d}.json", report(root, status))
            before = {p: p.read_bytes() for p in root.glob("*.json")}
            self.assertEqual(recover_interrupted_exports(root, root), [])
            self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_unrelated_invalid_and_foreign_manifests_unchanged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            save(root / "render_export_manifest.json", report(root / "other"))
            (root / "render_export_manifest_002.json").write_text("{invalid", encoding="utf-8")
            save(root / "render_export_manifest_003.json", report(root, format="other"))
            save(root / "render_export_manifest_custom.json", report(root))
            before = {p: p.read_bytes() for p in root.glob("*.json")}
            self.assertEqual(recover_interrupted_exports(root, root), [])
            self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_issues_preserved_without_duplicates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "render_export_manifest.json"
            save(path, report(root, issues=["prior", "render_interrupted"]))
            self.assertEqual(recover_interrupted_exports(root, root), [path])
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["issues"],
                ["prior", "render_interrupted"],
            )

    def test_replace_failure_does_not_corrupt_original(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "render_export_manifest.json"
            save(path, report(root))
            before = path.read_bytes()
            with patch("creator_studio.export_recovery.Path.replace", side_effect=OSError("disk")):
                self.assertEqual(recover_interrupted_exports(root, root), [])
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
