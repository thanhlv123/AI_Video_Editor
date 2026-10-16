"""M130: export history ordering and path safety."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from creator_studio.export_history import find_completed_exports


def write_record(root: Path, run: str, output: Path, *, status="completed") -> Path:
    folder = root / "work" / "automation" / run
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / "render_export_manifest.json"
    manifest.write_text(json.dumps({"status": status, "output_path": str(output)}), encoding="utf-8")
    return manifest


class ExportHistoryHardeningTests(unittest.TestCase):
    def test_newest_first_deduplicated_and_limit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            exports = root / "exports"
            exports.mkdir()
            first = exports / "final_video_001.mp4"
            second = exports / "final_video_002.mp4"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            old = write_record(root, "run_001", first)
            new = write_record(root, "run_002", second)
            dup = write_record(root, "run_003", first)
            os.utime(old, ns=(1_000_000_000, 1_000_000_000))
            os.utime(new, ns=(3_000_000_000, 3_000_000_000))
            os.utime(dup, ns=(2_000_000_000, 2_000_000_000))
            found = find_completed_exports(root)
            self.assertEqual([x.output_path.name for x in found], ["final_video_002.mp4", "final_video_001.mp4"])
            self.assertEqual(len(find_completed_exports(root, limit=1)), 1)
            self.assertEqual(find_completed_exports(root, limit=0), [])

    def test_rejects_non_mp4_empty_and_relative(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            exports = root / "exports"
            exports.mkdir()
            txt = exports / "not_video.txt"
            txt.write_bytes(b"data")
            write_record(root, "run_001", txt)
            empty = exports / "empty.mp4"
            empty.touch()
            write_record(root, "run_002", empty)
            write_record(root, "run_003", Path("relative.mp4"))
            self.assertEqual(find_completed_exports(root), [])

    def test_rejects_symlinked_video_and_run(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as foreign:
            root = Path(directory)
            outputs = root / "exports"
            outputs.mkdir()
            foreign_file = Path(foreign) / "foreign.mp4"
            foreign_file.write_bytes(b"foreign")
            work = root / "work" / "automation"
            work.mkdir(parents=True)
            linked_video = outputs / "final_video_001.mp4"
            try:
                linked_video.symlink_to(foreign_file)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation requires privileges on this runner")
            write_record(root, "run_001", linked_video)
            self.assertEqual(find_completed_exports(root), [])
            linked_video.unlink()
            linked_video.write_bytes(b"valid")
            foreign_run = Path(foreign) / "run_external"
            foreign_run.mkdir()
            (foreign_run / "render_export_manifest.json").write_text(
                json.dumps({"status": "completed", "output_path": str(linked_video)}),
                encoding="utf-8",
            )
            (work / "run_002").symlink_to(foreign_run, target_is_directory=True)
            found = find_completed_exports(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].manifest_path.parent.name, "run_001")


if __name__ == "__main__":
    unittest.main()
