"""M128 manual export page and worker regression coverage."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from creator_studio.manual_export_qt import ManualExportPage, ManualExportWorker
from creator_studio.timeline_assembly import TIMELINE_FILENAME, TIMELINE_FORMAT


class ManualExportGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = ManualExportPage()

    def tearDown(self):
        self.assertFalse(self.page.is_exporting())
        self.page.close()
        self.page.deleteLater()

    def test_no_project_disables_export(self):
        self.assertFalse(self.page.render_button.isEnabled())
        self.assertFalse(self.page.cancel_button.isEnabled())

    def test_ready_timeline_can_be_selected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "work" / "automation" / "run_001"
            directory.mkdir(parents=True)
            timeline = directory / TIMELINE_FILENAME
            timeline.write_text(json.dumps({
                "format": TIMELINE_FORMAT, "status": "ready"
            }), encoding="utf-8")
            self.page.set_project(None, root / "project_manifest.json")
            self.assertTrue(self.page.render_button.isEnabled())
            self.assertEqual(self.page.timeline_combo.currentData(), str(timeline.resolve()))
            self.page.set_project(None, None)
            self.assertFalse(self.page.render_button.isEnabled())

    def test_preflight_error_does_not_launch_render(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "work" / "automation" / "run_001"
            directory.mkdir(parents=True)
            (directory / TIMELINE_FILENAME).write_text(json.dumps({
                "format": TIMELINE_FORMAT, "status": "ready"
            }), encoding="utf-8")
            self.page.set_project(None, root / "project_manifest.json")
            with patch(
                "creator_studio.manual_export_qt.require_render_ready",
                side_effect=ValueError("not ready"),
            ):
                self.page._start()
            self.assertFalse(self.page.is_exporting())
            self.assertIn("not ready", self.page.status_label.text())

    def test_worker_calls_service_without_running_qt_event_loop(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            worker = ManualExportWorker(root / "timeline_manifest.json", root)
            captured = []
            worker.succeeded.connect(captured.append)
            result = SimpleNamespace(output_path=root / "exports" / "final_video_001.mp4")
            with patch("creator_studio.manual_export_qt.RenderExportService") as service:
                service.return_value.export.return_value = result
                worker.run()
                service.return_value.export.assert_called_once()
            self.assertEqual(captured, [result])
            worker.request_cancel()
            self.assertTrue(worker.cancel_token.is_cancelled())


if __name__ == "__main__":
    unittest.main()
