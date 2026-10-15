from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m110_4.py"


class GuiM1104UnifiedRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = GUI.read_text(encoding="utf-8")

    def test_gui_declares_unified_ranking_worker(self):
        self.assertIn("class MediaRankingWorker(QThread):", self.text)
        self.assertIn("UnifiedMediaRankingService", self.text)
        self.assertIn("self.media_ranking_worker", self.text)

    def test_youtube_success_chains_into_ranking(self):
        self.assertIn("_automation_start_media_ranking", self.text)
        self.assertIn("_on_media_ranking_succeeded", self.text)
        self.assertIn("QTimer.singleShot", self.text)

    def test_footer_identifies_m1104(self):
        self.assertIn("Creator Studio · M110.4 Unified Media Ranking", self.text)


if __name__ == "__main__":
    unittest.main()
