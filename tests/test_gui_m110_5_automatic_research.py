from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m110_5.py"
STOCK = ROOT / "creator_studio" / "stock_acquisition.py"


class GuiM1105AutomaticResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = GUI.read_text(encoding="utf-8")
        cls.stock_text = STOCK.read_text(encoding="utf-8")

    def test_gui_declares_research_worker_and_auto_chain(self):
        self.assertIn("class MediaResearchWorker(QThread):", self.text)
        self.assertIn("AutomaticMediaResearchService", self.text)
        self.assertIn("_automation_start_media_research", self.text)
        self.assertIn("_on_media_research_succeeded", self.text)

    def test_footer_identifies_m1105(self):
        self.assertIn("Creator Studio · M110.5 Automatic Re-search / Fallback", self.text)

    def test_stock_service_can_defer_assignment_until_replacement_gate(self):
        self.assertIn("assign_assets: bool = True", self.stock_text)
        self.assertIn("if self.assign_assets:", self.stock_text)

    def test_voice_finished_handler_does_not_clear_query_worker(self):
        start = self.text.index("def _on_voice_pipeline_thread_finished")
        end = self.text.index("def open_voice_output_folder", start)
        block = self.text[start:end]
        self.assertNotIn("self.media_query_worker = None", block)


if __name__ == "__main__":
    unittest.main()
