from __future__ import annotations

import ast
import unittest
from pathlib import Path


class GuiM1103YouTubeReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / 'gui_creator_studio_m110_3.py'
        cls.text = cls.path.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.text, filename=str(cls.path))
        cls.classes = {n.name: n for n in cls.tree.body if isinstance(n, ast.ClassDef)}

    def test_youtube_worker_exists(self):
        self.assertIn('YouTubeReferenceWorker', self.classes)
        self.assertIn('YouTubeReferenceService.from_runtime_environment', self.text)

    def test_window_initializes_youtube_worker(self):
        self.assertIn('self.youtube_reference_worker: YouTubeReferenceWorker | None = None', self.text)

    def test_stock_success_chains_to_youtube(self):
        self.assertIn('continue_to_youtube=True', self.text)
        self.assertIn('_automation_start_youtube_reference', self.text)
        self.assertIn('QTimer.singleShot(', self.text)

    def test_youtube_progress_updates_same_automation_screen(self):
        self.assertIn('coordinator.media_youtube_progress(', self.text)
        self.assertIn('self._automation_apply_state()', self.text)

    def test_youtube_success_updates_coordinator(self):
        self.assertIn('coordinator.media_youtube_completed(', self.text)
        self.assertIn('chapter_segment_count=', self.text)

    def test_footer_is_m110_3(self):
        self.assertIn('Creator Studio · M110.3 YouTube Reference Search', self.text)


if __name__ == '__main__':
    unittest.main()
