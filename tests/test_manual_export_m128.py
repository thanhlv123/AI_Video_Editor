from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from creator_studio.manual_export import find_ready_timelines
from creator_studio.timeline_assembly import TIMELINE_FILENAME, TIMELINE_FORMAT

def write_timeline(root: Path, name: str, status="ready") -> Path:
    directory = root / "work" / "automation" / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / TIMELINE_FILENAME
    path.write_text(json.dumps({"format": TIMELINE_FORMAT, "status": status}), encoding="utf-8")
    return path

class ManualExportDiscoveryTests(unittest.TestCase):
    def test_missing_runs(self):
        with TemporaryDirectory() as folder:
            self.assertEqual(find_ready_timelines(Path(folder)), [])

    def test_ready_and_failed(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            ready = write_timeline(root, "run_001")
            write_timeline(root, "run_002", status="failed")
            self.assertEqual(find_ready_timelines(root), [ready.resolve()])

    def test_invalid_json_and_unrelated_directory_ignored(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            good = write_timeline(root, "run_001")
            write_timeline(root, "run_002").write_text("{invalid", encoding="utf-8")
            write_timeline(root, "not_a_run")
            self.assertEqual(find_ready_timelines(root), [good.resolve()])

    def test_does_not_change_manifest(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = write_timeline(root, "run_001")
            before = path.read_bytes()
            find_ready_timelines(root)
            self.assertEqual(path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
