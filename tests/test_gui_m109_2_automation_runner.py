import ast
import unittest
from pathlib import Path


class M1092AutomationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = Path(__file__).resolve().parents[1] / "gui_creator_studio_m109_2.py"
        cls.text = cls.gui_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text, filename=str(cls.gui_path))

    def test_create_video_uses_real_start_callback(self):
        self.assertIn("self._start_automation_workflow,", self.text)
        self.assertIn("def _start_automation_workflow", self.text)
        self.assertIn('self._start_tts_worker(request, action="automation_generate")', self.text)

    def test_tts_success_chains_to_voice_pipeline(self):
        self.assertIn('if action == "automation_generate"', self.text)
        self.assertIn("self.automation_coordinator.voice_completed", self.text)
        self.assertIn("QTimer.singleShot(0, self._automation_start_voice_pipeline)", self.text)
        self.assertIn("self.run_voice_pipeline()", self.text)

    def test_voice_pipeline_updates_automation_state(self):
        self.assertIn("self.automation_coordinator.voice_pipeline_completed", self.text)
        self.assertIn('scene_count=int(scene_count or 0)', self.text)
        self.assertIn('run_name=output_dir.name', self.text)

    def test_automation_errors_surface_in_progress_instead_of_only_manual_dialog(self):
        self.assertIn('self._automation_fail("voice"', self.text)
        self.assertIn('self._automation_fail("voice_timing"', self.text)
        self.assertIn("def _automation_fail", self.text)

    def test_cooperative_cancel_is_connected(self):
        self.assertIn("self.cancel_button.clicked.connect(self.on_cancel_workflow)", self.text)
        self.assertIn("def _cancel_automation_workflow", self.text)
        self.assertIn("self._automation_cancel_requested = True", self.text)

    def test_m109_2_has_persisted_coordinator(self):
        self.assertIn("AutomationPipelineCoordinator", self.text)
        self.assertIn("self.automation_coordinator", self.text)
        self.assertIn("Creator Studio · M109.2 Automatic Voice + Scene Pipeline", self.text)

    def test_user_facing_setup_no_longer_claims_runner_is_future(self):
        self.assertNotIn("Automation Runner thực thi liên hoàn sẽ được nối ở M109.2", self.text)
        self.assertIn("Creator Studio sẽ tự tạo giọng đọc", self.text)


if __name__ == "__main__":
    unittest.main()
