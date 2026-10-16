import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from creator_studio.export_history import find_completed_exports

class ExportHistorySafetyTests(unittest.TestCase):
    def test_external_and_failed_outputs_ignored(self):
        with TemporaryDirectory() as folder, TemporaryDirectory() as outside:
            root = Path(folder)
            run = root / "work" / "automation" / "run_001"
            run.mkdir(parents=True)
            (root / "exports").mkdir()
            foreign = Path(outside) / "video.mp4"
            foreign.write_bytes(b"data")
            record = run / "render_export_manifest.json"
            record.write_text(json.dumps({"status": "completed", "output_path": str(foreign)}))
            self.assertEqual(find_completed_exports(root), [])
            record.write_text(json.dumps({"status": "failed", "output_path": str(foreign)}))
            self.assertEqual(find_completed_exports(root), [])

if __name__ == "__main__":
    unittest.main()
