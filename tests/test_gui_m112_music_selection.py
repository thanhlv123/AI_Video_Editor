import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m112.py"


class GuiM112MusicSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding="utf-8")

    def test_footer_identifies_m112(self):
        self.assertIn("Creator Studio · M112 Automatic Background Music Selection", self.source)

    def test_gui_declares_music_selection_worker(self):
        self.assertIn("class MusicSelectionWorker(QThread):", self.source)
        self.assertIn("self.music_selection_worker", self.source)
        self.assertIn("BackgroundMusicSelectionService", self.source)

    def test_final_renderable_success_chains_to_music(self):
        self.assertIn("self._automation_start_music_selection", self.source)
        self.assertIn("_on_music_selection_succeeded", self.source)
        self.assertIn("final_renderable_manifest_path", self.source)

    def test_existing_use_music_checkbox_controls_m112(self):
        self.assertIn('"use_music": self.music_checkbox.isChecked()', self.source)
        self.assertIn('(coordinator.config or {}).get("use_music", True)', self.source)


if __name__ == "__main__":
    unittest.main()
