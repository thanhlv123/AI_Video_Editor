import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m110_6.py"


class GuiM1106FinalRenderableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding="utf-8")

    def test_footer_identifies_m1106(self):
        self.assertIn("Creator Studio · M110.6 Final Renderable Asset", self.source)

    def test_gui_declares_final_renderable_worker(self):
        self.assertIn("class FinalRenderableWorker(QThread):", self.source)
        self.assertIn("self.final_renderable_worker", self.source)
        self.assertIn("FinalRenderableAssetService", self.source)

    def test_ranking_without_research_chains_into_finalization(self):
        self.assertIn("self._automation_start_final_renderable", self.source)
        self.assertIn("if research_count <= 0 and unresolved_count <= 0:", self.source)

    def test_research_success_chains_into_finalization(self):
        self.assertIn("research_manifest_path = Path", self.source)
        self.assertIn("self._on_final_renderable_succeeded", self.source)


if __name__ == "__main__":
    unittest.main()
