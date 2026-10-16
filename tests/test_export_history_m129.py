import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from creator_studio.export_history import find_completed_exports

class ExportHistoryTests(unittest.TestCase):
    def test_history_is_project_local(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / "work" / "automation" / "run_001"
            run.mkdir(parents=True)
            exports = root / "exports"
            exports.mkdir()
            video = exports / "final_video_001.mp4"
            video.write_bytes(b"video")
            manifest = run / "render_export_manifest.json"
            manifest.write_text(json.dumps({
                "status": "completed", "output_path": str(video)
            }), encoding="utf-8")
            found = find_completed_exports(root)
            self.assertEqual(len(found), 1)
            # Windows may use both a long path and its 8.3 alias for the same file.
            self.assertTrue(found[0].output_path.samefile(video))
            self.assertTrue(found[0].manifest_path.samefile(manifest))
            self.assertEqual(video.read_bytes(), b"video")

if __name__ == "__main__":
    unittest.main()
