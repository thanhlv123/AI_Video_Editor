import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_creator_studio_m113.py"


class GuiM113TimelineAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding="utf-8")

    def test_footer_identifies_m113(self):
        self.assertIn("Creator Studio · M113 Automatic Timeline Assembly", self.source)

    def test_gui_declares_timeline_worker_and_service(self):
        self.assertIn("class TimelineAssemblyWorker(QThread):", self.source)
        self.assertIn("self.timeline_assembly_worker", self.source)
        self.assertIn("AutomaticTimelineAssemblyService", self.source)

    def test_music_success_chains_into_timeline(self):
        self.assertIn("self._automation_start_timeline_assembly", self.source)
        self.assertIn("_on_timeline_assembly_succeeded", self.source)
        self.assertIn("MUSIC_SELECTION_FILENAME", self.source)
        self.assertIn("FINAL_RENDERABLE_FILENAME", self.source)

    def test_timeline_success_updates_coordinator(self):
        self.assertIn("coordinator.timeline_assembly_completed", self.source)
        self.assertIn('self._automation_fail("timeline"', self.source)


if __name__ == "__main__":
    unittest.main()
