"""M130: export history appears in the manual export UI and is project-scoped."""
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
from creator_studio.manual_export_qt import ManualExportPage


def write_export(root: Path, run_name: str, video_name: str, *, status="completed") -> Path:
    run = root / "work" / "automation" / run_name
    run.mkdir(parents=True, exist_ok=True)
    exports = root / "exports"
    exports.mkdir(exist_ok=True)
    video = exports / video_name
    video.write_bytes(b"synthetic fixture")
    (run / "render_export_manifest.json").write_text(
        json.dumps({"status": status, "output_path": str(video)}),
        encoding="utf-8",
    )
    return video


class ExportHistoryGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = ManualExportPage()

    def tearDown(self):
        self.assertFalse(self.page.is_exporting())
        self.page.close()
        self.page.deleteLater()

    def test_no_project_disables_history(self):
        self.assertEqual(self.page.history_combo.count(), 0)
        self.assertFalse(self.page.history_open_button.isEnabled())
        self.assertFalse(self.page.history_folder_button.isEnabled())
        self.assertFalse(self.page.history_refresh_button.isEnabled())

    def test_completed_export_can_be_opened_and_folder_shown(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            video = write_export(root, "run_001", "final_video_001.mp4")
            write_export(root, "run_002", "final_video_002.mp4", status="failed")
            self.page.set_project(None, root / "project_manifest.json")
            self.assertEqual(self.page.history_combo.count(), 1)
            self.assertEqual(Path(self.page.history_combo.currentData()), video.resolve())
            self.assertTrue(self.page.history_open_button.isEnabled())
            self.assertIn("final_video_001.mp4", self.page.history_status_label.text())
            with patch("creator_studio.manual_export_qt.QDesktopServices.openUrl") as opener:
                self.page._open_history_output()
                self.page._open_history_folder()
                self.assertEqual(opener.call_count, 2)
                self.assertEqual(Path(opener.call_args_list[0].args[0].toLocalFile()), video.resolve())
                self.assertEqual(Path(opener.call_args_list[1].args[0].toLocalFile()), video.parent.resolve())

    def test_switching_projects_clears_old_history(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            root = Path(first)
            write_export(root, "run_001", "final_video_001.mp4")
            self.page.set_project(None, root / "project_manifest.json")
            self.assertEqual(self.page.history_combo.count(), 1)
            self.page.set_project(None, Path(second) / "project_manifest.json")
            self.assertEqual(self.page.history_combo.count(), 0)
            self.assertFalse(self.page.history_open_button.isEnabled())
            self.page.set_project(None, None)
            self.assertFalse(self.page.history_refresh_button.isEnabled())

    def test_success_refreshes_history_and_selects_new_video(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.page.set_project(None, root / "project_manifest.json")
            self.assertEqual(self.page.history_combo.count(), 0)
            video = write_export(root, "run_001", "final_video_001.mp4")
            self.page._on_success(SimpleNamespace(output_path=video))
            self.assertEqual(self.page.history_combo.count(), 1)
            self.assertEqual(Path(self.page.history_combo.currentData()), video.resolve())
            self.assertEqual(self.page.progress_bar.value(), 100)

    def test_refresh_button_preserves_selected_video(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            first = write_export(root, "run_001", "final_video_001.mp4")
            write_export(root, "run_002", "final_video_002.mp4")
            self.page.set_project(None, root / "project_manifest.json")
            self.assertEqual(self.page.history_combo.count(), 2)
            index = self.page.history_combo.findData(str(first.resolve()))
            self.assertGreaterEqual(index, 0)
            self.page.history_combo.setCurrentIndex(index)
            self.page.history_refresh_button.click()
            self.assertEqual(Path(self.page.history_combo.currentData()), first.resolve())

    def test_refresh_does_not_change_manifest_bytes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            write_export(root, "run_001", "final_video_001.mp4")
            manifest = root / "work" / "automation" / "run_001" / "render_export_manifest.json"
            original = manifest.read_bytes()
            self.page.set_project(None, root / "project_manifest.json")
            self.page._refresh_history()
            self.assertEqual(manifest.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
